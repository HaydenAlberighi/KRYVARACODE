"""
Unit tests for src/api/prediction/service.py - PredictionService
"""

from unittest.mock import Mock, patch

import pytest

from src.api.prediction.service import PredictionService
from src.db.models import PredictionLog

# =============================================================================
# Module-level fixtures (available to all test classes)
# =============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings."""
    with patch("src.api.prediction.service.settings") as mock:
        mock.MLFLOW_TRACKING_URI = "http://localhost:5000"
        mock.MODEL_NAME = "test_model"
        yield mock


@pytest.fixture
def mock_mlflow():
    """Mock MLflow availability."""
    mock_mlflow = Mock()
    mock_artifacts = Mock()
    mock_sklearn = Mock()
    mock_mlflow.artifacts = mock_artifacts
    mock_mlflow.sklearn = mock_sklearn
    mock_mlflow.tracking = Mock()
    mock_mlflow.tracking.MlflowClient = Mock()

    with (
        patch("src.api.prediction.service._MLFLOW_AVAILABLE", True),
        patch("src.api.prediction.service.mlflow", mock_mlflow),
        patch("src.api.prediction.service.mlflow_artifacts", mock_artifacts),
        patch("src.api.prediction.service.mlflow.sklearn", mock_sklearn),
    ):
        yield mock_mlflow


@pytest.fixture
def mock_pandas():
    """Mock pandas availability."""
    with (
        patch("src.api.prediction.service._PANDAS_AVAILABLE", True),
        patch("src.api.prediction.service.pd") as mock,
    ):
        yield mock


@pytest.fixture
def mock_feature_processor():
    """Mock FeatureProcessor."""
    with patch("src.api.prediction.service.FeatureProcessor") as mock:
        yield mock


@pytest.fixture
def prediction_service(mock_settings, mock_mlflow, mock_pandas, mock_feature_processor):
    """Create PredictionService with mocked dependencies."""
    import src.api.prediction.service as svc_module

    svc_module.prediction_service = None

    service = PredictionService()
    yield (
        service,
        {
            "mlflow": mock_mlflow,
            "pd": mock_pandas,
            "FeatureProcessor": mock_feature_processor,
        },
    )


@pytest.fixture
def service_with_model(prediction_service, mock_pandas):
    """Create service with mocked model."""
    service, mocks = prediction_service

    mock_model = Mock()
    mock_model.predict.return_value = [1]
    service.model = mock_model

    mock_df = Mock()
    mock_pandas.DataFrame.return_value = mock_df

    yield service, mocks, mock_model, mock_df


# =============================================================================
# Test Classes
# =============================================================================


