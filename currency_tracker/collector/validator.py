from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import statistics
from currency_tracker.collector.sources import ExchangeRate, CollectionResult
from currency_tracker.config.settings import get_currency_config

@dataclass
class ValidationResult:
    valid: bool
    rate: ExchangeRate
    warnings: List[str]
    errors: List[str]
    adjusted_rate: Optional[ExchangeRate] = None

@dataclass
class OutlierDetectionResult:
    is_outlier: bool
    method: str
    value: float
    threshold: float
    details: Dict[str, Any]

class RateValidator:

    def __init__(self):
        self.config = get_currency_config()
        self.validation_config = self.config.validation_config
        self._recent_rates: Dict[str, List[ExchangeRate]] = defaultdict(list)
        self._max_history = 100

    def validate(self, rate: ExchangeRate) -> ValidationResult:
        warnings = []
        errors = []
        if rate.rate <= 0:
            errors.append('Rate must be positive')
        if rate.bid and rate.bid <= 0:
            warnings.append('Bid price should be positive')
        if rate.ask and rate.ask <= 0:
            warnings.append('Ask price should be positive')
        if rate.bid and rate.ask and (rate.bid > rate.ask):
            warnings.append('Bid price higher than ask (inverted spread)')
        if rate.spread:
            max_spread = Decimal(str(self.validation_config.get('max_spread_percent', 5.0)))
            if rate.spread > max_spread:
                warnings.append(f'Spread {rate.spread:.2f}% exceeds maximum {max_spread}%')
        min_rate = Decimal(str(self.validation_config.get('min_rate', 0.0001)))
        if rate.rate < min_rate:
            errors.append(f'Rate {rate.rate} below minimum {min_rate}')
        key = f'{rate.base_currency}/{rate.quote_currency}'
        outlier_result = self._detect_outlier(key, rate)
        if outlier_result.is_outlier:
            warnings.append(f'Potential outlier detected: {outlier_result.method} (value={outlier_result.value:.4f}, threshold={outlier_result.threshold:.4f})')
        change_result = self._check_rate_change(key, rate)
        if change_result:
            warnings.append(f'Large rate change detected: {change_result:.2f}%')
        self._add_to_history(key, rate)
        valid = len(errors) == 0
        return ValidationResult(valid=valid, rate=rate, warnings=warnings, errors=errors)

    def validate_collection(self, result: CollectionResult) -> CollectionResult:
        validated_rates = []
        all_errors = list(result.errors)
        all_warnings = []
        for rate in result.rates:
            validation = self.validate(rate)
            all_warnings.extend(validation.warnings)
            all_errors.extend(validation.errors)
            if validation.valid:
                validated_rates.append(rate)
            elif validation.adjusted_rate:
                validated_rates.append(validation.adjusted_rate)
        return CollectionResult(success=len(all_errors) == 0, rates=validated_rates, errors=all_errors, source=result.source, duration_ms=result.duration_ms, timestamp=result.timestamp)

    def _detect_outlier(self, key: str, rate: ExchangeRate) -> OutlierDetectionResult:
        method = self.validation_config.get('outlier_method', 'iqr')
        threshold = self.validation_config.get('outlier_threshold', 1.5)
        history = self._recent_rates.get(key, [])
        if len(history) < 10:
            return OutlierDetectionResult(is_outlier=False, method=method, value=float(rate.rate), threshold=threshold, details={'reason': 'insufficient_history', 'history_size': len(history)})
        values = [float(r.rate) for r in history[-50:]]
        current = float(rate.rate)
        if method == 'iqr':
            return self._iqr_outlier(values, current, threshold)
        elif method == 'zscore':
            return self._zscore_outlier(values, current, threshold)
        else:
            return OutlierDetectionResult(is_outlier=False, method=method, value=current, threshold=threshold, details={'reason': 'unknown_method'})

    def _iqr_outlier(self, values: List[float], current: float, multiplier: float) -> OutlierDetectionResult:
        try:
            q1 = statistics.quantiles(values, n=4)[0]
            q3 = statistics.quantiles(values, n=4)[2]
            iqr = q3 - q1
            lower = q1 - multiplier * iqr
            upper = q3 + multiplier * iqr
            is_outlier = current < lower or current > upper
            return OutlierDetectionResult(is_outlier=is_outlier, method='iqr', value=current, threshold=multiplier, details={'q1': q1, 'q3': q3, 'iqr': iqr, 'lower': lower, 'upper': upper})
        except Exception:
            return OutlierDetectionResult(is_outlier=False, method='iqr', value=current, threshold=multiplier, details={'reason': 'calculation_error'})

    def _zscore_outlier(self, values: List[float], current: float, threshold: float) -> OutlierDetectionResult:
        try:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values) if len(values) > 1 else 0
            if stdev == 0:
                return OutlierDetectionResult(is_outlier=False, method='zscore', value=current, threshold=threshold, details={'reason': 'zero_variance'})
            zscore = abs(current - mean) / stdev
            is_outlier = zscore > threshold
            return OutlierDetectionResult(is_outlier=is_outlier, method='zscore', value=current, threshold=threshold, details={'mean': mean, 'stdev': stdev, 'zscore': zscore})
        except Exception:
            return OutlierDetectionResult(is_outlier=False, method='zscore', value=current, threshold=threshold, details={'reason': 'calculation_error'})

    def _check_rate_change(self, key: str, rate: ExchangeRate) -> Optional[float]:
        history = self._recent_rates.get(key, [])
        if not history:
            return None
        last_rate = history[-1]
        if last_rate.rate == 0:
            return None
        change_pct = abs(float(rate.rate - last_rate.rate) / float(last_rate.rate)) * 100
        max_change = self.validation_config.get('max_rate_change_percent', 50.0)
        if change_pct > max_change:
            return change_pct
        return None

    def _add_to_history(self, key: str, rate: ExchangeRate):
        self._recent_rates[key].append(rate)
        if len(self._recent_rates[key]) > self._max_history:
            self._recent_rates[key] = self._recent_rates[key][-self._max_history:]

    def get_statistics(self, key: str) -> Dict[str, Any]:
        history = self._recent_rates.get(key, [])
        if not history:
            return {}
        values = [float(r.rate) for r in history]
        return {'count': len(values), 'mean': statistics.mean(values), 'median': statistics.median(values), 'stdev': statistics.stdev(values) if len(values) > 1 else 0, 'min': min(values), 'max': max(values), 'latest': values[-1], 'latest_timestamp': history[-1].timestamp.isoformat() if history else None}

