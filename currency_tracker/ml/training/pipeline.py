# ============================================
# CurrencyTracker - ML Training Pipeline
# ============================================

import mlflow
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import structlog
import json
import os

from currency_tracker.ml.features.engineering import FeatureEngineer, FeatureConfig, create_lagged_dataset
from currency_tracker.ml.models.registry import (
    ModelFactory, ModelConfig, BaseModel, EnsembleModel
)
from currency_tracker.storage.repository import RateRepository
from currency_tracker.storage.models import ModelRegistry
from currency_tracker.config.settings import get_settings

logger = structlog.get_logger()


@dataclass
class TrainingConfig:
    """Configuração do pipeline de treino"""
    target_currency: str
    base_currency: str = "BRL"
    model_types: List[str] = None
    prediction_horizon: int = 1  # dias
    lookback_days: int = 365
    test_size: float = 0.2
    validation_size: float = 0.1
    feature_config: FeatureConfig = None
    hyperparameter_tuning: bool = False
    n_trials: int = 50
    mlflow_experiment: str = "currency-prediction"
    register_best: bool = True
    min_training_samples: int = 100

    def __post_init__(self):
        if self.model_types is None:
            self.model_types = ["ridge", "random_forest", "xgboost", "lightgbm"]
        if self.feature_config is None:
            self.feature_config = FeatureConfig()


