"""Product CRUD + CSV upload routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Product, Marketplace, MarketplaceInventory
from services.csv_service import parse_csv, validate_csv, import_csv, clean_typography

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
        name = clean_typography(request.form.get('name', ''))
        category = clean_typography(request.form.get('category', 'General'))
        cost_price = float(request.form.get('cost_price', 0))
        quantity = int(request.form.get('quantity', 0))
        default_currency = request.form.get('default_currency')

        # Update user's default currency and custom category list if changed
        if default_currency and default_currency != current_user.default_currency:
            current_user.default_currency = default_currency
        
        if category:
            cat_list = current_user.category_list
            if category not in cat_list:
                cat_list.append(category)
                current_user.category_list = cat_list

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
        
        # Read custom attributes from form
        custom_attrs = {}
        for col in current_user.column_list:
            col_id = col['id']
            val = request.form.get(col_id, '')
            if val:
                custom_attrs[col_id] = val
        product.attributes = custom_attrs
        
        db.session.add(product)
        db.session.flush()

        # Handle marketplace listings
        for mp in marketplaces:
            listed = request.form.get(f'mp_{mp.id}_listed')
            price_val = request.form.get(f'mp_{mp.id}_price', '0')
            qty_val = request.form.get(f'mp_{mp.id}_qty', '0')
            if listed:
                mi = MarketplaceInventory(
                    product_id=product.id,
                    marketplace_id=mp.id,
                    selling_price=float(price_val) if price_val else 0,
                    allocated_qty=int(qty_val) if qty_val else 0,
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

    new_sku = request.form.get('sku', '').strip()
    if new_sku and new_sku != product.sku:
        existing = Product.query.filter_by(sku=new_sku, user_id=current_user.id).first()
        if existing:
            flash(f'SKU "{new_sku}" is already in use.', 'error')
            return redirect(url_for('products.list_products'))
        product.sku = new_sku

    product.name = clean_typography(request.form.get('name', product.name))
    category = clean_typography(request.form.get('category', product.category))
    product.category = category
    product.cost_price = float(request.form.get('cost_price', product.cost_price))
    product.total_warehouse_qty = int(request.form.get('quantity', product.total_warehouse_qty))

    if category:
        cat_list = current_user.category_list
        if category not in cat_list:
            cat_list.append(category)
            current_user.category_list = cat_list

    # Update custom attributes
    custom_attrs = product.attributes
    for col in current_user.column_list:
        col_id = col['id']
        val = request.form.get(col_id, '')
        if val:
            custom_attrs[col_id] = val
        else:
            custom_attrs.pop(col_id, None)
    product.attributes = custom_attrs

    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).all()
    for mp in marketplaces:
        listed = request.form.get(f'mp_{mp.id}_listed')
        price_val = request.form.get(f'mp_{mp.id}_price')
        qty_val = request.form.get(f'mp_{mp.id}_qty')
        
        mi = MarketplaceInventory.query.filter_by(product_id=product.id, marketplace_id=mp.id).first()
        if listed:
            if not mi:
                mi = MarketplaceInventory(product_id=product.id, marketplace_id=mp.id)
                db.session.add(mi)
            mi.is_listed = True
            mi.selling_price = float(price_val) if price_val else 0
            mi.allocated_qty = int(qty_val) if qty_val else 0
        else:
            if mi:
                mi.is_listed = False
                mi.allocated_qty = 0
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


@products_bp.route('/bulk_delete', methods=['POST'])
@login_required
def bulk_delete_products():
    product_ids = request.form.getlist('product_ids')
    if not product_ids:
        flash('No products selected.', 'warning')
        return redirect(url_for('products.list_products'))

    products = Product.query.filter(Product.id.in_(product_ids), Product.user_id == current_user.id).all()
    count = 0
    for p in products:
        p.is_active = False
        count += 1
        
    db.session.commit()
    flash(f'{count} product(s) deleted.', 'success')
    return redirect(url_for('products.list_products'))


@products_bp.route('/columns/add', methods=['POST'])
@login_required
def add_column():
    name = request.form.get('col_name', '').strip()
    col_type = request.form.get('col_type', 'text').strip()
    
    if not name:
        flash('Column name is required.', 'error')
        return redirect(url_for('products.list_products'))
        
    import time
    col_id = f"col_{int(time.time())}"
    
    cols = current_user.column_list
    cols.append({"id": col_id, "name": name, "type": col_type})
    current_user.column_list = cols
    db.session.commit()
    flash(f'Column "{name}" added.', 'success')
    return redirect(url_for('products.list_products'))

@products_bp.route('/columns/edit/<col_id>', methods=['POST'])
@login_required
def edit_column(col_id):
    name = request.form.get('col_name', '').strip()
    col_type = request.form.get('col_type', 'text').strip()
    
    if not name:
        flash('Column name is required.', 'error')
        return redirect(url_for('products.list_products'))
        
    cols = current_user.column_list
    for c in cols:
        if c.get('id') == col_id:
            c['name'] = name
            c['type'] = col_type
            break
            
    current_user.column_list = cols
    db.session.commit()
    flash(f'Column updated.', 'success')
    return redirect(url_for('products.list_products'))

@products_bp.route('/columns/delete/<col_id>', methods=['POST'])
@login_required
def delete_column(col_id):
    cols = current_user.column_list
    cols = [c for c in cols if c.get('id') != col_id]
    current_user.column_list = cols
    db.session.commit()
    flash(f'Column deleted.', 'success')
    return redirect(url_for('products.list_products'))


@products_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    marketplaces = Marketplace.query.filter_by(user_id=current_user.id, is_active=True).order_by(Marketplace.priority.desc()).all()
    
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a .csv file.', 'error')
            return render_template('products/upload.html', marketplaces=marketplaces)

        try:
            df = parse_csv(file)
            is_valid, errors = validate_csv(df)
            if not is_valid:
                for e in errors:
                    flash(e, 'error')
                return render_template('products/upload.html', marketplaces=marketplaces)

            imported, updated, errors = import_csv(df, current_user.id)
            flash(f'Import complete: {imported} new, {updated} updated.', 'success')
            if errors:
                for e in errors[:5]:
                    flash(e, 'warning')

        except ValueError as e:
            flash(str(e), 'error')

        return redirect(url_for('products.list_products'))

    return render_template('products/upload.html', marketplaces=marketplaces)
