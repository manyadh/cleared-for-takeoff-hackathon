# MUSTER: full context for Fable

This is the complete context from planning so far. The code is in this folder (`muster/`), already working.
Your job is to get it running on the physical **Dragonwing IQ-9075** board, polish it, and get it submitted.

Read order: this file → `BOARD_RUNBOOK.md` (step-by-step board commands) → the hackathon repo's `AGENTS.md`
and `docs/developer-guide.md`. **If anything here conflicts with `AGENTS.md`, AGENTS.md wins.**

---

## 1. The event

- **Name:** On-Device AI Hackathon "Cleared for Takeoff", Liquid AI × Qualcomm, San Francisco, Fri **Nov 13 2026**.
- **Schedule (PT):** workshop 6:00–6:15, **hacking 6:15–8:00**, submit 8:00–8:30, building ends and judging starts **8:15**,
  showcase and awards 8:30–9:00. **Total build time is about 2 hours.**
- **Venue Wi-Fi:** `555Mission Guest` / `GuestAccess`.
- **Team:** two people (me and a partner). We develop on laptops with Claude/Fable; the app must **run on the board**.
- **Hackathon repo:** https://github.com/heath0xFF/cleared-for-takeoff-hackathon. Fork it and put our app in `apps/muster/`.
  It has `AGENTS.md` for coding agents and skills in `skills/` (iq9-getting-started, iq9-preflight, iq9-geniex-lfm,
  iq9-d1-decision-gate, iq9-offline-rehearsal, iq9-demo-prep). Read the matching SKILL.md before doing that kind of work.
- **Prizes:** 1st place IQ9 boards, 2nd place Arduino UNO Qs. **Judges:** Liquid AI technical staff plus Qualcomm engineers and DevRel.

### Brief: "Build intelligence that doesn't need the internet"
- **Everything runs on the board:** models, data, inference and UI. Final demos run with external network access removed.
- **Name a real constraint:** no network, sensitive data, sub-second reactions, or flat cost at scale.
- **The idea must be distinct,** not another generic chatbot: a clear user, a real need, and a plausible next step.

### Scoring
| Weight | Criterion |
|---|---|
| 25% | Edge-native value (why better or only possible on-device) |
| 20% | Technical execution (reliability, integration, local operation) |
| 20% | Originality |
| 15% | Real-world usefulness |
| 10% | Performance / efficiency (latency, memory) |
| 10% | Demo quality |

### Demo format
- **Two minutes plus one judge question.** Every finalist gets **"Why should this not simply be a cloud API call?"**
  Answer with a specific constraint; "it's on-device" is not an answer.
- **Turn the board's Wi-Fi off in front of the judge** from the UART console or a USB-C link, never from SSH over Wi-Fi:
  `sudo nmcli radio wifi off`, then `nmcli -p device`. Unplug Ethernet.
- An **isolated USB-C network link** between laptop and board is allowed for SSH and a board-hosted web UI, with **no laptop internet sharing**.
- **Show the app's log:** local inputs, decisions, executed actions, and errors.
- **Bring a visible timer, local sample data and a backup recording.**

### Submission (8:00–8:30 PM PT) at submissions.loggia.sh/events/cleared-for-takeoff
1. A **public GitHub repo** link. Organizers review the code for anything that calls off the board.
2. An **Arduino Project Hub** post with the full write-up **and code**, not only a GitHub link. You need an Arduino account first.

## 2. Hardware and software stack

- **Board:** Qualcomm Dragonwing IQ-9075 EVK, Ubuntu 24.04 aarch64, 36 GB LPDDR5, octa-core Kryo CPU, Adreno 663 GPU,
  dual Hexagon NPU (up to 100 TOPS). Login `ubuntu` / `liquidxqualcomm` (UART and SSH); the user types passwords.
