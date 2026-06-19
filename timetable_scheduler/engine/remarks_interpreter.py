"""Deterministic interpretation of free-text scheduling remarks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover - imported only for type checkers
    from data.models import Assignment, Course, Room


class RemarkEnforcement(str, Enum):
    """How strongly an interpreted remark should be applied."""

    HARD = "hard"
    SOFT = "soft"
    FALLBACK = "fallback"
    REVIEW = "review"


class RemarkConfidence(str, Enum):
    """Confidence level for a deterministic remark interpretation."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RemarkHandlingStatus(str, Enum):
    """Primary operational outcome for one remarked course."""

    AUTOMATICALLY_APPLIED = "automatically_applied"
    PREFERENCE_CONSIDERED = "preference_considered"
    SCHEDULED_NEEDS_CONFIRMATION = "scheduled_needs_confirmation"
    UNSCHEDULED_DUE_TO_REQUEST = "unscheduled_due_to_request"
    UNSUPPORTED_NON_BLOCKING = "unsupported_non_blocking"
    NO_SCHEDULING_ACTION = "no_scheduling_action"


@dataclass(frozen=True, slots=True)
class RemarkInterpretation:
    """One explainable interpretation from a raw scheduling remark."""

    raw_text: str
    normalised_text: str
    rule_name: str
    parameters: dict[str, object]
    enforcement: RemarkEnforcement
    confidence: RemarkConfidence
    explanation: str


@dataclass(slots=True)
class RemarkRequirements:
    """Structured scheduling requirements derived from a raw remark."""

    required_room_count: int = 1
    required_room_types: tuple[str, ...] = ()
    preferred_room_types: tuple[str, ...] = ()
    allowed_delivery_modes: tuple[str, ...] = ()
    requires_hybrid_delivery: bool = False
    requires_recording_room: bool = False
    fixed_days: tuple[str, ...] = ()
    fixed_start_times: tuple[str, ...] = ()
    fixed_venues: tuple[str, ...] = ()
    duration_override_hours: float | None = None
    same_day_sessions: bool = False
    back_to_back_sessions: bool = False
    concurrent_groups: int | None = None
    must_follow_activity: str | None = None
    minimum_travel_buffer_minutes: int = 0
    interpretations: tuple[RemarkInterpretation, ...] = ()
    needs_manual_review: bool = False
    review_reason: str = ""


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
}

ROOM_TYPE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("computer lab", ("computer", "lab")),
    ("computer room", ("computer",)),
    ("ace room", ("ace",)),
    ("lectorial room", ("lectorial",)),
    ("lecture room", ("lecture", "room")),
    ("seminar room", ("seminar",)),
    ("laboratory", ("lab",)),
    ("exam seating", ("exam",)),
)

DAY_NAMES = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
}

SOFT_WORDS = ("prefer", "preferred", "if possible", "ideally")
HARD_WORDS = ("must", "required", "require", "requires", "need", "needs", "only", "fixed")
UNCERTAIN_WORDS = ("may", "might", "possibly", "can consider", "to be confirmed", "tbc")
SUPPORTED_HARD_RULES = {
    "multiple_room_requirement",
    "concurrent_parallel_groups",
    "hybrid_delivery",
    "recording_capable_room",
    "room_type",
    "fixed_day_time",
}
REPRESENTED_HARD_RULES = {
    "multiple_room_requirement",
    "concurrent_parallel_groups",
    "hybrid_delivery",
    "recording_capable_room",
    "room_type",
    "fixed_day_time",
}


