from pathlib import Path

from research_assistant.conversation.heuristic import HeuristicQueryResolver, RESOLVER_ID
from research_assistant.conversation.models import ConversationTurn
from research_assistant.evaluation.followup import evaluate_resolver, load_followup_dataset

ROOT = Path(__file__).resolve().parents[2]
FOLLOWUP_SET = ROOT / "evaluation" / "datasets" / "ragbench_followup_v1.jsonl"


def _turn(question: str, answer: str, sequence: int = 1) -> ConversationTurn:
    return ConversationTurn(question=question, answer=answer, sequence=sequence)


def test_pronoun_followup_preserves_couple_names() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Who are the main couple?", "Harry Potter and Hermione Granger."),)
    result = resolver.resolve("Do they get together?", history)
    query = result.retrieval_query.lower()
    assert result.rewrite_applied is True
    assert result.followup_detected is True
    assert "harry potter" in query
    assert "hermione granger" in query
    assert "together" in query
    assert result.diagnostics.resolver_id == RESOLVER_ID
    assert "harry potter and hermione granger. do they" not in query


def test_ellipsis_when_keeps_marriage_topic() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Are they married?", "Harry Potter and Hermione Granger later marry."),)
    result = resolver.resolve("When?", history)
    query = result.retrieval_query.lower()
    assert result.rewrite_applied is True
    assert "harry potter" in query
    assert "hermione granger" in query
    assert "married" in query or "marry" in query


def test_standalone_question_is_not_rewritten() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Harry Potter and Hermione Granger."),)
    original = "Who is Draco Malfoy?"
    result = resolver.resolve(original, history)
    assert result.rewrite_applied is False
    assert result.retrieval_query == original
    assert result.diagnostics.method == "passthrough"


def test_standalone_technical_question() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Willow Reed and Ash Calder."),)
    original = "What is reciprocal rank fusion?"
    result = resolver.resolve(original, history)
    assert result.retrieval_query == original


def test_wrong_previous_answer_is_not_copied_into_query() -> None:
    resolver = HeuristicQueryResolver()
    history = (
        _turn("Whose love story is this?", "Willow Reed and Ash Calder.", 1),
        _turn("Do they get together?", "They do not get together.", 2),
    )
    result = resolver.resolve(
        "But the document says they marry. Are you sure?",
        history,
    )
    query = result.retrieval_query.lower()
    assert "willow reed" in query
    assert "ash calder" in query
    assert "do not get together" not in query
    assert result.diagnostics.method != "passthrough"


def test_empty_history_does_not_invent_entities() -> None:
    resolver = HeuristicQueryResolver()
    result = resolver.resolve("Do they get together?", ())
    assert result.retrieval_query == "Do they get together?"
    assert result.rewrite_applied is False
    assert result.followup_detected is False
    assert result.ambiguous is True
    assert result.diagnostics.method == "unresolved_no_history"


def test_unresolved_pronoun_without_history_is_ambiguous() -> None:
    resolver = HeuristicQueryResolver()
    result = resolver.resolve("When did it launch?", ())
    assert result.rewrite_applied is False
    assert result.ambiguous is True
    assert result.diagnostics.method == "unresolved_no_history"
    assert result.retrieval_query == "When did it launch?"


def test_named_question_is_not_unresolved() -> None:
    resolver = HeuristicQueryResolver()
    named = resolver.resolve("When was the Riverton Transit Loop launched?", ())
    assert named.ambiguous is False
    assert named.diagnostics.method == "passthrough"
    boarding = resolver.resolve("What does a boarding mean in this archive?", ())
    assert boarding.ambiguous is False
    why = resolver.resolve("Why were infrared gate counts rejected?", ())
    assert why.ambiguous is False


def test_pronoun_with_history_still_rewrites() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("When was Cedar Field Station founded?", "2004."),)
    result = resolver.resolve("Where?", history)
    assert result.rewrite_applied is True
    assert result.followup_detected is True
    assert "Cedar Field Station" in result.retrieval_query


def test_conversation_window_is_bounded() -> None:
    resolver = HeuristicQueryResolver(window=2)
    history = (
        _turn("Who is Alpha Person?", "Alpha Person.", 1),
        _turn("Who is Beta Person?", "Beta Person.", 2),
        _turn("Who is Gamma Person?", "Gamma Person.", 3),
    )
    result = resolver.resolve("Do they marry?", history)
    query = result.retrieval_query
    assert "Gamma Person" in query
    assert "Beta Person" in query
    assert "Alpha Person" not in query
    assert result.diagnostics.history_turns_used == 2


def test_contraction_it_is_not_substituted() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Harry Potter and Hermione Granger."),)
    original = "Harry ends up with Hermione, it's written there"
    result = resolver.resolve(original, history)
    query = result.retrieval_query
    assert "Harry's written there" not in query
    assert "harry's written there" not in query.lower()
    assert "it's written there" in query.lower()
    assert result.rewrite_applied is False
    assert result.diagnostics.method in {"passthrough", "explicit_entities"}


def test_its_happy_ending_contraction_is_not_corrupted() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Harry Potter and Hermione Granger."),)
    original = "It's a happy ending, right?"
    result = resolver.resolve(original, history)
    query = result.retrieval_query
    assert query.lower().startswith("it's")
    assert "harry's a happy ending" not in query.lower()
    assert "granger's a happy ending" not in query.lower()


def test_dummy_it_is_not_replaced_with_subject_names() -> None:
    from research_assistant.conversation.entities import substitute_pronouns

    out = substitute_pronouns("Is it a happy ending?", "Willow Reed and Ash Calder")
    assert out == "Is it a happy ending?"


