"""CLI evaluation never opens or mutates serving stores. No model downloads."""
import hashlib
import json
from pathlib import Path

import pytest

from research_assistant.app import create_application
from research_assistant.chunking.config import default_config
from research_assistant.cli import main
from research_assistant.core.settings import load_settings
from research_assistant.evaluation.identity import corpus_fingerprint, METRICS_SCHEMA


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    serving = tmp_path / 'serving'
    monkeypatch.setenv('RESEARCH_ASSISTANT_DATABASE_PATH', str(serving / 'processed' / 'library.db'))
    monkeypatch.setenv('RESEARCH_ASSISTANT_VECTOR_INDEX_PATH', str(serving / 'indexes'))
    monkeypatch.setenv('RESEARCH_ASSISTANT_UPLOAD_DIR', str(serving / 'uploads'))
    monkeypatch.setenv('RESEARCH_ASSISTANT_EMBEDDING_MODEL', 'hashing')
    monkeypatch.setenv('RESEARCH_ASSISTANT_RERANKER_MODEL', 'overlap')
    monkeypatch.setenv('RESEARCH_ASSISTANT_LLM_PROVIDER', 'scripted')
    monkeypatch.setenv('RESEARCH_ASSISTANT_LLM_MODEL', 'scripted.v1')
    serving.joinpath('uploads').mkdir(parents=True)
    sentinel = serving / 'uploads' / 'sentinel.md'
    sentinel.write_text('The private library keeps blue notebooks.\n')
    app = create_application(load_settings())
    doc = app.ingest.ingest(sentinel).document
    assert doc is not None
    config = default_config()
    assert app.chunking.chunk_document(doc.document_id, config).ok
    assert app.indexing.index_chunker(config.chunker_id).ok
    app.indexing.vector_store.close()
    app.store.close()
    # SQLite connection finalizers may remove empty WAL/SHM files; settle those
    # from fixture setup before taking the immutable serving-tree snapshot.
    import gc
    gc.collect()
    corpus = tmp_path / 'corpus'
    corpus.mkdir()
    corpus.joinpath('fact.md').write_text('The proposal was approved.\n')
    dataset = tmp_path / 'tiny.jsonl'
    dataset.write_text(json.dumps(dict(example_id='fact', question='Was the proposal approved?',
                                      split='test', category='factual', answerable=True,
                                      gold_passages=[dict(filename='fact.md', text='The proposal was approved.')])) + '\n')
    return serving, corpus, dataset


def arguments(corpus, dataset, *extra):
    return ['evaluate', '--dataset', str(dataset), '--corpus', str(corpus),
            '--stage', 'full', *map(str, extra)]


def invoke(capsys, args):
    code = main(args)
    output = json.loads(capsys.readouterr().out)
    return code, output


@pytest.mark.parametrize('family', ['tiny', 'qualitybench_tiny'])
def test_prepare_isolated_default_workspace_and_reuse(environment, capsys, family):
    serving, corpus, original = environment
    dataset = original.with_name(family + '.jsonl')
    if dataset != original:
        dataset.write_bytes(original.read_bytes())
    before = snapshot(serving)
    code, summary = invoke(capsys, arguments(corpus, dataset, '--prepare'))
    assert code == 0, summary
    workspace = Path(summary['workspace'])
    assert workspace == Path.cwd() / 'evaluation' / 'workspaces' / family
    assert workspace.joinpath('research_assistant.db').is_file()
    assert workspace.joinpath('indexes/qdrant').is_dir()
    assert workspace.joinpath('uploads').is_dir()
    assert workspace.joinpath('cache').is_dir()
    assert snapshot(serving) == before
    import sqlite3
    with sqlite3.connect(workspace / 'research_assistant.db') as db:
        assert db.execute('select filename from documents').fetchall() == [('fact.md',)]
    report = json.loads(Path(summary['output_path']).read_text())
    assert report['metrics_schema'] == METRICS_SCHEMA
    assert report['dataset_sha256'] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert report['corpus_sha256'] == corpus_fingerprint(corpus)
    assert report['workspace'] == str(workspace)
    assert 'git_commit' in report
    assert Path(summary['output_path']).is_relative_to(Path.cwd() / 'evaluation/results')
    assert report['identities']['index_id']
    assert report['config']['embedding_model'] == 'hashing'
    row = report['examples'][0]
    assert row['rendered_gold_any'] is row['rendered_gold_all'] is True
    assert row['gold_chunk_selected'] is True
    assert row['context_blocks'][0]['filename'] == 'fact.md'
    assert row['context_blocks'][0]['truncated'] is False
    code, reused = invoke(capsys, arguments(corpus, dataset))
    assert code == 0, reused
    assert snapshot(serving) == before
    if family == 'tiny':
        assert list(workspace.joinpath('cache').glob('*.json'))
        cached = json.loads(Path(reused['output_path']).read_text())['examples'][0]
        assert cached['cached_generation'] is True
        assert cached['rendered_gold_all'] is True


