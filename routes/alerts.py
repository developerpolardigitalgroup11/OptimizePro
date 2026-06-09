"""Alerts routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Marketplace
from services.alert_service import get_active_alerts, mark_alert_read, evaluate_all_products

alerts_bp = Blueprint('alerts', __name__)


@alerts_bp.route('/')
@login_required
def list_alerts():
    mp_filter = request.args.get('marketplace_id', type=int)
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()
    alerts = get_active_alerts(current_user.id, marketplace_id=mp_filter)
    return render_template('alerts/list.html', alerts=alerts, marketplaces=marketplaces, selected_mp=mp_filter)


@alerts_bp.route('/<int:alert_id>/dismiss', methods=['POST'])
@login_required
def dismiss(alert_id):
    mark_alert_read(alert_id)
    flash('Alert dismissed.', 'success')
    return redirect(url_for('alerts.list_alerts'))


@alerts_bp.route('/refresh', methods=['POST'])
@login_required
def refresh():
    evaluate_all_products(current_user.id)
    flash('Alerts refreshed.', 'success')
    return redirect(url_for('alerts.list_alerts'))


@alerts_bp.route('/api/count')
@login_required
def alert_count():
    """API: Get unread alert count for navbar badge."""
    alerts = get_active_alerts(current_user.id)
    return jsonify({'count': len(alerts)})
