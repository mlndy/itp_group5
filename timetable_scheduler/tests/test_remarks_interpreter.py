"""Tests for deterministic remarks interpretation."""

from __future__ import annotations

from engine.remarks_interpreter import (
    RemarkConfidence,
    RemarkEnforcement,
    hard_enforceable_interpretations,
    interpret_remarks,
    is_hard_enforceable,
    normalise_remark,
)


def test_empty_remark_produces_no_requirements() -> None:
    """Blank remarks should not create hidden requirements."""
    requirements = interpret_remarks("")

    assert requirements.required_room_count == 1
    assert requirements.interpretations == ()
    assert requirements.needs_manual_review is False


def test_raw_remark_is_preserved() -> None:
    """Interpretations should retain the original text."""
    requirements = interpret_remarks("Two rooms")

    assert requirements.interpretations[0].raw_text == "Two rooms"
    assert requirements.interpretations[0].normalised_text == "2 rooms"


def test_number_word_normalisation() -> None:
    """Number words should normalise before pattern matching."""
    assert normalise_remark("two ACE rooms") == "2 ace rooms"


def test_two_rooms_creates_hard_room_count() -> None:
    """Explicit room counts should become hard requirements."""
    requirements = interpret_remarks("2 rooms")

    assert requirements.required_room_count == 2
    assert requirements.interpretations[0].enforcement == RemarkEnforcement.HARD


def test_two_rooms_as_word_creates_room_count() -> None:
    """Number words should also create room-count requirements."""
    requirements = interpret_remarks("two rooms")

    assert requirements.required_room_count == 2


def test_duration_expression_does_not_mean_two_rooms() -> None:
    """Session-duration numbers should not be treated as room counts."""
    requirements = interpret_remarks("2 x 2-hour lecture")

    assert requirements.required_room_count == 1


def test_groups_expression_does_not_mean_two_rooms() -> None:
    """Group counts alone should not imply room counts."""
    requirements = interpret_remarks("2 groups")

    assert requirements.required_room_count == 1


def test_parallel_tracks_are_detected_for_review_when_over_output_limit() -> None:
    """Three parallel tracks should be recognised and flagged for review."""
    requirements = interpret_remarks("Split into 3 parallel tracks at one go")

    assert requirements.concurrent_groups == 3
    assert requirements.required_room_count == 1
    assert requirements.needs_manual_review is True
    assert not hard_enforceable_interpretations(requirements)


def test_unspecified_additional_rooms_go_to_review() -> None:
    """Additional rooms without an exact count should remain visible for review."""
    requirements = interpret_remarks("Additional rooms for quizzes")

    assert requirements.needs_manual_review is True
    assert requirements.interpretations[0].rule_name == "additional_rooms_unspecified"


def test_hybrid_keywords_create_simultaneous_hybrid_delivery() -> None:
    """Ambiguous hybrid support wording should require confirmation only."""
    requirements = interpret_remarks("Room to support hybrid due to overseas IWSP students")

    assert requirements.requires_hybrid_delivery is False
    assert requirements.requires_recording_room is False
    assert requirements.allowed_delivery_modes == ()
    assert requirements.needs_manual_review is True
    assert not hard_enforceable_interpretations(requirements)


def test_physical_and_online_create_hybrid_delivery() -> None:
    """Physical and online wording means simultaneous hybrid delivery."""
    requirements = interpret_remarks("physical and online")

    assert requirements.requires_hybrid_delivery is True
    assert hard_enforceable_interpretations(requirements)


def test_online_or_physical_creates_flexible_delivery() -> None:
    """Either-or wording should create delivery alternatives."""
    requirements = interpret_remarks("online or physical")

    assert requirements.allowed_delivery_modes == ("f2f", "online")
    assert requirements.requires_hybrid_delivery is False


def test_preferred_room_type_is_soft() -> None:
    """Preferred wording should remain a soft preference."""
    requirements = interpret_remarks("Computer room preferred")

    assert requirements.preferred_room_types == ("computer room",)
    assert requirements.interpretations[0].enforcement == RemarkEnforcement.SOFT