def test_unprepared_fails_without_opening_any_store(environment, capsys):
    serving, corpus, dataset = environment
    before = snapshot(serving)
    code, result = invoke(capsys, arguments(corpus, dataset))
    assert code == 1 and result['error_type'] == 'corpus_not_prepared'
    assert not Path('evaluation/workspaces').exists()
    assert snapshot(serving) == before


def test_explicit_workspace_and_stale_manifest(environment, capsys):
    serving, corpus, dataset = environment
    before = snapshot(serving)
    workspace = Path.cwd() / 'custom-evaluation'
    args = arguments(corpus, dataset, '--workspace', workspace)
    assert invoke(capsys, [*args, '--prepare'])[0] == 0
    assert invoke(capsys, args)[0] == 0
    corpus.joinpath('fact.md').write_text('The proposal was approved. A new revision.\n')
    for extra in ([], ['--prepare']):
        code, result = invoke(capsys, args + extra)
        assert code == 1 and result['error_type'] == 'workspace_incompatible'
    assert snapshot(serving) == before


@pytest.mark.parametrize('flag', ['--db', '--index-path'])
def test_serving_storage_flags_rejected(environment, capsys, flag):
    serving, corpus, dataset = environment
    before = snapshot(serving)
    code, result = invoke(capsys, arguments(corpus, dataset, '--prepare', flag, serving / 'oops'))
    assert code == 1 and result['error_type'] == 'evaluation_storage_flags'
    assert snapshot(serving) == before


@pytest.mark.parametrize('target', ['serving', 'serving/processed', 'serving/indexes', 'serving/uploads', 'data/processed', 'data/indexes', 'data/uploads', 'corpus', '.'])
def test_overlapping_workspace_rejected_before_writes(environment, capsys, target):
    serving, corpus, dataset = environment
    before = snapshot(serving)
    code, result = invoke(capsys, arguments(corpus, dataset, '--prepare', '--workspace', target))
    assert code == 1 and result['error_type'] == 'unsafe_evaluation_path'
    assert snapshot(serving) == before


def test_symlink_and_unowned_directory_rejected(environment, capsys):
    serving, corpus, dataset = environment
    alias = Path.cwd() / 'alias'
    alias.symlink_to(serving / 'indexes', target_is_directory=True)
    assert invoke(capsys, arguments(corpus, dataset, '--prepare', '--workspace', alias))[0] == 1
    workspace = Path.cwd() / 'unowned'
    workspace.mkdir(); workspace.joinpath('precious.txt').write_text('keep me')
    before = snapshot(workspace)
    code, result = invoke(capsys, arguments(corpus, dataset, '--prepare', '--workspace', workspace))
    assert code == 1 and result['error_type'] == 'workspace_not_owned'
    assert snapshot(workspace) == before


