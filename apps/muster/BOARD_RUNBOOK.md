# Muster on the Dragonwing IQ-9075: board runbook

Every command is labeled **[LAPTOP]** or **[BOARD]**. Board commands run in a board shell (UART or SSH).
Sources: the hackathon repo's `docs/developer-guide.md`, `docs/offline-readiness.md`, `docs/judging.md`, `AGENTS.md`.

**Muster needs no pip installs.** It is standard-library Python 3.12, so it runs on the board's stock Python.
The only model it needs is LFM3-1.7B on GenieX. d1, voice and ZETIC are optional extras.

```
 Laptop (browser) --SSH tunnel over isolated USB-C link--> Board 127.0.0.1:8000  Muster app
                                                            Board 127.0.0.1:18181 GenieX -> LFM3-1.7B Q4_0 on NPU
                                                            Board UDP :9999       receiver ("regional command")
 Fallback UI with no network at all: UART console -> python3 -m muster.console
```

## Timeline (build window 6:15-8:00, judging 8:15)

| Clock | Phase | Done when |
|---|---|---|
| 6:15-6:30 | 1. Board access | SSH from the laptop works |
| 6:30-7:05 | 2. NPU + model | One capped LFM3 answer and an `HTP0` line in the server log |
| 7:05-7:30 | 3. Muster on the board | 4 demo lines give correct records in device mode |
| 7:30-7:45 | 4. Offline control path + rehearsal | Demo runs with Wi-Fi off |
| 7:45-8:00 | 5. Submit prep | Public repo pushed, Arduino Project Hub draft ready |

Partner, in parallel: fork the repo, set up the GitHub + Arduino accounts, draft the Project Hub write-up,
and ask the organizers early **how to set up the USB-C network link** (phase 4).

---

## Phase 1: board access (6:15)

**[LAPTOP]** Plug the micro-USB cable into the board's debug UART port (not the USB-C port) and open the second serial port at 115200:
```bash
ls /dev/cu.*                          # macOS   -> screen /dev/cu.<second-port> 115200
ls /dev/ttyUSB*                       # Linux   -> sudo screen /dev/ttyUSB1 115200
```
Log in with `ubuntu` / `liquidxqualcomm`, typing the password yourself.

**[BOARD]** Check the board and get it online for setup:
```bash
uname -m && grep VERSION= /etc/os-release      # aarch64, Ubuntu 24.04
nmcli dev wifi list
sudo nmcli --ask dev wifi connect '555Mission Guest'      # password: GuestAccess
ip -br address                                 # note the Wi-Fi IP
```

**[LAPTOP]** Clone the repo, then SSH in using the IP the board reported:
```bash
git clone https://github.com/<you>/cleared-for-takeoff-hackathon.git && cd cleared-for-takeoff-hackathon
mkdir -p apps && unzip ~/Downloads/muster.zip -d apps/        # -> apps/muster/
export IQ9_HOST='ubuntu@<BOARD_IP>'
ssh "$IQ9_HOST" 'bash -s -- --profile board --json' < skills/iq9-preflight/scripts/preflight.sh
```

## Phase 2: NPU + model (6:30)

**[BOARD]** Install the NPU packages. Simulate first, read the plan, then install without `-y`:
```bash
sudo apt-get update && apt-get -s install --no-install-recommends libatomic1 qcom-fastrpc1 libqnn1
sudo apt-get install --no-install-recommends libatomic1 qcom-fastrpc1 libqnn1
sudo usermod -aG fastrpc "$USER"               # then log out and SSH back in
for n in /dev/fastrpc-cdsp /dev/fastrpc-cdsp1; do [ -r $n ] && [ -w $n ] && echo "rw ok $n" || echo "NO rw $n"; done
```
Do **not** install or update `qcom-adreno1`, and do not run Qualcomm's `install_ppa_pkgs.sh`. They break external monitors.

**[BOARD]** Install GenieX v0.10.0, reading the installer before running it:
```bash
curl -fSLo install.sh https://qaihub-public-assets.s3.us-west-2.amazonaws.com/qai-hub-geniex/install.sh
less install.sh
sh install.sh --version v0.10.0
export PATH="$HOME/.local/bin:$PATH"
geniex version && geniex config get chipset    # v0.10.0, Dragonwing IQ-9075 EVK
```

**[BOARD]** Copy the model from the supplied USB drive. **Copy only, never move or modify the drive.**
```bash
lsblk -o NAME,TRAN,SIZE,FSTYPE,LABEL,MOUNTPOINTS ; df -h /
MODEL_USB_DIR='/media/.../<LFM3-1.7B QAD-Q4_0 GGUF dir>'       # the directory you actually see
geniex --skip-update pull LiquidAI/LFM3-1.7B-GGUF:Q4_0 --model-hub localfs --local-path "$MODEL_USB_DIR"
geniex --skip-update list
```
If there's no drive, `geniex --skip-update pull LiquidAI/LFM3-1.7B-GGUF:Q4_0` downloads it while online.

