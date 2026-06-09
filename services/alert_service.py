"""Alert engine — per-marketplace stock level evaluation with cross-marketplace rebalancing."""

from datetime import datetime
from models import db, Alert, Product, MarketplaceInventory, Marketplace
from services.forecast_service import forecast_demand, get_daily_average
from flask import current_app


def evaluate_product(product_id, marketplace_id):
    """Evaluate stock levels for a product on a specific marketplace."""
    try:
        critical_days = current_app.config.get('CRITICAL_DAYS', 3)
        high_days = current_app.config.get('HIGH_ALERT_DAYS', 7)
        overstock_mult = current_app.config.get('OVERSTOCK_MULTIPLIER', 2)
        horizon = current_app.config.get('FORECAST_HORIZON', 14)
    except RuntimeError:
        critical_days, high_days, overstock_mult, horizon = 3, 7, 2, 14

    mi = MarketplaceInventory.query.filter_by(
        product_id=product_id,
        marketplace_id=marketplace_id,
    ).first()

    if not mi or not mi.is_listed:
        return []

    marketplace = Marketplace.query.get(marketplace_id)
    mp_name = marketplace.name if marketplace else 'Unknown'
    daily_avg = get_daily_average(product_id, marketplace_id)
    alerts = []

    if daily_avg <= 0:
        return alerts

    days_of_stock = mi.allocated_qty / daily_avg

    # Get forecast for smarter alerts
    try:
        forecast = forecast_demand(product_id, marketplace_id)
        forecast_daily = forecast.daily_demand
    except Exception:
        forecast_daily = daily_avg

    # CRITICAL
    if days_of_stock < critical_days:
        alerts.append(_create_alert(
            product_id, marketplace_id,
            'CRITICAL', 'HIGH',
            f'🔴 CRITICAL: {mp_name} stock depletes in {days_of_stock:.1f} days! '
            f'Only {mi.allocated_qty} units left.',
        ))
    # UNDERSTOCK
    elif days_of_stock < high_days:
        alerts.append(_create_alert(
            product_id, marketplace_id,
            'UNDERSTOCK', 'HIGH',
            f'🟠 {mp_name}: Stock will run out in {days_of_stock:.1f} days. '
            f'{mi.allocated_qty} units remaining, avg {daily_avg:.1f}/day.',
        ))
    # OVERSTOCK
    elif days_of_stock > overstock_mult * horizon:
        alerts.append(_create_alert(
            product_id, marketplace_id,
            'OVERSTOCK', 'LOW',
            f'🟡 {mp_name}: Overstocked — stock will last {days_of_stock:.0f} days. '
            f'Consider reallocating to other marketplaces.',
        ))

    return alerts


def detect_imbalances(product_id):
    """Detect cross-marketplace stock imbalances and suggest rebalancing."""
    mi_list = MarketplaceInventory.query.filter_by(
        product_id=product_id, is_listed=True
    ).all()

    if len(mi_list) < 2:
        return []

    # Calculate days_of_stock per marketplace
    statuses = []
    for mi in mi_list:
        daily_avg = get_daily_average(product_id, mi.marketplace_id)
        if daily_avg > 0:
            days = mi.allocated_qty / daily_avg
        else:
            days = float('inf') if mi.allocated_qty > 0 else 0
        mp = Marketplace.query.get(mi.marketplace_id)
        statuses.append({
            'mi': mi,
            'marketplace': mp,
            'days': days,
            'daily_avg': daily_avg,
        })

    alerts = []
    overstocked = [s for s in statuses if s['days'] > 30]
    understocked = [s for s in statuses if 0 < s['days'] < 7]

    for over in overstocked:
        for under in understocked:
            # Suggest moving units
            transfer_qty = min(
                int(under['daily_avg'] * 7),  # 7 days worth
                over['mi'].allocated_qty // 4,  # max 25% of overstock
            )
            if transfer_qty > 0:
                alerts.append(_create_alert(
                    product_id, None,
                    'REBALANCE', 'MEDIUM',
                    f'🔄 Rebalance: Move ~{transfer_qty} units from {over["marketplace"].name} '
                    f'to {under["marketplace"].name}. '
                    f'{over["marketplace"].name} has {over["days"]:.0f} days of stock, '
                    f'{under["marketplace"].name} only {under["days"]:.1f} days.',
                ))

    return alerts


def evaluate_all_products(user_id):
    """Batch evaluation across all products × all marketplaces for a user."""
    products = Product.query.filter_by(user_id=user_id, is_active=True).all()
    marketplaces = Marketplace.query.filter_by(user_id=user_id, is_active=True).all()
    all_alerts = []

    for product in products:
        for mp in marketplaces:
            alerts = evaluate_product(product.id, mp.id)
            all_alerts.extend(alerts)
        # Also check for imbalances
        imbalance_alerts = detect_imbalances(product.id)
        all_alerts.extend(imbalance_alerts)

    return all_alerts


def get_active_alerts(user_id, marketplace_id=None):
    """Get unread alerts for a user, optionally filtered by marketplace."""
    products = Product.query.filter_by(user_id=user_id, is_active=True).all()
    product_ids = [p.id for p in products]

    query = Alert.query.filter(
        Alert.product_id.in_(product_ids),
        Alert.is_read == False,
    )

    if marketplace_id:
        query = query.filter(
            (Alert.marketplace_id == marketplace_id) | (Alert.marketplace_id.is_(None))
        )

    # Order by priority: HIGH > MEDIUM > LOW
    priority_order = db.case(
        (Alert.priority == 'HIGH', 1),
        (Alert.priority == 'MEDIUM', 2),
        (Alert.priority == 'LOW', 3),
        else_=4,
    )

    return query.order_by(priority_order, Alert.created_at.desc()).all()


def mark_alert_read(alert_id):
    """Mark an alert as read."""
    alert = Alert.query.get(alert_id)
    if alert:
        alert.is_read = True
        db.session.commit()


def _create_alert(product_id, marketplace_id, alert_type, priority, message):
    """Create and persist an alert, avoiding duplicates."""
    # Check for recent duplicate
    existing = Alert.query.filter_by(
        product_id=product_id,
        marketplace_id=marketplace_id,
        alert_type=alert_type,
        is_read=False,
    ).first()

    if existing:
        existing.message = message
        existing.created_at = datetime.utcnow()
        db.session.commit()
        return existing

    alert = Alert(
        product_id=product_id,
        marketplace_id=marketplace_id,
        alert_type=alert_type,
        priority=priority,
        message=message,
    )
    db.session.add(alert)
    db.session.commit()
    return alert
