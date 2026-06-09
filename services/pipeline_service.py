"""Data recording pipeline — aggregates sales into daily summaries for ML training."""

from datetime import date, timedelta
import pandas as pd
from models import db, DailySalesSummary, Sale
from cache import cache_invalidate


def record_daily_summary(product_id, marketplace_id, sale_date=None):
    """Upsert daily sales summary for a product × marketplace × date."""
    if sale_date is None:
        sale_date = date.today()
    elif hasattr(sale_date, 'date'):
        sale_date = sale_date.date()

    # Aggregate all sales for this product × marketplace × date
    day_sales = Sale.query.filter(
        Sale.product_id == product_id,
        Sale.marketplace_id == marketplace_id,
        db.func.date(Sale.sale_date) == sale_date,
    ).all()

    total_qty = sum(s.quantity_sold for s in day_sales)
    total_rev = sum(s.sale_price * s.quantity_sold for s in day_sales)
    total_cost = sum(s.cost_at_sale * s.quantity_sold for s in day_sales)

    summary = DailySalesSummary.query.filter_by(
        product_id=product_id,
        marketplace_id=marketplace_id,
        summary_date=sale_date,
    ).first()

    if summary:
        summary.total_quantity_sold = total_qty
        summary.total_revenue = total_rev
        summary.total_cost = total_cost
    else:
        summary = DailySalesSummary(
            product_id=product_id,
            marketplace_id=marketplace_id,
            summary_date=sale_date,
            total_quantity_sold=total_qty,
            total_revenue=total_rev,
            total_cost=total_cost,
        )
        db.session.add(summary)

    db.session.commit()

    # Invalidate caches
    cache_invalidate(f'analytics_')
    cache_invalidate(f'forecast_{product_id}_{marketplace_id}')


def get_training_data(product_id, marketplace_id):
    """Get contiguous daily time series for a product × marketplace, filling gaps with 0."""
    summaries = DailySalesSummary.query.filter_by(
        product_id=product_id,
        marketplace_id=marketplace_id,
    ).order_by(DailySalesSummary.summary_date).all()

    if not summaries:
        return pd.DataFrame(columns=['date', 'quantity', 'revenue', 'cost'])

    # Create date range from first to last sale
    start = summaries[0].summary_date
    end = max(summaries[-1].summary_date, date.today())
    date_range = pd.date_range(start=start, end=end, freq='D')

    # Build lookup
    data_map = {s.summary_date: s for s in summaries}

    rows = []
    for d in date_range:
        d_date = d.date()
        s = data_map.get(d_date)
        rows.append({
            'date': d_date,
            'quantity': s.total_quantity_sold if s else 0,
            'revenue': s.total_revenue if s else 0.0,
            'cost': s.total_cost if s else 0.0,
        })

    return pd.DataFrame(rows)


def get_training_data_all_marketplaces(product_id):
    """Get training data for all marketplaces for a product."""
    from models import MarketplaceInventory
    mi_list = MarketplaceInventory.query.filter_by(product_id=product_id, is_listed=True).all()
    result = {}
    for mi in mi_list:
        df = get_training_data(product_id, mi.marketplace_id)
        if not df.empty:
            result[mi.marketplace_id] = df
    return result


def get_data_quality_report(product_id, marketplace_id):
    """Return data quality metrics for a product × marketplace."""
    df = get_training_data(product_id, marketplace_id)
    if df.empty:
        return {'days': 0, 'mean': 0, 'std': 0, 'min': 0, 'max': 0, 'has_gaps': False}

    return {
        'days': len(df),
        'mean': round(df['quantity'].mean(), 2),
        'std': round(df['quantity'].std(), 2),
        'min': int(df['quantity'].min()),
        'max': int(df['quantity'].max()),
        'has_gaps': df['quantity'].sum() == 0,  # all zeros means no real data
    }
