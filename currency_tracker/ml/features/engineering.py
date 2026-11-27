# ============================================
# CurrencyTracker - Feature Engineering
# ============================================

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import ta  # Technical Analysis library
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler


class FeatureType(str, Enum):
    PRICE = "price"
    TECHNICAL = "technical"
    TIME = "time"
    STATISTICAL = "statistical"
    CROSS_CURRENCY = "cross_currency"
    MACRO = "macro"


@dataclass
class FeatureConfig:
    """Configuração de features"""
    # Price features
    use_returns: bool = True
    use_log_returns: bool = True
    use_price_levels: bool = True

    # Technical indicators
    use_sma: bool = True
    sma_periods: List[int] = None
    use_ema: bool = True
    ema_periods: List[int] = None
    use_rsi: bool = True
    rsi_period: int = 14
    use_macd: bool = True
    use_bollinger: bool = True
    bb_period: int = 20
    bb_std: float = 2.0
    use_atr: bool = True
    atr_period: int = 14

    # Time features
    use_time_features: bool = True
    use_cyclical_encoding: bool = True

    # Statistical features
    use_rolling_stats: bool = True
    rolling_windows: List[int] = None
    use_volatility: bool = True

    # Cross-currency
    use_cross_correlations: bool = False
    correlation_window: int = 30

    # Scaling
    scaler_type: str = "robust"  # standard, minmax, robust

    def __post_init__(self):
        if self.sma_periods is None:
            self.sma_periods = [5, 10, 20, 50, 100]
        if self.ema_periods is None:
            self.ema_periods = [5, 10, 20, 50]
        if self.rolling_windows is None:
            self.rolling_windows = [5, 10, 20, 50]


