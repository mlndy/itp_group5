"""Tests for deterministic remarks interpretation."""

from __future__ import annotations

from engine.remarks_interpreter import RemarkEnforcement, RemarkConfidence, interpret_remarks, normalise_remark


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
    assert requirements.required_room_count == 3
    assert requirements.needs_manual_review is True


def test_unspecified_additional_rooms_go_to_review() -> None:
    """Additional rooms without an exact count should remain visible for review."""
    requirements = interpret_remarks("Additional rooms for quizzes")

    assert requirements.needs_manual_review is True
    assert requirements.interpretations[0].rule_name == "additional_rooms_unspecified"


def test_hybrid_keywords_create_simultaneous_hybrid_delivery() -> None:
    """Hybrid wording should not become an either-or delivery choice."""
    requirements = interpret_remarks("Room to support hybrid due to overseas IWSP students")

    assert requirements.requires_hybrid_delivery is True
    assert requirements.requires_recording_room is True
    assert requirements.allowed_delivery_modes == ()


def test_physical_and_online_create_hybrid_delivery() -> None:
    """Physical and online wording means simultaneous hybrid delivery."""
    requirements = interpret_remarks("physical and online")

    assert requirements.requires_hybrid_delivery is True


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
