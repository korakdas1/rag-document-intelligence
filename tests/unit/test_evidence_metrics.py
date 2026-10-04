"""Exact excerpt, provenance, polarity, and taxonomy regressions."""
from dataclasses import replace

import pytest

from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.core.settings import Settings
from research_assistant.evaluation.evidence_metrics import (
    context_blocks, passage_metrics, classify_cited_gold_coverage,
)
from research_assistant.evaluation.models import EvaluationExample, ExampleTrace, GoldPassage, Split
from research_assistant.evaluation.quality_taxonomy import classify_quality
from research_assistant.evaluation.taxonomy import classify
from research_assistant.evaluation.semantic_support import (
    classify_claim_overlap, FULL_LEXICAL_OVERLAP, UNCLEAR, POLARITY_MISMATCH,
)
from research_assistant.retrieval.models import RetrievalHit


def example(*passages):
    return EvaluationExample('x', 'Was the proposal approved?', Split.TEST, 'factual', True,
                             gold_passages=tuple(GoldPassage(*p) for p in passages))


def block(filename, text):
    return {'filename': filename, 'text': text}


@pytest.mark.parametrize('blocks,expected', [
    ([block('a.md', 'The proposal was approved.')], (True, False, 0.5)),
    ([block('a.md', 'The proposal was approved.'), block('b.md', 'The budget was 42.')], (True, True, 1.0)),
    ([block('wrong.md', 'The proposal was approved. The budget was 42.')], (False, False, 0.0)),
    ([], (False, False, 0.0)),
])
def test_multi_passage_presence_respects_provenance(blocks, expected):
    result = passage_metrics(example(('a.md', 'The proposal was approved.'), ('b.md', 'The budget was 42.')), blocks)
    assert tuple(result[key] for key in ('rendered_gold_any', 'rendered_gold_all', 'rendered_gold_passage_recall')) == expected


def test_full_normalized_passage_and_not_applicable():
    result = passage_metrics(example(('a.md', 'The proposal was approved.')), [block('a.md', 'THE proposal\n was approved.')])
    assert result['rendered_gold_any'] is result['rendered_gold_all'] is True
    assert result['rendered_gold_passage_recall'] == 1
    for item in (example(), replace(example(('a.md', 'fact')), answerable=False)):
        result = passage_metrics(item, [])
        assert result['rendered_gold_all'] is None
        assert result['rendered_gold_passage_recall'] is None
    assert classify_cited_gold_coverage(None) == 'NOT_APPLICABLE'


def test_excerpts_are_not_joined_across_missing_text():
    result = passage_metrics(example(('a.md', 'The proposal was approved.')),
                             [block('a.md', 'The proposal'), block('a.md', 'was approved.')])
    assert result['rendered_gold_any'] is False


def test_real_context_builder_truncates_gold_after_selected_chunk():
    fact = 'The proposal was approved.'
    hit = RetrievalHit('gold', 'doc', 1, 1.0, 'hybrid', 'Background information. ' * 90 + fact,
                       None, None, (), 'chunker', 'index', 'embedding', filename='a.md')
    settings = Settings(database_path='unused.db', log_level='WARNING', max_file_bytes=10000)
    context = CitationAwareContextBuilder(settings).build([hit], max_tokens=100)
    assert context.items and context.items[0].truncated
    assert context.items[0].source.chunk_id == 'gold'
    result = passage_metrics(example(('a.md', fact)), context_blocks(context))
    assert result['rendered_gold_any'] is False
    assert result['rendered_gold_passage_recall'] == 0
    assert fact not in context.rendered_text


@pytest.mark.parametrize('evidence,claim', [
    ('The proposal was approved.', 'The proposal was not approved.'),
    ('The proposal was not approved.', 'The proposal was approved.'),
    ('The proposal was approved.', 'The proposal was never approved.'),
    ('The proposal can proceed.', 'The proposal cannot proceed.'),
    ('The proposal was approved.', 'The proposal was denied.'),
    ('The proposal was rejected.', 'The proposal was approved.'),
    ('There was approval for the proposal.', 'There was no approval for the proposal.'),
])
def test_opposite_polarity_never_gets_full_overlap(evidence, claim):
    assert classify_claim_overlap(claim, [evidence]) == POLARITY_MISMATCH


