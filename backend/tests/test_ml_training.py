import pytest
np = pytest.importorskip("numpy")
pytest.importorskip('sklearn')
pytest.importorskip('pandas')
from app.ml.dataset import build_dataset
from app.ml.features import BASE_FEATURES, FEATURE_NAMES, feature_vector
from app.ml.inference import DetectorBundle
from app.ml.metrics import classification_metrics, select_threshold
from app.ml.observations import load_observations, prefix_label
from app.ml.synthetic import make_events
from app.ml.train import train_models
import random


@pytest.fixture(scope='module')
def trained(tmp_path_factory):
    root = tmp_path_factory.mktemp('training')
    dataset, artifacts = root/'dataset', root/'artifacts'
    build_dataset(dataset, count=500, seed=42)
    report = train_models(dataset, artifacts, trees=12)
    return dataset, artifacts, report


def test_metrics_against_known_confusion_matrix():
    result = classification_metrics([0, 0, 1, 1], [0, 1, 0, 1])
    assert result['confusion_matrix'] == [[1, 1], [1, 1]]
    assert result['accuracy'] == .5
    assert result['precision'] == .5 and result['recall'] == .5 and result['f1'] == .5
    assert result['false_positive_rate'] == .5


def test_threshold_uses_validation_fpr_constraint():
    labels = np.array([0, 0, 1, 1])
    scores = np.array([.1, .2, .8, .9])
    threshold = select_threshold(labels, scores)
    assert .2 < threshold <= .8
    assert classification_metrics(labels, scores >= threshold)['f1'] == 1


def test_prefixes_have_no_future_attack_label_or_partition_leakage(trained):
    dataset, _, _ = trained
    observations, _ = load_observations(dataset)
    assert set(observations.observation) == {'complete', 'prefix'}
    assert observations.groupby('session_id').split.nunique().max() == 1
    assert observations.groupby('group_id').split.nunique().max() == 1
    events = make_events('transfer_burst', 3, random.Random(42), 0)
    assert prefix_label('transfer_burst', 1, events[:2]) == 0
    assert prefix_label('transfer_burst', 1, events[:14]) == 1
    assert prefix_label('normal_transfer', 0, events) == 0


def test_saved_model_inference_parity_and_finite_evidence(trained):
    _, artifacts, report = trained
    detector = DetectorBundle.load(artifacts)
    for scenario in ('normal_browsing', 'failed_login_burst', 'heldout_paced_transfer'):
        events = make_events(scenario, 5, random.Random(17), 0)
        result = detector.predict(events, complete=True)
        features = np.asarray([feature_vector(events)])
        assert result['random_forest']['score'] == pytest.approx(detector.bundle['random_forest'].predict_proba(features)[0, 1])
        assert result['isolation_forest']['raw_anomaly_score'] == pytest.approx(-detector.bundle['isolation_forest'].score_samples(features)[0])
        assert 0 <= result['isolation_forest']['anomaly_evidence'] <= 1
        assert 0 <= result['isolation_forest']['normal_reference_percentile'] <= 1
        assert result['provisional'] is False
        assert detector.predict(events[:2])['provisional'] is True
    assert len(detector.bundle['feature_schema']['feature_names']) == len(FEATURE_NAMES)
    assert report['isolation_training_normal_observations'] == report['training_labels']['0']
    assert report['isolation_training_normal_observations'] < report['observation_counts']['train']
    assert set(report['models']) == {'random_forest', 'isolation_forest'}
    for model in report['models'].values():
        assert model['metrics']['validation']['all_observations']['false_positive_rate'] <= .05
        assert model['metrics']['test']['complete']['samples'] == report['dataset']['split_sessions']['test']
        assert model['metrics']['held_out']['complete']['samples'] == report['dataset']['split_sessions']['held_out']
        assert model['latency']['median_ms'] >= 0
    with pytest.raises(ValueError):
        detector.predict([])


