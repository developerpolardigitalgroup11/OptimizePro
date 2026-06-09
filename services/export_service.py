"""Export service — CSV and PDF generation for reports."""

import io
import csv
from datetime import date, timedelta
from models import Product, Sale, Marketplace, AllocationPlan, Alert, Forecast, DailySalesSummary


def export_allocation_plan(plan):
    """Export a single allocation plan as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Marketplace', 'Recommended Qty', 'Predicted Demand (14d)', 'Share %', 'Reasoning'])

    for line in plan.lines:
        mp = Marketplace.query.get(line.marketplace_id)
        writer.writerow([
            mp.name if mp else 'Unknown',
            line.recommended_qty,
            round(line.predicted_demand_14d, 1),
            f'{line.marketplace_share_pct:.1f}%',
            line.reasoning,
        ])

    writer.writerow([])
    writer.writerow(['Total Units', plan.total_units_to_allocate])
    writer.writerow(['Status', plan.status])
    writer.writerow(['Generated', plan.created_at.strftime('%Y-%m-%d %H:%M')])

    output.seek(0)
    return output.getvalue()


def export_sales_history(user_id, days=30, marketplace_id=None):
    """Export sales history as CSV."""
    cutoff = date.today() - timedelta(days=days)
    products = Product.query.filter_by(user_id=user_id, is_active=True).all()
    product_ids = [p.id for p in products]
    product_map = {p.id: p for p in products}

    query = Sale.query.filter(
        Sale.product_id.in_(product_ids),
        Sale.sale_date >= cutoff,
    )
    if marketplace_id:
        query = query.filter(Sale.marketplace_id == marketplace_id)
    sales = query.order_by(Sale.sale_date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Product SKU', 'Product Name', 'Marketplace', 'Qty Sold', 'Sale Price', 'Cost', 'Revenue', 'Profit'])

    for s in sales:
        p = product_map.get(s.product_id)
        mp = Marketplace.query.get(s.marketplace_id)
        writer.writerow([
            s.sale_date.strftime('%Y-%m-%d %H:%M'),
            p.sku if p else '',
            p.name if p else '',
            mp.name if mp else '',
            s.quantity_sold,
            round(s.sale_price, 2),
            round(s.cost_at_sale, 2),
            round(s.revenue, 2),
            round(s.profit, 2),
        ])

    output.seek(0)
    return output.getvalue()


def export_analytics_summary(user_id, days=30):
    """Export analytics summary as CSV."""
    from services.analytics_service import get_financial_impact, get_marketplace_comparison, get_prediction_accuracy

    accuracy = get_prediction_accuracy(user_id, days)
    financial = get_financial_impact(user_id, days)
    mp_compare = get_marketplace_comparison(user_id, days)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['=== OptimizePro Analytics Summary ==='])
    writer.writerow(['Period', f'Last {days} days'])
    writer.writerow(['Generated', date.today().isoformat()])
    writer.writerow([])

    writer.writerow(['=== Overall KPIs ==='])
    writer.writerow(['Forecast Accuracy', f"{accuracy['accuracy_pct']}%"])
    writer.writerow(['Profits Gained', f"₹{financial['profits_gained']}"])
    writer.writerow(['Losses Saved', f"₹{financial['losses_saved']}"])
    writer.writerow(['Net Impact', f"₹{financial['net_impact']}"])
    writer.writerow([])

    writer.writerow(['=== Marketplace Performance ==='])
    writer.writerow(['Marketplace', 'Revenue', 'Units Sold', 'Profit', 'Avg Daily Units'])
    for mp in mp_compare:
        writer.writerow([mp['name'], f"₹{mp['revenue']}", mp['units_sold'], f"₹{mp['profit']}", mp['avg_daily_units']])

    output.seek(0)
    return output.getvalue()


def export_alerts(user_id):
    """Export active alerts as CSV."""
    products = Product.query.filter_by(user_id=user_id, is_active=True).all()
    product_ids = [p.id for p in products]
    product_map = {p.id: p for p in products}

    alerts = Alert.query.filter(
        Alert.product_id.in_(product_ids),
        Alert.is_read == False,
    ).order_by(Alert.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Product', 'Marketplace', 'Type', 'Priority', 'Message'])

    for a in alerts:
        p = product_map.get(a.product_id)
        mp = Marketplace.query.get(a.marketplace_id) if a.marketplace_id else None
        writer.writerow([
            a.created_at.strftime('%Y-%m-%d %H:%M'),
            p.name if p else '',
            mp.name if mp else 'Cross-marketplace',
            a.alert_type,
            a.priority,
            a.message,
        ])

    output.seek(0)
    return output.getvalue()