class TestPredictionService:
    """Tests for PredictionService class."""

    def test_init_loads_model(self, prediction_service, mock_mlflow):
        """Test that initialization loads model from MLflow."""
        _service, mocks = prediction_service

        mocks["mlflow"].set_tracking_uri.assert_called_once()
        mocks["mlflow"].sklearn.load_model.assert_called()

    def test_init_handles_mlflow_unavailable(self, mock_settings):
        """Test initialization when MLflow is not available."""
        with (
            patch("src.api.prediction.service._MLFLOW_AVAILABLE", False),
            patch("src.api.prediction.service.logger") as mock_logger,
        ):
            service = PredictionService()

            assert service.model is None
            assert service.feature_processor is None
            mock_logger.warning.assert_called_with("MLflow not available — skipping model load")

    def test_get_model_info_no_model(self, prediction_service):
        """Test get_model_info when no model loaded."""
        service, _mocks = prediction_service
        service.model = None

        info = service.get_model_info()

        assert info == {"status": "no_model_loaded"}

    def test_get_model_info_with_model(self, prediction_service):
        """Test get_model_info with loaded model."""
        service, _mocks = prediction_service

        mock_model = Mock()
        mock_model.__class__.__name__ = "RandomForestClassifier"
        service.model = mock_model
        service.model_uri = "models:/test/Production"
        service.feature_processor = Mock()
        service.feature_processor.feature_names_in_ = ["feat1", "feat2"]

        info = service.get_model_info()

        assert info["status"] == "model_loaded"
        assert info["model_uri"] == "models:/test/Production"
        assert info["model_type"] == "RandomForestClassifier"
        assert info["has_feature_processor"] is True
        assert info["feature_processor_fitted"] is True

    def test_get_model_info_without_feature_processor(self, prediction_service):
        """Test get_model_info without feature processor."""
        service, _mocks = prediction_service

        service.model = Mock()
        service.model_uri = "models:/test/latest"
        service.feature_processor = None

        info = service.get_model_info()

        assert info["has_feature_processor"] is False
        assert info["feature_processor_fitted"] is False

    def test_reload_model(self, prediction_service, mock_settings):
        """Test reload_model calls _load_model_from_mlflow."""
        service, _mocks = prediction_service

        with patch.object(service, "_load_model_from_mlflow") as mock_load:
            service.reload_model()

            mock_load.assert_called_once_with(mock_settings.MLFLOW_TRACKING_URI)

    def test_predict_no_model(self, prediction_service):
        """Test predict raises error when no model loaded."""
        service, _mocks = prediction_service
        service.model = None

        with pytest.raises(RuntimeError, match="No model loaded"):
            service.predict({"feature1": 1.0})

    def test_predict_no_pandas(self, prediction_service):
        """Test predict raises error when pandas not available."""
        service, _mocks = prediction_service
        service.model = Mock()

        with (
            patch("src.api.prediction.service._PANDAS_AVAILABLE", False),
            pytest.raises(RuntimeError, match="requires pandas/numpy"),
        ):
            service.predict({"feature1": 1.0})

    def test_predict_without_feature_processor(self, prediction_service, mock_pandas):
        """Test predict without feature processor."""
        service, _mocks = prediction_service

        mock_model = Mock()
        mock_model.predict.return_value = [0]
        service.model = mock_model
        service.feature_processor = None

        mock_df = Mock()
        mock_pandas.DataFrame.return_value = mock_df

        with patch("src.api.prediction.service.time.perf_counter", side_effect=[0, 0.03]):
            result = service.predict({"feat1": 1.0})

        assert result["prediction"] == [0]
        mock_pandas.DataFrame.assert_called_once_with([{"feat1": 1.0}])

    def test_predict_logs_to_db(self, prediction_service, mock_pandas):
        """Test predict logs to database when db provided."""
        service, _mocks = prediction_service

        mock_model = Mock()
        mock_model.predict.return_value = [1]
        service.model = mock_model

        mock_db = Mock()
        mock_df = Mock()
        mock_pandas.DataFrame.return_value = mock_df

        with patch("src.api.prediction.service.time.perf_counter", side_effect=[0, 0.02]):
            service.predict({"feat1": 1.0}, db=mock_db, user_id=42)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        logged = mock_db.add.call_args[0][0]
        assert isinstance(logged, PredictionLog)
        assert logged.user_id == 42
        assert logged.model_version == service.model_uri
        assert logged.features == {"feat1": 1.0}
        assert logged.prediction == [1]

    def test_predict_logs_failure_rollback(self, prediction_service, mock_pandas):
        """Test predict rolls back on log failure."""
        service, _mocks = prediction_service

        mock_model = Mock()
        mock_model.predict.return_value = [1]
        service.model = mock_model

        mock_db = Mock()
        mock_db.commit.side_effect = Exception("DB error")
        mock_df = Mock()
        mock_pandas.DataFrame.return_value = mock_df

        with (
            patch("src.api.prediction.service.logger") as mock_logger,
            patch("src.api.prediction.service.time.perf_counter", side_effect=[0, 0.01]),
        ):
            service.predict({"feat1": 1.0}, db=mock_db)

        mock_db.rollback.assert_called_once()
        mock_logger.error.assert_called()

    def test_predict_handles_processor_not_fitted(self, prediction_service, mock_pandas):
        """Test predict handles unfitted feature processor."""
        service, _mocks = prediction_service

        mock_model = Mock()
        mock_model.predict.return_value = [1]
        service.model = mock_model

        mock_processor = Mock()
        del mock_processor.feature_names_in_
        service.feature_processor = mock_processor

        mock_df = Mock()
        mock_pandas.DataFrame.return_value = mock_df

        with (
            patch("src.api.prediction.service.logger") as mock_logger,
            patch("src.api.prediction.service.time.perf_counter", side_effect=[0, 0.01]),
        ):
            result = service.predict({"feat1": 1.0})

        assert result["prediction"] == [1]
        mock_logger.warning.assert_called()

    def test_predict_handles_processor_transform_error(self, prediction_service, mock_pandas):
        """Test predict handles feature processor transform error."""
        service, _mocks = prediction_service

        mock_model = Mock()
        mock_model.predict.return_value = [1]
        service.model = mock_model

        mock_processor = Mock()
        mock_processor.feature_names_in_ = ["feat1"]
        mock_processor.transform.side_effect = Exception("Transform failed")
        service.feature_processor = mock_processor

        mock_df = Mock()
        mock_pandas.DataFrame.return_value = mock_df

        with (
            patch("src.api.prediction.service.logger") as mock_logger,
            patch("src.api.prediction.service.time.perf_counter", side_effect=[0, 0.01]),
        ):
            result = service.predict({"feat1": 1.0})

        assert result["prediction"] == [1]
        mock_logger.warning.assert_called()

    def test_predict_handles_model_without_predict_proba(self, prediction_service, mock_pandas):
        """Test predict with model that lacks predict_proba."""
        service, _mocks = prediction_service

        mock_model = Mock()
        mock_model.predict.return_value = [1]
        del mock_model.predict_proba
        service.model = mock_model

        mock_df = Mock()
        mock_pandas.DataFrame.return_value = mock_df

        with patch("src.api.prediction.service.time.perf_counter", side_effect=[0, 0.01]):
            result = service.predict({"feat1": 1.0})

        assert "probabilities" not in result
        assert result["prediction"] == [1]

    def test_predict_handles_prediction_error(self, prediction_service, mock_pandas):
        """Test predict handles model prediction error."""
        service, _mocks = prediction_service

        mock_model = Mock()
        mock_model.predict.side_effect = Exception("Prediction failed")
        service.model = mock_model

        mock_df = Mock()
        mock_pandas.DataFrame.return_value = mock_df

        with (
            patch("src.api.prediction.service.logger") as mock_logger,
            pytest.raises(RuntimeError, match="Prediction failed"),
        ):
            service.predict({"feat1": 1.0})

        mock_logger.error.assert_called()


