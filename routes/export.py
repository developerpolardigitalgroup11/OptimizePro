"""Export routes — CSV download endpoints."""

from flask import Blueprint, Response, request
from flask_login import login_required, current_user
from models import AllocationPlan
from services.export_service import (
    export_allocation_plan, export_sales_history,
    export_analytics_summary, export_alerts,
)

export_bp = Blueprint('export', __name__)


@export_bp.route('/allocation/<int:plan_id>')
@login_required
def allocation(plan_id):
    plan = AllocationPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        return 'Access denied', 403

    csv_data = export_allocation_plan(plan)
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=allocation_plan_{plan_id}.csv'}
    )


@export_bp.route('/sales')
@login_required
def sales():
    days = request.args.get('days', 30, type=int)
    marketplace_id = request.args.get('marketplace_id', type=int)
    csv_data = export_sales_history(current_user.id, days, marketplace_id)
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=sales_history_{days}d.csv'}
    )


@export_bp.route('/analytics')
@login_required
def analytics():
    days = request.args.get('days', 30, type=int)
    csv_data = export_analytics_summary(current_user.id, days)
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=analytics_summary_{days}d.csv'}
    )


@export_bp.route('/alerts')
@login_required
def alerts():
    csv_data = export_alerts(current_user.id)
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=active_alerts.csv'}
    )