def test_matching_and_conflicting_polarities():
    claim = 'The proposal was approved.'
    assert classify_claim_overlap(claim, [claim]) == FULL_LEXICAL_OVERLAP
    assert classify_claim_overlap(claim, [claim, 'The proposal was not approved.']) == UNCLEAR
    assert classify_claim_overlap(claim, [claim + ' The proposal was not approved.']) == UNCLEAR
    assert classify_claim_overlap(claim, ['The proposal was approved and not approved.']) == UNCLEAR
    assert classify_claim_overlap('The proposal was not approved.', ['The proposal was approved but not approved.']) == UNCLEAR
    assert classify_claim_overlap('The proposal was never approved.', ['The proposal was never approved.']) == FULL_LEXICAL_OVERLAP


def test_numbers_and_word_boundaries_are_conservative():
    assert classify_claim_overlap('The budget was 42 dollars.', ['The budget was 24 dollars.']) != FULL_LEXICAL_OVERLAP
    assert classify_claim_overlap('The proposal was approved.', ['The proposal was disapproved.']) != FULL_LEXICAL_OVERLAP


@pytest.mark.parametrize('hits,expected', [([False], 'CONTEXT_BUDGET_DROP'), ([True], 'FALSE_ABSTENTION_WITH_GOLD_CONTEXT')])
def test_both_taxonomies_use_rendered_evidence(hits, expected):
    item = example(('a.md', 'The proposal was approved.'))
    row = dict(expected_chunk_ids=['gold'], hybrid_ids=['gold'], rerank_ids=['gold'],
               context_chunk_ids=['gold'], gold_chunk_selected=True,
               rerank_gold_passage_hits=[True], rendered_gold_passage_hits=hits,
               rendered_gold_all=all(hits), insufficient_evidence=True,
               validation_status='insufficient_evidence')
    assert classify_quality(item, row)[0] == expected
    trace = ExampleTrace('x', 'q', 'test', 'factual', ['gold'], ['a.md'],
                         hybrid_ids=['gold'], rerank_ids=['gold'], context_chunk_ids=['gold'],
                         gold_chunk_selected=True, rerank_gold_passage_hits=[True],
                         rendered_gold_passage_hits=hits, rendered_gold_all=all(hits),
                         insufficient_evidence=True, validation_status='insufficient_evidence')
    labels = classify(item, trace)
    assert expected in labels
    if not all(hits):
        assert 'FALSE_ABSTENTION_WITH_GOLD_CONTEXT' not in labels


def test_chunk_membership_and_partial_gold_do_not_imply_false_abstention_with_gold():
    item = example(('a.md', 'one'), ('b.md', 'two'))
    row = dict(expected_chunk_ids=['gold'], hybrid_ids=['gold'], rerank_ids=['gold'],
               context_chunk_ids=['gold'], gold_chunk_selected=True,
               rendered_gold_any=True, rendered_gold_all=False,
               rerank_gold_passage_hits=[True, False], rendered_gold_passage_hits=[True, False],
               insufficient_evidence=True, validation_status='insufficient_evidence')
    assert classify_quality(item, row)[0] != 'FALSE_ABSTENTION_WITH_GOLD_CONTEXT'
    assert classify_quality(item, row)[0] != 'CONTEXT_BUDGET_DROP'
    # An old report's ID-only field is not accepted as rendered evidence.
    row.pop('rendered_gold_all')
    row['gold_in_context'] = True
    assert classify_quality(item, row)[0] != 'FALSE_ABSTENTION_WITH_GOLD_CONTEXT'


def test_citation_id_validity_excludes_missing_markers():
    from research_assistant.evaluation.aggregate import citation_summary
    item = example(('a.md', 'fact'))
    base = ExampleTrace('x', 'q', 'test', 'factual', [], [], validation_status='valid', insufficient_evidence=False)
    traces = [replace(base, cited_chunk_ids=['valid']),
              replace(base, validation_status='missing_citations'),
              replace(base, validation_status='insufficient_evidence', insufficient_evidence=True),
              replace(base, validation_status='invalid_citation', invalid_citation_ids=['S99'])]
    result = citation_summary(traces, [item])
    assert result['citation_id_valid_answer_rate'] == 0.5
    assert result['citation_coverage'] == 1 / 3
