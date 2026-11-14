"""Muster web app - Python standard library only (runs on the board's stock Python 3.12).

On the board:   python3 -m muster.app                    # serves 127.0.0.1:8000
On the laptop:  ssh -N -L 127.0.0.1:8000:127.0.0.1:8000 "$IQ9_HOST"   then open http://127.0.0.1:8000

Routes:
  GET  /               kiosk + staff board (static/index.html)
  POST /intake         JSON {"text": "..."}               -> {"record": ..., "matches": [...]}
  POST /intake_audio   raw audio body (wav/webm)           -> same
  GET  /board          dashboard data
  GET  /log            recent decision-log entries
  POST /reset          clear records
"""
from __future__ import annotations

import argparse
import json
import threading
from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config, db, log, pipeline, reunite, uplink
from .schema import Record

STATIC = Path(__file__).resolve().parent.parent / "static"
PRIO_ORDER = {"RED": 0, "ORANGE": 1, "YELLOW": 2, "GREEN": 3}
MAX_BODY = 8 * 1024 * 1024
_intake_lock = threading.Lock()   # one report at a time: models run sequentially, ids stay unique


def do_intake(text: str | None, audio: bytes | None) -> dict:
    with log.timed("asr", backend="typed" if text else config.ASR_BACKEND, audio_bytes=len(audio or b"")) as o:
        transcript = pipeline.transcribe(audio, text)
        o["transcript"] = transcript
    with log.timed("extract", backend=config.MODE) as o:
        info = pipeline.extract(transcript)
        o["record"] = asdict(info)
    with log.timed("triage", backend=config.TRIAGE_BACKEND, threshold=config.TRIAGE_THRESHOLD) as o:
        tri = pipeline.triage(info, transcript)
        o.update(priority=tri.priority, p={"life_threat": tri.life_threat,
                 "time_critical_meds": tri.time_critical_meds, "vulnerable": tri.vulnerable})
    rec_id = db.next_id()

    # Does this person close a missing-person case (either direction)? A match is a lead for staff.
    others = [{"id": r.id, "intake": r.intake} for r in db.all_records()]
    matches = [m for m in reunite.find_matches(others + [{"id": rec_id, "intake": info}])
               if rec_id in (m["missing_in"], m["found_in"])]
    note = None
    if matches:
        m = matches[0]
        log.write("action", action="reunite_lead", **m)
        note = (f"{m['name']} may be at this shelter (record {m['found_in']}); staff will confirm."
                if m["missing_in"] == rec_id
                else f"Someone here may be looking for {m['name']} (record {m['missing_in']}); staff will confirm.")

    line = uplink.encode(rec_id, info, tri)
    uplink.send(line)
    log.write("action", action="radio_uplink", line=line, bytes=len(line))
    with log.timed("reply", backend=config.MODE) as o:
        msg = pipeline.reply(info, tri, rec_id, note)
        o["text"] = msg
    rec = Record(id=rec_id, ts=datetime.now().strftime("%H:%M:%S"), transcript=transcript,
                 intake=info, triage=tri, reply=msg, uplink=line)
    db.save(rec)
    log.write("action", action="registered", id=rec_id, priority=tri.priority)
    return {"record": rec.to_dict(), "matches": matches}


def board() -> dict:
    recs = db.all_records()
    recs_sorted = sorted(recs, key=lambda r: (PRIO_ORDER.get(r.triage.priority, 9), -r.id))
    needs: dict[str, int] = {}
    for r in recs:
        for n in r.intake.needs + r.intake.medical_needs:
            needs[n] = needs.get(n, 0) + r.intake.group_size
    return {
        "site": config.SITE_ID,
        "mode": f"{config.MODE}/{config.TRIAGE_BACKEND}",
        "people": sum(r.intake.group_size for r in recs),
        "records": [r.to_dict() for r in recs_sorted],
        "needs": dict(sorted(needs.items(), key=lambda kv: -kv[1])),
        "matches": reunite.find_matches([{"id": r.id, "intake": r.intake} for r in recs]),
        "uplink_bytes": sum(len(r.uplink) for r in recs),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "Muster/1"

    def log_message(self, fmt, *args):  # keep the console quiet; the JSONL log is the record
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode(), "application/json")

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("request too large")
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/board":
            self._json(board())
        elif path == "/log":
            self._json(log.recent())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            if path == "/intake":
                text = (json.loads(self._body() or b"{}").get("text") or "").strip()
                if not text:
                    return self._json({"error": "empty report"}, 400)
                with _intake_lock:
                    return self._json(do_intake(text, None))
            if path == "/intake_audio":
                audio = self._body()
                with _intake_lock:
                    return self._json(do_intake(None, audio))
            if path == "/reset":
                db.reset()
                log.write("action", action="reset")
                return self._json({"ok": True})
            self._json({"error": "not found"}, 404)
        except Exception as e:  # errors are data, not crashes
            log.write("error", path=path, error=f"{type(e).__name__}: {e}")
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def main():
    ap = argparse.ArgumentParser(description="Muster offline shelter intake")
    ap.add_argument("--host", default="127.0.0.1", help="keep loopback; reach it via an SSH tunnel")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    log.write("startup", mode=config.MODE, triage=config.TRIAGE_BACKEND, asr=config.ASR_BACKEND,
              llm=config.LLM_MODEL, llm_url=config.LLM_URL, host=a.host, port=a.port)
    print(f"Muster on http://{a.host}:{a.port}  mode={config.MODE} triage={config.TRIAGE_BACKEND} "
          f"asr={config.ASR_BACKEND}  log={config.LOG_PATH}", flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
