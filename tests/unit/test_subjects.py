from research_assistant.evaluation.subjects import subject_completeness


def test_relationship_requires_both_supported_participants() -> None:
    assert subject_completeness(
        "Alex and Morgan’s relationship. [S1]",
        must_contain=("Alex", "Morgan"),
    )
    assert not subject_completeness(
        "Alex’s relationship.",
        must_contain=("Alex", "Morgan"),
    )


def test_single_founder_does_not_require_a_second_name() -> None:
    assert subject_completeness(
        "Alex founded the company. [S1]",
        must_contain=("Alex",),
        must_not_contain=("Morgan",),
    )


def test_distractor_names_fail_completeness() -> None:
    assert not subject_completeness(
        "Alex, Morgan, and Nell Ostern. [S1]",
        must_contain=("Alex", "Morgan"),
        must_not_contain=("Nell", "Ostern"),
    )


def test_any_temporal_phrase() -> None:
    assert subject_completeness(
        "They married one year later. [S1]",
        must_contain=("one year", "year later"),
        must_contain_any=True,
    )
