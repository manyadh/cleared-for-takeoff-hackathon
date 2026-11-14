# Fable brief: finish MUSTER for the Cleared for Takeoff hackathon

You are taking over a working prototype. Read this whole file first, then `BOARD_RUNBOOK.md` (the step-by-step board plan), then the hackathon repo's
`AGENTS.md` and `docs/developer-guide.md`. Where this brief and `AGENTS.md` conflict, **AGENTS.md wins**.

- Hackathon repo: https://github.com/heath0xFF/cleared-for-takeoff-hackathon
- Our code: the `muster/` folder next to this file. Place it at `apps/muster/` in a fork of the hackathon repo.

---

## 1. Event facts (from the organizers' slides and repo)

- **Event:** On-Device AI Hackathon "Cleared for Takeoff" (Liquid AI × Qualcomm), SF, Fri Nov 13 2026.
- **Time:** the build window is **2 hours** (6:15–8:00 PM PT). Building ends and judging starts at **8:15 PM**.
- **Submission (8:00–8:30 PM PT)** at submissions.loggia.sh/events/cleared-for-takeoff. Two links are required:
  1. A **public GitHub repo**. Organizers review the code for anything that calls a service off the board.
  2. An **Arduino Project Hub** post with the full write-up **and** the code, not only a link back to GitHub. Posting needs an Arduino account; sign in before 8:00.
- **Hardware:** Dragonwing IQ-9075 EVK, Ubuntu 24.04 aarch64, 36 GB RAM, up to 100 TOPS NPU. Login `ubuntu` / `liquidxqualcomm` over UART or SSH; the user types passwords themselves.
- **Reference stack:**
  - Generator: `LiquidAI/LFM3-1.7B-GGUF:Q4_0`, GenieX **v0.10.0**, NPU, `http://127.0.0.1:18181`. Start it with `bash skills/iq9-geniex-lfm/scripts/serve.sh run`.
  - Optional decision gate: `LiquidAI/d1-2B`, Transformers on CPU, fp32, local snapshot `~/models/d1-2B`, `model.system_one(state_json, questions)`.
  - Optional ZETIC route: `examples/zetic-lfm/run.py`, used for audio/Omni. WAV only, 30 s max, and its **ASR system prompt is English only**.
- **Model media:** teams get USB drives with the models. **Copy models onto the board; never move them off or modify the drive.** Ask before any download.
- **Demo format:** 2 minutes plus one judge question. Turn the board's Wi-Fi off in front of the judge from the **UART console** (`sudo nmcli radio wifi off`, then `nmcli -p device`). An isolated USB-C link from the laptop for SSH and the board-hosted web UI is allowed, as long as the laptop is not sharing its internet. Show the app's log of local inputs, decisions, actions and errors. Bring a visible timer, local sample data and a backup recording.
- **Every finalist is asked: "Why should this not simply be a cloud API call?"** The answer must name a specific constraint.
- **Scoring:** edge-native value 25%, technical execution 20%, originality 20%, real-world usefulness 15%, performance/efficiency 10%, demo quality 10%.

## 2. The product: Muster, offline disaster-shelter intake

**One line:** when the cell towers go down, the shelter still knows who's here, who's hurt, and who's missing.

**User:** volunteers at an emergency shelter after a hurricane or earthquake. Arrivals report by voice or typing,
in English or Spanish. The board:
1. Turns the report into a structured record (name, group size, injuries, medical needs, people they are
   looking for, unaccompanied people they brought in, supplies needed) using **LFM3-1.7B on the NPU**.
2. Assigns a triage priority (RED, ORANGE, YELLOW or GREEN) with **d1-2B** asking typed yes/no questions:
   life threat, time-critical medication, vulnerable person. The text model is the fallback.
3. **Reunites families:** fuzzy name plus age matching between the "looking for" and "brought in" lists, shown as a banner.
   A match is a lead for staff to verify, never an automatic decision.
