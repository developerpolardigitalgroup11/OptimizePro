"""Forecast routes."""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Product, Marketplace, MarketplaceInventory
from services.forecast_service import forecast_demand, forecast_demand_all_marketplaces, get_restock_recommendation
from services.pipeline_service import get_training_data, get_data_quality_report

forecasts_bp = Blueprint('forecasts', __name__)

_HIST_DEFAULT  = 30   # days of history shown by default
_HORIZ_DEFAULT = 14   # forecast horizon days by default


def _parse_forecast_params():
    """Parse hist_days / hist_from / hist_to / horizon from query string.
    Returns (hist_days, hist_from, hist_to, horizon, hist_from_str, hist_to_str).
    """
    today = date.today()

    hist_from_str = request.args.get('hist_from', '')
    hist_to_str   = request.args.get('hist_to', '')
    hist_days_raw = request.args.get('hist_days', None)
    horizon       = request.args.get('horizon', _HORIZ_DEFAULT, type=int)

    # Clamp horizon to valid values
    horizon = max(1, min(horizon, 90))

    hist_from = hist_to = None

    if hist_from_str and hist_to_str:
        try:
            hist_from = datetime.strptime(hist_from_str, '%Y-%m-%d').date()
            hist_to   = datetime.strptime(hist_to_str,   '%Y-%m-%d').date()
            if hist_to > today:
                hist_to = today
            if hist_from >= hist_to:
                hist_from = hist_to - timedelta(days=_HIST_DEFAULT)
            hist_days = max((hist_to - hist_from).days, 1)
        except ValueError:
            hist_from = hist_to = None
            hist_days = int(hist_days_raw) if hist_days_raw and str(hist_days_raw).isdigit() else _HIST_DEFAULT
    else:
        hist_days = int(hist_days_raw) if hist_days_raw and str(hist_days_raw).isdigit() else _HIST_DEFAULT
        hist_to   = today
        hist_from = today - timedelta(days=hist_days)

    hist_from_str = hist_from.isoformat()
    hist_to_str   = hist_to.isoformat()

    return hist_days, hist_from, hist_to, horizon, hist_from_str, hist_to_str


@forecasts_bp.route('/')
@login_required
def overview():
    hist_days, hist_from, hist_to, horizon, hist_from_str, hist_to_str = _parse_forecast_params()

    products = Product.query.filter_by(user_id=current_user.id, is_active=True).order_by(Product.name).all()
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()

    product_forecasts = []
    for p in products:
        fc = forecast_demand_all_marketplaces(p.id)
        mp_data = []
        for mp in marketplaces:
            f = fc.get(mp.id)
            mp_data.append({
                'marketplace': mp,
                'forecast': f.to_dict() if f else None,
            })
        product_forecasts.append({
            'product': p,
            'marketplaces': mp_data,
            'recommendation': get_restock_recommendation(p.id),
        })

    return render_template('forecasts/view.html',
        product_forecasts=product_forecasts,
        marketplaces=marketplaces,
        hist_days=hist_days,
        hist_from=hist_from_str,
        hist_to=hist_to_str,
        horizon=horizon,
    )


@forecasts_bp.route('/api/chart-data/<int:product_id>/<int:marketplace_id>')
@login_required
def chart_data(product_id, marketplace_id):
    """API: Get historical + forecast data for charts."""
    df = get_training_data(product_id, marketplace_id)
    forecast = forecast_demand(product_id, marketplace_id)
    quality = get_data_quality_report(product_id, marketplace_id)

    historical = []
    if not df.empty:
        for _, row in df.iterrows():
            historical.append({
                'date': row['date'].isoformat(),
                'quantity': int(row['quantity']),
                'revenue': round(row['revenue'], 2),
            })

    return jsonify({
        'historical': historical,
        'forecast': forecast.to_dict(),
        'quality': quality,
    })


@forecasts_bp.route('/api/product-chart-data/<int:product_id>')
@login_required
def product_chart_data(product_id):
    """API: Get combined historical + forecast data for all marketplaces of a product."""
    product = Product.query.get(product_id)
    if not product or product.user_id != current_user.id:
        return jsonify({'error': 'Not found'}), 404

    # Parse optional date range & horizon from query params
    _, hist_from, hist_to, horizon, hist_from_str, hist_to_str = _parse_forecast_params()

    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()
    result = {'marketplaces': []}

    for mp in marketplaces:
        mi = MarketplaceInventory.query.filter_by(
            product_id=product_id, marketplace_id=mp.id, is_listed=True
        ).first()
        if not mi:
            continue

        df = get_training_data(product_id, mp.id)
        forecast = forecast_demand(product_id, mp.id)

        # Filter historical data to the requested window
        historical = []
        if not df.empty:
            for _, row in df.iterrows():
                row_date = row['date'].date() if hasattr(row['date'], 'date') else row['date']
                if hist_from <= row_date <= hist_to:
                    historical.append({
                        'date': row_date.isoformat(),
                        'quantity': int(row['quantity']),
                    })

        # Build forecast dates using the requested horizon
        from datetime import date as date_cls, timedelta
        if historical:
            last_date = date_cls.fromisoformat(historical[-1]['date'])
        else:
            last_date = date_cls.today()

        forecast_points = []
        for day_offset in range(horizon):
            d = last_date + timedelta(days=day_offset + 1)
            forecast_points.append({
                'date': d.isoformat(),
                'predicted': round(forecast.daily_demand, 2),
                'lower': round(forecast.confidence_lower, 2),
                'upper': round(forecast.confidence_upper, 2),
            })

        result['marketplaces'].append({
            'id': mp.id,
            'name': mp.name,
            'color': mp.color,
            'historical': historical,
            'forecast': forecast_points,
            'model_used': forecast.model_used,
            'daily_demand': round(forecast.daily_demand, 2),
            'total_demand': round(forecast.total_demand, 2),
        })

    return jsonify(result)


@forecasts_bp.route('/<int:product_id>/refresh', methods=['POST'])
@login_required
def refresh(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('forecasts.overview'))

    from cache import cache_invalidate
    cache_invalidate(f'forecast_{product_id}')
    forecast_demand_all_marketplaces(product_id)
    flash(f'Forecasts refreshed for {product.name}.', 'success')
    return redirect(url_for('forecasts.overview'))
