"""Product CRUD + CSV upload routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Product, Marketplace, MarketplaceInventory
from services.csv_service import parse_csv, validate_csv, import_csv

products_bp = Blueprint('products', __name__)


@products_bp.route('/')
@login_required
def list_products():
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).order_by(Product.name).all()
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).order_by(Marketplace.priority.desc()).all()
    return render_template('products/list.html', products=products, marketplaces=marketplaces)


@products_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()

    if request.method == 'POST':
        sku = request.form.get('sku', '').strip()
        name = request.form.get('name', '').strip()
        category = request.form.get('category', 'General').strip()
        cost_price = float(request.form.get('cost_price', 0))
        quantity = int(request.form.get('quantity', 0))

        if not sku or not name:
            flash('SKU and name are required.', 'error')
            return render_template('products/add.html', marketplaces=marketplaces)

        existing = Product.query.filter_by(sku=sku, user_id=current_user.id).first()
        if existing:
            flash(f'Product with SKU "{sku}" already exists.', 'error')
            return render_template('products/add.html', marketplaces=marketplaces)

        product = Product(
            sku=sku, name=name, category=category,
            cost_price=cost_price, total_warehouse_qty=quantity,
            user_id=current_user.id,
        )
        db.session.add(product)
        db.session.flush()

        # Handle marketplace listings
        for mp in marketplaces:
            listed = request.form.get(f'mp_{mp.id}_listed')
            price = request.form.get(f'mp_{mp.id}_price', '0')
            if listed:
                mi = MarketplaceInventory(
                    product_id=product.id,
                    marketplace_id=mp.id,
                    selling_price=float(price) if price else 0,
                    allocated_qty=0,
                    is_listed=True,
                )
                db.session.add(mi)

        db.session.commit()
        flash(f'Product "{name}" added!', 'success')
        return redirect(url_for('products.list_products'))

    return render_template('products/add.html', marketplaces=marketplaces)


@products_bp.route('/<int:product_id>/edit', methods=['POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('products.list_products'))

    product.name = request.form.get('name', product.name).strip()
    product.category = request.form.get('category', product.category).strip()
    product.cost_price = float(request.form.get('cost_price', product.cost_price))
    product.total_warehouse_qty = int(request.form.get('quantity', product.total_warehouse_qty))
    db.session.commit()
    flash(f'Product "{product.name}" updated.', 'success')
    return redirect(url_for('products.list_products'))


@products_bp.route('/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('products.list_products'))

    product.is_active = False
    db.session.commit()
    flash(f'Product "{product.name}" removed.', 'success')
    return redirect(url_for('products.list_products'))


@products_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a .csv file.', 'error')
            return render_template('products/upload.html')

        try:
            df = parse_csv(file)
            is_valid, errors = validate_csv(df)
            if not is_valid:
                for e in errors:
                    flash(e, 'error')
                return render_template('products/upload.html')

            imported, updated, errors = import_csv(df, current_user.id)
            flash(f'Import complete: {imported} new, {updated} updated.', 'success')
            if errors:
                for e in errors[:5]:
                    flash(e, 'warning')

        except ValueError as e:
            flash(str(e), 'error')

        return redirect(url_for('products.list_products'))

    return render_template('products/upload.html')