def normalise_remark(raw_text: str | None) -> str:
    """Return a normalised remark while preserving meaning."""
    text = str(raw_text or "").replace("\xa0", " ").casefold()
    for word, value in NUMBER_WORDS.items():
        text = re.sub(rf"\b{word}\b", str(value), text)
    replacements = {
        "face-to-face": "f2f",
        "face to face": "f2f",
        "ftf": "f2f",
        "lec": "lecture",
        "tut": "tutorial",
    }
    for old, new in replacements.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[;|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _interpretation(
    raw: str,
    normalised: str,
    rule_name: str,
    parameters: dict[str, object],
    enforcement: RemarkEnforcement,
    confidence: RemarkConfidence,
    explanation: str,
) -> RemarkInterpretation:
    """Build one interpretation row."""
    return RemarkInterpretation(raw, normalised, rule_name, parameters, enforcement, confidence, explanation)


def _has_soft_word(text: str) -> bool:
    """Return True when the remark uses preference wording."""
    return any(word in text for word in SOFT_WORDS)


def _has_hard_word(text: str) -> bool:
    """Return True when the remark uses explicit requirement wording."""
    return any(word in text for word in HARD_WORDS)


def _has_uncertain_word(text: str) -> bool:
    """Return True when the remark wording is uncertain or pending confirmation."""
    return any(word in text for word in UNCERTAIN_WORDS)


def _is_informational(text: str) -> bool:
    """Return True for remarks that do not request timetable action."""
    patterns = [
        r"\bassessment details? to follow\b",
        r"\bfor programme information\b",
        r"\bpending lecturer confirmation\b",
        r"\btiming to be confirmed\b",
        r"\bto be confirmed\b",
        r"\btbc\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _number(value: str) -> int:
    """Parse a digit or already-normalised number word."""
    return int(value)


def _looks_like_non_room_count(text: str, start: int, end: int) -> bool:
    """Protect against numbers that describe duration, weeks, groups, or sessions."""
    window = text[max(start - 8, 0) : min(end + 18, len(text))]
    return bool(
        re.search(r"\d+\s*x\s*\d+\s*[- ]?hour", window)
        or re.search(r"\d+\s*(?:hours?|hrs?|groups?|sessions?)\b", window)
        or re.search(r"\bweek\s*\d+\b", window)
    )


def _detect_multiple_rooms(raw: str, text: str, req: RemarkRequirements, items: list[RemarkInterpretation]) -> None:
    """Detect explicit multi-room and concurrent-track requests."""
    for match in re.finditer(r"\b(\d+)\s+(?:additional\s+)?(?:ace\s+)?rooms?\b", text):
        if _looks_like_non_room_count(text, match.start(), match.end()):
            continue
        count = _number(match.group(1))
        if count <= 2 and count > req.required_room_count:
            req.required_room_count = count
        if count > 2:
            req.needs_manual_review = True
            req.review_reason = req.review_reason or "More rooms are requested than the output workbook can represent."
        items.append(
            _interpretation(
                raw,
                text,
                "multiple_room_requirement",
                {"required_room_count": count, "explicit": True, "complete": True, "representable": count <= 2},
                RemarkEnforcement.HARD if count <= 2 else RemarkEnforcement.REVIEW,
                RemarkConfidence.HIGH,
                f"Detected an explicit request for {count} rooms.",
            )
        )

    if re.search(r"\badditional rooms?\b", text) and not re.search(r"\b\d+\s+(?:additional\s+)?rooms?\b", text):
        req.needs_manual_review = True
        req.review_reason = req.review_reason or "Additional room request does not state how many rooms are required."
        items.append(
            _interpretation(
                raw,
                text,
                "additional_rooms_unspecified",
                {"explicit": False, "complete": False, "representable": False},
                RemarkEnforcement.REVIEW,
                RemarkConfidence.MEDIUM,
                "Detected additional-room wording, but no exact room count was supplied.",
            )
        )

    parallel = re.search(r"\bsplit into\s+(\d+)\s+parallel\b", text)
    if parallel:
        count = _number(parallel.group(1))
        req.concurrent_groups = count
        if count > 2:
            req.needs_manual_review = True
            req.review_reason = req.review_reason or "More rooms are requested than the output workbook can represent."
        elif count > req.required_room_count:
            req.required_room_count = count
        items.append(
            _interpretation(
                raw,
                text,
                "concurrent_parallel_groups",
                {"concurrent_groups": count, "required_room_count": count, "explicit": True, "complete": True, "representable": count <= 2},
                RemarkEnforcement.HARD if count <= 2 else RemarkEnforcement.REVIEW,
                RemarkConfidence.HIGH,
                f"Detected {count} concurrent parallel groups.",
            )
        )


def _detect_hybrid_delivery(raw: str, text: str, req: RemarkRequirements, items: list[RemarkInterpretation]) -> None:
    """Detect simultaneous physical and virtual delivery requests."""
    if _detect_flexible_delivery(raw, text, req, items):
        return

    hybrid_patterns = [
        r"\bhybrid\b",
        r"\bphysical\s+and\s+online\b",
        r"\bf2f\s+and\s+online\b",
        r"\bphysical\s+and\s+virtual\b",
        r"\bonline access\b",
        r"\boverseas\b.*\bonline\b",
    ]
    if any(re.search(pattern, text) for pattern in hybrid_patterns):
        explicit = _has_hard_word(text) or "simultaneous" in text or "physical and online" in text or "physical and virtual" in text or text.strip() == "hybrid"
        uncertain = _has_soft_word(text) or _has_uncertain_word(text) or "can support" in text or "to support" in text
        if explicit and not uncertain:
            req.requires_hybrid_delivery = True
            req.requires_recording_room = True
            enforcement = RemarkEnforcement.HARD
            confidence = RemarkConfidence.HIGH
            explanation = "Detected explicit simultaneous physical and online delivery wording."
        elif _has_soft_word(text):
            enforcement = RemarkEnforcement.SOFT
            confidence = RemarkConfidence.HIGH
            req.needs_manual_review = True
            req.review_reason = req.review_reason or "Hybrid support is requested as a preference and needs confirmation."
            explanation = "Detected a hybrid-delivery preference; it will not block scheduling."
        else:
            enforcement = RemarkEnforcement.REVIEW
            confidence = RemarkConfidence.MEDIUM
            req.needs_manual_review = True
            req.review_reason = req.review_reason or "Hybrid wording is not explicit enough to enforce automatically."
            explanation = "Detected possible hybrid delivery wording that needs confirmation."
        items.append(
            _interpretation(
                raw,
                text,
                "hybrid_delivery",
                {
                    "requires_hybrid_delivery": explicit and not uncertain,
                    "requires_recording_room": explicit and not uncertain,
                    "explicit": explicit,
                    "complete": explicit and not uncertain,
                    "representable": True,
                    "proxy_note": "Recording capability used as the available dataset proxy for hybrid support.",
                },
                enforcement,
                confidence,
                explanation,
            )
        )
    if re.search(r"\brecording\b|\brecorded\b|\brecord\b", text):
        explicit = _has_hard_word(text)
        if explicit:
            req.requires_recording_room = True
        items.append(
            _interpretation(
                raw,
                text,
                "recording_capable_room",
                {"requires_recording_room": explicit, "explicit": explicit, "complete": explicit, "representable": True},
                RemarkEnforcement.HARD if explicit else RemarkEnforcement.SOFT,
                RemarkConfidence.HIGH,
                "Detected a recording-capable room request.",
            )
        )


def _detect_flexible_delivery(
    raw: str,
    text: str,
    req: RemarkRequirements,
    items: list[RemarkInterpretation],
) -> bool:
    """Detect either physical or online delivery alternatives."""
    patterns = [
        r"\bonline\s+or\s+(?:physical|f2f)\b",
        r"\b(?:physical|f2f)\s+or\s+online\b",
        r"\bvirtual\s+or\s+(?:physical|f2f)\b",
        r"\beither\s+(?:mode|online|physical).*(?:acceptable|ok|okay)\b",
    ]
    if any(re.search(pattern, text) for pattern in patterns):
        req.allowed_delivery_modes = ("f2f", "online")
        items.append(
            _interpretation(
                raw,
                text,
                "flexible_delivery_mode",
                {"allowed_delivery_modes": ["f2f", "online"], "explicit": True, "complete": True, "representable": True},
                RemarkEnforcement.FALLBACK,
                RemarkConfidence.HIGH,
                "Detected wording that allows either online or physical delivery.",
            )
        )
        return True
    return False


def _room_type_name(text: str) -> str | None:
    """Return the first supported room-type phrase in a remark."""
    for name, tokens in ROOM_TYPE_PATTERNS:
        if all(token in text for token in tokens):
            return name
    return None


def _detect_room_type(raw: str, text: str, req: RemarkRequirements, items: list[RemarkInterpretation]) -> None:
    """Detect room-type requirements and preferences."""
    room_type = _room_type_name(text)
    if not room_type:
        return

    if _has_soft_word(text):
        req.preferred_room_types = tuple(dict.fromkeys([*req.preferred_room_types, room_type]))
        enforcement = RemarkEnforcement.SOFT
        parameter_key = "preferred_room_types"
        explanation = f"Detected a soft preference for {room_type}."
    elif _has_hard_word(text):
        req.required_room_types = tuple(dict.fromkeys([*req.required_room_types, room_type]))
        enforcement = RemarkEnforcement.HARD
        parameter_key = "required_room_types"
        explanation = f"Detected a hard requirement for {room_type}."
    else:
        req.needs_manual_review = True
        req.review_reason = req.review_reason or f"Room-type wording for {room_type} is not clearly required or preferred."
        enforcement = RemarkEnforcement.REVIEW
        parameter_key = "room_type_for_review"
        explanation = f"Detected {room_type}, but enforcement was unclear."

    items.append(
        _interpretation(
            raw,
            text,
            "room_type",
            {parameter_key: [room_type]},
            # Keep explicitness visible for hard-rule eligibility checks.
            enforcement,
            RemarkConfidence.HIGH if enforcement != RemarkEnforcement.REVIEW else RemarkConfidence.MEDIUM,
            explanation,
        )
    )
    items[-1].parameters.update({"explicit": enforcement == RemarkEnforcement.HARD, "complete": True, "representable": True})


def _detect_fixed_time(raw: str, text: str, req: RemarkRequirements, items: list[RemarkInterpretation]) -> None:
    """Detect explicit fixed day and start-time requests."""
    days = tuple(day for key, day in DAY_NAMES.items() if re.search(rf"\b{key}\b", text))
    has_day = bool(days)
    times: list[str] = []
    for match in re.finditer(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text):
        if match.group(2) is None and match.group(3) is None:
            continue
        hour = int(match.group(1))
        minute = int(match.group(2) or "00")
        suffix = match.group(3)
        if suffix == "pm" and hour < 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and minute in {0, 30}:
            times.append(f"{hour:02d}:{minute:02d}")

    explicit_request = _has_hard_word(text) or "fixed" in text or "only available" in text
    if _has_soft_word(text) and has_day:
        items.append(
            _interpretation(
                raw,
                text,
                "fixed_day_time",
                {"fixed_days": list(days), "fixed_start_times": [], "explicit": False, "complete": True, "representable": True},
                RemarkEnforcement.SOFT,
                RemarkConfidence.HIGH,
                "Detected a day/time preference; it will not block scheduling.",
            )
        )
        return
    if not explicit_request:
        return
    if days:
        req.fixed_days = tuple(dict.fromkeys([*req.fixed_days, *days]))
    if times:
        req.fixed_start_times = tuple(dict.fromkeys([*req.fixed_start_times, times[0]]))
    if days or times:
        items.append(
            _interpretation(
                raw,
                text,
                "fixed_day_time",
                {"fixed_days": list(days), "fixed_start_times": times[:1], "explicit": True, "complete": bool(days or times), "representable": True},
                RemarkEnforcement.HARD,
                RemarkConfidence.HIGH,
                "Detected fixed day or start-time wording.",
            )
        )


def _detect_duration(raw: str, text: str, req: RemarkRequirements, items: list[RemarkInterpretation]) -> None:
    """Detect a simple duration override without merging repeated sessions."""
    if re.search(r"\b\d+\s*x\s*\d+\s*[- ]?hour", text) or "session" in text:
        return
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:hrs?|hours?)\b", text)
    if not match:
        return
    req.duration_override_hours = float(match.group(1))
    items.append(
        _interpretation(
            raw,
            text,
            "duration_override",
            {"duration_override_hours": req.duration_override_hours, "explicit": _has_hard_word(text), "complete": True, "representable": False},
            RemarkEnforcement.REVIEW,
            RemarkConfidence.MEDIUM,
            "Detected a possible duration override.",
        )
    )
    if not _has_hard_word(text):
        req.needs_manual_review = True
        req.review_reason = req.review_reason or "Duration wording is present but not clearly mandatory."


def _detect_same_day_back_to_back(raw: str, text: str, req: RemarkRequirements, items: list[RemarkInterpretation]) -> None:
    """Detect same-day and back-to-back session requests."""
    if "same day" in text:
        req.same_day_sessions = True
        items.append(
            _interpretation(raw, text, "same_day_sessions", {"same_day_sessions": True}, RemarkEnforcement.HARD, RemarkConfidence.HIGH, "Detected same-day session wording.")
        )
    if "back to back" in text or "right after" in text:
        req.back_to_back_sessions = True
        items.append(
            _interpretation(raw, text, "back_to_back_sessions", {"back_to_back_sessions": True}, RemarkEnforcement.HARD, RemarkConfidence.HIGH, "Detected back-to-back session wording.")
        )


def _detect_sequence(raw: str, text: str, req: RemarkRequirements, items: list[RemarkInterpretation]) -> None:
    """Detect simple activity sequencing requests."""
    match = re.search(r"\b(?:must\s+be\s+after|after)\s+(lecture|laboratory|lab|tutorial|quiz)\b", text)
    if not match:
        return
    activity = "laboratory" if match.group(1) == "lab" else match.group(1)
    req.must_follow_activity = activity
    enforcement = RemarkEnforcement.SOFT if _has_soft_word(text) else RemarkEnforcement.HARD
    items.append(
        _interpretation(
            raw,
            text,
            "activity_sequence",
            {"must_follow_activity": activity, "explicit": enforcement == RemarkEnforcement.HARD, "complete": True, "representable": False},
            enforcement,
            RemarkConfidence.HIGH,
            f"Detected that this activity should occur after {activity}.",
        )
    )


def _detect_travel_buffer(raw: str, text: str, req: RemarkRequirements, items: list[RemarkInterpretation]) -> None:
    """Detect travel-buffer wording and request review unless safely scoped."""
    if "travel" not in text and "buffer" not in text and "external venue" not in text:
        return
    match = re.search(r"\b(\d+)\s*(?:hour|hr|minutes|min)\b", text)
    if match:
        value = int(match.group(1))
        req.minimum_travel_buffer_minutes = value * 60 if "hour" in match.group(0) or "hr" in match.group(0) else value
    req.needs_manual_review = True
    req.review_reason = req.review_reason or "Travel-buffer request needs manual review because the affected activity relationship is not explicit."
    items.append(
        _interpretation(
            raw,
            text,
            "travel_buffer",
            {"minimum_travel_buffer_minutes": req.minimum_travel_buffer_minutes, "explicit": False, "complete": False, "representable": False},
            RemarkEnforcement.REVIEW,
            RemarkConfidence.MEDIUM,
            "Detected travel-buffer wording requiring review.",
        )
    )


def interpret_remarks(raw_text: str | None) -> RemarkRequirements:
    """Interpret one free-text remark into explicit scheduling requirements."""
    raw = str(raw_text or "").strip()
    text = normalise_remark(raw)
    requirements = RemarkRequirements()
    if not text:
        return requirements

    interpretations: list[RemarkInterpretation] = []
    if _is_informational(text):
        requirements.interpretations = (
            _interpretation(
                raw,
                text,
                "unsupported_remark",
                {"informational": True, "explicit": False, "complete": True, "representable": True},
                RemarkEnforcement.REVIEW,
                RemarkConfidence.LOW,
                "Informational remark detected; no timetable action is required.",
            ),
        )
        return requirements

    _detect_multiple_rooms(raw, text, requirements, interpretations)
    _detect_hybrid_delivery(raw, text, requirements, interpretations)
    _detect_room_type(raw, text, requirements, interpretations)
    _detect_fixed_time(raw, text, requirements, interpretations)
    _detect_duration(raw, text, requirements, interpretations)
    _detect_same_day_back_to_back(raw, text, requirements, interpretations)
    _detect_sequence(raw, text, requirements, interpretations)
    _detect_travel_buffer(raw, text, requirements, interpretations)

    if not interpretations:
        requirements.needs_manual_review = True
        requirements.review_reason = "No supported deterministic remark pattern was detected."
        interpretations.append(
            _interpretation(
                raw,
                text,
                "unsupported_remark",
                {},
                RemarkEnforcement.REVIEW,
                RemarkConfidence.LOW,
                "Remark retained for manual review because no supported pattern matched.",
            )
        )

    if any(item.confidence == RemarkConfidence.LOW and item.enforcement == RemarkEnforcement.HARD for item in interpretations):
        requirements.needs_manual_review = True
        requirements.review_reason = requirements.review_reason or "Low-confidence interpretation cannot become a hard rule."

    requirements.interpretations = tuple(interpretations)
    return requirements


def is_hard_enforceable(interpretation: RemarkInterpretation) -> bool:
    """Return True only for explicit supported rules that can be safely enforced."""
    if interpretation.enforcement != RemarkEnforcement.HARD:
        return False
    if interpretation.confidence != RemarkConfidence.HIGH:
        return False
    if interpretation.rule_name not in SUPPORTED_HARD_RULES:
        return False
    if interpretation.rule_name not in REPRESENTED_HARD_RULES:
        return False
    if not bool(interpretation.parameters.get("explicit")):
        return False
    if not bool(interpretation.parameters.get("complete")):
        return False
    if not bool(interpretation.parameters.get("representable")):
        return False
    if bool(interpretation.parameters.get("conflicting")):
        return False
    return True


def hard_enforceable_interpretations(requirements: RemarkRequirements) -> tuple[RemarkInterpretation, ...]:
    """Return all interpretations that may affect hard scheduling feasibility."""
    return tuple(item for item in requirements.interpretations if is_hard_enforceable(item))


def scheduling_requirements(requirements: RemarkRequirements) -> RemarkRequirements:
    """Return only remark requirements the scheduler may enforce as hard rules."""
    filtered = RemarkRequirements(
        preferred_room_types=requirements.preferred_room_types,
        allowed_delivery_modes=requirements.allowed_delivery_modes,
        interpretations=requirements.interpretations,
        needs_manual_review=requirements.needs_manual_review,
        review_reason=requirements.review_reason,
    )
    for interpretation in hard_enforceable_interpretations(requirements):
        if interpretation.rule_name in {"multiple_room_requirement", "concurrent_parallel_groups"}:
            filtered.required_room_count = max(
                filtered.required_room_count,
                int(interpretation.parameters.get("required_room_count", 1)),
            )
        elif interpretation.rule_name == "hybrid_delivery":
            filtered.requires_hybrid_delivery = True
            filtered.requires_recording_room = True
        elif interpretation.rule_name == "recording_capable_room":
            filtered.requires_recording_room = True
        elif interpretation.rule_name == "room_type":
            values = interpretation.parameters.get("required_room_types", [])
            filtered.required_room_types = tuple(dict.fromkeys([*filtered.required_room_types, *[str(value) for value in values]]))
        elif interpretation.rule_name == "fixed_day_time":
            days = [str(value) for value in interpretation.parameters.get("fixed_days", [])]
            times = [str(value) for value in interpretation.parameters.get("fixed_start_times", [])]
            filtered.fixed_days = tuple(dict.fromkeys([*filtered.fixed_days, *days]))
            filtered.fixed_start_times = tuple(dict.fromkeys([*filtered.fixed_start_times, *times]))
    return filtered


def course_scheduling_requirements(course: "Course") -> RemarkRequirements:
    """Return the hard-enforceable scheduling requirements for a course."""
    return scheduling_requirements(course_remark_requirements(course))


def effective_remark_requirements(course: "Course", *, enabled: bool) -> RemarkRequirements:
    """Return scheduling-effective remark requirements for a feature-flag state."""
    if not enabled:
        return RemarkRequirements()
    return course_scheduling_requirements(course)


def has_hard_enforceable_remark(course: "Course") -> bool:
    """Return True when a course has at least one hard-enforceable remark."""
    return bool(hard_enforceable_interpretations(course_remark_requirements(course)))


def remark_unscheduled_reason(course: "Course") -> str:
    """Return a specific reason when explicit remark rules block scheduling."""
    requirements = course_scheduling_requirements(course)
    if requirements.required_room_count > 1:
        return "Explicit two-room requirement could not be satisfied simultaneously."
    if requirements.requires_hybrid_delivery:
        return "Explicit hybrid-capable room requirement could not be satisfied."
    if requirements.requires_recording_room:
        return "Explicit recording-capable room requirement could not be satisfied."
    if requirements.required_room_types:
        return f"Explicit required room type could not be satisfied: {', '.join(requirements.required_room_types)}."
    if requirements.fixed_days or requirements.fixed_start_times:
        parts = []
        if requirements.fixed_days:
            parts.append(f"day {', '.join(requirements.fixed_days)}")
        if requirements.fixed_start_times:
            parts.append(f"start {', '.join(requirements.fixed_start_times)}")
        return f"Explicit fixed {' and '.join(parts)} request could not be satisfied."
    return ""


def course_remark_requirements(course: "Course") -> RemarkRequirements:
    """Return cached remark requirements for a course when present."""
    cached = getattr(course, "remark_requirements", None)
    if isinstance(cached, RemarkRequirements):
        return cached
    return interpret_remarks(getattr(course, "remarks", ""))


def room_matches_type(room: "Room", room_type: str) -> bool:
    """Return True when a room appears to satisfy a supported room-type phrase."""
    text = f"{room.room_id} {room.room_type} {room.resource_type}".casefold()
    lookup = dict(ROOM_TYPE_PATTERNS)
    tokens = lookup.get(room_type, (room_type,))
    return all(token in text for token in tokens)


def room_supports_recording(room: "Room") -> bool:
    """Return True when venue metadata indicates recording or hybrid support."""
    text = f"{room.recording} {room.resource_type} {room.room_id}".casefold()
    return any(token in text for token in ("yes", "record", "hybrid", "online"))


def assignment_rooms(assignment: "Assignment") -> tuple["Room", ...]:
    """Return all rooms attached to an assignment."""
    if hasattr(assignment, "all_rooms"):
        return assignment.all_rooms
    return (assignment.room,) if assignment.room is not None else ()


def assignment_room_ids(assignment: "Assignment") -> str:
    """Return a display string for assigned rooms."""
    return ", ".join(room.room_id for room in assignment_rooms(assignment))


def assignment_satisfies_interpretation(assignment: "Assignment", interpretation: RemarkInterpretation) -> bool:
    """Return True when a final assignment satisfies one interpreted rule."""
    if assignment.room is None or assignment.timeslot is None:
        return False
    rooms = assignment_rooms(assignment)
    req = course_remark_requirements(assignment.course)
    if interpretation.rule_name in {"multiple_room_requirement", "concurrent_parallel_groups"}:
        return len(rooms) >= int(interpretation.parameters.get("required_room_count", req.required_room_count))
    if interpretation.rule_name == "hybrid_delivery":
        return bool(rooms) and rooms[0].room_type == "physical" and room_supports_recording(rooms[0])
    if interpretation.rule_name == "recording_capable_room":
        return bool(rooms) and room_supports_recording(rooms[0])
    if interpretation.rule_name == "flexible_delivery_mode":
        return bool(getattr(assignment, "selected_delivery_mode", None))
    if interpretation.rule_name == "room_type":
        target_types = req.required_room_types or req.preferred_room_types
        return bool(target_types) and all(any(room_matches_type(room, room_type) for room in rooms) for room_type in target_types)
    if interpretation.rule_name == "fixed_day_time":
        fixed_days = tuple(str(value) for value in interpretation.parameters.get("fixed_days", req.fixed_days))
        fixed_start_times = tuple(str(value) for value in interpretation.parameters.get("fixed_start_times", req.fixed_start_times))
        if not fixed_days and not fixed_start_times:
            return False
        day_ok = not fixed_days or assignment.timeslot.day in fixed_days
        time_ok = not fixed_start_times or assignment.timeslot.start_time in fixed_start_times
        return day_ok and time_ok
    if interpretation.enforcement == RemarkEnforcement.REVIEW:
        return False
    return not assignment.hard_violations


def _category_for_interpretation(interpretation: RemarkInterpretation) -> str:
    """Return an audit category name for an interpretation."""
    mapping = {
        "multiple_room_requirement": "Multiple-room requirement",
        "concurrent_parallel_groups": "Concurrent or parallel groups",
        "hybrid_delivery": "Hybrid physical and virtual delivery",
        "flexible_delivery_mode": "Flexible physical or online delivery",
        "fixed_day_time": "Fixed day or time",
        "room_type": "Room-type requirement",
        "recording_capable_room": "Recording or hybrid-capable room",
        "duration_override": "Duration override",
        "additional_rooms_unspecified": "Multiple-room requirement",
        "back_to_back_sessions": "Back-to-back sessions",
        "same_day_sessions": "Same-day sessions",
        "activity_sequence": "Activity sequencing",
        "travel_buffer": "Travel-time buffer",
    }
    if interpretation.rule_name == "room_type" and interpretation.enforcement == RemarkEnforcement.SOFT:
        return "Room-type preference"
    if interpretation.enforcement == RemarkEnforcement.REVIEW:
        return "Unclear or unsupported"
    return mapping.get(interpretation.rule_name, "Unclear or unsupported")


def remarks_audit_rows(courses: list["Course"]) -> list[dict[str, object]]:
    """Return workbook-audit rows for all non-empty course remarks."""
    rows: list[dict[str, object]] = []
    for course in courses:
        raw = getattr(course, "remarks", "")
        if not str(raw or "").strip():
            continue
        requirements = course_remark_requirements(course)
        for interpretation in requirements.interpretations:
            rows.append(
                {
                    "source workbook": getattr(course, "source_file", ""),
                    "source sheet": getattr(course, "source_sheet", ""),
                    "source row": getattr(course, "source_row", ""),
                    "programme/year": course.prog_yr,
                    "module": course.module_code,
                    "activity": course.activity,
                    "raw remark": interpretation.raw_text,
                    "normalised remark": interpretation.normalised_text,
                    "detected pattern": _category_for_interpretation(interpretation),
                    "proposed rule type": interpretation.enforcement.value,
                    "confidence": interpretation.confidence.value,
                    "supported or unsupported": "unsupported" if interpretation.enforcement == RemarkEnforcement.REVIEW else "supported",
                    "rule name": interpretation.rule_name,
                    "parameters": str(interpretation.parameters),
                    "explanation": interpretation.explanation,
                    "review reason": requirements.review_reason,
                }
            )
    return rows


def export_remarks_audit(courses: list["Course"], output_path: Path) -> None:
    """Export deterministic remark interpretations for development audit."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = remarks_audit_rows(courses)
    if not rows:
        rows = [
            {
                "source workbook": "",
                "source sheet": "",
                "source row": "",
                "programme/year": "",
                "module": "",
                "activity": "",
                "raw remark": "",
                "normalised remark": "",
                "detected pattern": "No remarks found",
                "proposed rule type": "",
                "confidence": "",
                "supported or unsupported": "",
                "rule name": "",
                "parameters": "",
                "explanation": "",
                "review reason": "",
            }
        ]
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Remarks Audit", index=False)
        summary = (
            pd.DataFrame(rows)
            .groupby(["detected pattern", "supported or unsupported"], dropna=False)
            .size()
            .reset_index(name="count")
        )
        summary.to_excel(writer, sheet_name="Category Summary", index=False)
