"""CSV parsing and validation service."""

import pandas as pd
from models import db, Product, MarketplaceInventory, Marketplace, User


import re

REQUIRED_COLUMNS = ['sku', 'name', 'cost_price', 'quantity']
OPTIONAL_COLUMNS = ['category']


def clean_typography(text):
    """Perform basic typography and casing cleanup on strings."""
    if not isinstance(text, str) or pd.isna(text):
        return text
    
    text = text.strip()
    if not text:
        return text
        
    text = re.sub(r'\s+', ' ', text)
    
    if text.isupper() or text.islower():
        text = text.title()
        
    text = re.sub(r'(?i)\biphone\b', 'iPhone', text)
    text = re.sub(r'(?i)\bipad\b', 'iPad', text)
    text = re.sub(r'(?i)\bmacbook\b', 'MacBook', text)
    text = re.sub(r'(?i)\bimac\b', 'iMac', text)
    
    text = re.sub(r'(?i)\b(\d+)\s*gb\b', r'\1GB', text)
    text = re.sub(r'(?i)\b(\d+)\s*tb\b', r'\1TB', text)
    text = re.sub(r'(?i)\b(\d+)\s*mb\b', r'\1MB', text)
    
    return text


def parse_csv(file_storage):
    """Parse an uploaded CSV file into a DataFrame."""
    try:
        df = pd.read_csv(file_storage)
        df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
        return df
    except Exception as e:
        raise ValueError(f'Could not parse CSV: {str(e)}')


def validate_csv(df):
    """Validate that required columns exist and data is clean."""
    errors = []

    # Check required columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return False, errors

    # Check for empty SKUs
    if df['sku'].isna().any() or (df['sku'].astype(str).str.strip() == '').any():
        errors.append('Some rows have empty SKU values')

    # Check numeric columns
    for col in ['cost_price', 'quantity']:
        try:
            pd.to_numeric(df[col], errors='raise')
        except (ValueError, TypeError):
            errors.append(f'Column "{col}" contains non-numeric values')

    # Check for duplicate SKUs within file
    dupes = df[df['sku'].duplicated(keep=False)]
    if not dupes.empty:
        errors.append(f'Duplicate SKUs found in file: {dupes["sku"].unique().tolist()[:5]}')

    return len(errors) == 0, errors


def import_csv(df, user_id):
    """Import products from DataFrame. Upserts by SKU."""
    imported = 0
    updated = 0
    errors = []

    # Detect marketplace price and quantity columns
    marketplaces = Marketplace.query.filter_by(user_id=user_id, is_active=True).all()
    mp_price_cols = {}
    mp_qty_cols = {}
    for mp in marketplaces:
        price_col = f'{mp.code}_price'
        qty_col = f'{mp.code}_quantity'
        if price_col in df.columns:
            mp_price_cols[mp] = price_col
        if qty_col in df.columns:
            mp_qty_cols[mp] = qty_col

    user = User.query.get(user_id)
    user_cols = user.column_list if user else []
    custom_col_map = {}
    for col in user_cols:
        cleaned_name = col['name'].strip().lower().replace(' ', '_')
        if cleaned_name in df.columns:
            custom_col_map[cleaned_name] = col['id']

    for idx, row in df.iterrows():
        try:
            sku = str(row['sku']).strip()
            name = clean_typography(str(row['name']))
            cost_price = float(row['cost_price'])
            quantity = int(float(row['quantity']))
            category = clean_typography(str(row.get('category', 'General'))) if 'category' in row else 'General'

            if not sku or not name:
                errors.append(f'Row {idx + 2}: Empty SKU or name')
                continue

            # Map custom attributes
            custom_attrs = {}
            for col_name, col_id in custom_col_map.items():
                val = row.get(col_name)
                if pd.notna(val):
                    custom_attrs[col_id] = str(val).strip()

            # Upsert product
            product = Product.query.filter_by(sku=sku, user_id=user_id).first()
            if product:
                product.name = name
                product.cost_price = cost_price
                product.total_warehouse_qty = quantity
                product.category = category
                
                existing_attrs = product.attributes
                existing_attrs.update(custom_attrs)
                product.attributes = existing_attrs
                
                updated += 1
            else:
                product = Product(
                    sku=sku,
                    name=name,
                    category=category,
                    cost_price=cost_price,
                    total_warehouse_qty=quantity,
                    user_id=user_id,
                )
                product.attributes = custom_attrs
                db.session.add(product)
                db.session.flush()
                imported += 1

            # We need a unified set of marketplaces from either price or qty
            mps_in_row = set(mp_price_cols.keys()).union(set(mp_qty_cols.keys()))
            
            # Handle marketplace prices and quantities
            for mp in mps_in_row:
                try:
                    price = float(row[mp_price_cols[mp]]) if mp in mp_price_cols else 0.0
                except (ValueError, TypeError, KeyError):
                    price = 0.0
                
                try:
                    qty = int(float(row[mp_qty_cols[mp]])) if mp in mp_qty_cols else 0
                except (ValueError, TypeError, KeyError):
                    qty = 0
                
                # If neither was in the row for this MP specifically (somehow), skip
                if mp not in mp_price_cols and mp not in mp_qty_cols:
                    continue
                    
                mi = MarketplaceInventory.query.filter_by(
                    product_id=product.id,
                    marketplace_id=mp.id,
                ).first()
                if mi:
                    if mp in mp_price_cols:
                        mi.selling_price = price
                    if mp in mp_qty_cols:
                        mi.allocated_qty = qty
                else:
                    mi = MarketplaceInventory(
                        product_id=product.id,
                        marketplace_id=mp.id,
                        selling_price=price,
                        allocated_qty=qty,
                        is_listed=True,
                    )
                    db.session.add(mi)

        except Exception as e:
            errors.append(f'Row {idx + 2}: {str(e)}')

    db.session.commit()
    return imported, updated, errors

