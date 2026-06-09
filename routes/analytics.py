"""Analytics dashboard routes."""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import Product, Marketplace
from services.analytics_service import (
    get_prediction_accuracy, get_predicted_vs_actual, get_financial_impact,
    get_marketplace_comparison, get_revenue_trend,
)

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/')
@login_required
def dashboard():
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).order_by(Product.name).all()
    days = request.args.get('days', 30, type=int)

    accuracy = get_prediction_accuracy(current_user.id, days)
    financial = get_financial_impact(current_user.id, days)
    mp_compare = get_marketplace_comparison(current_user.id, days)

    return render_template('analytics/dashboard.html',
        marketplaces=marketplaces,
        products=products,
        days=days,
        accuracy=accuracy,
        financial=financial,
        mp_compare=mp_compare,
    )


@analytics_bp.route('/api/predicted-vs-actual')
@login_required
def api_predicted_vs_actual():
    product_id = request.args.get('product_id', type=int)
    marketplace_id = request.args.get('marketplace_id', type=int)
    days = request.args.get('days', 30, type=int)

    if not product_id or not marketplace_id:
        return jsonify([])

    data = get_predicted_vs_actual(product_id, marketplace_id, days)
    return jsonify(data)


@analytics_bp.route('/api/revenue-trend')
@login_required
def api_revenue_trend():
    days = request.args.get('days', 30, type=int)
    data = get_revenue_trend(current_user.id, days)
    return jsonify(data)


@analytics_bp.route('/api/marketplace-comparison')
@login_required
def api_marketplace_comparison():
    days = request.args.get('days', 30, type=int)
    data = get_marketplace_comparison(current_user.id, days)
    return jsonify(data)
