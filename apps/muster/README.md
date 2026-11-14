# MUSTER: offline shelter intake

**When the cell towers go down, the shelter still knows who's here, who's hurt, and who's missing.**

People report to a kiosk by voice or typing. LFM3 models on the Dragonwing IQ-9075 turn each report into
a structured record. d1-2B flags who needs a medic first, the board matches people looking for family
against people who were brought in, and every record is packed into a ~40-byte line small enough for a radio link.
Models, data, inference and UI all run on the board.

```
 voice/text ─► LFM3-Omni-2B ─► LFM3-1.7B (NPU) ─► d1-2B (CPU) ─► board + reply + radio line
               ZETIC, WAV→text   GenieX :18181      system_one      reunite matching, JSONL log
```

## Why not a cloud API call? (the judges' first question)
1. **No network:** in a hurricane or earthquake the cell network fails first. The intake desk has to keep working without it.
2. **Sensitive data:** names, injuries, medications and missing children never leave the shelter's own hardware.
3. **Bandwidth:** what goes out is a 40-byte line per person (about 130 B for four people), small enough for LoRa, ham radio or a satellite messenger. It never sends audio or full records.

## Run it
Standard-library Python 3.12 only. **No pip install.** Full board steps are in `BOARD_RUNBOOK.md`.
```bash
python3 -m muster.app                      # 127.0.0.1:8000 (mock mode: works anywhere)
python3 -m muster.receiver 9999            # "regional command", 2nd terminal on the same board
python3 -m muster.console                  # text UI for the UART console (no network needed)
samples/run_demo.sh                        # backup: feeds the 4 local sample reports
```
On the board with real models (GenieX serving LFM3-1.7B on 127.0.0.1:18181):
```bash
MUSTER_MODE=device MUSTER_TRIAGE=llm MUSTER_UPLINK=127.0.0.1:9999 python3 -m muster.app
```
Laptop browser through an SSH tunnel: `ssh -N -L 127.0.0.1:8000:127.0.0.1:8000 "$IQ9_HOST"`, then open http://127.0.0.1:8000

| Piece | Setting | Notes |
|---|---|---|
| Text LLM | `http://127.0.0.1:18181/v1`, `LiquidAI/LFM3-1.7B-GGUF:Q4_0`, `compute: npu`, `enable_think: false` | same request fields as the repo's `lfm_client.py` |
| d1 triage | `MUSTER_TRIAGE=d1`, `MUSTER_D1_DIR=~/models/d1-2B`, run with `~/.venvs/d1/bin/python` | `model.system_one(state, questions)`, CPU fp32, local files only; set `MUSTER_THRESHOLD` |
| Voice | `MUSTER_ASR=zetic` + `MUSTER_ZETIC_RUN/SDK/MODEL` | repo's ZETIC wrapper; WAV ≤30 s; English ASR only; needs `ffmpeg` |

## Files
| file | what |
|---|---|
| `muster/pipeline.py` | transcribe → extract JSON (LFM3-1.7B) → triage (d1) → reply. Mock + device paths |
| `muster/reunite.py` | missing ↔ found matching (fuzzy name + age within 3 years) |
| `muster/uplink.py` | record → `S07|001|O|G1|MED:insulin|MISS:Luis/8` + UDP send |
| `muster/log.py` | flushed JSONL: inputs, decisions with ms, actions, errors (`muster_log.jsonl`) |
| `muster/receiver.py` | regional-command terminal |
| `static/index.html` | kiosk + priority queue + supplies + radio log + decision log |
| `samples/` | local demo data + backup script |

## Demo (2 min, network off)
0. **On the UART console:** `sudo nmcli radio wifi off` then `nmcli -p device`. Start a visible timer.
1. Ana (Spanish, typed or spoken): insulin + missing son Luis → **ORANGE**, reply in Spanish.
2. David: "I found a boy named Luis, about eight…" → **possible-reunion banner**. Pause on it.
3. Grace: husband bleeding → jumps to the top as **RED**.
4. Point at the radio log and receiver: "Regional command knows all of this from ~130 bytes."
5. Point at the decision log: each stage timed, each action logged, errors visible.

## Next steps
LoRa module for real radio links, a consent prompt before names go out on the radio, an encrypted DB with a wipe button, and Spanish/Arabic ASR checked on-device.
