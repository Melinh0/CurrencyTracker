# ============================================
# CurrencyTracker - Predictions API Routes
# ============================================

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel

from currency_tracker.api.schemas import (
    PredictionRequest,
    PredictionResponse,
    TrainingRequest,
    TrainingResponse,
    ModelResponse,
    ErrorResponse
)
from currency_tracker.ml.prediction.service import prediction_service
from currency_tracker.ml.training.pipeline import train_currency_model
from currency_tracker.storage.repository import RateRepository
from currency_tracker.api.dependencies import get_rate_repo
from currency_tracker.config.settings import get_settings

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Generate prediction",
    description="Generates future exchange rate predictions using trained ML models"
)
async def generate_prediction(
    request: PredictionRequest,
    repo: RateRepository = Depends(get_rate_repo)
):
    """Gera previsão para um par de moedas"""
    # Inicializa serviço se necessário
    if not prediction_service.repository._session_factory:
        await prediction_service.initialize()

    try:
        result = await prediction_service.predict(
            base=request.base,
            quote=request.quote,
            horizon_days=request.horizon_days,
            model_name=request.model_name,
            confidence_level=request.confidence_level
        )

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"]
            )

        # Converte para schema
        predictions = [
            {
                "day": p["day"],
                "date": p["date"],
                "predicted_rate": p["predicted_rate"],
                "lower_bound": p["lower_bound"],
                "upper_bound": p["upper_bound"],
                "confidence_level": p["confidence_level"]
            }
            for p in result["predictions"]
        ]

        return PredictionResponse(
            base=result["base"],
            quote=result["quote"],
            model=result["model"],
            horizon_days=result["horizon_days"],
            confidence_level=result["confidence_level"],
            predictions=predictions,
            generated_at=result["generated_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


@router.post(
    "/predict/batch",
    response_model=dict,
    summary="Generate predictions for multiple currencies",
    description="Generates predictions for multiple currency pairs at once"
)
async def generate_batch_predictions(
    base: str = Query(..., pattern="^[A-Z]{3}$"),
    quotes: List[str] = Query(..., min_length=1),
    horizon_days: int = Query(default=7, ge=1, le=90)
):
    """Gera previsões para múltiplas moedas"""
    if not prediction_service.repository._session_factory:
        await prediction_service.initialize()

    try:
        results = await prediction_service.predict_multiple(base, quotes, horizon_days)
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch prediction failed: {str(e)}"
        )


@router.get(
    "/latest/{quote}",
    response_model=PredictionResponse,
    summary="Get latest saved prediction",
    description="Returns the most recent prediction for a currency pair"
)
async def get_latest_prediction(
    quote: str,
    base: str = Query(default="BRL", pattern="^[A-Z]{3}$"),
    model_id: Optional[int] = Query(default=None),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Busca última previsão salva"""
    if not prediction_service.repository._session_factory:
        await prediction_service.initialize()

    result = await prediction_service.get_latest_prediction(base, quote, model_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No prediction found for {base}/{quote}"
        )

    predictions = [{
        "day": 1,
        "date": result["prediction_timestamp"][:10],
        "predicted_rate": result["predicted_rate"],
        "lower_bound": result["lower_bound"] or result["predicted_rate"],
        "upper_bound": result["upper_bound"] or result["predicted_rate"],
        "confidence_level": result["confidence_level"] / 100
    }]

    return PredictionResponse(
        base=result["base"],
        quote=result["quote"],
        model=f"model_{result['model_id']}",
        horizon_days=result["horizon_days"],
        confidence_level=result["confidence_level"] / 100,
        predictions=predictions,
        generated_at=result["prediction_timestamp"]
    )


# ============================================
# Training Routes
# ============================================

@router.post(
    "/train",
    response_model=TrainingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Train model",
    description="Trains ML models for a currency pair (runs in background)"
)
async def train_model(
    request: TrainingRequest,
    background_tasks: BackgroundTasks
):
    """Inicia treino de modelo em background"""
    # Adiciona task em background
    background_tasks.add_task(
        _train_model_task,
        request.target_currency,
        request.base_currency,
        request.model_types,
        request.prediction_horizon,
        request.lookback_days,
        request.test_size,
        request.min_training_samples
    )

    return TrainingResponse(
        target_currency=request.target_currency,
        base_currency=request.base_currency,
        data_samples=0,
        feature_count=0,
        models_trained=[],
        test_results={},
        timestamp=datetime.utcnow().isoformat()
    )


async def _train_model_task(
    target_currency: str,
    base_currency: str,
    model_types: Optional[List[str]],
    prediction_horizon: int,
    lookback_days: int,
    test_size: float,
    min_training_samples: int
):
    """Task de treino em background"""
    try:
        result = await train_currency_model(
            target_currency=target_currency,
            base_currency=base_currency,
            model_types=model_types,
            prediction_horizon=prediction_horizon,
            lookback_days=lookback_days,
            test_size=test_size,
            min_training_samples=min_training_samples
        )
        print(f"Training completed for {target_currency}: {result}")
    except Exception as e:
        print(f"Training failed for {target_currency}: {e}")


@router.get(
    "/models",
    response_model=List[ModelResponse],
    summary="List trained models",
    description="Returns all trained models for a currency"
)
async def list_models(
    target_currency: str = Query(..., pattern="^[A-Z]{3}$"),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Lista modelos treinados para uma moeda"""
    models = await repo.get_models_for_currency(target_currency)
    return [ModelResponse.model_validate(m) for m in models]


@router.get(
    "/models/active/{quote}",
    response_model=ModelResponse,
    summary="Get active model",
    description="Returns the currently active production model for a currency pair"
)
async def get_active_model(
    quote: str,
    base: str = Query(default="BRL", pattern="^[A-Z]{3}$"),
    repo: RateRepository = Depends(get_rate_repo)
):
    """Busca modelo ativo para um par"""
    model = await repo.get_active_model(quote, base)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active model for {base}/{quote}"
        )

    return ModelResponse.model_validate(model)


# Import datetime
from datetime import datetime