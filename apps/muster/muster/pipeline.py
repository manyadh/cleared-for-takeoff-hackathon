"""voice -> transcript -> structured intake -> triage flags -> reply.

Each stage has a `mock` path (works anywhere, good for building the UI) and a
`device` path (real LFM3 models on the IQ9). Swap with env vars, see config.py.
"""
from __future__ import annotations

import json
import re

import urllib.request

from . import config
from .schema import INTAKE_EXAMPLE, Intake, Person, Triage

# ---------------------------------------------------------------- 1. speech

def transcribe(audio: bytes | None, text: str | None) -> str:
    """Typed text always wins (handy for testing + backup). Otherwise run local ASR."""
    if text:
        return text.strip()
    if not audio:
        raise ValueError("need audio or text")
    if config.ASR_BACKEND == "mock":
        raise ValueError("ASR is in mock mode - type the report instead, or set MUSTER_ASR=zetic")
    return _zetic_asr(audio)


def _zetic_asr(audio: bytes) -> str:
    """LFM3-Omni-2B (or Audio-2B) on the NPU through the event repo's ZETIC wrapper.
    Wrapper limits: WAV only, <=30 s, and its ASR system prompt is English."""
    import subprocess, tempfile, os
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "clip.bin")
        wav = os.path.join(d, "clip.wav")
        open(src, "wb").write(audio)
        if audio[:4] == b"RIFF":
            os.replace(src, wav)
        else:  # browser sends webm/ogg - convert locally
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-ac", "1", "-ar", "16000",
                            "-t", "30", wav], check=True)
        r = subprocess.run(["python3", config.ZETIC_RUN, "--sdk", config.ZETIC_SDK, "--model", config.ZETIC_MODEL,
                            "--audio", wav, "--prompt", "Transcribe the audio.", "--max-tokens", "200"],
                           capture_output=True, text=True, timeout=180)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    if not out.get("text"):
        raise RuntimeError(f"ASR failed: {out.get('errors')}")
    return out["text"].strip()


# ------------------------------------------------------------- 2. extraction

EXTRACT_PROMPT = """You are the intake clerk at an emergency shelter. A person just spoke the report below.
It may be in any language. Fill in the JSON exactly; use English for every field value except names.
Only include facts the person actually said. Use empty lists when nothing applies.

- people_present: everyone physically at the shelter now (speaker + who came with them)
- missing: people the speaker is LOOKING FOR
- found: people the speaker brought in who are NOT their family (e.g. a lost child)
- medical_needs: medicines or devices needed soon (insulin, dialysis, oxygen, heart pills...)
- language: ISO 639-1 code of the language spoken

Report:
\"\"\"{transcript}\"\"\"

Fill in this JSON shape:
{schema}
Return only JSON."""


def _chat(prompt: str, json_mode: bool = False, max_tokens: int = 700) -> str:
    # Same request shape as the event repo's lfm_client.py (GenieX v0.10.0).
    body = {
        "model": config.LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": max_tokens,
        "compute": config.LLM_COMPUTE,
        "stream": False,
        "enable_think": False,
        "temperature": 0.1,
    }
    if json_mode and config.LLM_JSON_MODE:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(f"{config.LLM_URL}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        c = json.load(r)["choices"][0]
    text = ((c.get("message") or {}).get("content") or "").strip()
    text = re.sub(r"<think>.*?(?:</think>|$)", "", text, flags=re.S).strip()
    if not text:
        raise RuntimeError(f"empty answer (finish={c.get('finish_reason')})")
    return text


def _parse_json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0) if m else raw)


def extract(transcript: str) -> Intake:
    if config.MODE == "mock":
        return _mock_extract(transcript)
    schema = json.dumps(INTAKE_EXAMPLE, ensure_ascii=False)
    raw = _chat(EXTRACT_PROMPT.format(transcript=transcript, schema=schema), json_mode=True)
    try:
        return Intake.from_dict(_parse_json(raw))
    except Exception:
        # one retry with the error shown - small models usually fix it
        raw = _chat(EXTRACT_PROMPT.format(transcript=transcript, schema=schema)
                    + "\nYour last answer was not valid JSON for this schema. Try again.", json_mode=True)
        return Intake.from_dict(_parse_json(raw))


