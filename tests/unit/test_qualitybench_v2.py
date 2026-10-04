"""Frozen benchmark integrity checks; no retrieval, generation, or downloads."""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from research_assistant.chunking.config import default_config
from research_assistant.chunking.structure import StructureAwareChunker
from research_assistant.core.types import ContentType
from research_assistant.evaluation.dataset import load_dataset, validate_dataset
from research_assistant.evaluation.identity import METRICS_SCHEMA
from research_assistant.evaluation.quality_metrics import key_fact_hits, key_fact_recall, quality_aggregates
from research_assistant.evaluation.quality_taxonomy import CONFLICT_HANDLING_FAILURE, classify_quality
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
        assert len({tuple(row['key_facts']) for row in members}) == 1, name


def test_key_facts_are_complete_compact_and_serialized(benchmark):
    rows, _ = benchmark
    answerable = [row for row in rows if row['answerable']]
    unanswerable = [row for row in rows if not row['answerable']]
    assert len(answerable) == 80 and all(row.get('key_facts') for row in answerable)
    assert len(unanswerable) == 16 and all(not row.get('key_facts') for row in unanswerable)
    loaded = {example.example_id: example for example in load_dataset(DATASET).examples}
    for row in answerable:
        facts = row['key_facts']
        identifier = row['example_id']
        assert isinstance(facts, list), identifier
        assert all(isinstance(fact, str) and fact.strip() == fact and fact for fact in facts), identifier
        assert all(len(fact) <= 64 and len(fact.split()) <= 10 for fact in facts), identifier
        # Bare 1–3 digit integers can match inside unrelated counts. Four-digit
        # years, decimals, percentages, identifiers, and values with units remain valid.
        assert all(re.fullmatch(r'[0-9]{1,3}', fact) is None for fact in facts), identifier
        assert len(set(map(normalized, facts))) == len(facts), identifier
        # Avoid labels such as "9" and "90" that count one component twice.
        assert not any(normalized(a) in normalized(b) for a in facts for b in facts if a != b), identifier
        # Reference phrasing may differ from gold; do not require gold substrings.
        assert key_fact_recall(row['reference_answer'], facts) == 1.0, identifier
        assert loaded[identifier].key_facts == tuple(facts), identifier
        assert loaded[identifier].to_dict()['key_facts'] == facts, identifier


def test_key_facts_cover_multiple_components(benchmark):
    rows, _ = benchmark
    multiple = [row for row in rows if max(len(row['gold_passages']), len(row.get('claims', []))) > 1]
    assert len(multiple) == 16
    for row in multiple:
        assert len(row['key_facts']) >= max(len(row['gold_passages']), len(row.get('claims', []))), row['example_id']
    conflicts = [row for row in rows if row.get('expected_conflict')]
    assert len(conflicts) == 6
    assert all(len(row['key_facts']) >= 2 for row in conflicts)
    # One short passage can still supply several required answer components.
    required = {
        'qb2-008': {'3.6 mA', 'indicator off'},
        'qb2-034': {'24 ms', '24 s'},
        'qb2-039': {'92.6%', 'staffed weekday sample'},
        'qb2-058': {'Ivo Marr', 'Sora Finn'},
        'qb2-064': {'0.7 degrees Celsius', 'unshielded test mount'},
        'qb2-079': {'searchable as historical sources', 'not current instructions'},
        'qb2-082': {'36 ms', '36 s'},
        'qb2-091': {'in 7 of 60 answer records'},
    }
    by_id = {row['example_id']: row for row in rows}
    for identifier, components in required.items():
        assert components <= set(by_id[identifier]['key_facts']), identifier


def test_answer_record_relation_rejects_numeric_substring_collision():
    example = next(item for item in load_dataset(DATASET).examples if item.example_id == 'qb2-091')
    assert key_fact_recall(example.reference_answer, example.key_facts) == 1.0
    # The leading relation word prevents the correct 7 from matching within 17.
    for incorrect in ('17 of 60 answer records',
                      'Source labels were lost in 17 of 60 answer records.',
                      'Source labels were lost in 7 of 160 answer records.'):
        assert key_fact_recall(incorrect, example.key_facts) == 0.0


