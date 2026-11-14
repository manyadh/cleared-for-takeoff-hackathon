"""Family reunification: match someone's 'missing' list against everyone registered.

Deliberately simple and explainable: fuzzy first-name match + age within 3 years.
Spoken names get misheard ("Luis" / "Louis" / "Luiz"), so fuzzy matters.
"""
from difflib import SequenceMatcher
import unicodedata

from .schema import Person


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
    return s.split()[0] if s else s


def name_score(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def is_match(wanted: Person, candidate: Person) -> float:
    s = name_score(wanted.name, candidate.name)
    if s < 0.75:
        return 0.0
    if wanted.age is not None and candidate.age is not None and abs(wanted.age - candidate.age) > 3:
        return 0.0
    return round(s, 2)


def find_matches(records: list[dict]) -> list[dict]:
    """records: [{'id', 'intake': Intake}] -> list of {missing_in, found_in, name, score}."""
    here = [(r["id"], p) for r in records for p in r["intake"].people_present + r["intake"].found]
    out, seen = [], set()
    for r in records:
        for wanted in r["intake"].missing:
            for rid, cand in here:
                if rid == r["id"]:
                    continue
                score = is_match(wanted, cand)
                key = (r["id"], rid, _norm(wanted.name))
                if score and key not in seen:
                    seen.add(key)
                    out.append({"missing_in": r["id"], "found_in": rid,
                                "name": cand.name, "age": cand.age, "score": score})
    return out
