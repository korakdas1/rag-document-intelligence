"""Frozen benchmark integrity checks; no retrieval, generation, or downloads."""

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from research_assistant.chunking.config import default_config
from research_assistant.chunking.structure import StructureAwareChunker
from research_assistant.core.types import ContentType
from research_assistant.evaluation.dataset import load_dataset, validate_dataset
from research_assistant.evaluation.identity import METRICS_SCHEMA
from research_assistant.parsing.markdown import MarkdownParser
from research_assistant.parsing.protocol import ParseInput

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / 'evaluation/datasets/qualitybench_v2.jsonl'
CORPUS = ROOT / 'evaluation/corpus/quality_v2'
FAMILIES = {'northstar', 'meridian', 'kestrel', 'atlas'}
SLICES = {'core', 'hard_negative', 'versioning', 'multisource', 'longdoc',
          'conflict', 'unanswerable', 'followup', 'subset', 'paraphrase'}


def normalized(text):
    return ' '.join(text.casefold().split())


@pytest.fixture(scope='module')
def benchmark():
    rows = [json.loads(line) for line in DATASET.read_text(encoding='utf-8').splitlines()]
    files = {path.name: path.read_text(encoding='utf-8') for path in CORPUS.glob('*.md')}
    return rows, files


def test_counts_identity_and_document_lengths(benchmark):
    rows, files = benchmark
    dataset = load_dataset(DATASET)
    validate_dataset(dataset, corpus_dir=CORPUS)
    assert dataset.dataset_id == 'qualitybench_v2'
    assert METRICS_SCHEMA == 'evidence-metrics.v2'
    assert len(rows) == 96
    assert Counter(row['split'] for row in rows) == {'dev': 24, 'test': 72}
    assert Counter(row['answerable'] for row in rows) == {True: 80, False: 16}
    assert len({row['example_id'] for row in rows}) == 96
    assert len({normalized(row['question']) for row in rows}) == 96
    assert len(files) == 20
    assert {p.name for p in CORPUS.iterdir()} == set(files)
    assert Counter(name.split('_')[0] for name in files) == dict.fromkeys(FAMILIES, 5)
    sizes = [len(body.encode('utf-8')) for body in files.values()]
    assert 70_000 <= sum(sizes) <= 100_000
    assert sum(1_000 <= size <= 2_000 for size in sizes) == 6
    assert sum(2_500 <= size <= 5_000 for size in sizes) == 10
    assert sum(8_000 <= size <= 12_000 for size in sizes) == 4


def test_gold_claims_answerability_and_scope(benchmark):
    rows, files = benchmark
    referenced = set()
    for row in rows:
        identifier = row['example_id']
        assert row['question'].strip(), identifier
        assert 'relevant_chunk_ids' not in row, identifier
        passages = row['gold_passages']
        relevant = set(row['relevant_filenames'])
        selected = set(row.get('selected_filenames', []))
        assert relevant <= files.keys(), identifier
        assert selected <= files.keys(), identifier
        assert relevant == {gold['filename'] for gold in passages}, identifier
        referenced.update(relevant)
        assert row['answerable'] is bool(passages), identifier
        if not row['answerable']:
            assert row['expected_insufficient'] is True, identifier
            assert row['notes'].strip(), identifier
            assert not row.get('claims'), identifier
        else:
            assert not row.get('expected_insufficient', False), identifier
            assert row['reference_answer'].strip(), identifier
        for gold in passages:
            assert gold['text'].strip() and len(gold['text']) <= 250, identifier
            assert gold['filename'] in files, identifier
            assert files[gold['filename']].count(gold['text']) == 1, (identifier, gold)
            assert not selected or gold['filename'] in selected, identifier
        pairs = {(gold['filename'], gold['text']) for gold in passages}
        claims = row.get('claims', [])
        assert len({claim['claim_id'] for claim in claims}) == len(claims), identifier
        for claim in claims:
            assert all(claim[field].strip() for field in ('claim_id', 'text', 'filename', 'gold_text')), identifier
            assert (claim['filename'], claim['gold_text']) in pairs, identifier
        for forbidden in row.get('forbidden_facts', []):
            assert normalized(forbidden) not in normalized(row['reference_answer']), identifier
        if row.get('expected_conflict'):
            assert row['split'] == 'test' and len(relevant) >= 2, identifier
            assert 'superseded' not in row['tags'], identifier
    assert referenced == files.keys()