def test_current_and_qualified_labels_preserve_question_scope(benchmark):
    rows, _ = benchmark
    by_id = {row['example_id']: row for row in rows}
    current = {'qb2-007': ['78%'], 'qb2-021': ['78%'], 'qb2-031': ['0.83'],
               'qb2-055': ['12 minutes'], 'qb2-056': ['0.64 kWh per day'], 'qb2-083': ['87%']}
    for identifier, facts in current.items():
        assert by_id[identifier]['key_facts'] == facts, identifier
    assert {'74%', '78%'} <= set(by_id['qb2-013']['key_facts'])
    assert by_id['qb2-020']['key_facts'] == ['74%']  # Selected historical protocol.
    assert by_id['qb2-067']['key_facts'] == ['15 minutes']
    qualified = {
        'qb2-012': 'production deployment is not',
        'qb2-025': 'without collecting face images',
        'qb2-028': 'income cannot be inferred',
        'qb2-042': 'weekend departures are excluded',
        'qb2-045': 'not automatic dispatch control',
        'qb2-060': 'fog-wetted shield readings are excluded',
        'qb2-076': 'handwritten annotations are not evaluated',
    }
    for identifier, fact in qualified.items():
        assert fact in by_id[identifier]['key_facts'], identifier


def test_dataset_contains_labels_not_execution_results(benchmark):
    rows, _ = benchmark
    allowed = {'example_id', 'split', 'category', 'slice', 'question', 'answerable',
               'relevant_filenames', 'gold_passages', 'tags', 'reference_answer',
               'expected_insufficient', 'notes', 'claims', 'expected_conflict',
               'selected_filenames', 'history', 'paraphrase_group', 'key_facts',
               'expected_resolved_contains', 'expected_resolved_must_not', 'forbidden_facts'}
    for row in rows:
        # Reject traces, ranked hits, generated answers, scores, and ad hoc
        # labeling metadata. Supplied conversation history is authored input.
        assert set(row) <= allowed, row['example_id']
        for gold in row['gold_passages']:
            assert set(gold) == {'filename', 'text'}
        for claim in row.get('claims', []):
            assert set(claim) == {'claim_id', 'text', 'filename', 'gold_text'}
        for turn in row.get('history', []):
            assert set(turn) == {'question', 'answer', 'grounding_status'}


@pytest.mark.parametrize('identifier', [
    'qb2-014', 'qb2-015', 'qb2-036', 'qb2-037', 'qb2-062', 'qb2-084',
])
def test_conflict_labels_detect_either_missing_side(identifier):
    example = next(item for item in load_dataset(DATASET).examples if item.example_id == identifier)

    def diagnostic_row(answer):
        # An authored text fixture, not a retrieval/generation run or stored trace.
        return {'example_id': identifier, 'answer_text': answer, 'validation_status': 'valid',
                'insufficient_evidence': False, 'rendered_gold_all': True,
                'lexical_key_fact_hits': key_fact_hits(answer, example.key_facts),
                'lexical_key_fact_recall': key_fact_recall(answer, example.key_facts)}

    for gold in example.gold_passages:
        one_side = diagnostic_row(gold.text)
        assert sum(one_side['lexical_key_fact_hits']) == 1
        assert classify_quality(example, one_side)[0] == CONFLICT_HANDLING_FAILURE
        assert quality_aggregates([one_side], [example])['conflict']['true_conflict_both_key_facts'] == 0
    complete = diagnostic_row(example.reference_answer)
    assert classify_quality(example, complete)[0] is None
    assert quality_aggregates([complete], [example])['conflict']['true_conflict_both_key_facts'] == 1


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
