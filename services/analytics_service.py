"""Analytics computation engine — cross-marketplace insights."""

from datetime import date, timedelta
from models import db, DailySalesSummary, Forecast, RecommendationOutcome, Product, Marketplace, Sale
from cache import cache_get, cache_set


def get_prediction_accuracy(user_id, days=30, marketplace_id=None):
    """Calculate MAPE (Mean Absolute Percentage Error) for forecasts."""
    cache_key = f'analytics_accuracy_{user_id}_{days}_{marketplace_id}'
    cached = cache_get(cache_key)
    if cached:
        return cached

    cutoff = date.today() - timedelta(days=days)
    products = Product.query.filter_by(user_id=user_id, is_active=True).all()
    product_ids = [p.id for p in products]

    forecasts = Forecast.query.filter(
        Forecast.product_id.in_(product_ids),
        Forecast.forecast_date >= cutoff,
        Forecast.forecast_date <= date.today(),
    )
    if marketplace_id:
        forecasts = forecasts.filter(Forecast.marketplace_id == marketplace_id)
    forecasts = forecasts.all()

    if not forecasts:
        result = {'mape': 0, 'accuracy_pct': 100, 'data_points': 0, 'per_marketplace': {}}
        cache_set(cache_key, result, 300)
        return result

    errors = []
    mp_errors = {}

    for f in forecasts:
        actual = DailySalesSummary.query.filter_by(
            product_id=f.product_id,
            marketplace_id=f.marketplace_id,
            summary_date=f.forecast_date,
        ).first()

        if actual and actual.total_quantity_sold > 0:
            ape = abs(f.predicted_demand - actual.total_quantity_sold) / actual.total_quantity_sold
            errors.append(ape)
            mp_id = f.marketplace_id
            if mp_id not in mp_errors:
                mp_errors[mp_id] = []
            mp_errors[mp_id].append(ape)

    mape = (sum(errors) / len(errors) * 100) if errors else 0
    per_mp = {}
    for mp_id, errs in mp_errors.items():
        mp = Marketplace.query.get(mp_id)
        mp_mape = sum(errs) / len(errs) * 100
        per_mp[mp_id] = {
            'name': mp.name if mp else 'Unknown',
            'color': mp.color if mp else '#666',
            'mape': round(mp_mape, 1),
            'accuracy_pct': round(max(100 - mp_mape, 0), 1),
            'data_points': len(errs),
        }

    result = {
        'mape': round(mape, 1),
        'accuracy_pct': round(max(100 - mape, 0), 1),
        'data_points': len(errors),
        'per_marketplace': per_mp,
    }
    cache_set(cache_key, result, 300)
    return result


def get_predicted_vs_actual(product_id, marketplace_id, days=30):
    """Get day-by-day predicted vs actual pairs."""
    cutoff = date.today() - timedelta(days=days)

    summaries = DailySalesSummary.query.filter(
        DailySalesSummary.product_id == product_id,
        DailySalesSummary.marketplace_id == marketplace_id,
        DailySalesSummary.summary_date >= cutoff,
    ).order_by(DailySalesSummary.summary_date).all()

    result = []
    for s in summaries:
        forecast = Forecast.query.filter_by(
            product_id=product_id,
            marketplace_id=marketplace_id,
            forecast_date=s.summary_date,
        ).first()

        result.append({
            'date': s.summary_date.isoformat(),
            'actual': s.total_quantity_sold,
            'predicted': round(forecast.predicted_demand, 1) if forecast else 0,
            'revenue': round(s.total_revenue, 2),
        })

    return result


def get_financial_impact(user_id, days=30):
    """Calculate total financial impact from recommendations."""
    cache_key = f'analytics_financial_{user_id}_{days}'
    cached = cache_get(cache_key)
    if cached:
        return cached

    cutoff = date.today() - timedelta(days=days)
    products = Product.query.filter_by(user_id=user_id, is_active=True).all()
    product_ids = [p.id for p in products]

    outcomes = RecommendationOutcome.query.filter(
        RecommendationOutcome.product_id.in_(product_ids),
        RecommendationOutcome.recommendation_date >= cutoff,
    ).all()

    total_profit = sum(o.profit_impact for o in outcomes if o.profit_impact > 0)
    total_loss_saved = sum(o.loss_saved for o in outcomes if o.loss_saved > 0)
    total_followed = sum(1 for o in outcomes if o.followed)
    total_count = len(outcomes)

    result = {
        'profits_gained': round(total_profit, 2),
        'losses_saved': round(total_loss_saved, 2),
        'net_impact': round(total_profit + total_loss_saved, 2),
        'follow_rate': round(total_followed / total_count * 100, 1) if total_count > 0 else 0,
        'total_recommendations': total_count,
    }
    cache_set(cache_key, result, 300)
    return result


def get_marketplace_comparison(user_id, days=30):
    """Per-marketplace KPIs for comparison."""
    cache_key = f'analytics_mp_compare_{user_id}_{days}'
    cached = cache_get(cache_key)
    if cached:
        return cached

    cutoff = date.today() - timedelta(days=days)
    marketplaces = Marketplace.query.filter_by(user_id=user_id, is_active=True).all()
    products = Product.query.filter_by(user_id=user_id, is_active=True).all()
    product_ids = [p.id for p in products]

    result = []
    for mp in marketplaces:
        summaries = DailySalesSummary.query.filter(
            DailySalesSummary.product_id.in_(product_ids),
            DailySalesSummary.marketplace_id == mp.id,
            DailySalesSummary.summary_date >= cutoff,
        ).all()

        total_revenue = sum(s.total_revenue for s in summaries)
        total_units = sum(s.total_quantity_sold for s in summaries)
        total_cost = sum(s.total_cost for s in summaries)

        result.append({
            'id': mp.id,
            'name': mp.name,
            'code': mp.code,
            'color': mp.color,
            'revenue': round(total_revenue, 2),
            'units_sold': total_units,
            'profit': round(total_revenue - total_cost, 2),
            'avg_daily_units': round(total_units / max(days, 1), 1),
        })

    cache_set(cache_key, result, 300)
    return result


def get_revenue_trend(user_id, days=30):
    """Daily revenue per marketplace for trend chart."""
    cutoff = date.today() - timedelta(days=days)
    products = Product.query.filter_by(user_id=user_id, is_active=True).all()
    product_ids = [p.id for p in products]
    marketplaces = Marketplace.query.filter_by(user_id=user_id, is_active=True).all()

    result = {'dates': [], 'datasets': {}}

    # Build date list
    for i in range(days):
        d = cutoff + timedelta(days=i + 1)
        result['dates'].append(d.isoformat())

    for mp in marketplaces:
        daily_rev = []
        for i in range(days):
            d = cutoff + timedelta(days=i + 1)
            summaries = DailySalesSummary.query.filter(
                DailySalesSummary.product_id.in_(product_ids),
                DailySalesSummary.marketplace_id == mp.id,
                DailySalesSummary.summary_date == d,
            ).all()
            daily_rev.append(round(sum(s.total_revenue for s in summaries), 2))
        result['datasets'][mp.id] = {
            'label': mp.name,
            'color': mp.color,
            'data': daily_rev,
        }

    return result