class CrossSourceValidator:

    def __init__(self, max_spread_percent: float=2.0):
        self.max_spread_percent = max_spread_percent

    def validate_consensus(self, rates_by_source: Dict[str, List[ExchangeRate]]) -> Dict[str, List[ValidationResult]]:
        pairs: Dict[str, Dict[str, ExchangeRate]] = defaultdict(dict)
        for source, rates in rates_by_source.items():
            for rate in rates:
                key = f'{rate.base_currency}/{rate.quote_currency}'
                pairs[key][source] = rate
        results = defaultdict(list)
        for pair, source_rates in pairs.items():
            if len(source_rates) < 2:
                for source, rate in source_rates.items():
                    results[source].append(ValidationResult(valid=True, rate=rate, warnings=['Single source - no cross validation'], errors=[]))
                continue
            rate_values = [float(r.rate) for r in source_rates.values()]
            median_rate = statistics.median(rate_values)
            for source, rate in source_rates.items():
                deviation = abs(float(rate.rate) - median_rate) / median_rate * 100
                warnings = []
                errors = []
                if deviation > self.max_spread_percent:
                    warnings.append(f'Rate deviates {deviation:.2f}% from median ({median_rate:.4f}) across {len(source_rates)} sources')
                results[source].append(ValidationResult(valid=True, rate=rate, warnings=warnings, errors=errors))
        return dict(results)

    def get_consensus_rate(self, rates_by_source: Dict[str, List[ExchangeRate]]) -> Dict[str, ExchangeRate]:
        pairs: Dict[str, List[ExchangeRate]] = defaultdict(list)
        for source, rates in rates_by_source.items():
            for rate in rates:
                key = f'{rate.base_currency}/{rate.quote_currency}'
                pairs[key].append(rate)
        consensus = {}
        for pair, rates in pairs.items():
            if not rates:
                continue
            rate_values = [float(r.rate) for r in rates]
            median_rate = statistics.median(rate_values)
            base_rate = rates[0]
            consensus_rate = ExchangeRate(base_currency=base_rate.base_currency, quote_currency=base_rate.quote_currency, rate=Decimal(str(median_rate)), rate_type=base_rate.rate_type, source='consensus', raw_data={'method': 'median', 'sources': [r.source for r in rates], 'values': rate_values, 'count': len(rates)})
            consensus[pair] = consensus_rate
        return consensus
