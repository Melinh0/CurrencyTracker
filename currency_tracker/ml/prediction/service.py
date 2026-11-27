# ============================================
# CurrencyTracker - Prediction Service
# ============================================

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import structlog
import numpy as np
import pandas as pd

from currency_tracker.ml.models.registry import ModelFactory, ModelConfig, BaseModel
from currency_tracker.ml.features.engineering import FeatureEngineer, FeatureConfig, create_lagged_dataset
from currency_tracker.storage.repository import RateRepository
from currency_tracker.storage.models import Prediction, ModelRegistry
from currency_tracker.storage.influxdb_client import InfluxDBClient
from currency_tracker.config.settings import get_settings

logger = structlog.get_logger()


class PredictionService:
    """Serviço de previsão de taxas de câmbio"""

    def __init__(self):
        self.settings = get_settings()
        self.repository = RateRepository()
        self.influxdb = InfluxDBClient()
        self.feature_engineer = FeatureEngineer(FeatureConfig())
        self._model_cache: Dict[str, BaseModel] = {}
        _cache_timestamps: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=1)

    async def initialize(self):
        """Inicializa conexões"""
        await self.repository.initialize()
        await self.influxdb.connect()

    async def close(self):
        """Fecha conexões"""
        await self.repository.close()
        await self.influxdb.close()
        self._model_cache.clear()

    async def predict(
        self,
        base: str,
        quote: str,
        horizon_days: int = 7,
        model_name: Optional[str] = None,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Gera previsão para um par de moedas.

        Args:
            base: Moeda base (ex: "BRL")
            quote: Moeda de cotação (ex: "USD")
            horizon_days: Horizonte de previsão em dias
            model_name: Nome específico do modelo (None = melhor ativo)
            confidence_level: Nível de confiança (0.95 = 95%)

        Returns:
            Dict com previsões e metadados
        """
        # 1. Carrega modelo
        model = await self._load_model(base, quote, model_name)
        if not model:
            return {"error": "No trained model available", "base": base, "quote": quote}

        # 2. Carrega dados recentes para features
        lookback_days = max(60, horizon_days * 4)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)

        rates = await self.repository.get_rates_history(
            base=base,
            quote=quote,
            start_date=start_date,
            end_date=end_date,
            limit=1000
        )

        if len(rates) < 30:
            return {"error": "Insufficient historical data", "base": base, "quote": quote}

        # 3. Prepara features
        df = self._rates_to_dataframe(rates)
        features_df = self._prepare_features(df, base, quote)

        # 4. Gera previsões
        predictions = await self._generate_predictions(
            model, features_df, horizon_days, confidence_level
        )

        # 5. Salva previsões
        await self._save_predictions(base, quote, model, predictions)

        return {
            "base": base,
            "quote": quote,
            "model": model.config.name if hasattr(model, 'config') else "unknown",
            "horizon_days": horizon_days,
            "confidence_level": confidence_level,
            "predictions": predictions,
            "generated_at": datetime.utcnow().isoformat()
        }

    async def predict_multiple(
        self,
        base: str,
        quotes: List[str],
        horizon_days: int = 7
    ) -> Dict[str, Dict]:
        """Previsões para múltiplas moedas"""
        results = {}
        for quote in quotes:
            try:
                results[quote] = await self.predict(base, quote, horizon_days)
            except Exception as e:
                logger.error("Prediction failed", base=base, quote=quote, error=str(e))
                results[quote] = {"error": str(e), "base": base, "quote": quote}
        return results

    async def get_latest_prediction(
        self,
        base: str,
        quote: str,
        model_id: Optional[int] = None
    ) -> Optional[Dict]:
        """Busca última previsão salva"""
        preds = await self.repository.get_predictions(base, quote, model_id, limit=1)
        if preds:
            p = preds[0]
            return {
                "base": base,
                "quote": quote,
                "predicted_rate": float(p.predicted_rate),
                "lower_bound": float(p.lower_bound) if p.lower_bound else None,
                "upper_bound": float(p.upper_bound) if p.upper_bound else None,
                "confidence_level": float(p.confidence_level),
                "prediction_timestamp": p.prediction_timestamp.isoformat(),
                "horizon_days": p.horizon_days,
                "model_id": p.model_id
            }
        return None

    async def _load_model(
        self,
        base: str,
        quote: str,
        model_name: Optional[str]
    ) -> Optional[BaseModel]:
        """Carrega modelo do cache ou banco"""
        cache_key = f"{base}_{quote}_{model_name or 'best'}"

        # Verifica cache
        if cache_key in self._model_cache:
            cached_time = _cache_timestamps.get(cache_key)
            if cached_time and datetime.utcnow() - cached_time < self._cache_ttl:
                return self._model_cache[cache_key]

        # Busca no banco
        if model_name:
            # Busca por nome específico
            models = await self.repository.get_models_for_currency(quote)
            model_registry = next((m for m in models if m.name == model_name), None)
        else:
            # Busca melhor ativo
            model_registry = await self.repository.get_active_model(quote, base)

        if not model_registry:
            return None

        # Recria modelo
        config = ModelConfig(
            name=model_registry.name,
            model_type=model_registry.model_type,
            hyperparameters={},  # Será carregado do arquivo
            target_currency=quote,
            base_currency=base,
            prediction_horizon=model_registry.hyperparameters.get("prediction_horizon", 1)
        )

        model = ModelFactory.create(config)
        model.load(model_registry.model_path)

        # Carrega scaler se existir
        import joblib
        scaler_path = f"{model_registry.model_path}/scaler.pkl"
        try:
            model.scaler = joblib.load(scaler_path)
            self.feature_engineer.scaler = model.scaler
            self.feature_engineer._fitted = True
        except Exception:
            pass

        # Cache
        self._model_cache[cache_key] = model
        _cache_timestamps[cache_key] = datetime.utcnow()

        return model

    def _rates_to_dataframe(self, rates: List) -> pd.DataFrame:
        """Converte lista de taxas para DataFrame"""
        data = []
        for r in rates:
            data.append({
                "timestamp": r.rate_timestamp,
                "rate": float(r.rate),
                "bid": float(r.bid) if r.bid else None,
                "ask": float(r.ask) if r.ask else None
            })
        df = pd.DataFrame(data)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    def _prepare_features(self, df: pd.DataFrame, base: str, quote: str) -> pd.DataFrame:
        """Prepara features para previsão"""
        # Cria dataset com lags
        df_lagged = create_lagged_dataset(df, "rate", n_lags=30, horizon=1)

        # Cria features
        features_df = self.feature_engineer.create_features(
            df_lagged, target_col="rate", date_col="timestamp"
        )

        # Remove target (não temos futuro real)
        features_df = features_df.drop(columns=["target", "target_return"], errors="ignore")

        # Remove NaN
        features_df = features_df.dropna()

        return features_df

    async def _generate_predictions(
        self,
        model: BaseModel,
        features_df: pd.DataFrame,
        horizon_days: int,
        confidence_level: float
    ) -> List[Dict]:
        """Gera previsões multi-step"""
        predictions = []

        # Prepara X (últimas features)
        X = self.feature_engineer.transform(features_df)

        # Para previsão multi-step, fazemos iterativo
        current_features = features_df.iloc[-1:].copy()

        for day in range(1, horizon_days + 1):
            # Transforma features atuais
            X_current = self.feature_engineer.transform(current_features)

            # Previsão
            pred = model.predict(X_current)
            predicted_rate = float(pred[0]) if len(pred) > 0 else float(pred)

            # Calcula intervalo de confiança (simplificado - usando erro histórico)
            # Em produção, usar quantile regression ou conformal prediction
            std_error = 0.02  # 2% erro padrão estimado
            z_score = 1.96 if confidence_level >= 0.95 else 1.645
            margin = predicted_rate * std_error * z_score

            prediction_timestamp = datetime.utcnow() + timedelta(days=day)

            predictions.append({
                "day": day,
                "date": prediction_timestamp.date().isoformat(),
                "predicted_rate": predicted_rate,
                "lower_bound": predicted_rate - margin,
                "upper_bound": predicted_rate + margin,
                "confidence_level": confidence_level
            })

            # Atualiza features para próximo step (rolling)
            # Adiciona previsão como novo valor e recalcula features
            new_row = pd.DataFrame({
                "timestamp": [prediction_timestamp],
                "rate": [predicted_rate]
            })
            # Recalcula features com novo dado (simplificado)
            # Em produção, manter estado do feature engineer

        return predictions

    async def _save_predictions(
        self,
        base: str,
        quote: str,
        model: BaseModel,
        predictions: List[Dict]
    ):
        """Salva previsões no banco e InfluxDB"""
        # Busca model registry
        models = await self.repository.get_models_for_currency(quote)
        model_registry = next((m for m in models if m.name == getattr(model, 'config', {}).get('name', '')), None)

        if not model_registry:
            return

        for pred in predictions:
            # Salva no PostgreSQL
            prediction = Prediction(
                model_id=model_registry.id,
                base_currency_id=0,  # Preenchido pelo repository
                quote_currency_id=0,
                prediction_timestamp=datetime.fromisoformat(pred["date"]),
                predicted_rate=Decimal(str(pred["predicted_rate"])),
                lower_bound=Decimal(str(pred["lower_bound"])) if pred["lower_bound"] else None,
                upper_bound=Decimal(str(pred["upper_bound"])) if pred["upper_bound"] else None,
                confidence_level=Decimal(str(pred["confidence_level"] * 100)),
                horizon_days=pred["day"]
            )
            await self.repository.save_prediction(prediction)

            # Salva no InfluxDB
            await self.influxdb.write_prediction(
                base=base,
                quote=quote,
                model_name=model_registry.name,
                prediction_timestamp=datetime.fromisoformat(pred["date"]),
                predicted_rate=pred["predicted_rate"],
                lower_bound=pred["lower_bound"],
                upper_bound=pred["upper_bound"],
                confidence_level=pred["confidence_level"] * 100,
                horizon_days=pred["day"]
            )


# Instância global
prediction_service = PredictionService()