class TrainingPipeline:
    """Pipeline completo de treino de modelos"""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.settings = get_settings()
        self.repository = RateRepository()
        self.feature_engineer = FeatureEngineer(config.feature_config)

        # Setup MLflow
        mlflow.set_tracking_uri(self.settings.ml.mlflow_tracking_uri)
        mlflow.set_experiment(config.mlflow_experiment)

        self.results = {}

    async def initialize(self):
        """Inicializa conexões"""
        await self.repository.initialize()

    async def close(self):
        """Fecha conexões"""
        await self.repository.close()

    async def run(self) -> Dict[str, Any]:
        """Executa pipeline completo"""
        logger.info("Starting training pipeline", config=asdict(self.config))

        # 1. Carrega dados
        df = await self._load_data()
        if df is None or len(df) < self.config.min_training_samples:
            raise ValueError(f"Insufficient data: {len(df) if df is not None else 0} samples")

        # 2. Cria features
        features_df = self._create_features(df)

        # 3. Prepara dados de treino/validação/teste
        X_train, y_train, X_val, y_val, X_test, y_test, feature_names = \
            self._prepare_splits(features_df)

        # 4. Treina modelos
        models_results = {}
        for model_type in self.config.model_types:
            try:
                logger.info("Training model", model_type=model_type)
                result = await self._train_model(
                    model_type, X_train, y_train, X_val, y_val, feature_names
                )
                models_results[model_type] = result
            except Exception as e:
                logger.error("Model training failed", model_type=model_type, error=str(e))
                models_results[model_type] = {"error": str(e)}

        # 5. Avalia no teste
        test_results = {}
        for model_type, result in models_results.items():
            if "error" not in result:
                model = result["model"]
                test_metrics = model.evaluate(X_test, y_test)
                test_results[model_type] = test_metrics
                logger.info("Test metrics", model_type=model_type, **test_metrics)

        # 6. Seleciona melhor modelo
        best_model = self._select_best_model(test_results)
        if best_model and self.config.register_best:
            await self._register_model(best_model, test_results[best_model])

        # 7. Treina ensemble se múltiplos modelos
        ensemble_result = None
        if len([m for m in models_results if "error" not in models_results[m]]) > 1:
            ensemble_result = await self._train_ensemble(
                models_results, X_train, y_train, X_val, y_val, feature_names
            )

        return {
            "target_currency": self.config.target_currency,
            "base_currency": self.config.base_currency,
            "data_samples": len(df),
            "feature_count": len(feature_names),
            "models_trained": list(models_results.keys()),
            "test_results": test_results,
            "best_model": best_model,
            "ensemble": ensemble_result is not None,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _load_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados históricos do repositório"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=self.config.lookback_days)

        rates = await self.repository.get_rates_history(
            base=self.config.base_currency,
            quote=self.config.target_currency,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )

        if not rates:
            logger.warning("No rates found", pair=f"{self.config.base_currency}/{self.config.target_currency}")
            return None

        # Converte para DataFrame
        data = []
        for r in rates:
            data.append({
                "timestamp": r.rate_timestamp,
                "rate": float(r.rate),
                "bid": float(r.bid) if r.bid else None,
                "ask": float(r.ask) if r.ask else None,
                "source": r.source_rel.name if r.source_rel else "unknown"
            })

        df = pd.DataFrame(data)
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Remove duplicatas (mesmo timestamp)
        df = df.drop_duplicates(subset=["timestamp"], keep="last")

        logger.info("Data loaded", pair=f"{self.config.base_currency}/{self.config.target_currency}",
                   samples=len(df), date_range=f"{df['timestamp'].min()} to {df['timestamp'].max()}")

        return df

    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cria features a partir dos dados brutos"""
        # Cria dataset com lags para modelos sequenciais
        df_lagged = create_lagged_dataset(
            df, "rate", n_lags=30, horizon=self.config.prediction_horizon
        )

        # Features técnicas
        features_df = self.feature_engineer.create_features(
            df_lagged, target_col="rate", date_col="timestamp"
        )

        # Adiciona target (próximo valor)
        features_df["target"] = df_lagged[f"target_h{self.config.prediction_horizon}"]

        # Remove linhas com NaN
        features_df = features_df.dropna()

        logger.info("Features created", shape=features_df.shape, features=len(features_df.columns))
        return features_df

    def _prepare_splits(
        self,
        features_df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
        """Prepara splits treino/validação/teste (temporal)"""
        # Ordena por tempo
        features_df = features_df.sort_index()

        n = len(features_df)
        test_size = int(n * self.config.test_size)
        val_size = int(n * self.config.validation_size)
        train_size = n - test_size - val_size

        # Split temporal (não aleatório!)
        train_df = features_df.iloc[:train_size]
        val_df = features_df.iloc[train_size:train_size + val_size]
        test_df = features_df.iloc[train_size + val_size:]

        # Prepara X, y
        target_col = "target"
        exclude_cols = [target_col, "target_return", "timestamp", "date"]
        feature_cols = [c for c in features_df.columns if c not in exclude_cols]

        X_train, y_train, _ = self.feature_engineer.prepare_training_data(
            train_df, target_col=target_col, drop_na=False, scale=True
        )
        X_val, y_val, _ = self.feature_engineer.prepare_training_data(
            val_df, target_col=target_col, drop_na=False, scale=True
        )
        X_test, y_test, _ = self.feature_engineer.prepare_training_data(
            test_df, target_col=target_col, drop_na=False, scale=True
        )

        logger.info("Data splits", train=len(X_train), val=len(X_val), test=len(X_test))

        return X_train, y_train, X_val, y_val, X_test, y_test, feature_cols

    async def _train_model(
        self,
        model_type: str,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, Any]:
        """Treina um modelo específico"""
        with mlflow.start_run(run_name=f"{self.config.target_currency}_{model_type}") as run:
            # Config do modelo
            model_config = ModelConfig(
                name=f"{self.config.target_currency}_{model_type}",
                model_type=model_type,
                hyperparameters=self._get_default_hyperparams(model_type),
                target_currency=self.config.target_currency,
                base_currency=self.config.base_currency,
                feature_columns=feature_names,
                prediction_horizon=self.config.prediction_horizon
            )

            # Cria e treina
            model = ModelFactory.create(model_config)

            # Log params
            mlflow.log_params(model_config.hyperparameters)
            mlflow.log_param("model_type", model_type)
            mlflow.log_param("target_currency", self.config.target_currency)
            mlflow.log_param("base_currency", self.config.base_currency)
            mlflow.log_param("prediction_horizon", self.config.prediction_horizon)
            mlflow.log_param("train_samples", len(X_train))
            mlflow.log_param("feature_count", len(feature_names))

            # Treina com validation set para early stopping se suportado
            train_kwargs = {}
            if model_type in ["xgboost", "lightgbm"]:
                train_kwargs["eval_set"] = [(X_val, y_val)]
                train_kwargs["early_stopping_rounds"] = 50
                train_kwargs["verbose"] = False

            train_metrics = model.train(X_train, y_train, **train_kwargs)

            # Validação
            val_metrics = model.evaluate(X_val, y_val)

            # Log metrics
            for k, v in train_metrics.items():
                mlflow.log_metric(f"train_{k}", v)
            for k, v in val_metrics.items():
                mlflow.log_metric(f"val_{k}", v)

            # Salva modelo como artifact
            model_path = f"models/{model_type}"
            os.makedirs(model_path, exist_ok=True)
            model.save(f"{model_path}/model.pkl")
            mlflow.log_artifacts(model_path, artifact_path="model")

            # Salva scaler
            import joblib
            joblib.dump(self.feature_engineer.scaler, f"{model_path}/scaler.pkl")
            mlflow.log_artifact(f"{model_path}/scaler.pkl", artifact_path="model")

            return {
                "model": model,
                "model_config": model_config,
                "train_metrics": train_metrics,
                "val_metrics": val_metrics,
                "mlflow_run_id": run.info.run_id,
                "model_path": model_path
            }

    def _get_default_hyperparams(self, model_type: str) -> Dict[str, Any]:
        """Retorna hiperparâmetros padrão por tipo"""
        defaults = {
            "ridge": {"alpha": 1.0},
            "lasso": {"alpha": 0.1},
            "elasticnet": {"alpha": 0.1, "l1_ratio": 0.5},
            "random_forest": {"n_estimators": 200, "max_depth": 10, "random_state": 42, "n_jobs": -1},
            "gradient_boosting": {"n_estimators": 200, "learning_rate": 0.1, "max_depth": 5, "random_state": 42},
            "svr": {"kernel": "rbf", "C": 1.0, "gamma": "scale"},
            "knn": {"n_neighbors": 5, "weights": "distance"},
            "xgboost": {
                "n_estimators": 500,
                "learning_rate": 0.05,
                "max_depth": 6,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
                "n_jobs": -1
            },
            "lightgbm": {
                "n_estimators": 500,
                "learning_rate": 0.05,
                "max_depth": 6,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
                "n_jobs": -1,
                "verbosity": -1
            },
            "arima": {"order": (2, 1, 2)},
            "sarima": {"order": (1, 1, 1), "seasonal_order": (1, 1, 1, 12)},
            "prophet": {"yearly_seasonality": True, "weekly_seasonality": True, "changepoint_prior_scale": 0.05},
            "lstm_pytorch": {
                "input_size": len(feature_names) if 'feature_names' in locals() else 50,
                "hidden_size": 64,
                "num_layers": 2,
                "dropout": 0.2,
                "learning_rate": 0.001,
                "epochs": 100,
                "batch_size": 32,
                "sequence_length": 20
            },
            "lstm_tf": {
                "sequence_length": 20,
                "units": [64, 32],
                "dropout": 0.2,
                "learning_rate": 0.001,
                "epochs": 100,
                "batch_size": 32,
                "patience": 10
            }
        }
        return defaults.get(model_type, {})

    def _select_best_model(self, test_results: Dict[str, Dict]) -> Optional[str]:
        """Seleciona melhor modelo baseado no RMSE"""
        if not test_results:
            return None

        best_model = min(test_results.keys(), key=lambda k: test_results[k].get("rmse", float("inf")))
        logger.info("Best model selected", model=best_model, rmse=test_results[best_model].get("rmse"))
        return best_model

    async def _register_model(self, model_type: str, metrics: Dict):
        """Registra melhor modelo no registry"""
        result = self.results.get(model_type)
        if not result:
            return

        model_registry = ModelRegistry(
            name=f"{self.config.target_currency}_{model_type}",
            version="1.0.0",
            model_type=model_type,
            target_currency_id=0,  # Será preenchido pelo repository
            base_currency_id=0,
            hyperparameters=json.dumps(result["model_config"].hyperparameters),
            train_mae=metrics.get("mae"),
            train_rmse=metrics.get("rmse"),
            val_mae=result["val_metrics"].get("mae"),
            val_rmse=result["val_metrics"].get("rmse"),
            test_mae=metrics.get("mae"),
            test_rmse=metrics.get("rmse"),
            model_path=result["model_path"],
            mlflow_run_id=result["mlflow_run_id"],
            status="ready",
            is_active=True,
            is_production=True
        )

        await self.repository.save_model(model_registry)
        logger.info("Model registered", model=model_type)

    async def _train_ensemble(
        self,
        models_results: Dict,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        feature_names: List[str]
    ) -> Dict:
        """Treina ensemble dos melhores modelos"""
        # Seleciona modelos sem erro
        valid_models = {
            k: v for k, v in models_results.items()
            if "error" not in v
        }

        if len(valid_models) < 2:
            return None

        # Config do ensemble
        ensemble_config = ModelConfig(
            name=f"{self.config.target_currency}_ensemble",
            model_type="ensemble",
            hyperparameters={
                "models": [
                    {
                        "name": f"{self.config.target_currency}_{k}",
                        "model_type": k,
                        "hyperparameters": v["model_config"].hyperparameters,
                        "target_currency": self.config.target_currency,
                        "base_currency": self.config.base_currency,
                        "feature_columns": feature_names,
                        "prediction_horizon": self.config.prediction_horizon,
                        "weight": 1.0 / len(valid_models)
                    }
                    for k, v in valid_models.items()
                ]
            },
            target_currency=self.config.target_currency,
            base_currency=self.config.base_currency,
            feature_columns=feature_names,
            prediction_horizon=self.config.prediction_horizon
        )

        with mlflow.start_run(run_name=f"{self.config.target_currency}_ensemble") as run:
            ensemble = EnsembleModel(ensemble_config)
            ensemble.train(X_train, y_train)

            val_metrics = ensemble.evaluate(X_val, y_val)

            mlflow.log_metric("val_mae", val_metrics["mae"])
            mlflow.log_metric("val_rmse", val_metrics["rmse"])
            mlflow.log_metric("val_r2", val_metrics["r2"])

            return {
                "model": ensemble,
                "val_metrics": val_metrics,
                "mlflow_run_id": run.info.run_id
            }


# Função de conveniência
async def train_currency_model(
    target_currency: str,
    base_currency: str = "BRL",
    model_types: List[str] = None,
    **kwargs
) -> Dict:
    """Treina modelo para uma moeda"""
    config = TrainingConfig(
        target_currency=target_currency,
        base_currency=base_currency,
        model_types=model_types,
        **kwargs
    )

    pipeline = TrainingPipeline(config)
    await pipeline.initialize()
    try:
        result = await pipeline.run()
        return result
    finally:
        await pipeline.close()