class FeatureEngineer:
    """Engenharia de features para séries temporais de câmbio"""

    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        self.scaler = self._get_scaler()
        self._fitted = False

    def _get_scaler(self):
        """Retorna scaler configurado"""
        if self.config.scaler_type == "standard":
            return StandardScaler()
        elif self.config.scaler_type == "minmax":
            return MinMaxScaler()
        elif self.config.scaler_type == "robust":
            return RobustScaler()
        return RobustScaler()

    def create_features(
        self,
        df: pd.DataFrame,
        target_col: str = "rate",
        date_col: str = "timestamp",
        additional_cols: Optional[Dict[str, pd.Series]] = None
    ) -> pd.DataFrame:
        """
        Cria features a partir de série temporal de taxas.

        Args:
            df: DataFrame com colunas [date_col, target_col]
            target_col: Nome da coluna de taxa
            date_col: Nome da coluna de data
            additional_cols: Colunas adicionais (ex: outras moedas para correlação)

        Returns:
            DataFrame com features
        """
        df = df.copy()
        df = df.sort_values(date_col).reset_index(drop=True)

        # Garante que date_col é datetime
        if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
            df[date_col] = pd.to_datetime(df[date_col])

        features = pd.DataFrame(index=df.index)

        # ============================================
        # Price Features
        # ============================================
        if self.config.use_price_levels:
            features[f"{target_col}_level"] = df[target_col]

        if self.config.use_returns:
            features[f"{target_col}_return_1"] = df[target_col].pct_change(1)
            features[f"{target_col}_return_5"] = df[target_col].pct_change(5)
            features[f"{target_col}_return_20"] = df[target_col].pct_change(20)

        if self.config.use_log_returns:
            features[f"{target_col}_logret_1"] = np.log(df[target_col] / df[target_col].shift(1))
            features[f"{target_col}_logret_5"] = np.log(df[target_col] / df[target_col].shift(5))

        # ============================================
        # Technical Indicators
        # ============================================
        if self.config.use_sma:
            for period in self.config.sma_periods:
                features[f"{target_col}_sma_{period}"] = ta.trend.sma_indicator(
                    df[target_col], window=period
                )
                features[f"{target_col}_sma_ratio_{period}"] = (
                    df[target_col] / features[f"{target_col}_sma_{period}"] - 1
                )

        if self.config.use_ema:
            for period in self.config.ema_periods:
                features[f"{target_col}_ema_{period}"] = ta.trend.ema_indicator(
                    df[target_col], window=period
                )
                features[f"{target_col}_ema_ratio_{period}"] = (
                    df[target_col] / features[f"{target_col}_ema_{period}"] - 1
                )

        if self.config.use_rsi:
            features[f"{target_col}_rsi_{self.config.rsi_period}"] = ta.momentum.rsi(
                df[target_col], window=self.config.rsi_period
            )

        if self.config.use_macd:
            macd = ta.trend.MACD(df[target_col])
            features[f"{target_col}_macd"] = macd.macd()
            features[f"{target_col}_macd_signal"] = macd.macd_signal()
            features[f"{target_col}_macd_diff"] = macd.macd_diff()

        if self.config.use_bollinger:
            bb = ta.volatility.BollingerBands(
                df[target_col], window=self.config.bb_period, window_dev=self.config.bb_std
            )
            features[f"{target_col}_bb_upper"] = bb.bollinger_hband()
            features[f"{target_col}_bb_lower"] = bb.bollinger_lband()
            features[f"{target_col}_bb_middle"] = bb.bollinger_mavg()
            features[f"{target_col}_bb_width"] = bb.bollinger_wband()
            features[f"{target_col}_bb_pct"] = bb.bollinger_pband()

        if self.config.use_atr:
            # ATR precisa de high, low, close - aproximamos com close
            features[f"{target_col}_atr_{self.config.atr_period}"] = ta.volatility.average_true_range(
                high=df[target_col], low=df[target_col], close=df[target_col], window=self.config.atr_period
            )

        # ============================================
        # Rolling Statistics
        # ============================================
        if self.config.use_rolling_stats:
            for window in self.config.rolling_windows:
                features[f"{target_col}_roll_mean_{window}"] = df[target_col].rolling(window).mean()
                features[f"{target_col}_roll_std_{window}"] = df[target_col].rolling(window).std()
                features[f"{target_col}_roll_min_{window}"] = df[target_col].rolling(window).min()
                features[f"{target_col}_roll_max_{window}"] = df[target_col].rolling(window).max()
                features[f"{target_col}_roll_median_{window}"] = df[target_col].rolling(window).median()
                features[f"{target_col}_roll_skew_{window}"] = df[target_col].rolling(window).skew()
                features[f"{target_col}_roll_kurt_{window}"] = df[target_col].rolling(window).kurt()

        if self.config.use_volatility:
            # Volatilidade realizada (rolling std de log returns)
            logret = np.log(df[target_col] / df[target_col].shift(1))
            for window in self.config.rolling_windows:
                features[f"{target_col}_realized_vol_{window}"] = logret.rolling(window).std() * np.sqrt(252)

        # ============================================
        # Time Features
        # ============================================
        if self.config.use_time_features:
            dt = df[date_col].dt
            features["hour"] = dt.hour
            features["day_of_week"] = dt.dayofweek
            features["day_of_month"] = dt.day
            features["week_of_year"] = dt.isocalendar().week
            features["month"] = dt.month
            features["quarter"] = dt.quarter
            features["year"] = dt.year
            features["is_month_end"] = dt.is_month_end.astype(int)
            features["is_quarter_end"] = dt.is_quarter_end.astype(int)
            features["is_year_end"] = dt.is_year_end.astype(int)

            if self.config.use_cyclical_encoding:
                # Encoding cíclico para features temporais
                features["hour_sin"] = np.sin(2 * np.pi * dt.hour / 24)
                features["hour_cos"] = np.cos(2 * np.pi * dt.hour / 24)
                features["dow_sin"] = np.sin(2 * np.pi * dt.dayofweek / 7)
                features["dow_cos"] = np.cos(2 * np.pi * dt.dayofweek / 7)
                features["month_sin"] = np.sin(2 * np.pi * dt.month / 12)
                features["month_cos"] = np.cos(2 * np.pi * dt.month / 12)

        # ============================================
        # Lag Features
        # ============================================
        for lag in [1, 2, 3, 5, 10, 20]:
            features[f"{target_col}_lag_{lag}"] = df[target_col].shift(lag)
            if self.config.use_returns:
                features[f"{target_col}_return_lag_{lag}"] = df[target_col].pct_change(lag)

        # ============================================
        # Cross-Currency Features (se fornecido)
        # ============================================
        if additional_cols and self.config.use_cross_correlations:
            for name, series in additional_cols.items():
                if len(series) == len(df):
                    aligned = series.reindex(df.index)
                    # Correlação rolling
                    features[f"{target_col}_corr_{name}_{self.config.correlation_window}"] = (
                        df[target_col].rolling(self.config.correlation_window)
                        .corr(aligned)
                    )
                    # Ratio
                    features[f"{target_col}_ratio_{name}"] = df[target_col] / aligned

        # ============================================
        # Target (para treino supervisionado)
        # ============================================
        # Target: próxima taxa (para previsão 1-step ahead)
        features["target"] = df[target_col].shift(-1)
        # Target: retorno próximo
        features["target_return"] = df[target_col].pct_change(1).shift(-1)

        # Remove NaN
        features = features.replace([np.inf, -np.inf], np.nan)

        return features

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        target_col: str = "target",
        drop_na: bool = True,
        scale: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepara dados para treino.

        Returns:
            X: Features array
            y: Target array
            feature_names: Nomes das features
        """
        # Separa features e target
        feature_cols = [c for c in df.columns if c not in [target_col, "target_return", "timestamp", "date"]]
        X = df[feature_cols].values
        y = df[target_col].values

        if drop_na:
            # Remove linhas com NaN
            mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
            X = X[mask]
            y = y[mask]

        if scale and not self._fitted:
            X = self.scaler.fit_transform(X)
            self._fitted = True
        elif scale and self._fitted:
            X = self.scaler.transform(X)

        return X, y, feature_cols

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Transforma novos dados usando scaler já fitado"""
        feature_cols = [c for c in df.columns if c not in ["target", "target_return", "timestamp", "date"]]
        X = df[feature_cols].values
        if self._fitted:
            X = self.scaler.transform(X)
        return X

    def get_feature_importance_names(self) -> List[str]:
        """Retorna nomes das features na ordem correta"""
        # Serve para interpretar feature importance dos modelos
        return []


