"""Canonical programme-year identity helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re


UNKNOWN_PROGRAMME_YEAR_MARKERS = {"", "ALL YEARS", "ALL YEAR", "COMMON", "MIXED", "TBC", "TBD", "N/A", "NA"}
PROGRAMME_YEAR_PATTERN = re.compile(
    r"(?P<programme>[A-Z][A-Z0-9]*)\s*(?:/|-|\s+)?\s*(?:YEAR|YR|Y)?\s*(?P<year>[1-9])\b"
)


@dataclass(frozen=True, slots=True)
class ProgrammeYearIdentity:
    """Result of programme-year identity normalisation."""

    raw_value: str
    canonical: str
    rule: str
    status: str

    @property
    def is_confident(self) -> bool:
        """Return True when the value is a countable programme-year."""
        return self.status == "confident" and bool(self.canonical)


def clean_programme_year_text(value: object) -> str:
    """Return a compact uppercase string for traceable matching."""
    text = re.sub(r"\s+", " ", str(value or "").strip().upper())
    text = text.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    return text


def identify_programme_year(value: object) -> ProgrammeYearIdentity:
    """Return canonical <PROGRAMME>/Y<number> identity when unambiguous."""
    raw = str(value or "")
    text = clean_programme_year_text(raw)
    if text in UNKNOWN_PROGRAMME_YEAR_MARKERS:
        return ProgrammeYearIdentity(raw, "", "unknown-marker", "unknown")
    if re.fullmatch(r"P\s*[0-9]+", text):
        return ProgrammeYearIdentity(raw, "", "subgroup-only", "ambiguous")
    if re.search(r"\b(?:YEAR|YR|Y)?\s*[1-9]\s*/\s*(?:YEAR|YR|Y)?\s*[1-9]\b", text):
        return ProgrammeYearIdentity(raw, "", "year-range", "ambiguous")

    matches = list(PROGRAMME_YEAR_PATTERN.finditer(text))
    matches = [match for match in matches if match.group("programme") not in {"P", "PART", "GROUP"}]
    if len(matches) != 1:
        return ProgrammeYearIdentity(raw, "", "no-single-programme-year", "ambiguous" if matches else "unknown")

    match = matches[0]
    programme = match.group("programme")
    year = match.group("year")
    before = text[: match.start()].strip(" /-,")
    after = text[match.end() :].strip(" /-,")
    if _has_other_programme_tokens(before) or _has_other_programme_tokens(after):
        return ProgrammeYearIdentity(raw, "", "mixed-programme-label", "ambiguous")
    return ProgrammeYearIdentity(raw, f"{programme}/Y{year}", "single-programme-year", "confident")


def canonical_programme_year(value: object) -> str:
    """Return countable canonical programme-year, or blank when ambiguous."""
    return identify_programme_year(value).canonical


def normalise_programme_year(value: object) -> str:
    """Return legacy-compatible normalised text for broad matching."""
    text = clean_programme_year_text(value).replace("YEAR", "Y").replace("YR", "Y")
    text = text.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    text = re.sub(r"\bY\s*([0-9])\b", r"Y\1", text)
    return text


def programme_year_report_value(value: object) -> str:
    """Return canonical value or traceable unresolved identity for reports."""
    identity = identify_programme_year(value)
    if identity.canonical:
        return identity.canonical
    text = clean_programme_year_text(value)
    return f"UNRESOLVED:{text}" if text else "UNRESOLVED"


def _has_other_programme_tokens(text: str) -> bool:
    """Return True when nearby text contains another programme-like token."""
    if not text:
        return False
    leftovers = re.sub(r"\b(?:P|PART|GROUP)\s*[0-9]+\b", "", text)
    leftovers = leftovers.strip(" /-,+")
    return bool(re.search(r"[A-Z][A-Z0-9]+", leftovers))