class TestPredictionServiceSingleton:
    """Tests for PredictionService singleton."""

    def test_singleton_instance(self):
        """Test that PredictionService can be instantiated."""
        service = PredictionService()
        assert isinstance(service, PredictionService)

    def test_singleton_can_create_multiple(self):
        """Test that we can create multiple instances."""
        service1 = PredictionService()
        service2 = PredictionService()
        assert isinstance(service1, PredictionService)
        assert isinstance(service2, PredictionService)


class TestLoadAssociatedFeatureProcessor:
    """Tests for _load_associated_feature_processor (requires MLflow mocking)."""

    @pytest.fixture
    def service_with_mlflow(self, mock_settings, mock_mlflow):
        """Create service with MLflow mocked."""
        import src.api.prediction.service as svc_module

        svc_module.prediction_service = None

        with patch("src.api.prediction.service._MLFLOW_AVAILABLE", True):
            # Create instance without calling __init__ to avoid auto-loading
            service = object.__new__(PredictionService)
            service.model = None
            service.feature_processor = None
            service.model_uri = None
            service.feature_processor_uri = None
            service.model_name = "test_model"
            yield service, mock_mlflow

    def test_load_associated_feature_processor_success(self, service_with_mlflow):
        """Test _load_associated_feature_processor success path."""
        service, mock_mlflow = service_with_mlflow

        mock_client = Mock()
        mock_mlflow.tracking.MlflowClient.return_value = mock_client

        mock_version = Mock()
        mock_version.run_id = "test_run_id"
        mock_client.get_latest_versions.return_value = [mock_version]

        mock_mlflow.artifacts.download_artifacts.return_value = "/tmp/feature_processor.pkl"

        with patch("src.api.prediction.service.FeatureProcessor") as mock_fp:
            mock_processor = Mock()
            mock_fp.load.return_value = mock_processor

            service._load_associated_feature_processor("models:/test/Production")

            mock_fp.load.assert_called_once_with("/tmp/feature_processor.pkl")
            assert service.feature_processor is mock_processor

    def test_load_associated_feature_processor_failure(self, service_with_mlflow):
        """Test _load_associated_feature_processor failure raises RuntimeError."""
        service, mock_mlflow = service_with_mlflow

        mock_mlflow.tracking.MlflowClient.side_effect = Exception("Client error")

        with pytest.raises(RuntimeError, match="Feature processor binding failed"):
            service._load_associated_feature_processor("models:/test/Production")