# ----------------------------------------------------------------- 3. triage
# d1 asks fixed, typed questions about the transcript. One forward pass, no text
# generated, a calibrated probability per question - exactly what triage needs.

TRIAGE_QUESTIONS = {
    "life_threat": "Is anyone described in immediate danger of dying: heavy bleeding, not breathing, "
                   "unconscious, chest pain, severe burns?",
    "time_critical_meds": "Does anyone need a medicine or medical device within 24 hours "
                          "(insulin, dialysis, oxygen, seizure or heart medication)?",
    "vulnerable": "Is there an unaccompanied child, a pregnant person, an infant, or someone who cannot walk?",
}

_d1 = None


def _d1_answers(transcript: str) -> dict[str, float]:
    """P(yes) per question from d1-2B: one forward pass, zero output tokens.
    Matches the event repo's docs/decision-models.md (Transformers, CPU, local snapshot)."""
    global _d1
    if _d1 is None:
        import os
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        import torch
        from transformers import AutoModel
        _d1 = AutoModel.from_pretrained(config.D1_DIR, trust_remote_code=True, local_files_only=True,
                                        dtype=torch.float32).to("cpu").eval()
    import torch
    questions = {k: {"type": "noul", "instructions": q} for k, q in TRIAGE_QUESTIONS.items()}
    state = json.dumps({"spoken_report": transcript})
    with torch.inference_mode():
        res = _d1.system_one(state, questions)
    return {k: round(float(v["noul"]), 4) for k, v in res["answers"].items()}


def _llm_answers(transcript: str) -> dict[str, float]:
    """Fallback if d1 isn't running yet: ask LFM3-1.7B for the same yes/no flags."""
    q = "\n".join(f'"{k}": {v}' for k, v in TRIAGE_QUESTIONS.items())
    raw = _chat(f"Report:\n\"\"\"{transcript}\"\"\"\nAnswer each with true or false as JSON:\n{q}",
                json_mode=True, max_tokens=80)
    d = _parse_json(raw)
    return {k: 1.0 if d.get(k) else 0.0 for k in TRIAGE_QUESTIONS}


def _rule_answers(intake: Intake, transcript: str) -> dict[str, float]:
    t = transcript.lower() + " " + " ".join(intake.injuries + intake.medical_needs).lower()
    hit = lambda words: 1.0 if any(w in t for w in words) else 0.0
    vulnerable = hit(["pregnan", "embarazada", "baby", "bebé", "bebe", "wheelchair", "can't walk"])
    if intake.found and any((p.age or 99) < 16 for p in intake.found):
        vulnerable = 1.0
    return {
        "life_threat": hit(["bleeding", "sangr", "not breathing", "unconscious", "inconsciente",
                            "chest pain", "dolor de pecho", "burn"]),
        "time_critical_meds": 1.0 if intake.medical_needs else 0.0,
        "vulnerable": vulnerable,
    }


def triage(intake: Intake, transcript: str) -> Triage:
    if config.TRIAGE_BACKEND == "d1":
        p = _d1_answers(transcript)
    elif config.TRIAGE_BACKEND == "llm":
        p = _llm_answers(transcript)
    else:
        p = _rule_answers(intake, transcript)

    th = config.TRIAGE_THRESHOLD
    reasons = [k for k, v in p.items() if v >= th]
    if p["life_threat"] >= th:
        prio = "RED"
    elif p["time_critical_meds"] >= th or p["vulnerable"] >= th:
        prio = "ORANGE"
    elif intake.injuries or intake.missing:
        prio = "YELLOW"
    else:
        prio = "GREEN"
    return Triage(priority=prio, reasons=reasons, **p)


# ------------------------------------------------------------------ 4. reply

