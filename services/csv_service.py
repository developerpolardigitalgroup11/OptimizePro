"""CSV parsing and validation service."""

import pandas as pd
from models import db, Product, MarketplaceInventory, Marketplace


REQUIRED_COLUMNS = ['sku', 'name', 'cost_price', 'quantity']
OPTIONAL_COLUMNS = ['category']


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

    # Detect marketplace price columns
    marketplaces = Marketplace.query.filter_by(user_id=user_id, is_active=True).all()
    mp_price_cols = {}
    for mp in marketplaces:
        col_name = f'{mp.code}_price'
        if col_name in df.columns:
            mp_price_cols[mp] = col_name

    for idx, row in df.iterrows():
        try:
            sku = str(row['sku']).strip()
            name = str(row['name']).strip()
            cost_price = float(row['cost_price'])
            quantity = int(float(row['quantity']))
            category = str(row.get('category', 'General')).strip() if 'category' in row else 'General'

            if not sku or not name:
                errors.append(f'Row {idx + 2}: Empty SKU or name')
                continue

            # Upsert product
            product = Product.query.filter_by(sku=sku, user_id=user_id).first()
            if product:
                product.name = name
                product.cost_price = cost_price
                product.total_warehouse_qty = quantity
                product.category = category
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
                db.session.add(product)
                db.session.flush()
                imported += 1

            # Handle marketplace prices
            for mp, col in mp_price_cols.items():
                try:
                    price = float(row[col])
                    mi = MarketplaceInventory.query.filter_by(
                        product_id=product.id,
                        marketplace_id=mp.id,
                    ).first()
                    if mi:
                        mi.selling_price = price
                    else:
                        mi = MarketplaceInventory(
                            product_id=product.id,
                            marketplace_id=mp.id,
                            selling_price=price,
                            allocated_qty=0,
                            is_listed=True,
                        )
                        db.session.add(mi)
                except (ValueError, TypeError):
                    pass  # Skip invalid prices

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
