"""Both runners measure post-budget context, including cached generation."""
import json
from pathlib import Path

import pytest

from research_assistant.app import create_application
from research_assistant.core.settings import Settings
from research_assistant.evaluation.models import EvaluationDataset, EvaluationExample, GoldPassage, Split
from research_assistant.evaluation.prepare import prepare_corpus
from research_assistant.evaluation.runner import EvaluationRunner
from research_assistant.evaluation.quality_runner import QualityEvaluationRunner
from research_assistant.generation.scripted import ScriptedLLM


@pytest.fixture
def prepared(tmp_path):
    corpus = tmp_path / 'corpus'
    corpus.mkdir()
    fact = 'The proposal was approved.'
    corpus.joinpath('fact.md').write_text('Proposal background details. ' * 25 + fact)
    settings = Settings(database_path=tmp_path / 'workspace/eval.db', log_level='WARNING',
                        max_file_bytes=10000, vector_index_path=tmp_path / 'workspace/indexes',
                        embedding_model_name='hashing', reranker_model_name='overlap',
                        llm_provider='scripted', llm_model_name='scripted.v1')
    llm = ScriptedLLM(lambda request: json.dumps({'answer': 'The proposal was approved [S1].', 'insufficient_evidence': False}))
    app = create_application(settings, llm=llm)
    state = prepare_corpus(app, corpus)
    dataset = EvaluationDataset('tiny', 'test.v1', (EvaluationExample(
        'fact', 'Was the proposal approved?', Split.TEST, 'factual', True,
        gold_passages=(GoldPassage('fact.md', fact),),
    ),))
    yield app, state, dataset
    app.indexing.vector_store.close(); app.store.close()


@pytest.mark.parametrize('runner_type', [EvaluationRunner, QualityEvaluationRunner])
def test_both_runners_measure_truncated_cited_excerpt(prepared, runner_type, monkeypatch):
    app, state, dataset = prepared
    runner = runner_type(app, dataset, chunker_id=state['chunker_id'])
    monkeypatch.setattr(runner_type.__module__ + '.git_commit', lambda: 'a' * 40)
    report = runner.run(stage='full', max_context_tokens=90)
    assert report['git_commit'] == 'a' * 40
    assert report['metrics_schema'] == report['config']['metrics_schema'] == 'evidence-metrics.v2'
    assert report['dataset_sha256'] and report['identities']['index_id']
    row = report['examples'][0]
    assert row['gold_chunk_selected'] is True
    assert row['context_blocks'][0]['truncated'] is True
    assert row['rendered_gold_all'] is row['rendered_gold_any'] is False
    assert row['rendered_gold_passage_recall'] == 0
    assert row['cited_gold_passage_recall'] == 0
    assert row['cited_gold_coverage_class'] == 'NO_GOLD_PASSAGE_COVERAGE'
    assert row['cited_passages'][0]['text'] == row['context_blocks'][0]['text']
    assert row['cited_passages'][0]['filename'] == 'fact.md'
    labels = row.get('failure_categories', [row.get('primary_failure')])
    assert 'CONTEXT_BUDGET_DROP' in labels
    for old in ('gold_in_context', 'context_gold_hit', 'context_evidence_recall',
                'semantically_supported_grounded', 'lexical_citation_support', 'support_class'):
        assert old not in row


def test_cached_generation_recomputes_evidence_and_current_provenance(prepared, tmp_path):
    app, state, dataset = prepared
    cache = tmp_path / 'cache'
    runner = EvaluationRunner(app, dataset, chunker_id=state['chunker_id'], cache_dir=cache)
    first = runner.run(stage='full', max_context_tokens=1000)['examples'][0]
    assert first['cited_gold_all'] is True
    for path in cache.glob('*.json'):
        payload = json.loads(path.read_text())
        payload.pop('cited_citation_ids', None)  # Exercise an older cache payload.
        payload.update(rendered_gold_all=False, cited_gold_passage_recall=0, cited_chunk_ids=['obsolete-chunk'])
        path.write_text(json.dumps(payload))
    second = runner.run(stage='full', max_context_tokens=1000)['examples'][0]
    assert second['cached_generation'] is True
    assert second['rendered_gold_all'] is True
    assert second['cited_gold_all'] is True
    assert second['cited_gold_passage_recall'] == 1
    assert second['cited_chunk_ids'] == first['cited_chunk_ids']
