"""Records as plain dataclasses (standard library only, so nothing to pip install on the board).

`Intake.from_dict` is also the validator for model output: it coerces types, drops unknown
keys and fills defaults, so a slightly-off JSON answer from a small model still yields a
well-formed record (AGENTS.md rule 4: code validates, not model prose).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

PRIORITIES = ("RED", "ORANGE", "YELLOW", "GREEN")


def _int(v) -> Optional[int]:
    try:
        return int(v) if v is not None and str(v).strip() != "" else None
    except (TypeError, ValueError):
        return None


def _strs(v) -> list[str]:
    if isinstance(v, str):
        v = [v]
    return [str(x).strip() for x in (v or []) if str(x).strip()]


@dataclass
class Person:
    name: str
    age: Optional[int] = None
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, d) -> Optional["Person"]:
        if isinstance(d, str):
            d = {"name": d}
        if not isinstance(d, dict) or not str(d.get("name") or "").strip():
            return None
        return cls(name=str(d["name"]).strip(), age=_int(d.get("age")),
                   description=(str(d["description"]) if d.get("description") else None))


def _people(v) -> list[Person]:
    return [p for p in (Person.from_dict(x) for x in (v or [])) if p]


@dataclass
class Intake:
    """What the text model must fill in from one spoken report."""
    speaker_name: Optional[str] = None
    language: str = "en"                                        # ISO 639-1 of what they spoke
    group_size: int = 1                                         # people arriving with the speaker
    people_present: list[Person] = field(default_factory=list)  # everyone physically here
    injuries: list[str] = field(default_factory=list)
    medical_needs: list[str] = field(default_factory=list)      # insulin, dialysis, oxygen...
    missing: list[Person] = field(default_factory=list)         # people they are LOOKING FOR
    found: list[Person] = field(default_factory=list)           # unaccompanied people they brought in
    needs: list[str] = field(default_factory=list)              # water, food, blanket, charger...
    summary_en: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Intake":
        if not isinstance(d, dict):
            raise ValueError("model output is not a JSON object")
        lang = str(d.get("language") or "en").strip().lower()[:2] or "en"
        return cls(
            speaker_name=(str(d["speaker_name"]).strip() if d.get("speaker_name") else None),
            language=lang,
            group_size=max(1, _int(d.get("group_size")) or 1),
            people_present=_people(d.get("people_present")),
            injuries=[s.lower() for s in _strs(d.get("injuries"))],
            medical_needs=[s.lower() for s in _strs(d.get("medical_needs"))],
            missing=_people(d.get("missing")),
            found=_people(d.get("found")),
            needs=[s.lower() for s in _strs(d.get("needs"))],
            summary_en=str(d.get("summary_en") or ""),
        )


@dataclass
class Triage:
    priority: str
    life_threat: float
    time_critical_meds: float
    vulnerable: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class Record:
    id: int
    ts: str
    transcript: str
    intake: Intake
    triage: Triage
    reply: str        # spoken back to the person, in their language
    uplink: str       # compact line sent over radio

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Record":
        return cls(id=d["id"], ts=d["ts"], transcript=d["transcript"], intake=Intake.from_dict(d["intake"]),
                   triage=Triage(**d["triage"]), reply=d["reply"], uplink=d["uplink"])


INTAKE_EXAMPLE = {
    "speaker_name": "string or null",
    "language": "es",
    "group_size": 1,
    "people_present": [{"name": "string", "age": 0}],
    "injuries": ["string"],
    "medical_needs": ["insulin"],
    "missing": [{"name": "string", "age": 0}],
    "found": [{"name": "string", "age": 0}],
    "needs": ["water"],
    "summary_en": "one short English sentence",
}
