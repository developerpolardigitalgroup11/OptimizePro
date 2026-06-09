"""Generate 60 days of synthetic multi-marketplace sales history for testing."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import numpy as np
from datetime import date, timedelta, datetime


def generate_seed_data():
    """Seed the database with products, marketplace inventory, and 60 days of sales history."""
    from app import create_app
    from models import db, User, Product, Marketplace, MarketplaceInventory, Sale, DailySalesSummary
    import bcrypt

    app = create_app()

    with app.app_context():
        # Check if already seeded
        if User.query.filter_by(username='demo').first():
            print('⚠️  Demo user already exists. Skipping seed.')
            return

        # Create demo user
        pw = bcrypt.hashpw('demo123'.encode(), bcrypt.gensalt(12)).decode()
        user = User(username='demo', email='demo@optimizepro.com', password_hash=pw)
        db.session.add(user)
        db.session.flush()

        # Create marketplaces
        marketplaces_data = [
            {'name': 'Amazon', 'code': 'amazon', 'color': '#FF9900', 'priority': 3},
            {'name': 'Flipkart', 'code': 'flipkart', 'color': '#2874F0', 'priority': 2},
            {'name': 'Meesho', 'code': 'meesho', 'color': '#570A57', 'priority': 1},
        ]
        marketplaces = []
        for mp_data in marketplaces_data:
            mp = Marketplace(user_id=user.id, **mp_data)
            db.session.add(mp)
            marketplaces.append(mp)
        db.session.flush()

        # Define products with different demand profiles per marketplace
        products_config = [
            {'sku': 'WH-1000XM5', 'name': 'Sony WH-1000XM5 Headphones', 'cat': 'Electronics', 'cost': 15000, 'qty': 500,
             'prices': [24990, 23999, 22500], 'demand': {'amazon': (12, 4), 'flipkart': (8, 3), 'meesho': (5, 2)}},
            {'sku': 'BOAT-AIRDOPES', 'name': 'boAt Airdopes 441', 'cat': 'Electronics', 'cost': 800, 'qty': 800,
             'prices': [1499, 1399, 1199], 'demand': {'amazon': (15, 5), 'flipkart': (18, 6), 'meesho': (10, 4)}},
            {'sku': 'IP-15-CASE', 'name': 'iPhone 15 Silicone Case', 'cat': 'Accessories', 'cost': 200, 'qty': 1200,
             'prices': [599, 549, 449], 'demand': {'amazon': (20, 7), 'flipkart': (15, 5), 'meesho': (25, 8)}},
            {'sku': 'PUMA-TSHIRT', 'name': 'Puma Essential T-Shirt', 'cat': 'Fashion', 'cost': 400, 'qty': 1000,
             'prices': [899, 849, 699], 'demand': {'amazon': (8, 3), 'flipkart': (12, 4), 'meesho': (18, 6)}},
            {'sku': 'NIKE-SHOES', 'name': 'Nike Revolution 6', 'cat': 'Footwear', 'cost': 2500, 'qty': 300,
             'prices': [4999, 4799, 4499], 'demand': {'amazon': (5, 2), 'flipkart': (7, 3), 'meesho': (3, 2)}},
            {'sku': 'PRESTIGE-PAN', 'name': 'Prestige Omega Pan', 'cat': 'Kitchen', 'cost': 600, 'qty': 600,
             'prices': [1199, 1099, 999], 'demand': {'amazon': (10, 3), 'flipkart': (8, 3), 'meesho': (6, 2)}},
            {'sku': 'JBL-GO3', 'name': 'JBL Go 3 Speaker', 'cat': 'Electronics', 'cost': 2000, 'qty': 400,
             'prices': [3499, 3299, 2999], 'demand': {'amazon': (6, 2), 'flipkart': (5, 2), 'meesho': (4, 2)}},
            {'sku': 'CAMPUS-SHOES', 'name': 'Campus Running Shoes', 'cat': 'Footwear', 'cost': 800, 'qty': 800,
             'prices': [1599, 1499, 1299], 'demand': {'amazon': (7, 3), 'flipkart': (10, 4), 'meesho': (15, 5)}},
        ]

        today = date.today()
        start_date = today - timedelta(days=60)

        for pc in products_config:
            product = Product(
                sku=pc['sku'], name=pc['name'], category=pc['cat'],
                cost_price=pc['cost'], total_warehouse_qty=pc['qty'],
                user_id=user.id,
            )
            db.session.add(product)
            db.session.flush()

            # Create marketplace inventory
            for idx, mp in enumerate(marketplaces):
                allocated = pc['qty'] // 3
                mi = MarketplaceInventory(
                    product_id=product.id,
                    marketplace_id=mp.id,
                    selling_price=pc['prices'][idx],
                    allocated_qty=allocated,
                    is_listed=True,
                )
                db.session.add(mi)
            db.session.flush()

            # Generate 60 days of sales per marketplace
            for mp in marketplaces:
                demand_config = pc['demand'][mp.code]
                base_demand, std = demand_config

                for day_offset in range(60):
                    current_date = start_date + timedelta(days=day_offset)

                    # Add weekly seasonality (weekends have higher sales)
                    weekday = current_date.weekday()
                    season_factor = 1.3 if weekday >= 5 else 1.0

                    # Add slight upward trend for some marketplaces
                    trend = 1.0 + (day_offset / 60) * 0.15 if mp.code == 'meesho' else 1.0

                    daily_qty = max(0, int(np.random.normal(base_demand * season_factor * trend, std)))

                    if daily_qty == 0:
                        continue

                    mi = MarketplaceInventory.query.filter_by(
                        product_id=product.id, marketplace_id=mp.id
                    ).first()

                    sale_price = mi.selling_price
                    sale_dt = datetime.combine(current_date, datetime.min.time().replace(hour=random.randint(8, 22)))

                    sale = Sale(
                        product_id=product.id,
                        marketplace_id=mp.id,
                        quantity_sold=daily_qty,
                        sale_price=sale_price,
                        cost_at_sale=pc['cost'],
                        sale_date=sale_dt,
                        user_id=user.id,
                    )
                    db.session.add(sale)

                    # Create daily summary
                    existing = DailySalesSummary.query.filter_by(
                        product_id=product.id,
                        marketplace_id=mp.id,
                        summary_date=current_date,
                    ).first()

                    if existing:
                        existing.total_quantity_sold += daily_qty
                        existing.total_revenue += sale_price * daily_qty
                        existing.total_cost += pc['cost'] * daily_qty
                    else:
                        summary = DailySalesSummary(
                            product_id=product.id,
                            marketplace_id=mp.id,
                            summary_date=current_date,
                            total_quantity_sold=daily_qty,
                            total_revenue=sale_price * daily_qty,
                            total_cost=pc['cost'] * daily_qty,
                        )
                        db.session.add(summary)

        db.session.commit()
        print('✅ Seed data generated successfully!')
        print(f'   📧 Login: demo / demo123')
        print(f'   📦 {len(products_config)} products across 3 marketplaces')
        print(f'   📊 60 days of sales history with marketplace-specific demand patterns')


if __name__ == '__main__':
    generate_seed_data()