def test_load_rejects_corrupt_artifacts_and_incompatible_contract(trained, tmp_path):
    _, artifacts, _ = trained
    detector = DetectorBundle.load(artifacts)
    with pytest.raises(ValueError, match='feature contract'):
        DetectorBundle({**detector.bundle, 'feature_schema': {}})
    with pytest.raises(ValueError, match='version mismatch'):
        DetectorBundle({**detector.bundle, 'sklearn_version': 'wrong'})
    (tmp_path/'artifact-manifest.json').write_bytes((artifacts/'artifact-manifest.json').read_bytes())
    (tmp_path/'detectors.joblib').write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='checksum'):
        DetectorBundle.load(tmp_path)


def test_dataset_tampering_and_model_overwrite_are_rejected(trained, tmp_path):
    dataset, artifacts, _ = trained
    with pytest.raises(FileExistsError):
        train_models(dataset, artifacts, trees=12)
    for path in dataset.iterdir():
        (tmp_path/path.name).write_bytes(path.read_bytes())
    with (tmp_path/'features.csv').open('a') as handle:
        handle.write('corrupt\n')
    with pytest.raises(ValueError, match='checksum'):
        load_observations(tmp_path)


def test_predictions_reproduce_with_same_seed(trained, tmp_path):
    dataset, artifacts, first_report = trained
    second_report = train_models(dataset, tmp_path/'second', trees=12)
    first, second = DetectorBundle.load(artifacts), DetectorBundle.load(tmp_path/'second')
    events = make_events('normal_transfer', 8, random.Random(42), 0)
    assert first.predict(events) == second.predict(events)
    for name in first_report['models']:
        assert first_report['models'][name]['threshold'] == second_report['models'][name]['threshold']
        assert first_report['models'][name]['metrics'] == second_report['models'][name]['metrics']


def test_saved_evaluation_matches_training_without_fitting(trained, monkeypatch):
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    from app.ml.evaluate import evaluate_saved
    def must_not_fit(*args, **kwargs):
        raise AssertionError("Saved evaluation must not fit models")
    monkeypatch.setattr(RandomForestClassifier, 'fit', must_not_fit)
    monkeypatch.setattr(IsolationForest, 'fit', must_not_fit)
    dataset, artifacts, report = trained
    result = evaluate_saved(dataset, artifacts)
    assert result == {name: model['metrics'] for name, model in report['models'].items()}


def test_fit_and_threshold_selection_use_only_intended_partitions(trained, tmp_path, monkeypatch):
    import app.ml.train as training
    from sklearn.ensemble import RandomForestClassifier, IsolationForest
    dataset, _, _ = trained
    observations, _ = load_observations(dataset)
    train = observations[observations.split == 'train']
    validation = observations[observations.split == 'validation']
    rf_fit, isolation_fit, threshold = RandomForestClassifier.fit, IsolationForest.fit, training.select_threshold
    calls = []
    def fit_rf(self, features, labels):
        assert np.array_equal(features, train[list(FEATURE_NAMES)].to_numpy(dtype=float))
        assert np.array_equal(labels, train.label.to_numpy(dtype=int))
        calls.append('rf')
        return rf_fit(self, features, labels)
    def fit_isolation(self, features, labels=None):
        assert labels is None
        expected = train[train.label == 0][list(BASE_FEATURES)].to_numpy(dtype=float)
        assert np.array_equal(features, expected)
        calls.append('isolation')
        return isolation_fit(self, features)
    def validation_threshold(labels, scores):
        assert np.array_equal(labels, validation.label.to_numpy(dtype=int))
        calls.append('threshold')
        return threshold(labels, scores)
    monkeypatch.setattr(RandomForestClassifier, 'fit', fit_rf)
    monkeypatch.setattr(IsolationForest, 'fit', fit_isolation)
    monkeypatch.setattr(training, 'select_threshold', validation_threshold)
    training.train_models(dataset, tmp_path/'checked', trees=4)
    assert calls == ['rf', 'isolation', 'threshold', 'threshold']


def test_isolation_projection_is_saved_and_uses_base_activity_features(trained):
    _, artifacts, report = trained
    detector = DetectorBundle.load(artifacts)
    pipeline = detector.bundle["isolation_forest"]
    assert pipeline.n_features_in_ == len(FEATURE_NAMES)
    assert pipeline.named_steps["detector"].n_features_in_ == len(BASE_FEATURES)
    assert report["isolation_feature_names"] == list(BASE_FEATURES)