- **Boards start as a fresh Ubuntu install.** NPU packages, GenieX and models must be set up during the event.
- **Reference generator:** `LiquidAI/LFM3-1.7B-GGUF:Q4_0` on the NPU through **GenieX v0.10.0**, OpenAI-compatible server at
  **`http://127.0.0.1:18181`**. Request fields: `model`, `messages`, `max_completion_tokens`, `compute: "npu"`,
  `stream: false`, `enable_think: false`. Verify NPU use by an `HTP0` line in the server log.
- **Optional d1 decision gate:** `LiquidAI/d1-2B`, Transformers on **CPU fp32**, local snapshot `~/models/d1-2B`, venv `~/.venvs/d1`.
  API: `model.system_one(json_state, questions)`. Question types are `noul` (yes/no → `{"noul": p}`), `choice` and `score`, with key `"instructions"`.
  Zero output tokens is expected.
- **Optional ZETIC route:** `examples/zetic-lfm/run.py` (Ixian Hexagon SDK 0.2.1) for LFM3-Omni/Audio. WAV input only, **30 s max**,
  and **its ASR prompt is English only**. It also needs `ffmpeg` to convert browser audio.
- **Models come on supplied USB drives.** Copy them onto the board and **never move or modify the drive**. Ask before downloading anything.
- **Don't install or update `qcom-adreno1` and don't run `install_ppa_pkgs.sh`;** both break external monitors.

### LFM3 family (released Oct 27 2026, open weights, LFM Open License v1.0)
| Model | What it does |
|---|---|
| LFM3-1.7B | text, 256K context, tool calling, about 1 GB at 4-bit |
| LFM3-VL-2B | text + images + video → text |
| LFM3-Audio-2B | speech in and out (18 languages), tool calls from speech |
| LFM3-Omni-2B | text, images, video and audio → text or speech |
| d1-2B / d1-Omni-2B | decision models: typed answers with calibrated probabilities in one forward pass, no text generated |

## 3. The idea we chose: Muster, offline disaster-shelter intake

**Pitch:** *When the cell towers go down, the shelter still knows who's here, who's hurt, and who's missing.*

**User:** volunteers running an emergency shelter after a hurricane or earthquake, when the cell network is down.

**Flow:** an arrival speaks or types a report in English or Spanish, and the board then:
1. **Extracts** a structured record with LFM3-1.7B on the NPU: name, language, group size, people present, injuries,
   medical needs, people they're **looking for**, unaccompanied people they **brought in**, supplies needed, and an English summary.
