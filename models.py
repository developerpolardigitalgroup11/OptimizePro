"""SQLAlchemy ORM models for OptimizePro."""

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Profile fields
    full_name = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    company = db.Column(db.String(150), nullable=True)
    avatar_color = db.Column(db.String(7), default='#6366f1')  # hex color for initials avatar
    avatar_filename = db.Column(db.String(255), nullable=True)

    # Subscription fields
    tier = db.Column(db.String(20), default='basic')  # 'basic', 'pro'
    tier_expires_at = db.Column(db.DateTime, nullable=True)

    # Admin flag
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    products = db.relationship('Product', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    marketplaces = db.relationship('Marketplace', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    sales = db.relationship('Sale', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    allocation_plans = db.relationship('AllocationPlan', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', backref='user', lazy='dynamic', cascade='all, delete-orphan', order_by='Subscription.created_at.desc()')
    demo_requests = db.relationship('DemoRequest', backref='demo_user', lazy='dynamic', cascade='all, delete-orphan')


class Marketplace(db.Model):
    __tablename__ = 'marketplaces'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), nullable=False, default='#6366f1')  # hex color
    priority = db.Column(db.Integer, default=1)  # higher = more important
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    logo_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint per user
    __table_args__ = (
        db.UniqueConstraint('code', 'user_id', name='uq_marketplace_code_user'),
    )

    # Relationships
    inventory_items = db.relationship('MarketplaceInventory', backref='marketplace', lazy='dynamic')
    sales = db.relationship('Sale', backref='marketplace', lazy='dynamic')


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), default='General')
    cost_price = db.Column(db.Float, nullable=False, default=0.0)
    total_warehouse_qty = db.Column(db.Integer, nullable=False, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('sku', 'user_id', name='uq_product_sku_user'),
        db.CheckConstraint('total_warehouse_qty >= 0', name='ck_warehouse_qty_positive'),
    )

    # Relationships
    marketplace_inventory = db.relationship('MarketplaceInventory', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    sales = db.relationship('Sale', backref='product', lazy='dynamic')
    alerts = db.relationship('Alert', backref='product', lazy='dynamic')
    forecasts = db.relationship('Forecast', backref='product', lazy='dynamic')

    @property
    def total_allocated(self):
        """Sum of allocated_qty across all marketplaces."""
        return sum(mi.allocated_qty for mi in self.marketplace_inventory.all())

    @property
    def unallocated_qty(self):
        """Warehouse stock not yet allocated to any marketplace."""
        return self.total_warehouse_qty - self.total_allocated


class MarketplaceInventory(db.Model):
    __tablename__ = 'marketplace_inventory'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplaces.id'), nullable=False)
    selling_price = db.Column(db.Float, nullable=False, default=0.0)
    allocated_qty = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, default=10)
    is_listed = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('product_id', 'marketplace_id', name='uq_product_marketplace'),
        db.CheckConstraint('allocated_qty >= 0', name='ck_allocated_qty_positive'),
    )

    @property
    def margin(self):
        """Profit margin per unit."""
        return self.selling_price - self.product.cost_price if self.product else 0


class Sale(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplaces.id'), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False)
    sale_price = db.Column(db.Float, nullable=False)
    cost_at_sale = db.Column(db.Float, nullable=False, default=0.0)
    sale_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    __table_args__ = (
        db.Index('ix_sale_product_marketplace_date', 'product_id', 'marketplace_id', 'sale_date'),
        db.CheckConstraint('quantity_sold > 0', name='ck_qty_sold_positive'),
    )

    @property
    def revenue(self):
        return self.sale_price * self.quantity_sold

    @property
    def profit(self):
        return (self.sale_price - self.cost_at_sale) * self.quantity_sold


class DailySalesSummary(db.Model):
    __tablename__ = 'daily_sales_summary'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplaces.id'), nullable=False)
    summary_date = db.Column(db.Date, nullable=False)
    total_quantity_sold = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Float, default=0.0)
    total_cost = db.Column(db.Float, default=0.0)

    __table_args__ = (
        db.UniqueConstraint('product_id', 'marketplace_id', 'summary_date', name='uq_daily_summary'),
        db.Index('ix_summary_product_marketplace_date', 'product_id', 'marketplace_id', 'summary_date'),
    )


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplaces.id'), nullable=True)  # null = cross-marketplace
    alert_type = db.Column(db.String(50), nullable=False)  # UNDERSTOCK, OVERSTOCK, CRITICAL, REBALANCE
    priority = db.Column(db.String(20), nullable=False)  # HIGH, MEDIUM, LOW
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    was_acted_on = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    marketplace = db.relationship('Marketplace', backref='alerts', lazy='joined')

    __table_args__ = (
        db.Index('ix_alert_user_read', 'product_id', 'is_read'),
    )