**[LAPTOP]** Copy the server helpers and Muster to the board:
```bash
ssh "$IQ9_HOST" 'mkdir -p ~/iq9-work'
scp skills/iq9-geniex-lfm/scripts/{serve.sh,lfm_client.py} "$IQ9_HOST":iq9-work/
scp -r apps/muster "$IQ9_HOST":~/muster
```

**[BOARD, terminal A]** Start the server and leave it running in the foreground. Use `tmux` if it's installed so it survives disconnects.
```bash
bash ~/iq9-work/serve.sh run                    # LFM3 on NPU, 127.0.0.1:18181, 30-min keepalive
```
**[BOARD, terminal B]** Prove it works:
```bash
python3 ~/iq9-work/lfm_client.py --sentence 'Say hello in five words.'
bash ~/iq9-work/serve.sh status                 # must show an HTP0 line = ran on the NPU
```

## Phase 3: Muster on the board (7:05)

**[BOARD, terminal B]** Start the receiver:
```bash
cd ~/muster && python3 -m muster.receiver 9999
```
**[BOARD, terminal C]** Start the app in device mode, with the text model doing triage:
```bash
cd ~/muster && MUSTER_MODE=device MUSTER_TRIAGE=llm MUSTER_UPLINK=127.0.0.1:9999 python3 -m muster.app
```
**[LAPTOP]** Open a tunnel to the dashboard, then open http://127.0.0.1:8000:
```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8000:127.0.0.1:8000 "$IQ9_HOST"
```
**[BOARD, terminal D]** Run the four demo lines and check them against the expected results:
```bash
cd ~/muster && DELAY=1 samples/run_demo.sh
```
| Line | Expected |
|---|---|
| Ana (Spanish) | ORANGE, `MED:insulin`, `MISS:Luis/8`, reply in Spanish |
| David | ORANGE, `FND:Luis/8`, reunion banner fires |
| Grace | RED, `INJ:bleeding` |
| Omar | GREEN, group 4 |

If a line is wrong, the log (`tail -f ~/muster/muster_log.jsonl`) shows the model's raw extraction.
Tune `EXTRACT_PROMPT` in `muster/pipeline.py`. Don't touch anything else unless it's broken.

**If device mode won't work in time,** run `python3 -m muster.app` (mock mode) so the demo still works,
and tell the judges honestly which parts are mocked. A real LFM3 extract is worth far more, so give device mode a fair try first.

## Phase 4: offline control path + rehearsal (7:30)

When Wi-Fi goes off, **SSH over Wi-Fi dies too**, and so does your tunnel. Pick your demo path **before** the cut:

- **Plan A, USB-C network link.** The browser dashboard stays up. Ask the organizers or Qualcomm DevRel how to configure
  it on this image. A USB-C cable alone is not networking. Once it's up, SSH to the board's USB-C address and
  redo the tunnel over it. **Turn off internet sharing, bridging and forwarding on the laptop.**
- **Plan B, UART only.** No network needed at all. On the UART console:
  ```bash
  cd ~/muster && python3 -m muster.console        # type reports live; shows queue, reunion, radio, log
  ```
  Start the app and GenieX from UART too, either in `tmux` or before the cut, because SSH sessions die with Wi-Fi.

**Rehearse once [BOARD, from UART or the USB-C session]:**
```bash
sudo nmcli radio wifi off && nmcli -p device     # show: no Wi-Fi
curl -m 5 -I https://huggingface.co               # should FAIL
python3 ~/iq9-work/lfm_client.py --sentence 'Offline check.'   # should still work
cd ~/muster && DELAY=3 samples/run_demo.sh
sudo nmcli radio wifi on                          # restore afterwards
```
Record the screen during the rehearsal. That's your backup video.

## Phase 5: submit (7:45)

- **[LAPTOP]** `git add apps/muster && git commit -m "Muster: offline shelter intake" && git push`. Make the repo **public**.
- Add the measured numbers to `apps/muster/README.md`: extract ms and triage ms (medians from `muster_log.jsonl`),
  the model and precision, board, GenieX version and sample count. Use only numbers you measured.
- Post on Arduino Project Hub (write-up + code). Submit both links at submissions.loggia.sh/events/cleared-for-takeoff from 8:00.

## Optional extras (only if ahead of schedule)

- **d1 triage:** `~/.venvs/d1` per developer-guide section 3.4, snapshot at `~/models/d1-2B`, review its code, then
  `MUSTER_TRIAGE=d1 ~/.venvs/d1/bin/python -m muster.app`. Set `MUSTER_THRESHOLD` from the demo lines.
- **English voice:** stage ZETIC Omni (`examples/zetic-lfm/README.md`), install `ffmpeg`, set `MUSTER_ASR=zetic`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no GenieX server` / connection refused on 18181 | terminal A died; `bash ~/iq9-work/serve.sh run` again |
| no `HTP0` in status | fastrpc access: re-check `rw ok`, re-login after `usermod`, restart the server |
| extract error "not a JSON object" / empty answer | check the log; shorten the report; raise `max_tokens` in `extract` |
| first request very slow | model loading after idle; send one warm-up request before judging |
| browser can't load the page | the tunnel died with Wi-Fi; use the USB-C address or Plan B |
| `Address already in use` on 8000 | an old app is still running: `pkill -f muster.app` |