def create_lagged_dataset(
    df: pd.DataFrame,
    target_col: str,
    n_lags: int = 20,
    horizon: int = 1,
    date_col: str = "timestamp"
) -> pd.DataFrame:
    """
    Cria dataset com lags para modelos que precisam de janela temporal
    (ex: LSTM, ARIMA com regressores)
    """
    df = df.copy()
    df = df.sort_values(date_col).reset_index(drop=True)

    # Cria lags
    for i in range(1, n_lags + 1):
        df[f"{target_col}_lag_{i}"] = df[target_col].shift(i)

    # Target: horizon steps ahead
    df[f"target_h{horizon}"] = df[target_col].shift(-horizon)

    return df.dropna().reset_index(drop=True)


def add_external_features(
    df: pd.DataFrame,
    external_data: Dict[str, pd.DataFrame],
    date_col: str = "timestamp",
    how: str = "left"
) -> pd.DataFrame:
    """
    Adiciona features externas (ex: índices econômicos, commodities, etc.)

    Args:
        df: DataFrame principal
        external_data: Dict[name, DataFrame] com colunas [date_col, value_col]
        date_col: Coluna de data para merge
        how: Tipo de join

    Returns:
        DataFrame com features externas merged
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    for name, ext_df in external_data.items():
        ext_df = ext_df.copy()
        ext_df[date_col] = pd.to_datetime(ext_df[date_col])
        ext_df = ext_df.rename(columns={ext_df.columns[1]: f"ext_{name}"})
        df = df.merge(ext_df, on=date_col, how=how)

    return df