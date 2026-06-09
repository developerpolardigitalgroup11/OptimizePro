"""Sales recording routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Product, Marketplace, MarketplaceInventory, Sale
from services.sales_service import record_sale, InsufficientStockError
from datetime import datetime, date, timedelta

sales_bp = Blueprint('sales', __name__)


@sales_bp.route('/record', methods=['GET', 'POST'])
@login_required
def record():
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).order_by(Product.name).all()

    if request.method == 'POST':
        product_id = int(request.form.get('product_id', 0))
        marketplace_id = int(request.form.get('marketplace_id', 0))
        quantity = int(request.form.get('quantity', 0))
        sale_price = float(request.form.get('sale_price', 0))

        # Parse optional sale date
        sale_date_str = request.form.get('sale_date', '').strip()
        sale_date = None
        if sale_date_str:
            try:
                sale_date = datetime.strptime(sale_date_str, '%Y-%m-%d')
            except ValueError:
                flash('Invalid date format.', 'error')
                return render_template('sales/record.html', marketplaces=marketplaces, products=products)

        if not product_id or not marketplace_id or quantity <= 0:
            flash('All fields are required.', 'error')
            return render_template('sales/record.html', marketplaces=marketplaces, products=products)

        try:
            sale = record_sale(product_id, marketplace_id, quantity, sale_price, current_user.id, sale_date=sale_date)
            mi = MarketplaceInventory.query.filter_by(product_id=product_id, marketplace_id=marketplace_id).first()
            mp = Marketplace.query.get(marketplace_id)
            flash(f'Sale recorded! {quantity} units on {mp.name}. Remaining: {mi.allocated_qty}', 'success')
            return redirect(url_for('sales.record'))
        except InsufficientStockError as e:
            flash(str(e), 'error')
        except ValueError as e:
            flash(str(e), 'error')

    return render_template('sales/record.html', marketplaces=marketplaces, products=products)


@sales_bp.route('/history')
@login_required
def history():
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).all()
    product_ids = [p.id for p in products]
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()

    mp_filter = request.args.get('marketplace_id', type=int)
    days = request.args.get('days', 30, type=int)
    cutoff = datetime.now() - timedelta(days=days)

    query = Sale.query.filter(
        Sale.product_id.in_(product_ids),
        Sale.sale_date >= cutoff,
    )
    if mp_filter:
        query = query.filter(Sale.marketplace_id == mp_filter)

    sales = query.order_by(Sale.sale_date.desc()).limit(200).all()

    # KPI aggregates for the summary ribbon
    total_revenue = sum(s.revenue for s in sales) if sales else 0
    total_units = sum(s.quantity_sold for s in sales) if sales else 0
    total_profit = sum(s.profit for s in sales) if sales else 0
    avg_price = (total_revenue / total_units) if total_units else 0
    transaction_count = len(sales)

    return render_template('sales/history.html', sales=sales, marketplaces=marketplaces,
                           selected_mp=mp_filter, days=days,
                           total_revenue=total_revenue, total_units=total_units,
                           total_profit=total_profit, avg_price=avg_price,
                           transaction_count=transaction_count)


@sales_bp.route('/api/product-inventory/<int:product_id>')
@login_required
def product_inventory(product_id):
    """API: Get marketplace inventory for a product (used by sale form AJAX)."""
    mis = MarketplaceInventory.query.filter_by(product_id=product_id, is_listed=True).all()
    result = []
    for mi in mis:
        mp = Marketplace.query.get(mi.marketplace_id)
        if mp and mp.is_active:
            result.append({
                'marketplace_id': mi.marketplace_id,
                'marketplace_name': mp.name,
                'color': mp.color,
                'allocated_qty': mi.allocated_qty,
                'selling_price': mi.selling_price,
            })
    return jsonify(result)


@sales_bp.route('/api/product-details/<int:product_id>')
@login_required
def product_details(product_id):
    """API: Get product details and recent sales for the record form."""
    product = Product.query.get(product_id)
    if not product or product.user_id != current_user.id:
        return jsonify({}), 404

    # Recent sales (last 5)
    recent = Sale.query.filter_by(product_id=product_id).order_by(Sale.sale_date.desc()).limit(5).all()
    recent_sales = []
    for s in recent:
        mp = Marketplace.query.get(s.marketplace_id)
        recent_sales.append({
            'date': s.sale_date.strftime('%b %d, %H:%M'),
            'marketplace': mp.name if mp else 'Unknown',
            'color': mp.color if mp else '#6366f1',
            'qty': s.quantity_sold,
            'price': s.sale_price,
            'revenue': s.revenue,
            'profit': s.profit,
        })

    # 7-day and 30-day totals
    now = datetime.now()
    sales_7d = Sale.query.filter(
        Sale.product_id == product_id,
        Sale.sale_date >= now - timedelta(days=7)
    ).all()
    sales_30d = Sale.query.filter(
        Sale.product_id == product_id,
        Sale.sale_date >= now - timedelta(days=30)
    ).all()

    return jsonify({
        'sku': product.sku,
        'name': product.name,
        'category': product.category,
        'cost_price': product.cost_price,
        'warehouse_qty': product.total_warehouse_qty,
        'total_allocated': product.total_allocated,
        'unallocated_qty': product.unallocated_qty,
        'recent_sales': recent_sales,
        'stats_7d': {
            'units': sum(s.quantity_sold for s in sales_7d),
            'revenue': sum(s.revenue for s in sales_7d),
        },
        'stats_30d': {
            'units': sum(s.quantity_sold for s in sales_30d),
            'revenue': sum(s.revenue for s in sales_30d),
        },
    })


@sales_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    from services.csv_service import parse_csv, validate_sales_csv, import_sales_csv
    
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a .csv file.', 'error')
            return render_template('sales/upload.html')

        deduct_inventory = request.form.get('deduct_inventory') == 'on'

        try:
            df = parse_csv(file)
            is_valid, errors = validate_sales_csv(df)
            if not is_valid:
                for e in errors:
                    flash(e, 'error')
                return render_template('sales/upload.html')

            imported, errors = import_sales_csv(df, current_user.id, deduct_inventory)
            flash(f'Import complete: {imported} sales records added.', 'success')
            if errors:
                for e in errors[:5]:
                    flash(e, 'warning')

        except ValueError as e:
            flash(str(e), 'error')

        return redirect(url_for('sales.history'))

    return render_template('sales/upload.html')
