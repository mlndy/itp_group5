"""Deterministic interpretation of free-text scheduling remarks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime
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
    fixed_end_times: tuple[str, ...] = ()
    fixed_time_ranges: tuple[tuple[str, str], ...] = ()
    explicit_dates: tuple[str, ...] = ()
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
MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
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


def _detected_weekdays(text: str) -> tuple[str, ...]:
    """Return weekdays named in a remark, including plural forms."""
    days = [day for key, day in DAY_NAMES.items() if re.search(rf"\b{key}s?\b", text)]
    return tuple(dict.fromkeys(days))


def _explicit_date_info(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return explicit date labels and computed weekdays where possible."""
    month_pattern = "|".join(sorted((re.escape(key) for key in MONTH_NAMES), key=len, reverse=True))
    dates: list[str] = []
    days: list[str] = []
    for match in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})\.?(?:\s+(\d{{4}}))?\b", text):
        day_text, month_text, year_text = match.groups()
        month_number = MONTH_NAMES[month_text.rstrip(".")]
        label = f"{int(day_text)} {month_text.title()}"
        if year_text:
            label = f"{label} {year_text}"
            try:
                days.append(datetime(int(year_text), month_number, int(day_text)).strftime("%A"))
            except ValueError:
                pass
        dates.append(label)
    return tuple(dict.fromkeys(dates)), tuple(dict.fromkeys(days))


def _clock_minutes(hour: int, minute: int, suffix: str | None) -> int | None:
    """Return minutes after midnight for a parsed clock token."""
    if minute < 0 or minute > 59 or hour < 0:
        return None
    if suffix == "pm" and hour < 12:
        hour += 12
    elif suffix == "am" and hour == 12:
        hour = 0
    elif suffix is None and hour > 23:
        return None
    if hour > 23:
        return None
    return hour * 60 + minute


def _format_minutes(minutes: int) -> str:
    """Return HH:MM for minutes after midnight."""
    hour, minute = divmod(minutes, 60)
    return f"{hour:02d}:{minute:02d}"


def _time_range_duration(start_time: str, end_time: str) -> float:
    """Return duration in hours for a parsed time range."""
    start_hour, start_minute = [int(part) for part in start_time.split(":", 1)]
    end_hour, end_minute = [int(part) for part in end_time.split(":", 1)]
    return ((end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)) / 60


def _best_time_range(
    start_hour: int,
    start_minute: int,
    start_suffix: str | None,
    end_hour: int,
    end_minute: int,
    end_suffix: str | None,
) -> tuple[str, str] | None:
    """Infer a sensible same-day time range from partially suffixed text."""
    start_suffixes = [start_suffix]
    if start_suffix is None and end_suffix is not None:
        start_suffixes.append(end_suffix)
    end_suffixes = [end_suffix]
    if end_suffix is None and start_suffix is not None:
        end_suffixes.append(start_suffix)
        if start_suffix == "am":
            end_suffixes.append("pm")
    candidates: list[tuple[int, int]] = []
    for candidate_start_suffix in dict.fromkeys(start_suffixes):
        for candidate_end_suffix in dict.fromkeys(end_suffixes):
            start = _clock_minutes(start_hour, start_minute, candidate_start_suffix)
            end = _clock_minutes(end_hour, end_minute, candidate_end_suffix)
            if start is None or end is None:
                continue
            if 0 < end - start <= 12 * 60:
                candidates.append((start, end))
    if not candidates:
        return None
    start, end = min(candidates, key=lambda item: (item[1] - item[0], item[0]))
    return _format_minutes(start), _format_minutes(end)


def _parse_time_ranges(text: str) -> list[tuple[str, str, tuple[int, int]]]:
    """Return explicit time ranges and their source spans."""
    token = r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?"
    ranges: list[tuple[str, str, tuple[int, int]]] = []
    for match in re.finditer(rf"\b{token}\s*(?:-|–|—|\bto\b)\s*{token}\b", text):
        start_hour, start_minute, start_suffix, end_hour, end_minute, end_suffix = match.groups()
        if start_suffix is None and end_suffix is None:
            continue
        parsed = _best_time_range(
            int(start_hour),
            int(start_minute or "0"),
            start_suffix,
            int(end_hour),
            int(end_minute or "0"),
            end_suffix,
        )
        if parsed is not None:
            ranges.append((*parsed, match.span()))
    return ranges


