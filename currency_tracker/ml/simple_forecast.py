import os
import datetime as dt
import numpy as np
import joblib
from sklearn.linear_model import Ridge
from currency_tracker.config.settings import get_settings

def _model_dir():
    path = os.path.join(get_settings().ml.model_registry_path, 'simple')
    os.makedirs(path, exist_ok=True)
    return path

def _make_lags(series, k):
    X = np.array([series[i - k:i] for i in range(k, len(series))])
    y = np.array([series[i] for i in range(k, len(series))])
    return (X, y)

def fit_and_save(rates, base, quote):
    rates = [float(r) for r in rates]
    n = len(rates)
    if n < 8:
        return None
    k = min(7, max(3, n // 3))
    X, y = _make_lags(rates, k)
    if len(X) < 3:
        return None
    model = Ridge(alpha=0.5)
    model.fit(X, y)
    resid = y - model.predict(X)
    abs_std = float(np.std(resid)) if len(resid) > 0 else 0.01
    mean_rate = float(np.mean(rates)) or 1.0
    rel_std = abs_std / abs(mean_rate) if mean_rate else 0.01
    mae = float(np.mean(np.abs(resid))) if len(resid) > 0 else 0.0
    path = os.path.join(_model_dir(), f'{base}_{quote}_ridge.joblib')
    joblib.dump({'model': model, 'k': k, 'rel_std': rel_std, 'last': rates[-k:]}, path)
    return {'path': path, 'k': k, 'rel_std': rel_std, 'mae': mae, 'samples': int(len(X))}

def forecast(path, horizon, confidence):
    bundle = joblib.load(path)
    model = bundle['model']
    k = bundle['k']
    rel_std = bundle.get('rel_std', 0.01)
    window = list(bundle['last'])
    z = 1.96 if confidence >= 0.95 else 1.645
    today = dt.datetime.utcnow()
    out = []
    for day in range(1, horizon + 1):
        x = np.array(window[-k:]).reshape(1, -1)
        pred = float(model.predict(x)[0])
        margin = abs(pred) * rel_std * z
        d = (today + dt.timedelta(days=day)).date().isoformat()
        out.append({'day': day, 'date': d, 'predicted_rate': round(pred, 6), 'lower_bound': round(pred - margin, 6), 'upper_bound': round(pred + margin, 6), 'confidence_level': confidence})
        window.append(pred)
    return out