def test_dummy_it_followup_keeps_predicate_and_adds_subjects() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Willow Reed and Ash Calder."),)
    result = resolver.resolve("Is it a happy ending?", history)
    query = result.retrieval_query
    lowered = query.lower()
    assert result.rewrite_applied is True
    assert lowered.startswith("is it a happy ending")
    assert "willow reed" in lowered
    assert "ash calder" in lowered
    assert not lowered.startswith("is willow")
    assert not lowered.startswith("is harry")


def test_thats_contraction_is_not_corrupted() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Harry Potter and Hermione Granger."),)
    original = "That's what you said earlier."
    result = resolver.resolve(original, history)
    query = result.retrieval_query.lower()
    assert "that's" in query
    assert not query.startswith("harry's")
    assert "harry potter and hermione granger's what you said" not in query


def test_hes_contraction_is_not_corrupted() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Harry Potter and Hermione Granger."),)
    original = "He's Harry's friend, right?"
    result = resolver.resolve(original, history)
    query = result.retrieval_query
    assert query.lower().startswith("he's")
    assert "harry potter and hermione granger's harry's friend" not in query.lower()
    assert result.rewrite_applied is False


def test_shes_contraction_is_not_corrupted() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Harry Potter and Hermione Granger."),)
    original = "She's Hermione's friend?"
    result = resolver.resolve(original, history)
    query = result.retrieval_query
    assert query.lower().startswith("she's")
    assert "granger's hermione's friend" not in query.lower()
    assert result.rewrite_applied is False


def test_explicit_named_query_is_not_destructively_rewritten() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Harry Potter and Hermione Granger."),)
    original = "Does Harry Potter end up with Hermione Granger in the story?"
    result = resolver.resolve(original, history)
    assert result.rewrite_applied is False
    assert result.retrieval_query == original
    assert result.diagnostics.method in {"passthrough", "explicit_entities"}


def test_standalone_it_still_resolves_happy_ending() -> None:
    resolver = HeuristicQueryResolver()
    history = (_turn("Whose love story is this?", "Harry Potter and Hermione Granger."),)
    result = resolver.resolve("Is it a happy ending?", history)
    query = result.retrieval_query.lower()
    assert result.rewrite_applied is True
    assert "harry potter" in query
    assert "hermione granger" in query
    assert "happy" in query


def test_theyre_contraction_is_not_substituted() -> None:
    from research_assistant.conversation.entities import substitute_pronouns

    out = substitute_pronouns("they're mentioned in the notes", "Harry Potter")
    assert out == "they're mentioned in the notes"
    out_plain = substitute_pronouns("they are mentioned in the notes", "Harry Potter")
    assert out_plain == "Harry Potter are mentioned in the notes"


def test_when_followup_does_not_inject_location_subjects() -> None:
    resolver = HeuristicQueryResolver()
    history = (
        _turn(
            "Do Harry Potter and Hermione Granger marry?",
            "Harry and Hermione were married in the Welsh village of Godrics Hollow. [S1]",
        ),
    )
    result = resolver.resolve("When?", history)
    query = result.retrieval_query
    lowered = query.lower()
    assert result.rewrite_applied is True
    assert "harry potter" in lowered
    assert "hermione granger" in lowered
    assert "marry" in lowered or "married" in lowered
    assert "welsh" not in lowered
    assert "godrics" not in lowered
    assert "hollow" not in lowered
    assert "welsh" not in " ".join(result.diagnostics.entities).lower()
    assert "godrics" not in " ".join(result.diagnostics.entities).lower()


def test_location_in_answer_is_not_a_followup_subject() -> None:
    resolver = HeuristicQueryResolver()
    history = (
        _turn(
            "Do Mira Solen and Julian Pike marry?",
            "Mira and Julian were married in the coastal village of Northhaven Reach. [S1]",
        ),
    )
    result = resolver.resolve("When?", history)
    query = result.retrieval_query.lower()
    assert "mira solen" in query
    assert "julian pike" in query
    assert "northhaven" not in query
    assert "reach" not in query


def test_organization_they_resolves_from_prior_question() -> None:
    resolver = HeuristicQueryResolver()
    history = (
        _turn(
            "Did the River Council delay the bridge vote?",
            "The River Council delayed the vote until spring. Mayor Bramble objected.",
        ),
    )
    result = resolver.resolve("Did they publish the decision?", history)
    query = result.retrieval_query
    assert result.rewrite_applied is True
    assert "River Council" in query
    assert "Mayor Bramble" not in query
    assert "they" not in query.lower().split()


def test_topic_switch_does_not_keep_old_couple() -> None:
    resolver = HeuristicQueryResolver()
    history = (
        _turn("Whose relationship is this?", "Mira Solen and Julian Pike.", 1),
        _turn(
            "Who chairs the Northhaven Council?",
            "Mayor Bramble chairs the Northhaven Council.",
            2,
        ),
    )
    result = resolver.resolve("Do they meet weekly?", history)
    query = result.retrieval_query
    assert "Northhaven Council" in query
    assert "Mira Solen" not in query
    assert "Julian Pike" not in query


def test_followup_dataset_scores_cleanly() -> None:
    examples = load_followup_dataset(FOLLOWUP_SET)
    summary = evaluate_resolver(examples)
    assert summary["n"] == len(examples)
    failed = [
        item["example_id"]
        for item in summary["traces"]
        if not item["standalone_query_completeness"] or not item["rewrite_required_accuracy"]
    ]
    assert failed == [], failed
    assert summary["entity_preservation"] == 1.0
    assert summary["rewrite_required_accuracy"] == 1.0
