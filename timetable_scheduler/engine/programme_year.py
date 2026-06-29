"""Canonical programme-year identity helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re


UNKNOWN_PROGRAMME_YEAR_MARKERS = {"", "ALL YEARS", "ALL YEAR", "COMMON", "MIXED", "TBC", "TBD", "N/A", "NA"}
SAFE_PROGRAMME_YEAR_DESCRIPTORS = {"ALL", "AEROSPACE", "CBWL", "DESIGN", "MECHATRONICS"}
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
    if _has_other_programme_tokens(before, programme) or _has_other_programme_tokens(after, programme):
        return ProgrammeYearIdentity(raw, "", "mixed-programme-label", "ambiguous")
    return ProgrammeYearIdentity(raw, f"{programme}/Y{year}", "single-programme-year", "confident")


def canonical_programme_year(value: object) -> str:
    """Return countable canonical programme-year, or blank when ambiguous."""
    return identify_programme_year(value).canonical


def canonical_programme_year_from_source(value: object, source_file: object = "") -> str:
    """Return canonical programme-year using source-file year evidence when safe."""
    canonical = canonical_programme_year(value)
    if canonical:
        return canonical

    text = clean_programme_year_text(value)
    match = re.fullmatch(r"(?P<programme>[A-Z][A-Z0-9]*)\s*/\s*20[0-9]{2}", text)
    if not match:
        return ""

    programme = match.group("programme")
    source_text = clean_programme_year_text(source_file).replace("_", " ")
    year_match = re.search(r"\bYEAR\s*(?P<year>[1-9])\b", source_text)
    if not year_match or programme not in source_text:
        return ""
    return f"{programme}/Y{year_match.group('year')}"


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


def programme_year_report_value_from_source(value: object, source_file: object = "") -> str:
    """Return report identity with source-file year evidence where available."""
    canonical = canonical_programme_year_from_source(value, source_file)
    if canonical:
        return canonical
    text = clean_programme_year_text(value)
    return f"UNRESOLVED:{text}" if text else "UNRESOLVED"


def _has_other_programme_tokens(text: str, programme: str = "") -> bool:
    """Return True when nearby text contains another programme-like token."""
    if not text:
        return False
    leftovers = re.sub(r"\b(?:P|PART|GROUP)\s*[0-9]+\b", "", text)
    leftovers = re.sub(r"[-–—_/,+()]", " ", leftovers)
    leftovers = leftovers.strip(" /-,+")
    tokens = re.findall(r"[A-Z][A-Z0-9]*", leftovers)
    return any(token not in {programme, *SAFE_PROGRAMME_YEAR_DESCRIPTORS} for token in tokens)
