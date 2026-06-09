"""Stock allocation planner routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Product, Marketplace, AllocationPlan
from services.allocation_service import generate_allocation, apply_allocation, get_allocation_history

allocation_bp = Blueprint('allocation', __name__)


@allocation_bp.route('/')
@login_required
def planner():
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).order_by(Product.name).all()
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('allocation/planner.html', products=products, marketplaces=marketplaces)


@allocation_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    product_id = request.form.get('product_id', type=int)
    total_units = request.form.get('total_units', type=int)

    if not product_id or not total_units or total_units <= 0:
        flash('Please select a product and enter units to allocate.', 'error')
        return redirect(url_for('allocation.planner'))

    try:
        plan = generate_allocation(product_id, total_units, current_user.id)

        plan_data = {
            'plan_id': plan.id,
            'product': Product.query.get(product_id).name,
            'total_units': total_units,
            'lines': [],
        }
        for line in plan.lines:
            mp = Marketplace.query.get(line.marketplace_id)
            plan_data['lines'].append({
                'marketplace': mp.name,
                'color': mp.color,
                'qty': line.recommended_qty,
                'demand': round(line.predicted_demand_14d, 1),
                'share': round(line.marketplace_share_pct, 1),
                'reasoning': line.reasoning,
            })

        return jsonify({'success': True, 'plan': plan_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@allocation_bp.route('/<int:plan_id>/apply', methods=['POST'])
@login_required
def apply(plan_id):
    try:
        plan = apply_allocation(plan_id)
        flash('Allocation applied successfully! Marketplace inventories updated.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('allocation.planner'))


@allocation_bp.route('/history')
@login_required
def history():
    plans = get_allocation_history(current_user.id)
    return render_template('allocation/history.html', plans=plans)