class TestLoadModelFromMlflow:
    """Tests for _load_model_from_mlflow (requires MLflow mocking)."""

    @pytest.fixture
    def service_with_mlflow(self, mock_settings, mock_mlflow):
        """Create service with MLflow mocked."""
        import src.api.prediction.service as svc_module

        svc_module.prediction_service = None

        with patch("src.api.prediction.service._MLFLOW_AVAILABLE", True):
            # Create instance without calling __init__ to avoid auto-loading
            service = object.__new__(PredictionService)
            service.model = None
            service.feature_processor = None
            service.model_uri = None
            service.feature_processor_uri = None
            service.model_name = "test_model"
            yield service, mock_mlflow

    def test_load_model_fallback_to_latest(self, service_with_mlflow):
        """Test _load_model_from_mlflow falls back to latest."""
        service, mock_mlflow = service_with_mlflow

        # First call (production) fails, second (latest) succeeds
        mock_model = Mock()
        mock_mlflow.sklearn.load_model.side_effect = [Exception("No prod"), mock_model]

        # Mock the feature processor loading to avoid complex MLflow mocking
        with patch.object(service, "_load_associated_feature_processor"):
            service._load_model_from_mlflow("http://localhost:5000")

        assert service.model is mock_model
        assert mock_mlflow.sklearn.load_model.call_count == 2

    def test_load_model_both_fail(self, service_with_mlflow):
        """Test _load_model_from_mlflow when both production and latest fail."""
        service, mock_mlflow = service_with_mlflow

        mock_mlflow.sklearn.load_model.side_effect = Exception("Failed")

        with patch("src.api.prediction.service.logger") as mock_logger:
            service._load_model_from_mlflow("http://localhost:5000")

        assert service.model is None
        assert service.feature_processor is None
        mock_logger.warning.assert_called()


class TestPredictEdgeCases:
    """Additional edge case tests for predict method."""

    def test_predict_returns_numpy_array(self, service_with_model):
        """Test predict handles numpy array prediction."""
        service, _mocks, mock_model, _mock_df = service_with_model

        import numpy as np

        mock_model.predict.return_value = np.array([1, 2, 3])
        mock_model.predict_proba.return_value = np.array([[0.1, 0.9], [0.2, 0.8], [0.3, 0.7]])

        with patch("src.api.prediction.service.time.perf_counter", side_effect=[0, 0.01]):
            result = service.predict({"feat1": 1.0})

        assert result["prediction"] == [1, 2, 3]
        assert result["probabilities"] == [[0.1, 0.9], [0.2, 0.8], [0.3, 0.7]]

    def test_predict_with_list_features(self, service_with_model):
        """Test predict with list feature values."""
        service, _mocks, _mock_model, _mock_df = service_with_model

        with patch("src.api.prediction.service.time.perf_counter", side_effect=[0, 0.01]):
            result = service.predict({"feat1": [1, 2, 3]})

        assert result["prediction"] == [1]