def test_required_room_type_is_hard() -> None:
    """Must wording should create a hard room-type requirement."""
    requirements = interpret_remarks("must use computer lab")

    assert requirements.required_room_types == ("computer lab",)
    assert requirements.interpretations[0].enforcement == RemarkEnforcement.HARD


def test_must_after_lecture_creates_hard_sequence() -> None:
    """Explicit sequencing should be recognised as a hard rule."""
    requirements = interpret_remarks("must be after lecture")

    assert requirements.must_follow_activity == "lecture"
    assert requirements.interpretations[0].enforcement == RemarkEnforcement.HARD


def test_prefer_after_lecture_creates_soft_sequence() -> None:
    """Preference wording should not become a hard sequencing rule."""
    requirements = interpret_remarks("prefer after lecture")

    assert requirements.must_follow_activity == "lecture"
    assert requirements.interpretations[0].enforcement == RemarkEnforcement.SOFT


def test_unrecognised_text_is_retained_for_review() -> None:
    """Unsupported remarks should not be guessed."""
    requirements = interpret_remarks("Discuss with programme lead nearer to term")

    assert requirements.needs_manual_review is True
    assert requirements.interpretations[0].rule_name == "unsupported_remark"
    assert requirements.interpretations[0].confidence == RemarkConfidence.LOW


def test_low_confidence_text_never_becomes_hard_rule() -> None:
    """Low-confidence interpretations should never become hard constraints."""
    requirements = interpret_remarks("Maybe something special")

    assert all(item.enforcement != RemarkEnforcement.HARD for item in requirements.interpretations)


def test_high_confidence_explicit_supported_rule_is_hard_enforceable() -> None:
    """A complete explicit supported rule may be enforced as hard."""
    requirements = interpret_remarks("Need 2 rooms")

    assert is_hard_enforceable(requirements.interpretations[0]) is True


def test_medium_confidence_rule_cannot_be_hard_enforceable() -> None:
    """Medium-confidence interpretations should stay out of hard scheduling."""
    requirements = interpret_remarks("May need hybrid")

    assert requirements.interpretations[0].confidence == RemarkConfidence.MEDIUM
    assert not hard_enforceable_interpretations(requirements)


def test_unsupported_rule_cannot_be_hard_enforceable() -> None:
    """Unsupported text should be retained without becoming hard."""
    requirements = interpret_remarks("Special arrangement required")

    assert requirements.interpretations[0].rule_name == "unsupported_remark"
    assert not hard_enforceable_interpretations(requirements)


def test_preference_wording_cannot_be_hard_enforceable() -> None:
    """Preference wording should not create a hard room requirement."""
    requirements = interpret_remarks("Computer room preferred")

    assert requirements.interpretations[0].enforcement == RemarkEnforcement.SOFT
    assert not hard_enforceable_interpretations(requirements)


def test_incomplete_room_count_cannot_be_hard_enforceable() -> None:
    """Missing room counts should require confirmation, not hard filtering."""
    requirements = interpret_remarks("Additional rooms for quizzes")

    assert requirements.interpretations[0].rule_name == "additional_rooms_unspecified"
    assert not hard_enforceable_interpretations(requirements)


def test_hybrid_preferred_is_soft() -> None:
    """Preferred hybrid wording should not block scheduling."""
    requirements = interpret_remarks("Hybrid preferred")

    assert requirements.interpretations[0].enforcement == RemarkEnforcement.SOFT
    assert not hard_enforceable_interpretations(requirements)


def test_recording_proxy_note_is_visible_for_explicit_hybrid() -> None:
    """Explicit hybrid rules should document the recording-capability proxy."""
    requirements = interpret_remarks("Hybrid delivery required")

    assert "Recording capability" in str(requirements.interpretations[0].parameters["proxy_note"])
    assert hard_enforceable_interpretations(requirements)


