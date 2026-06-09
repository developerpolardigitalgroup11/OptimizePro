"""ML Forecasting Engine — per-product × per-marketplace time-series forecasting."""

import numpy as np
from datetime import date, timedelta
from flask import current_app
from models import db, Forecast, MarketplaceInventory
from services.pipeline_service import get_training_data, get_training_data_all_marketplaces
from cache import cache_get, cache_set


class ForecastResult:
    def __init__(self, daily_demand, confidence_lower, confidence_upper, model_used, horizon, data_points):
        self.daily_demand = daily_demand
        self.confidence_lower = confidence_lower
        self.confidence_upper = confidence_upper
        self.model_used = model_used
        self.horizon = horizon
        self.data_points = data_points

    @property
    def total_demand(self):
        return self.daily_demand * self.horizon

    def to_dict(self):
        return {
            'daily_demand': round(self.daily_demand, 2),
            'total_demand': round(self.total_demand, 2),
            'confidence_lower': round(self.confidence_lower, 2),
            'confidence_upper': round(self.confidence_upper, 2),
            'model_used': self.model_used,
            'horizon': self.horizon,
            'data_points': self.data_points,
        }


def get_daily_average(product_id, marketplace_id, window=30):
    """Get rolling average daily sales for a product on a marketplace."""
    df = get_training_data(product_id, marketplace_id)
    if df.empty:
        return 0.0
    recent = df.tail(window)
    return recent['quantity'].mean()


def forecast_demand(product_id, marketplace_id, horizon=None):
    """Forecast demand using tiered model selection."""
    if horizon is None:
        try:
            horizon = current_app.config.get('FORECAST_HORIZON', 14)
        except RuntimeError:
            horizon = 14

    # Check cache
    cache_key = f'forecast_{product_id}_{marketplace_id}_{horizon}'
    cached = cache_get(cache_key)
    if cached:
        return cached

    df = get_training_data(product_id, marketplace_id)
    data_points = len(df) if not df.empty else 0

    if data_points < 3:
        # Not enough data — use simple fallback
        avg = get_daily_average(product_id, marketplace_id, window=data_points) if data_points > 0 else 1.0
        result = ForecastResult(
            daily_demand=max(avg, 0.1),
            confidence_lower=0,
            confidence_upper=avg * 2,
            model_used='insufficient_data',
            horizon=horizon,
            data_points=data_points,
        )
        cache_set(cache_key, result, 300)
        return result

    quantities = df['quantity'].values.astype(float)

    try:
        min_data_hw = 30
        min_data_es = 14
        min_data_sma = 7

        if data_points >= min_data_hw:
            result = _holt_winters_forecast(quantities, horizon, data_points)
        elif data_points >= min_data_es:
            result = _exp_smoothing_forecast(quantities, horizon, data_points)
        elif data_points >= min_data_sma:
            result = _sma_forecast(quantities, horizon, data_points)
        else:
            result = _simple_avg_forecast(quantities, horizon, data_points)
    except Exception:
        # Fallback on any model failure
        result = _simple_avg_forecast(quantities, horizon, data_points)

    # Store forecast in DB
    _store_forecast(product_id, marketplace_id, result)

    cache_set(cache_key, result, 300)
    return result


def _holt_winters_forecast(quantities, horizon, data_points):
    """Holt-Winters Exponential Smoothing with weekly seasonality."""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        model = ExponentialSmoothing(
            quantities,
            seasonal_periods=7,
            trend='add',
            seasonal='add',
            initialization_method='estimated',
        )
        fitted = model.fit(optimized=True, use_brute=False)
        forecast = fitted.forecast(horizon)
        daily_demand = max(np.mean(forecast), 0.1)
        std = np.std(forecast)
        return ForecastResult(
            daily_demand=daily_demand,
            confidence_lower=max(daily_demand - 1.96 * std, 0),
            confidence_upper=daily_demand + 1.96 * std,
            model_used='holt_winters',
            horizon=horizon,
            data_points=data_points,
        )
    except Exception:
        return _exp_smoothing_forecast(quantities, horizon, data_points)