2. **Triages** to RED, ORANGE, YELLOW or GREEN by asking three yes/no questions (d1-2B, or LLM/rules as fallback):
   life threat, time-critical medication (insulin, dialysis, oxygen), vulnerable person (child, pregnant, can't walk).
3. **Flags possible family reunions** by fuzzy name plus age matching between "looking for" and "brought in" lists.
   These are **leads for staff to verify**, never automatic.
4. **Replies** to the person in their own language.
5. **Packs** each record into a ~40-byte radio line such as `S07|001|O|G1|MED:insulin|MISS:Luis/8|N:water` for LoRa, ham radio or satellite.
   The demo sends it over UDP to a receiver process on the board playing "regional command".
6. **Logs** every stage with timings to a flushed JSONL file, shown live on the dashboard.

**Answer to "why not a cloud API call?":**
1. **No network:** the cell network is the first thing to fail in a disaster, and intake can't fail with it.
2. **Sensitive data:** medical details and missing children's names never leave the shelter's hardware.
3. **Bandwidth:** about 40 bytes per person goes out (about 130 B for four people). It works over radio, where a cloud API can't.

**Why we picked it over other ideas:** offline is the whole premise, not a feature. It has real-world impact, a memorable demo moment
(the reunion banner), and a clean split of work for two people. Rejected ideas: a pre-flight checklist co-pilot, a camera-trap that sends text
instead of video, pytest-style checks for the physical world, a homework tutor, an air-gapped document reader, and a board-game referee.

### Privacy (judges may ask)
- **Nothing calls any cloud service at runtime, Claude included.** All inference runs on the board.
- **Records stay on the board** in SQLite (`muster.db`); the dashboard is reachable only over local links.
- **Radio lines only go where `MUSTER_UPLINK` points.** In the demo, that's a process on the same board.
- **Known gap:** the radio line currently includes names and medical needs in plaintext. A planned upgrade, if time allows:
  ask for consent at intake, send only flags and counts by default and names only with consent, encrypt the DB, and add a wipe button.

## 4. Code: what exists (all standard-library Python 3.12, no pip installs)

```
muster/
  FABLE_CONTEXT.md     this file
  BOARD_RUNBOOK.md     step-by-step [LAPTOP]/[BOARD] commands with a 6:15-8:00 timeline
  FABLE_BRIEF.md       shorter task brief (overlaps this file)
  README.md            project README (add measured numbers before submitting)
  muster/config.py     all settings via env vars; defaults = reference stack
  muster/schema.py     dataclasses Person/Intake/Triage/Record; Intake.from_dict validates and coerces model JSON
  muster/pipeline.py   transcribe -> extract -> triage -> reply; mock and device paths per stage
  muster/reunite.py    missing <-> found matching (difflib ratio >= 0.75, age within 3)
  muster/uplink.py     compact radio line (<=160 B) + UDP send
  muster/receiver.py   "regional command" UDP listener (terminal)
  muster/log.py        flushed JSONL log: stage, ms, inputs/outputs, actions, errors
  muster/db.py         SQLite (one JSON blob per record)
  muster/app.py        stdlib http.server on 127.0.0.1:8000
                       POST /intake {"text"} | POST /intake_audio (raw body) | GET /board | GET /log | POST /reset
  muster/console.py    text UI for the UART console (interactive, or --watch) - no-network fallback
  static/index.html    dashboard: kiosk (push-to-talk + text), priority queue, possible-reunion banner,
                       supplies, radio log, decision log. No CDN assets, no emoji.
  samples/demo_lines.txt, samples/run_demo.sh   local demo data + backup script (DELAY=secs)
```

### Environment variables
| Var | Values / default | Purpose |
|---|---|---|
| `MUSTER_MODE` | `mock` (default) / `device` | mock = keyword rules, runs anywhere; device = real LFM3 |
| `MUSTER_TRIAGE` | `rules` / `llm` / `d1` | triage backend |
| `MUSTER_ASR` | `mock` / `zetic` | speech input (typed input always works) |
| `MUSTER_LLM_URL` | `http://127.0.0.1:18181/v1` | GenieX server |
| `MUSTER_LLM_MODEL` | `LiquidAI/LFM3-1.7B-GGUF:Q4_0` | |
| `MUSTER_LLM_COMPUTE` | `npu` | |
| `MUSTER_JSON_MODE` | `0` | set `1` only if GenieX accepts `response_format` |
| `MUSTER_D1_DIR` | `~/models/d1-2B` | |
| `MUSTER_THRESHOLD` | `0.5` | set from demo lines; don't trust 0.5 blindly |
| `MUSTER_ZETIC_RUN/SDK/MODEL` | `~/zetic-demo/...` | ZETIC wrapper paths |
| `MUSTER_UPLINK` | unset | e.g. `127.0.0.1:9999` to send radio lines to the receiver |
| `MUSTER_SITE`, `MUSTER_DB`, `MUSTER_LOG` | `S07`, `muster.db`, `muster_log.jsonl` | |

### Verified (on a laptop, not the board)
- **Mock mode end to end:** the four demo lines give Ana ORANGE (insulin, looking for Luis/8, Spanish reply), David ORANGE (brought
  Luis/8) with the **possible-reunion match**, Grace RED (bleeding) and Omar GREEN (group 4). About 133 B of radio lines,
  the receiver gets them, errors are logged, and the browser submit flow and console UI both work.
- **Device path against a fake GenieX server:** the request fields match the repo's `lfm_client.py`. Messy model output
  (code fences, numbers as strings, a string instead of a list, `<think>` tags) normalizes to a correct record.

### Not verified
- Anything on the real board, including real GenieX v0.10.0 responses.
- Whether LFM3-1.7B extracts the four demo lines correctly.
- d1 `system_one` on the real snapshot, the ZETIC ASR subprocess, ffmpeg on the board, and USB-C networking.

## 5. What Fable should do (priority order, 2-hour budget)

Per AGENTS.md, propose the setup as **one plan for one approval**. Don't guess IPs, change network or SSH settings,
install packages, copy models or bind beyond loopback without asking. Don't stop servers you didn't start.

1. **Board access:** UART (micro-USB, 115200, second serial port), then join the venue Wi-Fi, then SSH from the laptop, then preflight `--profile board`.
2. **NPU + model:** install `libatomic1 qcom-fastrpc1 libqnn1` (simulate first, no `-y`), add the user to the `fastrpc` group and re-login,
   install GenieX v0.10.0, `geniex pull ... --model-hub localfs --local-path <USB dir>`, run `serve.sh run`, then one capped request
   and check for `HTP0`.
3. **Muster on the board:** `scp -r apps/muster` to the board, then run
   `MUSTER_MODE=device MUSTER_TRIAGE=llm MUSTER_UPLINK=127.0.0.1:9999 python3 -m muster.app`, plus `python3 -m muster.receiver 9999`.
   On the laptop: `ssh -N -L 127.0.0.1:8000:127.0.0.1:8000 "$IQ9_HOST"` → http://127.0.0.1:8000.
4. **Make the four demo lines correct in device mode.** Tune only `EXTRACT_PROMPT` and the `_chat`/`extract`/`reply`
   functions in `pipeline.py`. Keep the mock path working. Cap tokens and reject empty or reasoning-only answers (AGENTS.md rule 2).
5. **Offline path:** get the isolated USB-C network link working (ask the organizers how), or fall back to `python3 -m muster.console`
   on UART. Start GenieX and the app so they survive the Wi-Fi cut (UART or tmux). Rehearse once with Wi-Fi off and record a backup video.
6. **Push the public repo by 7:45.** Add only measured numbers to the README: extract/triage ms medians from the JSONL,
   board, runtime, model/precision and sample count.
7. **Extras if there's time:** d1 triage, English voice via ZETIC Omni, and the privacy upgrade (consent + flags-only radio lines).
8. **Draft the Arduino Project Hub write-up:** problem, what it does, architecture, models/runtimes, why on-device (the 3 constraints),
   measured performance, how to run, demo, limitations (English-only ASR, mock fallbacks, uncalibrated threshold),
   and next steps (LoRa hardware, consent/encryption, more languages).

## 6. Demo script (2 minutes, network off)

0. From UART: `sudo nmcli radio wifi off` → `nmcli -p device`. Start the visible timer.
1. **Ana** (Spanish, typed): *"Me llamo Ana. Tengo diabetes y necesito insulina. No encuentro a mi hijo Luis, tiene 8 años."*
   → ORANGE, insulin flagged, reply in Spanish.
2. **David:** *"My name is David. I found a boy named Luis, about eight years old, alone by the bridge."*
   → **possible-reunion banner**. Pause here; it's the moment.
3. **Grace:** *"I'm Grace. My husband is bleeding badly from his leg."* → jumps to the top as RED.
4. Point at the radio log and receiver: "Regional command knows all of this from about 130 bytes."
5. Point at the decision log: every stage is timed, every action is recorded, errors are visible.
6. Close: "In every disaster the network dies first. The intake desk shouldn't die with it."

**Backups:** `samples/run_demo.sh`, `python3 -m muster.console` on UART, mock mode, and the rehearsal recording.

## 7. Rules that must not be broken
- **Offline at runtime:** no downloads, installs, telemetry, cloud calls or CDN assets. Load local files only
  (`local_files_only=True`, HF offline env vars for d1).
- **Code authorizes actions, not model prose.** Validate extracted JSON (`Intake.from_dict`); reunions are leads for staff to verify.
- **Only claim board or offline verification that was actually performed,** and list what's unverified.
- **Report only numbers measured on our own app and board,** never numbers quoted from docs.
- **No emoji in code or docs** (repo guidance).
