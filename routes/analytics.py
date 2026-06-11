"""Analytics dashboard routes."""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import Product, Marketplace
from services.analytics_service import (
    get_prediction_accuracy, get_predicted_vs_actual, get_financial_impact,
    get_marketplace_comparison, get_revenue_trend,
)

analytics_bp = Blueprint('analytics', __name__)


def _parse_date_params():
    """Parse days / date_from / date_to from query string.
    Returns (days, date_from, date_to, date_from_str, date_to_str).
    If date_from+date_to are supplied, days is derived from them.
    """
    today = date.today()

    date_from_str = request.args.get('date_from', '')
    date_to_str   = request.args.get('date_to', '')
    days_raw      = request.args.get('days', None)

    date_from = date_to = None

    # Try explicit date range first
    if date_from_str and date_to_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            date_to   = datetime.strptime(date_to_str,   '%Y-%m-%d').date()
            # Clamp to today
            if date_to > today:
                date_to = today
            if date_from > date_to:
                date_from = date_to - timedelta(days=30)
            days = max((date_to - date_from).days, 1)
        except ValueError:
            date_from = date_to = None
            days = int(days_raw) if days_raw and days_raw.isdigit() else 30
    else:
        days = int(days_raw) if days_raw and str(days_raw).isdigit() else 30
        date_to   = today
        date_from = today - timedelta(days=days)
        date_from_str = date_from.isoformat()
        date_to_str   = date_to.isoformat()

    return days, date_from, date_to, date_from_str, date_to_str


@analytics_bp.route('/')
@login_required
def dashboard():
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).order_by(Product.name).all()

    days, date_from, date_to, date_from_str, date_to_str = _parse_date_params()

    accuracy   = get_prediction_accuracy(current_user.id, days, date_from=date_from, date_to=date_to)
    financial  = get_financial_impact(current_user.id, days, date_from=date_from, date_to=date_to)
    mp_compare = get_marketplace_comparison(current_user.id, days, date_from=date_from, date_to=date_to)

    return render_template('analytics/dashboard.html',
        marketplaces=marketplaces,
        products=products,
        days=days,
        date_from=date_from_str,
        date_to=date_to_str,
        accuracy=accuracy,
        financial=financial,
        mp_compare=mp_compare,
    )


@analytics_bp.route('/api/predicted-vs-actual')
@login_required
def api_predicted_vs_actual():
    product_id     = request.args.get('product_id', type=int)
    marketplace_id = request.args.get('marketplace_id', type=int)
    days, date_from, date_to, _, _ = _parse_date_params()

    if not product_id or not marketplace_id:
        return jsonify([])

    data = get_predicted_vs_actual(product_id, marketplace_id, days,
                                   date_from=date_from, date_to=date_to)
    return jsonify(data)


@analytics_bp.route('/api/revenue-trend')
@login_required
def api_revenue_trend():
    days, date_from, date_to, _, _ = _parse_date_params()
    data = get_revenue_trend(current_user.id, days, date_from=date_from, date_to=date_to)
    return jsonify(data)


@analytics_bp.route('/api/marketplace-comparison')
@login_required
def api_marketplace_comparison():
    days, date_from, date_to, _, _ = _parse_date_params()
    data = get_marketplace_comparison(current_user.id, days, date_from=date_from, date_to=date_to)
    return jsonify(data)