def test_missing_prepared_index_fails_clearly(environment, capsys):
    _, corpus, dataset = environment
    code, prepared = invoke(capsys, arguments(corpus, dataset, '--prepare'))
    assert code == 0
    # Move only this test's own index aside, preserving it.
    index = Path(prepared['workspace']) / 'indexes' / 'qdrant'
    index.rename(index.with_name('saved-index'))
    code, result = invoke(capsys, arguments(corpus, dataset))
    assert code == 1 and result['error_type'] == 'corpus_not_prepared'


def test_model_and_retrieval_configuration_preserved(environment, capsys, monkeypatch):
    _, corpus, dataset = environment
    monkeypatch.setenv('RESEARCH_ASSISTANT_RRF_K', '77')
    code, result = invoke(capsys, arguments(corpus, dataset, '--prepare', '--candidate-k', 3, '--rerank-top-k', 2, '--max-context-tokens', 333))
    assert code == 0, result
    config = result['config']
    assert config['candidate_k'] == 3 and config['rerank_top_k'] == 2
    assert config['max_context_tokens'] == 333 and config['rrf_k'] == 77
    assert config['embedding_model'] == 'hashing' and config['reranker_model'] == 'overlap'
    assert config['llm_model'] == 'scripted.v1'


def test_fingerprints_ignore_location_mtimes_and_generated_files(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    for directory in (a, b):
        directory.joinpath('z.md').write_text('z')
        directory.joinpath('a.txt').write_text('a')
    digest = corpus_fingerprint(a)
    b.joinpath('generated.db').write_text('runtime')
    b.joinpath('workspace').mkdir(); b.joinpath('workspace/generated.md').write_text('runtime')
    assert corpus_fingerprint(b) == digest
    b.joinpath('a.txt').write_text('changed')
    assert corpus_fingerprint(b) != digest
    b.joinpath('a.txt').write_text('a')
    b.joinpath('a.txt').rename(b / 'renamed.txt')
    assert corpus_fingerprint(b) != digest


def test_workspace_may_be_a_sibling_of_custom_serving_database(tmp_path):
    from dataclasses import replace
    from research_assistant.evaluation.workspace import validate_runtime_path
    settings = replace(load_settings(), database_path=tmp_path / "library.db",
                       vector_index_path=tmp_path / "vectors", upload_dir=tmp_path / "uploads")
    workspace = tmp_path / "evaluation"
    assert validate_runtime_path(workspace, settings, tmp_path / "corpus") == workspace


@pytest.mark.parametrize("flag,target", [("--cache-dir", "serving/uploads"), ("--output", "serving/indexes")])
def test_auxiliary_output_paths_cannot_write_serving_storage(environment, capsys, flag, target):
    serving, corpus, dataset = environment
    before = snapshot(serving)
    code, result = invoke(capsys, arguments(corpus, dataset, "--prepare", flag, target))
    assert code == 1 and result["error_type"] == "unsafe_evaluation_path"
    assert snapshot(serving) == before


def test_expanded_workspace_is_used_for_cache_and_reports(environment, capsys, monkeypatch):
    _, corpus, dataset = environment
    fake_home = Path.cwd() / 'home'
    original = Path.expanduser
    monkeypatch.setattr(Path, 'expanduser', lambda p: fake_home / str(p)[2:] if str(p).startswith('~/') else original(p))
    code, result = invoke(capsys, arguments(corpus, dataset, '--prepare', '--workspace', '~/evaluation', '--output', '~/reports'))
    assert code == 0, result
    assert Path(result['workspace']) == fake_home / 'evaluation'
    assert list((fake_home / 'evaluation/cache').glob('*.json'))
    assert Path(result['output_path']).is_relative_to(fake_home / 'reports')
    assert not Path('~').exists()


@pytest.mark.parametrize('flag', ['--cache-dir', '--output'])
@pytest.mark.parametrize('target', [
    '.', '..', 'research_assistant.db', 'research_assistant.db/nested',
    'indexes', 'indexes/qdrant', 'uploads', 'uploads/nested',
    'workspace.json', 'workspace.json/nested', 'other',
    'cache/../uploads', 'results/../indexes/qdrant',
])
def test_reserved_workspace_paths_rejected_before_writes(environment, capsys, flag, target):
    serving, corpus, dataset = environment
    workspace = Path('evaluation/workspaces/tiny')
    before = snapshot(serving)
    code, result = invoke(capsys, arguments(
        corpus, dataset, '--prepare', '--workspace', workspace, flag, workspace / target,
    ))
    assert code == 1 and result['error_type'] == 'unsafe_evaluation_path', result
    assert flag in result['error_message']
    assert not Path('evaluation').exists()
    assert snapshot(serving) == before


@pytest.mark.parametrize('target', ['cache', 'cache/nested'])
def test_report_output_cannot_use_generation_cache(environment, capsys, target):
    serving, corpus, dataset = environment
    workspace = Path('evaluation/workspaces/tiny')
    before = snapshot(serving)
    code, result = invoke(capsys, arguments(
        corpus, dataset, '--prepare', '--workspace', workspace, '--output', workspace / target,
    ))
    assert code == 1 and result['error_type'] == 'unsafe_evaluation_path', result
    assert '--output' in result['error_message']
    assert not Path('evaluation').exists()
    assert snapshot(serving) == before


def test_reserved_path_rejections_preserve_prepared_workspace(environment, capsys):
    serving, corpus, dataset = environment
    code, prepared = invoke(capsys, arguments(corpus, dataset, '--prepare'))
    assert code == 0, prepared
    workspace = Path(prepared['workspace'])
    # Settle SQLite finalizers from preparation before measuring later writes.
    import gc
    gc.collect()
    before_workspace, before_serving = snapshot(workspace), snapshot(serving)
    for flag in ('--cache-dir', '--output'):
        targets = ['research_assistant.db', 'research_assistant.db/nested',
                   'indexes/qdrant', 'uploads', 'workspace.json', 'workspace.json/nested']
        if flag == '--output':
            targets.append('cache')
        for target in targets:
            code, result = invoke(capsys, arguments(
                corpus, dataset, '--prepare', '--workspace', workspace, flag, workspace / target,
            ))
            assert code == 1 and result['error_type'] == 'unsafe_evaluation_path', result
            assert flag in result['error_message']
    assert snapshot(workspace) == before_workspace
    assert snapshot(serving) == before_serving


@pytest.mark.parametrize('cache_path', ['cache', 'cache/generation/v1'])
@pytest.mark.parametrize('output_path', ['results', 'results/review'])
def test_dedicated_workspace_cache_and_results_work(environment, capsys, cache_path, output_path):
    serving, corpus, dataset = environment
    workspace = Path.cwd() / 'evaluation/workspaces/tiny'
    before = snapshot(serving)
    args = arguments(corpus, dataset, '--workspace', workspace,
                     '--cache-dir', workspace / cache_path, '--output', workspace / output_path)
    code, prepared = invoke(capsys, [*args, '--prepare'])
    assert code == 0, prepared
    code, reused = invoke(capsys, args)
    assert code == 0, reused
    assert list((workspace / cache_path).glob('*.json'))
    assert Path(reused['output_path']).is_relative_to(workspace / output_path)
    report = json.loads(Path(reused['output_path']).read_text())
    assert report['examples'][0]['cached_generation'] is True
    assert snapshot(serving) == before


@pytest.mark.parametrize('flag,target', [('--cache-dir', 'indexes/qdrant'), ('--output', 'cache')])
def test_aliases_cannot_bypass_reserved_workspace_paths(environment, capsys, flag, target):
    serving, corpus, dataset = environment
    workspace = Path.cwd() / 'evaluation/workspaces/tiny'
    alias = Path.cwd() / 'alias'
    alias.symlink_to(workspace / target, target_is_directory=True)
    before = snapshot(serving)
    code, result = invoke(capsys, arguments(
        corpus, dataset, '--prepare', '--workspace', workspace, flag, alias,
    ))
    assert code == 1 and result['error_type'] == 'unsafe_evaluation_path', result
    assert flag in result['error_message']
    assert not workspace.exists()
    assert snapshot(serving) == before
