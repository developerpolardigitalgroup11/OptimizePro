"""Sale processing service — atomic sale recording with quantity reduction."""


class InsufficientStockError(Exception):
    pass


def record_sale(product_id, marketplace_id, quantity, sale_price, user_id, sale_date=None):
    """Record a sale: reduce inventory atomically, create sale record, trigger pipeline."""
    from models import db, Product, MarketplaceInventory, Sale
    from services.pipeline_service import record_daily_summary
    from services.alert_service import evaluate_product
    from cache import cache_invalidate
    from datetime import datetime

    # Fetch product and marketplace inventory in one go
    product = Product.query.get(product_id)
    if not product:
        raise ValueError('Product not found')

    mi = MarketplaceInventory.query.filter_by(
        product_id=product_id,
        marketplace_id=marketplace_id,
    ).first()

    if not mi:
        raise ValueError('Product is not listed on this marketplace')

    if mi.allocated_qty < quantity:
        raise InsufficientStockError(
            f'Insufficient stock on this marketplace. Available: {mi.allocated_qty}, Requested: {quantity}'
        )

    # Atomic update
    mi.allocated_qty -= quantity
    product.total_warehouse_qty -= quantity

    # Create sale record
    sale = Sale(
        product_id=product_id,
        marketplace_id=marketplace_id,
        quantity_sold=quantity,
        sale_price=sale_price,
        cost_at_sale=product.cost_price,
        user_id=user_id,
    )
    if sale_date is not None:
        sale.sale_date = sale_date
    db.session.add(sale)
    db.session.commit()

    # Trigger pipeline (post-commit)
    try:
        record_daily_summary(product_id, marketplace_id, sale.sale_date)
    except Exception:
        pass  # Pipeline failure shouldn't block the sale

    # Evaluate alerts (post-commit)
    try:
        evaluate_product(product_id, marketplace_id)
    except Exception:
        pass  # Alert failure shouldn't block the sale

    # Invalidate caches
    cache_invalidate('dashboard_')
    cache_invalidate(f'analytics_')

    return sale
