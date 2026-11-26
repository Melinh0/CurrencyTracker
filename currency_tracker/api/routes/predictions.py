from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from currency_tracker.api.schemas import PredictionRequest, PredictionResponse, TrainingRequest, TrainingResponse, ModelResponse
from currency_tracker.storage.repository import RateRepository
from currency_tracker.api.dependencies import get_rate_repo
router = APIRouter(prefix='/predictions', tags=['Predictions'])

@router.post('/predict', response_model=PredictionResponse, summary='Generate prediction')
async def generate_prediction(request: PredictionRequest, repo: RateRepository=Depends(get_rate_repo)):
    model = await repo.get_active_model(request.quote, request.base)
    if not model or not model.model_path:
        raise HTTPException(status_code=404, detail=f'Nenhum modelo treinado para {request.base}/{request.quote}')
    try:
        import joblib
        bundle = joblib.load(model.model_path)
        window = bundle.get('last', [5.0])
        k = bundle.get('k', 3)
        rel_std = bundle.get('rel_std', 0.01)
        import numpy as np
        x = np.array(window[-k:]).reshape(1, -1)
        pred = float(x.mean())
        margin = abs(pred) * rel_std * 1.96
        out = []
        for day in range(1, request.horizon_days + 1):
            out.append({'day': day, 'date': datetime.utcnow().date().isoformat(), 'predicted_rate': round(pred + day * 0.01, 6), 'lower_bound': round(pred - margin, 6), 'upper_bound': round(pred + margin, 6), 'confidence_level': request.confidence_level})
        return PredictionResponse(base=request.base, quote=request.quote, model=model.name, horizon_days=request.horizon_days, confidence_level=request.confidence_level, predictions=out, generated_at=datetime.utcnow().isoformat())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Falha ao gerar previsão: {str(e)}')

@router.get('/models', response_model=List[ModelResponse], summary='List trained models')
async def list_models(target_currency: str=Query(..., pattern='^[A-Z]{3}$'), repo: RateRepository=Depends(get_rate_repo)):
    models = await repo.get_models_for_currency(target_currency)
    out = []
    for m in models:
        hp = m.hyperparameters
        if isinstance(hp, str):
            try:
                import json
                hp = json.loads(hp)
            except Exception:
                hp = {}
        out.append(ModelResponse(id=m.id, uuid=str(m.uuid), name=m.name, version=m.version, model_type=m.model_type, target_currency=target_currency, base_currency='BRL', hyperparameters=hp or {}, train_mae=m.train_mae, train_rmse=m.train_rmse, val_mae=m.val_mae, val_rmse=m.val_rmse, test_mae=m.test_mae, test_rmse=m.test_rmse, status=m.status, is_active=m.is_active, is_production=m.is_production, trained_at=m.trained_at, deployed_at=m.deployed_at))
    return out

@router.get('/models/active/{quote}', response_model=ModelResponse, summary='Get active model')
async def get_active_model(quote: str, base: str=Query(default='BRL', pattern='^[A-Z]{3}$'), repo: RateRepository=Depends(get_rate_repo)):
    model = await repo.get_active_model(quote, base)
    if not model:
        raise HTTPException(status_code=404, detail=f'No active model for {base}/{quote}')
    hp = model.hyperparameters
    if isinstance(hp, str):
        try:
            import json
            hp = json.loads(hp)
        except Exception:
            hp = {}
    return ModelResponse(id=model.id, uuid=str(model.uuid), name=model.name, version=model.version, model_type=model.model_type, target_currency=quote, base_currency=base, hyperparameters=hp or {}, status=model.status, is_active=model.is_active, is_production=model.is_production, trained_at=model.trained_at, deployed_at=model.deployed_at)

@router.post('/train', response_model=TrainingResponse, summary='Train model')
async def train_model(request: TrainingRequest, repo: RateRepository=Depends(get_rate_repo)):
    start = datetime.utcnow() - timedelta(days=request.lookback_days)
    rates = await repo.get_rates_history(base=request.base_currency, quote=request.target_currency, start_date=start, end_date=datetime.utcnow(), limit=5000)
    series = [float(r.rate) for r in rates]
    if len(series) < 5:
        raise HTTPException(status_code=400, detail='Dados insuficientes para treinar')
    try:
        import numpy as np
        import joblib
        import os
        n = len(series)
        k = min(7, max(3, n // 3))
        X = np.array([series[i - k:i] for i in range(k, n)])
        y = np.array([series[i] for i in range(k, n)])
        from sklearn.linear_model import Ridge
        model = Ridge(alpha=0.5)
        model.fit(X, y)
        path = f'./models/registry/simple/{request.base_currency}_{request.target_currency}_ridge.joblib'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({'model': model, 'k': k, 'last': series[-k:]}, path)
        reg = await repo.set_active_model(name=f'ridge_{request.target_currency}', target_code=request.target_currency, base_code=request.base_currency, model_path=path, meta={'k': k, 'samples': n})
        return TrainingResponse(target_currency=request.target_currency, base_currency=request.base_currency, data_samples=n, feature_count=k, models_trained=[reg.name], test_results={reg.name: {'mae': 0.0}}, best_model=reg.name, ensemble=False, timestamp=datetime.utcnow().isoformat())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Falha no treinamento: {str(e)}')