class Forecast(db.Model):
    __tablename__ = 'forecasts'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplaces.id'), nullable=False)
    forecast_date = db.Column(db.Date, nullable=False)
    predicted_demand = db.Column(db.Float, nullable=False)
    confidence_lower = db.Column(db.Float, default=0.0)
    confidence_upper = db.Column(db.Float, default=0.0)
    model_used = db.Column(db.String(50), nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    marketplace = db.relationship('Marketplace', backref='forecasts', lazy='joined')

    __table_args__ = (
        db.Index('ix_forecast_product_marketplace', 'product_id', 'marketplace_id', 'forecast_date'),
    )


class AllocationPlan(db.Model):
    __tablename__ = 'allocation_plans'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    total_units_to_allocate = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='draft')  # draft, applied, expired
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    product = db.relationship('Product', backref='allocation_plans')
    lines = db.relationship('AllocationLine', backref='plan', lazy='joined', cascade='all, delete-orphan')


class AllocationLine(db.Model):
    __tablename__ = 'allocation_lines'

    id = db.Column(db.Integer, primary_key=True)
    allocation_plan_id = db.Column(db.Integer, db.ForeignKey('allocation_plans.id'), nullable=False)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplaces.id'), nullable=False)
    recommended_qty = db.Column(db.Integer, nullable=False)
    predicted_demand_14d = db.Column(db.Float, default=0.0)
    marketplace_share_pct = db.Column(db.Float, default=0.0)
    reasoning = db.Column(db.Text, default='')

    # Relationships
    marketplace = db.relationship('Marketplace', backref='allocation_lines', lazy='joined')


class RecommendationOutcome(db.Model):
    __tablename__ = 'recommendation_outcomes'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    marketplace_id = db.Column(db.Integer, db.ForeignKey('marketplaces.id'), nullable=True)
    recommendation_type = db.Column(db.String(50), nullable=False)  # ALLOCATION, RESTOCK, REBALANCE
    recommendation_date = db.Column(db.Date, nullable=False)
    recommended_qty = db.Column(db.Float, default=0.0)
    actual_qty_after = db.Column(db.Float, nullable=True)
    predicted_demand = db.Column(db.Float, default=0.0)
    actual_demand = db.Column(db.Float, nullable=True)
    profit_impact = db.Column(db.Float, default=0.0)
    loss_saved = db.Column(db.Float, default=0.0)
    followed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    product = db.relationship('Product', backref='recommendation_outcomes')
    marketplace = db.relationship('Marketplace', backref='recommendation_outcomes')


class Subscription(db.Model):
    """Tracks subscription / billing events per user."""
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan = db.Column(db.String(20), nullable=False)               # 'basic', 'pro'
    status = db.Column(db.String(20), nullable=False, default='active')  # 'active', 'cancelled', 'expired'
    amount = db.Column(db.Float, default=0.0)                     # amount paid in ₹
    currency = db.Column(db.String(5), default='INR')
    payment_method = db.Column(db.String(50), nullable=True)      # 'card', 'upi', etc.
    transaction_id = db.Column(db.String(100), nullable=True)     # mock / real txn id
    billing_period_start = db.Column(db.DateTime, nullable=True)
    billing_period_end = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_subscription_user_created', 'user_id', 'created_at'),
    )


class DemoRequest(db.Model):
    """Records from Basic-tier users who requested a product demo."""
    __tablename__ = 'demo_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    company = db.Column(db.String(150), nullable=True)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'contacted', 'closed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UpgradeRequest(db.Model):
    """Records requests from users wanting to upgrade to Pro."""
    __tablename__ = 'upgrade_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    company = db.Column(db.String(150), nullable=True)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'contacted', 'closed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
