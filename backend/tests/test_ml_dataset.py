import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from types import SimpleNamespace
import pytest
from app.fsm.engine import evaluate
from app.ml.dataset import build_dataset, METADATA_COLUMNS
from app.ml.features import ActivityEvent, FEATURE_NAMES, extract_features, feature_vector, from_security_events
from app.ml.synthetic import generate_sessions, make_events, split_recipes, HELDOUT_SCENARIOS, SCENARIOS
import random


def event(kind, seconds, path='/api/bank/balance'):
    return ActivityEvent(kind, seconds, path)


def test_hand_calculated_features_and_fixed_order():
    events = [event('LOGIN_ATTEMPT', 0, '/api/auth/login'), event('LOGIN_SUCCESS', 0, '/api/auth/login'),
              event('VIEW_BALANCE', 2), event('LOGOUT', 6, '/api/auth/logout')]
    features = extract_features(events)
    assert features['event_count'] == 4
    assert features['session_duration_seconds'] == 6
    assert features['request_frequency'] == .5
    assert features['average_inter_event_seconds'] == 2
    assert features['minimum_inter_event_seconds'] == 0
    assert features['short_interval_ratio'] == pytest.approx(1/3)
    assert features['distinct_endpoint_count'] == 3
    assert features['invalid_transition_count'] == 0
    assert features['event_fraction:VIEW_BALANCE'] == .25
    assert features['transition_fraction:AUTHENTICATED:VIEWING_ACCOUNT'] == .25
    assert list(features) == list(FEATURE_NAMES)
    assert feature_vector(events) == list(features.values())
    assert len(features) == 90


def test_unknown_events_sink_and_finite_zero_duration():
    features = extract_features([event('NOT_IN_ALPHABET', 7), event('VIEW_BALANCE', 7)])
    assert features['unknown_event_count'] == 1
    assert features['invalid_transition_count'] == 2
    assert features['invalid_transition_rate'] == 1
    assert features['request_frequency'] == 1
    assert all(math.isfinite(value) for value in features.values())
    assert all(value == 0 for value in extract_features([]).values())
    assert all(math.isfinite(value) for value in extract_features([event('LOGIN_ATTEMPT', 0)]).values())
    assert extract_features([event('VIEW_BALANCE', 1)], 'AUTHENTICATED')['invalid_transition_count'] == 0


@pytest.mark.parametrize('timestamp', [float('nan'), float('inf'), -float('inf'), True, 'bad'])
def test_bad_timestamps(timestamp):
    with pytest.raises(ValueError):
        event('VIEW_BALANCE', timestamp)


def test_order_validation_and_event_contract():
    with pytest.raises(ValueError):
        extract_features([event('LOGIN_ATTEMPT', 3), event('LOGIN_SUCCESS', 2)])
    with pytest.raises(ValueError):
        ActivityEvent('', 0, '/api')
    with pytest.raises(ValueError):
        ActivityEvent('VIEW_BALANCE', 0, 'not-an-api-path')
    with pytest.raises(ValueError):
        extract_features([], initial_state='NOT_A_STATE')


def test_live_database_adapter_uses_same_contract():
    rows = [SimpleNamespace(event_type='LOGIN_ATTEMPT', created_at=datetime(2025, 1, 1), endpoint='/api/auth/login'),
            SimpleNamespace(event_type='LOGIN_SUCCESS', created_at=datetime(2025, 1, 1, 0, 0, 2, tzinfo=timezone.utc), endpoint='/api/auth/login')]
    observed = from_security_events(rows)
    synthetic = (event('LOGIN_ATTEMPT', 1735689600, '/api/auth/login'), event('LOGIN_SUCCESS', 1735689602, '/api/auth/login'))
    assert observed == synthetic
    assert feature_vector(observed) == feature_vector(synthetic)
    # Absolute clock time is deliberately absent from model inputs.
    assert feature_vector(synthetic) == feature_vector([event(e.event_type, e.timestamp+9000, e.endpoint) for e in synthetic])


def test_deterministic_generation_and_recipe_splits():
    assert list(generate_sessions(20, 42)) == list(generate_sessions(20, 42))
    assert list(generate_sessions(20, 42)) != list(generate_sessions(20, 43))
    partitions = split_recipes(42)
    for scenario in SCENARIOS:
        splits = [partitions[scenario, recipe] for recipe in range(20)]
        if scenario in HELDOUT_SCENARIOS:
            assert set(splits) == {'held_out'}
        else:
            assert splits.count('train') == 14
            assert splits.count('validation') == 3
            assert splits.count('test') == 3


@pytest.mark.parametrize('count', [0, -1, True, 1.5])
def test_invalid_dataset_size(count, tmp_path):
    with pytest.raises(ValueError):
        build_dataset(tmp_path/'invalid', count=count)
    assert not (tmp_path/'invalid').exists()


def test_labels_are_not_equivalent_to_dfa_violations():
    for scenario in SCENARIOS:
        events = make_events(scenario, 5, random.Random(42), 0)
        report = evaluate([e.event_type for e in events])
        features = extract_features(events)
        assert all(math.isfinite(value) for value in features.values())
        if SCENARIOS[scenario][0] == 0:
            assert report['accepted']
        if scenario in {'failed_login_burst', 'rapid_requests', 'transfer_burst', 'heldout_paced_transfer'}:
            assert SCENARIOS[scenario][0] == 1 and report['invalid_transition_count'] == 0


def test_reproducible_export_integrity_no_group_overlap_and_no_label_features(tmp_path):
    first, second = tmp_path/'first', tmp_path/'second'
    manifest = build_dataset(first, count=600, seed=42)
    assert manifest == build_dataset(second, count=600, seed=42)
    for filename in ('features.csv', 'sessions.jsonl', 'manifest.json'):
        assert (first/filename).read_bytes() == (second/filename).read_bytes()
    assert set(manifest['split_counts']) == {'train', 'validation', 'test', 'held_out'}
    assert sum(manifest['split_counts'].values()) == 600
    assert not set(METADATA_COLUMNS) & set(FEATURE_NAMES)
    for name, details in manifest['files'].items():
        assert hashlib.sha256((first/name).read_bytes()).hexdigest() == details['sha256']
    with (first/'features.csv').open() as handle:
        features = list(csv.DictReader(handle))
    raw = [json.loads(line) for line in (first/'sessions.jsonl').read_text().splitlines()]
    assert len({s['session_id'] for s in raw}) == 600
    group_partitions = {}
    for row, session in zip(features, raw, strict=True):
        group_partitions.setdefault(row['group_id'], set()).add(row['split'])
        assert row['session_id'] == session['session_id']
        assert float(row['event_count']) == len(session['events'])
        if row['scenario'] in HELDOUT_SCENARIOS:
            assert row['split'] == 'held_out'
        else:
            assert row['split'] != 'held_out'
    assert all(len(splits) == 1 for splits in group_partitions.values())
    with pytest.raises(FileExistsError):
        build_dataset(first, count=600, seed=42)
    assert json.loads((first/'manifest.json').read_text()) == manifest