REPLY_TEMPLATES = {
    "en": "You are registered, number {id}. {extra}Please stay nearby.",
    "es": "Está registrado, número {id}. {extra}Por favor quédese cerca.",
}
EXTRA = {
    ("en", "RED"): "A medic is coming to you now. ",
    ("es", "RED"): "Un médico viene ahora mismo. ",
    ("en", "ORANGE"): "A medic will see you soon. ",
    ("es", "ORANGE"): "Un médico le atenderá pronto. ",
}


def reply(intake: Intake, tri: Triage, rec_id: int, match_note: str | None) -> str:
    """Short message read back to the person in their own language."""
    if config.MODE != "mock":
        msg = (f"Write ONE short calm sentence in language '{intake.language}' telling a shelter arrival: "
               f"they are registered as number {rec_id}; priority {tri.priority} "
               f"({'a medic is coming now' if tri.priority == 'RED' else 'a medic will see them soon' if tri.priority == 'ORANGE' else 'staff will help them'})"
               + (f"; and this good news: {match_note}" if match_note else "") + ". Output only the sentence.")
        return _chat(msg, max_tokens=80).strip()
    lang = intake.language if intake.language in REPLY_TEMPLATES else "en"
    out = REPLY_TEMPLATES[lang].format(id=rec_id, extra=EXTRA.get((lang, tri.priority), ""))
    if match_note:
        out += (" ¡Buenas noticias! " if lang == "es" else " Good news: ") + match_note
    return out


# ------------------------------------------------------- mock extractor (demo)

_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
        "nine": 9, "ten": 10, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
        "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}


def _age(s: str) -> int | None:
    m = re.search(r"(\d{1,3})|\b(" + "|".join(_NUM) + r")\b", s.lower())
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else _NUM[m.group(2)]


def _mock_extract(t: str) -> Intake:
    low = t.lower()
    es = bool(re.search(r"\b(me llamo|mi |tengo|hijo|hija|no encuentro|necesito)\b", low))
    name = re.search(r"(?i:my name is|i am|i'm|me llamo|soy)\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)", t)
    speaker = name.group(1) if name else None

    missing, found = [], []
    for m in re.finditer(r"(?i:can't find|cannot find|looking for|lost|no encuentro a|busco a)\s+"
                         r"(?i:my\s+\w+\s+|mi\s+\w+\s+)?([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)([^.]*)", t):
        missing.append(Person(name=m.group(1), age=_age(m.group(2))))
    for m in re.finditer(r"(?i:found|brought|encontré a|traje a)\s+(?i:a\s+\w+\s+named\s+|un niño llamado\s+|una niña llamada\s+)?"
                         r"([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)([^.]*)", t):
        found.append(Person(name=m.group(1), age=_age(m.group(2))))

    meds = [w for w in ["insulin", "dialysis", "oxygen", "inhaler", "seizure"] if w in low]
    meds += [{"insulina": "insulin", "diálisis": "dialysis", "oxígeno": "oxygen"}[w]
             for w in ["insulina", "diálisis", "oxígeno"] if w in low]
    injuries = [w for w in ["bleeding", "broken", "burn", "cut", "chest pain"] if w in low]
    injuries += ["bleeding" for w in ["sangra"] if w in low]
    needs = [w for w in ["water", "food", "blanket", "charger", "diapers"] if w in low]
    needs += [{"agua": "water", "comida": "food", "manta": "blanket", "pañales": "diapers"}[w]
              for w in ["agua", "comida", "manta", "pañales"] if w in low]

    present = [Person(name=speaker)] if speaker else []
    present += found
    g = re.search(r"(?:there are|we are|somos)\s+(\w+)", low)
    group = (_age(g.group(1)) if g else None) or len(present)
    return Intake(
        speaker_name=speaker, language="es" if es else "en", group_size=max(1, group),
        people_present=present, injuries=injuries, medical_needs=sorted(set(meds)),
        missing=missing, found=found, needs=sorted(set(needs)),
        summary_en=(f"{speaker or 'Unnamed'}" + (f"; needs {', '.join(set(meds))}" if meds else "")
                    + (f"; looking for {', '.join(p.name for p in missing)}" if missing else "")
                    + (f"; brought in {', '.join(p.name for p in found)}" if found else "")),
    )