def test_monday_preferred_is_soft_fixed_day() -> None:
    """Preferred days should be visible but non-blocking."""
    requirements = interpret_remarks("Monday preferred")

    assert requirements.interpretations[0].enforcement == RemarkEnforcement.SOFT
    assert requirements.interpretations[0].parameters["fixed_days"] == ["Monday"]
    assert not hard_enforceable_interpretations(requirements)


def test_timing_to_be_confirmed_is_non_blocking_information() -> None:
    """Timing confirmation notes should not become scheduling failures."""
    requirements = interpret_remarks("Timing to be confirmed")

    assert requirements.needs_manual_review is False
    assert requirements.interpretations[0].rule_name == "unsupported_remark"
    assert requirements.interpretations[0].parameters["informational"] is True


def test_explicit_fixed_day_time_request_is_hard_enforceable() -> None:
    """Mandatory day/time wording should be an explicit fixed-placement request."""
    requirements = interpret_remarks("Must be Thursday at 2 pm")

    assert requirements.fixed_days == ("Thursday",)
    assert requirements.fixed_start_times == ("14:00",)
    assert hard_enforceable_interpretations(requirements)


def test_complete_day_time_range_is_hard_enforceable() -> None:
    """A clear day and time range should be applied as a hard fixed request."""
    requirements = interpret_remarks("Monday, 10am-12pm")

    assert requirements.fixed_days == ("Monday",)
    assert requirements.fixed_start_times == ("10:00",)
    assert requirements.fixed_end_times == ("12:00",)
    assert requirements.fixed_time_ranges == (("10:00", "12:00"),)
    assert requirements.duration_override_hours == 2
    assert hard_enforceable_interpretations(requirements)


def test_plural_day_time_range_is_normalised() -> None:
    """Plural weekday wording should still create the expected fixed day."""
    requirements = interpret_remarks("Tuesdays, 9am-11am")

    assert requirements.fixed_days == ("Tuesday",)
    assert requirements.fixed_start_times == ("09:00",)
    assert requirements.fixed_end_times == ("11:00",)


def test_explicit_date_time_range_captures_date_and_weekday() -> None:
    """Dated remarks should keep the date evidence and compute a weekday when possible."""
    requirements = interpret_remarks("10 Sep 2025, 8.30am-12pm")

    assert requirements.explicit_dates == ("10 Sep 2025",)
    assert requirements.fixed_days == ("Wednesday",)
    assert requirements.fixed_start_times == ("08:30",)
    assert requirements.fixed_end_times == ("12:00",)
    assert requirements.duration_override_hours == 3.5


def test_parenthesised_weekday_date_time_range_is_hard() -> None:
    """A date plus parenthesised weekday should enforce the weekday and time."""
    requirements = interpret_remarks("7 Nov (Friday), 2-4pm")

    assert requirements.explicit_dates == ("7 Nov",)
    assert requirements.fixed_days == ("Friday",)
    assert requirements.fixed_time_ranges == (("14:00", "16:00"),)


def test_time_range_without_day_preserves_full_duration() -> None:
    """A long explicit time range must not collapse to a two-hour class."""
    requirements = interpret_remarks("9AM-6PM")

    assert requirements.fixed_start_times == ("09:00",)
    assert requirements.fixed_end_times == ("18:00",)
    assert requirements.duration_override_hours == 9
    assert hard_enforceable_interpretations(requirements)


def test_multi_session_time_ranges_preserve_all_starts() -> None:
    """Multiple explicit ranges should not be reduced to the final start time."""
    requirements = interpret_remarks("AF can only teach on Fridays, 2-4pm (T1) and 4-6pm (T2)")

    assert requirements.fixed_days == ("Friday",)
    assert requirements.fixed_start_times == ("14:00", "16:00")
    assert requirements.fixed_end_times == ("16:00", "18:00")
    assert requirements.fixed_time_ranges == (("14:00", "16:00"), ("16:00", "18:00"))
    assert requirements.needs_manual_review is True