def _exp_smoothing_forecast(quantities, horizon, data_points):
    """Single Exponential Smoothing."""
    try:
        from statsmodels.tsa.holtwinters import SimpleExpSmoothing
        model = SimpleExpSmoothing(quantities, initialization_method='estimated')
        fitted = model.fit(optimized=True)
        forecast = fitted.forecast(horizon)
        daily_demand = max(np.mean(forecast), 0.1)
        std = np.std(quantities[-14:])
        return ForecastResult(
            daily_demand=daily_demand,
            confidence_lower=max(daily_demand - 1.96 * std, 0),
            confidence_upper=daily_demand + 1.96 * std,
            model_used='exponential_smoothing',
            horizon=horizon,
            data_points=data_points,
        )
    except Exception:
        return _sma_forecast(quantities, horizon, data_points)


def _sma_forecast(quantities, horizon, data_points):
    """Simple Moving Average (7-day window)."""
    window = min(7, len(quantities))
    avg = np.mean(quantities[-window:])
    std = np.std(quantities[-window:])
    daily_demand = max(avg, 0.1)
    return ForecastResult(
        daily_demand=daily_demand,
        confidence_lower=max(daily_demand - 1.96 * std, 0),
        confidence_upper=daily_demand + 1.96 * std,
        model_used='sma_7',
        horizon=horizon,
        data_points=data_points,
    )


def _simple_avg_forecast(quantities, horizon, data_points):
    """Simple average of all available data."""
    avg = np.mean(quantities) if len(quantities) > 0 else 1.0
    std = np.std(quantities) if len(quantities) > 1 else avg * 0.5
    daily_demand = max(avg, 0.1)
    return ForecastResult(
        daily_demand=daily_demand,
        confidence_lower=max(daily_demand - 1.96 * std, 0),
        confidence_upper=daily_demand + 1.96 * std,
        model_used='simple_average',
        horizon=horizon,
        data_points=data_points,
    )


def _store_forecast(product_id, marketplace_id, result):
    """Store forecast results in the database."""
    try:
        today = date.today()
        for day_offset in range(result.horizon):
            forecast_date = today + timedelta(days=day_offset + 1)
            existing = Forecast.query.filter_by(
                product_id=product_id,
                marketplace_id=marketplace_id,
                forecast_date=forecast_date,
            ).first()
            if existing:
                existing.predicted_demand = result.daily_demand
                existing.confidence_lower = result.confidence_lower
                existing.confidence_upper = result.confidence_upper
                existing.model_used = result.model_used
            else:
                f = Forecast(
                    product_id=product_id,
                    marketplace_id=marketplace_id,
                    forecast_date=forecast_date,
                    predicted_demand=result.daily_demand,
                    confidence_lower=result.confidence_lower,
                    confidence_upper=result.confidence_upper,
                    model_used=result.model_used,
                )
                db.session.add(f)
        db.session.commit()
    except Exception:
        db.session.rollback()


def forecast_demand_all_marketplaces(product_id, horizon=None):
    """Forecast demand across all active marketplaces for a product."""
    mi_list = MarketplaceInventory.query.filter_by(product_id=product_id, is_listed=True).all()
    results = {}
    for mi in mi_list:
        results[mi.marketplace_id] = forecast_demand(product_id, mi.marketplace_id, horizon)
    return results


def get_restock_recommendation(product_id):
    """Calculate total restock recommendation based on all marketplace forecasts."""
    from models import Product
    try:
        safety = current_app.config.get('SAFETY_FACTOR', 1.5)
        lead_time = current_app.config.get('DEFAULT_LEAD_TIME', 7)
    except RuntimeError:
        safety = 1.5
        lead_time = 7

    product = Product.query.get(product_id)
    if not product:
        return None

    forecasts = forecast_demand_all_marketplaces(product_id)
    total_daily_demand = sum(f.daily_demand for f in forecasts.values())
    recommended_qty = int(total_daily_demand * lead_time * safety)

    return {
        'product_id': product_id,
        'product_name': product.name,
        'current_stock': product.total_warehouse_qty,
        'recommended_restock': max(recommended_qty - product.total_warehouse_qty, 0),
        'total_daily_demand': round(total_daily_demand, 2),
        'lead_time_days': lead_time,
        'safety_factor': safety,
        'per_marketplace': {mid: f.to_dict() for mid, f in forecasts.items()},
    }