def test_split_leakage_and_controlled_paraphrases(benchmark):
    rows, _ = benchmark
    passages = defaultdict(set)
    groups = defaultdict(list)
    for row in rows:
        passages[row['split']].update(normalized(gold['text']) for gold in row['gold_passages'])
        if row.get('paraphrase_group'):
            groups[row['paraphrase_group']].append(row)
    # Compare text globally, not just (filename, text): copying to another source
    # must not hide a cross-split duplicate.
    assert not passages['dev'] & passages['test']
    assert len(groups) == 3
    for name, members in groups.items():
        assert len(members) == 3, name
        assert len({row['split'] for row in members}) == 1, name
        assert len({json.dumps(row['gold_passages'], sort_keys=True) for row in members}) == 1, name
        assert len({tuple(row.get('selected_filenames', [])) for row in members}) == 1, name


def test_distribution_and_difficulty_coverage(benchmark):
    rows, files = benchmark
    categories = Counter(row['category'] for row in rows)
    slices = Counter(row['slice'] for row in rows)
    test_slices = Counter(row['slice'] for row in rows if row['split'] == 'test')
    references = Counter(name for row in rows for name in set(row['relevant_filenames']))
    distribution = {'categories': dict(categories), 'slices': dict(slices),
                    'test_slices': dict(test_slices), 'source_references': dict(references)}
    print(json.dumps(distribution, sort_keys=True, indent=2))
    assert max(categories.values()) <= len(rows) * .25, distribution
    assert set(slices) == SLICES, distribution
    assert all(test_slices[slice_] >= 2 for slice_ in SLICES), distribution
    assert set(references) == set(files), distribution
    assert max(references.values()) <= len(rows) * .20, distribution
    assert sum(len(row['gold_passages']) > 1 for row in rows) >= 12
    assert sum(len(row['relevant_filenames']) > 1 for row in rows) >= 12
    assert 12 <= sum(not row['answerable'] for row in rows) <= 16
    assert 5 <= sum(row.get('expected_conflict', False) for row in rows) <= 6
    assert 5 <= sum(bool(row.get('selected_filenames')) for row in rows) <= 6
    assert 6 <= sum(bool(row.get('history')) for row in rows) <= 8
    assert sum('near_duplicate' in row['tags'] for row in rows) >= 12
    assert test_slices['versioning'] >= 4
    assert test_slices['hard_negative'] >= 4
    for row in rows:
        if row.get('history'):
            assert all(turn.get('question') and turn.get('answer') for turn in row['history'])
            assert row.get('expected_resolved_contains'), row['example_id']
            assert row.get('expected_resolved_must_not'), row['example_id']
            history_text = normalized(json.dumps(row['history']))
            assert all(normalized(term) in history_text for term in row['expected_resolved_contains'])


def test_long_documents_have_early_middle_late_and_distant_gold(benchmark):
    rows, files = benchmark
    long_files = {name: body for name, body in files.items() if len(body.encode()) >= 8_000}
    assert len(long_files) == 4
    for name, body in long_files.items():
        positions = [body.index(gold['text']) / len(body) for row in rows
                     if row['split'] == 'test' and row['slice'] == 'longdoc'
                     for gold in row['gold_passages'] if gold['filename'] == name]
        assert any(pos < .25 for pos in positions), name
        assert any(.35 <= pos <= .65 for pos in positions), name
        assert any(pos > .75 for pos in positions), name
        distant = []
        for row in rows:
            if row['split'] != 'test' or set(row['relevant_filenames']) != {name}:
                continue
            offsets = [body.index(gold['text']) / len(body) for gold in row['gold_passages']]
            if len(offsets) > 1 and max(offsets) - min(offsets) > .60:
                distant.append(row['example_id'])
        assert distant, name


def test_all_gold_resolves_under_default_structure_chunker(benchmark):
    rows, _ = benchmark
    config = default_config()
    chunks = {}
    for path in sorted(CORPUS.glob('*.md')):
        parsed = MarkdownParser().parse(ParseInput(
            document_id=path.stem, path=path, data=path.read_bytes(),
            content_type=ContentType.MARKDOWN,
        ))
        chunks[path.name] = StructureAwareChunker().chunk(parsed, config)
    checked = Counter()
    for row in rows:
        for gold in row['gold_passages']:
            assert any(normalized(gold['text']) in normalized(chunk.text)
                       for chunk in chunks[gold['filename']]), (row['example_id'], gold)
            checked[row['split']] += 1
    print(f'Default structure chunker: {dict(checked)} passage labels resolved; '
          f'{sum(len(items) for items in chunks.values())} chunks; no retrieval run.')


@pytest.mark.parametrize('name,version', [
    ('qualitybench_v1', 'qualitybench.v1'),
    ('qualitybench_v2', 'qualitybench.v2'),
])
def test_dataset_version_metadata(name, version):
    assert load_dataset(ROOT / f'evaluation/datasets/{name}.jsonl').version == version