def validate_sales_csv(df):
    """Validate that required columns exist for sales import."""
    errors = []
    required = ['sku', 'marketplace', 'quantity', 'sale_price']
    
    missing = [c for c in required if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return False, errors

    if df.get('sku') is not None and (df['sku'].isna().any() or (df['sku'].astype(str).str.strip() == '').any()):
        errors.append('Some rows have empty SKU values')

    for col in ['quantity', 'sale_price']:
        if col in df.columns:
            try:
                pd.to_numeric(df[col], errors='raise')
            except (ValueError, TypeError):
                errors.append(f'Column "{col}" contains non-numeric values')

    return len(errors) == 0, errors


def import_sales_csv(df, user_id, deduct_inventory=False):
    """Import sales from DataFrame."""
    from services.sales_service import record_sale, InsufficientStockError
    from models import Sale
    from datetime import datetime
    import pandas as pd
    
    imported = 0
    errors = []

    # Map marketplace code to id
    marketplaces = Marketplace.query.filter_by(user_id=user_id, is_active=True).all()
    mp_map = {mp.code.lower(): mp.id for mp in marketplaces}

    # Fetch products to avoid DB queries in loop
    products = Product.query.filter_by(user_id=user_id).all()
    sku_map = {p.sku: p.id for p in products}

    for idx, row in df.iterrows():
        try:
            sku = str(row['sku']).strip()
            mp_code = str(row['marketplace']).strip().lower()
            quantity = int(float(row['quantity']))
            sale_price = float(row['sale_price'])
            
            # Handle date if present
            sale_date = datetime.utcnow()
            if 'date' in df.columns and pd.notna(row['date']):
                try:
                    sale_date = pd.to_datetime(row['date']).to_pydatetime()
                except Exception:
                    pass # fallback to now

            if sku not in sku_map:
                errors.append(f"Row {idx + 2}: Product SKU '{sku}' not found.")
                continue
                
            if mp_code not in mp_map:
                errors.append(f"Row {idx + 2}: Marketplace '{mp_code}' not found.")
                continue

            product_id = sku_map[sku]
            marketplace_id = mp_map[mp_code]

            if deduct_inventory:
                # Use standard flow which deducts inventory and triggers pipelines
                try:
                    # We inject the specific date directly into the sale object after creation if needed,
                    # but record_sale doesn't accept date. Let's modify record_sale to accept date or just do it here.
                    # Since record_sale doesn't accept date, we will insert it directly if deduct_inventory is False,
                    # but if it's True, we'd ideally want to pass the date. For simplicity, we just use record_sale 
                    # and then update the date.
                    sale = record_sale(product_id, marketplace_id, quantity, sale_price, user_id)
                    sale.sale_date = sale_date
                    db.session.add(sale)
                    imported += 1
                except InsufficientStockError as e:
                    errors.append(f"Row {idx + 2} (SKU {sku}): Insufficient stock.")
                except ValueError as e:
                    errors.append(f"Row {idx + 2} (SKU {sku}): {str(e)}")
            else:
                # Just insert the sale record without deducting inventory
                product = Product.query.get(product_id)
                sale = Sale(
                    product_id=product_id,
                    marketplace_id=marketplace_id,
                    quantity_sold=quantity,
                    sale_price=sale_price,
                    cost_at_sale=product.cost_price,
                    sale_date=sale_date,
                    user_id=user_id,
                )
                db.session.add(sale)
                
                # Also need to manually update DailySalesSummary if we don't use record_sale
                from services.pipeline_service import record_daily_summary
                db.session.commit() # commit first so summary sees it
                try:
                    record_daily_summary(product_id, marketplace_id, sale_date)
                except Exception:
                    pass
                imported += 1
                
        except Exception as e:
            errors.append(f"Row {idx + 2}: Error processing row - {str(e)}")

    if deduct_inventory:
        # cache invalidation and commit are handled by record_sale, but we altered sale_date
        db.session.commit()
        
    return imported, errors