4. Replies to the person in their own language.
5. Packs each record into a **~40-byte radio line** (for example `S07|001|O|G1|MED:insulin|MISS:Luis/8`) for LoRa, ham radio or satellite.
   The demo simulates this with UDP to a receiver process **on the board**.
6. Logs every step with timings to a flushed JSONL file and shows it live on the dashboard.

**Answer to the judges' question:**
1. **The network is gone:** in disasters the cell network fails first, and the intake desk can't fail with it.
2. **The data is sensitive:** medical details and missing children's names never leave the shelter's hardware.
3. **Bandwidth:** only about 40 bytes per person leave the board, so it works over radio links where a cloud API is impossible.

## 3. Current state of the code (works end to end in mock mode)

```
muster/
  muster/config.py     env-var settings; defaults already match the reference stack
  muster/schema.py     dataclasses + Intake.from_dict, which validates/coerces model JSON
  muster/pipeline.py   transcribe -> extract (LFM3 JSON) -> triage (d1 / llm / rules) -> reply; mock + device paths
  muster/reunite.py    missing <-> found matching (difflib name ratio >= 0.75, age within 3)
  muster/uplink.py     compact radio line (<=160 B) + UDP send if MUSTER_UPLINK is set
  muster/receiver.py   "regional command" terminal (UDP listener)
  muster/log.py        flushed JSONL log (stage, ms, inputs, outputs, errors) + /log endpoint feed
  muster/db.py         SQLite on the board
  muster/app.py        stdlib http.server: POST /intake {text}, POST /intake_audio (raw), GET /board, GET /log, POST /reset
  muster/console.py    UART text UI: no-network fallback for the demo
  static/index.html    one page: kiosk (push-to-talk + text box), priority queue, reunite banner,
                       supplies, radio log, decision log. No CDN assets.
  samples/demo_lines.txt, samples/run_demo.sh   local demo data + backup script
```

**Verified on a laptop (standard library only):** the device path was tested against a fake GenieX server. The request fields match `lfm_client.py`, and messy model JSON (code fences, numbers as strings, `<think>` tags) is normalized correctly. In mock mode: the four demo lines give Ana ORANGE (insulin, looking for Luis, 8, Spanish reply),
David ORANGE (brought in Luis, 8) with the possible-reunion match firing, Grace RED (bleeding), and Omar GREEN (group of 4).
About 130 bytes go out over the uplink in total, the error path is logged, and the dashboard renders.

**Not verified at all:** anything on the real board. That includes real GenieX v0.10.0 responses,
JSON reliability of LFM3-1.7B extraction, the d1 `system_one` call, the ZETIC ASR subprocess, and ffmpeg on the board.

**Env vars (see config.py):** `MUSTER_MODE=mock|device`, `MUSTER_TRIAGE=rules|llm|d1`, `MUSTER_ASR=mock|zetic`,
`MUSTER_LLM_URL` (default `http://127.0.0.1:18181/v1`), `MUSTER_LLM_MODEL` (default `LiquidAI/LFM3-1.7B-GGUF:Q4_0`),
`MUSTER_JSON_MODE=1` (only if GenieX accepts `response_format`), `MUSTER_D1_DIR`, `MUSTER_THRESHOLD`,
`MUSTER_ZETIC_RUN/SDK/MODEL`, `MUSTER_UPLINK=127.0.0.1:9999`, `MUSTER_SITE`, `MUSTER_DB`, `MUSTER_LOG`.

## 4. Your job, in priority order (2 hours total)

Put the setup in **one plan for one approval** (AGENTS.md asks for this). Don't ask step by step.

1. **Board access (laptop side):** find the connection method (UART or USB-C/SSH). Don't guess IP addresses, change network settings,
   or install anything without asking. Follow `skills/iq9-getting-started/SKILL.md`, then run preflight `--profile board`.