def _parse_single_times(text: str, range_spans: list[tuple[int, int]]) -> list[str]:
    """Return explicit single clock times outside already parsed ranges."""
    times: list[str] = []
    for match in re.finditer(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b", text):
        if any(start <= match.start() < end for start, end in range_spans):
            continue
        hour_text, minute_text, suffix = match.groups()
        if suffix is None and minute_text is None:
            continue
        minutes = _clock_minutes(int(hour_text), int(minute_text or "0"), suffix)
        if minutes is not None:
            times.append(_format_minutes(minutes))
    return times


def _detect_fixed_time(raw: str, text: str, req: RemarkRequirements, items: list[RemarkInterpretation]) -> None:
    """Detect explicit fixed day, date and time-range requests."""
    explicit_dates, date_days = _explicit_date_info(text)
    days = tuple(dict.fromkeys([*_detected_weekdays(text), *date_days]))
    time_ranges = _parse_time_ranges(text)
    range_spans = [span for _, _, span in time_ranges]
    single_times = _parse_single_times(text, range_spans)
    starts = [start for start, _, _ in time_ranges] + single_times
    ends = [end for _, end, _ in time_ranges]

    if _has_soft_word(text) and (days or starts or explicit_dates):
        items.append(
            _interpretation(
                raw,
                text,
                "fixed_day_time",
                {
                    "fixed_days": list(days),
                    "fixed_start_times": starts,
                    "fixed_end_times": ends,
                    "explicit_dates": list(explicit_dates),
                    "explicit": False,
                    "complete": True,
                    "representable": True,
                },
                RemarkEnforcement.SOFT,
                RemarkConfidence.HIGH,
                "Detected a day/time preference; it will not block scheduling.",
            )
        )
        return

    explicit_request = (
        _has_hard_word(text)
        or bool(time_ranges)
        or bool(single_times and (days or explicit_dates))
        or "only available" in text
    )
    if not explicit_request or not (days or starts or explicit_dates):
        return
    if days:
        req.fixed_days = tuple(dict.fromkeys([*req.fixed_days, *days]))
    if starts:
        req.fixed_start_times = tuple(dict.fromkeys([*req.fixed_start_times, *starts]))
    if ends:
        req.fixed_end_times = tuple(dict.fromkeys([*req.fixed_end_times, *ends]))
    if time_ranges:
        req.fixed_time_ranges = tuple(
            dict.fromkeys([*req.fixed_time_ranges, *[(start, end) for start, end, _ in time_ranges]])
        )
        durations = {_time_range_duration(start, end) for start, end, _ in time_ranges}
        if len(durations) == 1:
            req.duration_override_hours = durations.pop()
        if len(time_ranges) > 1:
            req.needs_manual_review = True
            req.review_reason = req.review_reason or "Multiple explicit time ranges were parsed; confirm any group-specific split before submission."
    if explicit_dates:
        req.explicit_dates = tuple(dict.fromkeys([*req.explicit_dates, *explicit_dates]))

    items.append(
        _interpretation(
            raw,
            text,
            "fixed_day_time",
            {
                "fixed_days": list(days),
                "fixed_start_times": starts,
                "fixed_end_times": ends,
                "fixed_time_ranges": [(start, end) for start, end, _ in time_ranges],
                "duration_override_hours": req.duration_override_hours,
                "explicit_dates": list(explicit_dates),
                "explicit": True,
                "complete": bool(days or starts or explicit_dates),
                "representable": True,
            },
            RemarkEnforcement.HARD,
            RemarkConfidence.HIGH,
            "Detected explicit fixed date, day or time-range wording.",
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
            ends = [str(value) for value in interpretation.parameters.get("fixed_end_times", [])]
            ranges = [
                (str(value[0]), str(value[1]))
                for value in interpretation.parameters.get("fixed_time_ranges", [])
                if isinstance(value, (list, tuple)) and len(value) == 2
            ]
            dates = [str(value) for value in interpretation.parameters.get("explicit_dates", [])]
            filtered.fixed_days = tuple(dict.fromkeys([*filtered.fixed_days, *days]))
            filtered.fixed_start_times = tuple(dict.fromkeys([*filtered.fixed_start_times, *times]))
            filtered.fixed_end_times = tuple(dict.fromkeys([*filtered.fixed_end_times, *ends]))
            filtered.fixed_time_ranges = tuple(dict.fromkeys([*filtered.fixed_time_ranges, *ranges]))
            duration = interpretation.parameters.get("duration_override_hours")
            if duration is not None:
                filtered.duration_override_hours = float(duration)
            filtered.explicit_dates = tuple(dict.fromkeys([*filtered.explicit_dates, *dates]))
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
    if requirements.fixed_days or requirements.fixed_start_times or requirements.fixed_end_times:
        parts = []
        if requirements.fixed_days:
            parts.append(f"day {', '.join(requirements.fixed_days)}")
        if requirements.fixed_start_times:
            parts.append(f"start {', '.join(requirements.fixed_start_times)}")
        if requirements.fixed_end_times:
            parts.append(f"end {', '.join(requirements.fixed_end_times)}")
        return f"Explicit fixed {' and '.join(parts)} request could not be satisfied."
    if requirements.duration_override_hours is not None:
        return f"Explicit duration {requirements.duration_override_hours:g} hour(s) could not be satisfied."
    return ""


def _duration_conflict_reason(course: "Course", requirements: RemarkRequirements) -> str:
    """Return a review reason for fixed-session duration conflicts."""
    expected = requirements.duration_override_hours
    if expected is None:
        return ""
    if abs(float(course.duration_hrs) - expected) <= 0.01:
        return ""
    if not (getattr(course, "is_fixed_requirement", False) or getattr(course, "fixed_source", None)):
        return ""
    starts = ", ".join(requirements.fixed_start_times) or "explicit start"
    ends = ", ".join(requirements.fixed_end_times) or "explicit end"
    return (
        f"Explicit remark requests {starts}-{ends} ({expected:g} hour(s)), "
        f"but the authoritative structured duration is {float(course.duration_hrs):g} hour(s)."
    )


def _requirements_with_course_context(course: "Course", requirements: RemarkRequirements) -> RemarkRequirements:
    """Apply course-level evidence unavailable during raw remark parsing."""
    reason = _duration_conflict_reason(course, requirements)
    if not reason:
        return requirements
    requirements.needs_manual_review = True
    requirements.review_reason = requirements.review_reason or reason
    for interpretation in requirements.interpretations:
        if interpretation.rule_name == "fixed_day_time" and interpretation.parameters.get("duration_override_hours") is not None:
            interpretation.parameters["conflicting"] = True
            interpretation.parameters["duration_conflict"] = reason
            interpretation.parameters["instruction_treatment"] = "CONFLICT_REQUIRES_REVIEW"
    return requirements


def course_remark_requirements(course: "Course") -> RemarkRequirements:
    """Return cached remark requirements for a course when present."""
    cached = getattr(course, "remark_requirements", None)
    if isinstance(cached, RemarkRequirements):
        return _requirements_with_course_context(course, cached)
    return _requirements_with_course_context(course, interpret_remarks(getattr(course, "remarks", "")))


def course_with_effective_remark_duration(course: "Course", *, enabled: bool = True) -> "Course":
    """Return a course copy using an explicit safe remark duration."""
    if not enabled or getattr(course, "is_fixed_requirement", False) or getattr(course, "fixed_source", None):
        return course
    requirements = course_scheduling_requirements(course)
    expected = requirements.duration_override_hours
    if expected is None or abs(float(course.duration_hrs) - expected) <= 0.01:
        return course
    return replace(course, duration_hrs=float(expected))


def courses_with_effective_remark_durations(courses: list["Course"], *, enabled: bool = True) -> list["Course"]:
    """Return courses with enforceable explicit duration ranges applied."""
    return [course_with_effective_remark_duration(course, enabled=enabled) for course in courses]


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


def _assignment_end_time(assignment: "Assignment") -> str:
    """Return an assignment end time without importing the constraint checker."""
    if assignment.timeslot is None:
        return ""
    start_hour, start_minute = [int(part) for part in assignment.timeslot.start_time.split(":", 1)]
    end_minutes = start_hour * 60 + start_minute + int(round(float(assignment.course.duration_hrs) * 60))
    return _format_minutes(end_minutes)


def _normalise_module_for_match(value: str) -> str:
    """Return a conservative module key for fixed-override evidence."""
    text = str(value or "").strip().upper()
    match = re.match(r"([A-Z]{2,4}\d{4}[A-Z]?)", text)
    return match.group(1) if match else text


def _normalise_programme_for_match(value: str) -> str:
    """Return a compact programme/year key for fixed-override evidence."""
    text = re.sub(r"\s+", " ", str(value or "").upper().replace("YEAR", "Y").replace("YR", "Y")).strip()
    text = text.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    return re.sub(r"\bY\s*([0-9])\b", r"Y\1", text)


def _fixed_assignment_matches_course(course: "Course", assignment: "Assignment") -> bool:
    """Return True when a fixed assignment plausibly anchors a remarked course."""
    if not getattr(assignment, "is_fixed", False) or assignment.timeslot is None:
        return False
    if _normalise_module_for_match(course.module_code) != _normalise_module_for_match(assignment.course.module_code):
        return False
    course_programme = _normalise_programme_for_match(course.prog_yr)
    fixed_programme = _normalise_programme_for_match(assignment.course.prog_yr)
    if course_programme not in fixed_programme and fixed_programme not in course_programme:
        return False
    if assignment.timeslot.week not in set(course.teaching_weeks):
        return False
    return True


def _requested_placement_text(interpretation: RemarkInterpretation) -> str:
    """Return the requested day/date/time placement in one audit string."""
    days = [str(value) for value in interpretation.parameters.get("fixed_days", [])]
    starts = [str(value) for value in interpretation.parameters.get("fixed_start_times", [])]
    ends = [str(value) for value in interpretation.parameters.get("fixed_end_times", [])]
    ranges = [
        f"{value[0]}-{value[1]}"
        for value in interpretation.parameters.get("fixed_time_ranges", [])
        if isinstance(value, (list, tuple)) and len(value) == 2
    ]
    dates = [str(value) for value in interpretation.parameters.get("explicit_dates", [])]
    parts = []
    if dates:
        parts.append(f"date {', '.join(dates)}")
    if days:
        parts.append(f"day {', '.join(days)}")
    if ranges:
        parts.append(f"time range {', '.join(ranges)}")
    elif starts:
        time_text = ", ".join(starts)
        if ends:
            time_text = f"{time_text}-{', '.join(ends)}"
        parts.append(f"time {time_text}")
    return "; ".join(parts)


def _assignment_placement_text(assignment: "Assignment") -> str:
    """Return the final fixed placement in one audit string."""
    if assignment.timeslot is None:
        return ""
    return (
        f"{assignment.timeslot.day} {assignment.timeslot.start_time}-{_assignment_end_time(assignment)} "
        f"week {assignment.timeslot.week}; rooms {assignment_room_ids(assignment)}"
    )


def fixed_session_override_rows(
    courses: list["Course"],
    assignments: list["Assignment"],
) -> list[dict[str, object]]:
    """Return audit rows where an official fixed session overrides a remark."""
    rows: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    fixed_assignments = [assignment for assignment in assignments if getattr(assignment, "is_fixed", False)]
    for course in courses:
        raw = getattr(course, "remarks", "")
        if not str(raw or "").strip():
            continue
        requirements = course_remark_requirements(course)
        for interpretation in requirements.interpretations:
            if interpretation.rule_name != "fixed_day_time" or not is_hard_enforceable(interpretation):
                continue
            requested = _requested_placement_text(interpretation)
            if not requested:
                continue
            for assignment in fixed_assignments:
                if not _fixed_assignment_matches_course(course, assignment):
                    continue
                if assignment_satisfies_interpretation(assignment, interpretation):
                    continue
                key = (
                    getattr(course, "source_file", ""),
                    getattr(course, "source_sheet", ""),
                    getattr(course, "source_row", ""),
                    course.module_code,
                    course.prog_yr,
                    interpretation.rule_name,
                    str(interpretation.parameters),
                    assignment.fixed_source,
                    assignment.timeslot.day if assignment.timeslot else "",
                    assignment.timeslot.start_time if assignment.timeslot else "",
                    _assignment_end_time(assignment),
                )
                if key in seen:
                    continue
                seen.add(key)
                final_placement = _assignment_placement_text(assignment)
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
                        "supported or unsupported": "supported",
                        "rule name": interpretation.rule_name,
                        "parameters": str(interpretation.parameters),
                        "explanation": "Official fixed-session placement overrides the free-text remark.",
                        "review reason": "Authoritative fixed-session placement retained.",
                        "applied status": "FIXED_SESSION_OVERRIDES_REMARK",
                        "instruction treatment": "OVERRIDDEN_BY_STRUCTURED_FIXED_SESSION",
                        "requested placement": requested,
                        "authoritative fixed placement": final_placement,
                        "final placement": final_placement,
                        "override source": assignment.fixed_source or "",
                    }
                )
    return rows


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
        fixed_end_times = tuple(str(value) for value in interpretation.parameters.get("fixed_end_times", req.fixed_end_times))
        fixed_time_ranges = tuple(
            (str(value[0]), str(value[1]))
            for value in interpretation.parameters.get("fixed_time_ranges", req.fixed_time_ranges)
            if isinstance(value, (list, tuple)) and len(value) == 2
        )
        if not fixed_days and not fixed_start_times and not fixed_end_times and not fixed_time_ranges:
            return False
        day_ok = not fixed_days or assignment.timeslot.day in fixed_days
        time_ok = not fixed_start_times or assignment.timeslot.start_time in fixed_start_times
        end_time = _assignment_end_time(assignment)
        end_ok = not fixed_end_times or end_time in fixed_end_times
        range_ok = not fixed_time_ranges or (assignment.timeslot.start_time, end_time) in fixed_time_ranges
        return day_ok and time_ok and end_ok and range_ok
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


REMARKS_AUDIT_COLUMNS = [
    "source workbook",
    "source sheet",
    "source row",
    "programme/year",
    "module",
    "activity",
    "raw remark",
    "normalised remark",
    "detected pattern",
    "proposed rule type",
    "confidence",
    "supported or unsupported",
    "rule name",
    "parameters",
    "explanation",
    "review reason",
    "applied status",
    "instruction treatment",
    "requested placement",
    "authoritative fixed placement",
    "final placement",
    "override source",
]


def remarks_audit_rows(courses: list["Course"], assignments: list["Assignment"] | None = None) -> list[dict[str, object]]:
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
                    "applied status": "",
                    "instruction treatment": str(interpretation.parameters.get("instruction_treatment", "")),
                    "requested placement": _requested_placement_text(interpretation)
                    if interpretation.rule_name == "fixed_day_time"
                    else "",
                    "authoritative fixed placement": "",
                    "final placement": "",
                    "override source": "",
                }
            )
    if assignments is not None:
        rows.extend(fixed_session_override_rows(courses, assignments))
    return rows


def export_remarks_audit(courses: list["Course"], output_path: Path, assignments: list["Assignment"] | None = None) -> None:
    """Export deterministic remark interpretations for development audit."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = remarks_audit_rows(courses, assignments=assignments)
    if not rows:
        rows = [{column: "" for column in REMARKS_AUDIT_COLUMNS}]
        rows[0]["detected pattern"] = "No remarks found"
    df = pd.DataFrame(rows)
    for column in REMARKS_AUDIT_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df[REMARKS_AUDIT_COLUMNS]
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Remarks Audit", index=False)
        summary = (
            df
            .groupby(["detected pattern", "supported or unsupported"], dropna=False)
            .size()
            .reset_index(name="count")
        )
        summary.to_excel(writer, sheet_name="Category Summary", index=False)
