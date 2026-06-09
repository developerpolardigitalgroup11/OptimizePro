"""Dashboard routes — main landing page."""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import db, Product, Sale, Alert, Marketplace, MarketplaceInventory, DailySalesSummary
from datetime import date, datetime
from services.alert_service import get_active_alerts

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).all()
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()

    # KPIs
    total_products = len(products)
    total_warehouse_stock = sum(p.total_warehouse_qty for p in products)

    # Today's sales
    today = date.today()
    today_start = datetime(today.year, today.month, today.day)
    product_ids = [p.id for p in products]
    today_sales = Sale.query.filter(
        Sale.product_id.in_(product_ids),
        Sale.sale_date >= today_start,
    ).all() if product_ids else []
    sales_today_count = sum(s.quantity_sold for s in today_sales)
    sales_today_revenue = sum(s.sale_price * s.quantity_sold for s in today_sales)

    # Alerts
    alerts = get_active_alerts(current_user.id)
    alert_count = len(alerts)

    # Marketplace overview
    mp_overview = []
    for mp in marketplaces:
        mi_list = MarketplaceInventory.query.filter(
            MarketplaceInventory.marketplace_id == mp.id,
            MarketplaceInventory.product_id.in_(product_ids),
        ).all() if product_ids else []
        total_allocated = sum(mi.allocated_qty for mi in mi_list)

        mp_today_sales = [s for s in today_sales if s.marketplace_id == mp.id]
        mp_today_units = sum(s.quantity_sold for s in mp_today_sales)
        mp_today_rev = sum(s.sale_price * s.quantity_sold for s in mp_today_sales)

        mp_overview.append({
            'marketplace': mp,
            'allocated': total_allocated,
            'today_units': mp_today_units,
            'today_revenue': round(mp_today_rev, 2),
            'products_listed': len([mi for mi in mi_list if mi.is_listed]),
        })

    # Recent sales
    recent_sales = Sale.query.filter(
        Sale.product_id.in_(product_ids),
    ).order_by(Sale.sale_date.desc()).limit(10).all() if product_ids else []

    return render_template('dashboard.html',
        total_products=total_products,
        total_warehouse_stock=total_warehouse_stock,
        sales_today_count=sales_today_count,
        sales_today_revenue=round(sales_today_revenue, 2),
        alert_count=alert_count,
        alerts=alerts[:5],
        mp_overview=mp_overview,
        recent_sales=recent_sales,
        marketplaces=marketplaces,
    )