2. **First NPU response:** stage LFM3-1.7B from the USB drive (copy, never move), start the GenieX server, send one capped request,
   and confirm `HTP0` in the server log.
3. **Dependencies:** none. Muster is **standard-library Python 3.12** (no pip). Only d1 needs `~/.venvs/d1`.
4. **Switch to real models:** run with `MUSTER_MODE=device MUSTER_TRIAGE=llm`. Adapt only `_chat`, `extract`,
   and `reply` in `pipeline.py` if the request or response shape differs. Follow AGENTS.md rule 2: cap tokens and reject
   empty or reasoning-only answers. Run the four `samples/demo_lines.txt` lines and show me the records.
   Tune `EXTRACT_PROMPT` until all four produce the same fields as the mock run (above all, Ana's missing Luis and David's found Luis).
5. **UI path:** the app binds 127.0.0.1:8000 and the laptop reaches it with `ssh -L 8000:127.0.0.1:8000`.
   For the Wi-Fi-off demo, set up the isolated USB-C network link (ask the organizers how) or fall back to
   `python3 -m muster.console` on the UART console. Run `muster.receiver` in a second board terminal and set `MUSTER_UPLINK=127.0.0.1:9999`.
6. **Offline rehearsal:** Wi-Fi off from UART, then run `samples/run_demo.sh` and one live typed entry. Fix anything that breaks.
   Push the public GitHub repo **before 7:45**.
7. **Extras, only if time remains:**
   - d1 triage (`MUSTER_TRIAGE=d1`; the code already calls `system_one`; review the snapshot code before `trust_remote_code`; set the threshold from the demo lines, not a copied 0.5).
   - English voice via ZETIC Omni (needs ffmpeg and the staged ZETIC packages).
   - Privacy upgrade: a consent checkbox at intake, and radio lines that send only flags and counts unless consent is given for names.
8. **Docs:** update `README.md` with the measured numbers for our app (time to first token or extract latency, triage latency,
   end-to-end ms from the JSONL log, board/runtime/model/precision, sample count, medians), and only numbers we measured.

## 5. Demo script (2 min, network off)

0. UART: `sudo nmcli radio wifi off` → `nmcli -p device`. Start the visible timer.
1. **Ana** (Spanish, typed): "Me llamo Ana. Tengo diabetes y necesito insulina. No encuentro a mi hijo Luis, tiene 8 años."
   → ORANGE, insulin flagged, reply in Spanish.
2. **David:** "My name is David. I found a boy named Luis, about eight years old, alone by the bridge." → **possible-reunion banner**. Pause here.
3. **Grace:** "I'm Grace. My husband is bleeding badly from his leg." → jumps to the top as RED.
4. Point at the radio log and receiver: "Regional command knows all of this from about 130 bytes."
5. Point at the decision log: every stage is timed, every action is recorded, errors are visible.
6. Close: "In every disaster the network dies first. The intake desk shouldn't die with it."

**Backups:** `samples/run_demo.sh`, `python3 -m muster.console` over UART, mock mode, and a screen recording made during rehearsal.

## 6. Rules you must not break

- No cloud calls, downloads, telemetry or CDN assets at runtime. Load models from local files only (`local_files_only=True`, HF offline env vars).
- Get approval before installs, model copies or imports, network or SSH config changes, or non-loopback binding.
  Don't stop servers you didn't start.
- Code decides actions, not model prose. Validate the extracted JSON against the schema, and treat reunite matches as leads for staff to verify.
- Only claim board or offline verification you actually performed, and list what is still unverified.

## 7. Arduino Project Hub write-up (draft it at the end)

Sections: problem (shelter intake when the network is down), what it does, architecture diagram (text),
models and runtimes used, why on-device (the three constraints), measured performance, how to run, the demo,
limitations (English-only ASR via the wrapper, mock fallbacks, d1 threshold not calibrated on real data),
and next steps (LoRa hardware, consent and encryption, more ASR languages). Paste the code or attach the repo files.
