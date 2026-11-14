"""Squash a record into one short ASCII line that fits a LoRa packet / SMS (<=160 bytes).

Example:  S07|014|O|MED:insulin|MISS:Luis/8|N:water
Regional command gets the situation from every shelter without internet.
For the demo, `python -m muster.receiver` on a second laptop plays 'regional command'.
"""
from . import config
from .schema import Intake, Triage

MAX_BYTES = 160


def encode(rec_id: int, intake: Intake, tri: Triage) -> str:
    parts = [config.SITE_ID, f"{rec_id:03d}", tri.priority[0], f"G{intake.group_size}"]
    if intake.medical_needs:
        parts.append("MED:" + ",".join(m[:8] for m in intake.medical_needs))
    if intake.injuries:
        parts.append("INJ:" + ",".join(i[:8] for i in intake.injuries))
    if intake.missing:
        parts.append("MISS:" + ",".join(f"{p.name}/{p.age or '?'}" for p in intake.missing))
    if intake.found:
        parts.append("FND:" + ",".join(f"{p.name}/{p.age or '?'}" for p in intake.found))
    if intake.needs:
        parts.append("N:" + ",".join(n[:6] for n in intake.needs))
    line = "|".join(parts)
    return line.encode("ascii", "ignore")[:MAX_BYTES].decode()


def send(line: str) -> None:
    """Stand-in for a radio: fire the line over UDP to a second laptop on a local
    network (no internet). Set MUSTER_UPLINK=192.168.x.x:9999. Swap for a LoRa/serial
    write if you get a radio module."""
    import os, socket
    target = os.getenv("MUSTER_UPLINK")
    if not target:
        return
    host, port = target.rsplit(":", 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(line.encode("ascii"), (host, int(port)))
