"""Admin dashboard blueprint — master control panel for OptimizePro."""

import functools
from datetime import datetime, timedelta

from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash, jsonify)
from flask_login import current_user, login_user, logout_user
import bcrypt

from models import db, User, Product, Subscription, DemoRequest, Sale, Marketplace

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin')


# ─────────────────────────────────────────────
#  Helper — require admin session
# ─────────────────────────────────────────────

def admin_required(f):
    """Decorator: redirect to admin login if not authenticated as admin."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not (current_user.is_authenticated and current_user.is_admin):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


def _get_admin_user():
    """Return the currently logged-in admin User object, or None."""
    if current_user.is_authenticated and current_user.is_admin:
        return current_user
    return None


# ─────────────────────────────────────────────
#  Admin Login / Logout
# ─────────────────────────────────────────────

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin.dashboard'))

    error = None
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter(
            (User.username == login_id) | (User.email == login_id.lower())
        ).first()

        if user and user.is_admin and bcrypt.checkpw(
                password.encode('utf-8'), user.password_hash.encode('utf-8')):
            login_user(user, remember=True)
            return redirect(url_for('admin.dashboard'))

        error = 'Invalid credentials or insufficient privileges.'

    return render_template('admin/login.html', error=error)


@admin_bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for('admin.login'))


# ─────────────────────────────────────────────
#  Overview Dashboard
# ─────────────────────────────────────────────

@admin_bp.route('/')
@admin_required
def dashboard():
    total_users      = User.query.filter_by(is_admin=False).count()
    pro_users        = User.query.filter_by(tier='pro', is_admin=False).count()
    basic_users      = User.query.filter_by(tier='basic', is_admin=False).count()
    pending_demos    = DemoRequest.query.filter_by(status='pending').count()
    total_products   = Product.query.count()
    total_revenue    = db.session.query(db.func.sum(Subscription.amount)).scalar() or 0

    # New signups last 30 days
    cutoff_30 = datetime.utcnow() - timedelta(days=30)
    new_users_30d = User.query.filter(
        User.created_at >= cutoff_30, User.is_admin == False
    ).count()

    # Revenue last 30 days
    revenue_30d = db.session.query(db.func.sum(Subscription.amount)).filter(
        Subscription.created_at >= cutoff_30
    ).scalar() or 0

    # Recent signups (last 8)
    recent_users = User.query.filter_by(is_admin=False).order_by(
        User.created_at.desc()
    ).limit(8).all()

    # Pending demo requests (last 8)
    pending_demo_list = DemoRequest.query.filter_by(status='pending').order_by(
        DemoRequest.created_at.desc()
    ).limit(8).all()

    # Revenue by day (last 14 days) for chart
    revenue_chart = []
    for i in range(13, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end   = datetime.combine(day, datetime.max.time())
        rev = db.session.query(db.func.sum(Subscription.amount)).filter(
            Subscription.created_at >= day_start,
            Subscription.created_at <= day_end,
        ).scalar() or 0
        revenue_chart.append({'date': day.strftime('%d %b'), 'revenue': rev})

    admin_user = _get_admin_user()

    return render_template('admin/dashboard.html',
        total_users=total_users,
        pro_users=pro_users,
        basic_users=basic_users,
        pending_demos=pending_demos,
        total_products=total_products,
        total_revenue=total_revenue,
        new_users_30d=new_users_30d,
        revenue_30d=revenue_30d,
        recent_users=recent_users,
        pending_demo_list=pending_demo_list,
        revenue_chart=revenue_chart,
        admin_user=admin_user,
    )


# ─────────────────────────────────────────────
#  Client Management
# ─────────────────────────────────────────────

@admin_bp.route('/clients')
@admin_required
def clients():
    tier_filter = request.args.get('tier', '')
    search      = request.args.get('q', '').strip()

    q = User.query.filter_by(is_admin=False)
    if tier_filter in ('basic', 'pro'):
        q = q.filter_by(tier=tier_filter)
    if search:
        q = q.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.company.ilike(f'%{search}%'))
        )
    users = q.order_by(User.created_at.desc()).all()

    # Attach product count + demo flag + expiry days
    for u in users:
        u._product_count = Product.query.filter_by(user_id=u.id).count()
        u._sub_count     = Subscription.query.filter_by(user_id=u.id).count()
        # Demo user = has an active subscription with payment_method='demo'
        demo_sub = Subscription.query.filter_by(
            user_id=u.id, payment_method='demo', status='active'
        ).first()
        u._is_demo = demo_sub is not None
        # Days left until tier expiry
        if u.tier_expires_at:
            delta = u.tier_expires_at - datetime.utcnow()
            u._days_left = max(0, delta.days)
        else:
            u._days_left = None

    return render_template('admin/clients.html',
        users=users,
        tier_filter=tier_filter,
        search=search,
        admin_user=_get_admin_user(),
    )


@admin_bp.route('/clients/<int:user_id>/tier', methods=['POST'])
@admin_required
def change_tier(user_id):
    user = db.session.get(User, user_id)
    if not user or user.is_admin:
        return jsonify({'success': False, 'message': 'User not found.'}), 404

    new_tier = request.form.get('tier', '').strip()
    if new_tier not in ('basic', 'pro'):
        return jsonify({'success': False, 'message': 'Invalid tier.'}), 400

    # Admin-specified expiry days (1-365), default 30
    try:
        days = int(request.form.get('days', 30))
        days = max(1, min(365, days))
    except (ValueError, TypeError):
        days = 30

    user.tier = new_tier
    if new_tier == 'pro':
        user.tier_expires_at = datetime.utcnow() + timedelta(days=days)
    else:
        user.tier_expires_at = None
        days = 0

    # Log a subscription record
    sub = Subscription(
        user_id=user.id,
        plan=new_tier,
        status='active',
        amount=0,
        payment_method='admin',
        transaction_id=f'admin-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
        billing_period_start=datetime.utcnow(),
        billing_period_end=user.tier_expires_at,
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Tier updated to {new_tier}.',
        'tier': new_tier,
        'days': days,
        'expires_at': user.tier_expires_at.strftime('%d %b %Y') if user.tier_expires_at else None,
    })


@admin_bp.route('/clients/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_client(user_id):
    user = db.session.get(User, user_id)
    if not user or user.is_admin:
        return jsonify({'success': False, 'message': 'User not found.'}), 404

    db.session.delete(user)
    db.session.commit()
    flash(f'User "{user.username}" deleted.', 'success')
    return redirect(url_for('admin.clients'))


@admin_bp.route('/clients/<int:user_id>/cancel-demo', methods=['POST'])
@admin_required
def cancel_demo(user_id):
    """Cancel a demo Pro account — downgrade to Basic and mark demo sub as cancelled."""
    user = db.session.get(User, user_id)
    if not user or user.is_admin:
        return jsonify({'success': False, 'message': 'User not found.'}), 404

    # Mark all active demo subscriptions as cancelled
    demo_subs = Subscription.query.filter_by(
        user_id=user.id, payment_method='demo', status='active'
    ).all()

    if not demo_subs:
        return jsonify({'success': False, 'message': 'No active demo subscription found.'}), 400

    for sub in demo_subs:
        sub.status = 'cancelled'
        sub.billing_period_end = datetime.utcnow()

    # Downgrade user to Basic
    user.tier = 'basic'
    user.tier_expires_at = None

    # Log a cancellation record
    cancel_sub = Subscription(
        user_id=user.id,
        plan='basic',
        status='active',
        amount=0,
        payment_method='admin',
        transaction_id=f'demo-cancel-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
        billing_period_start=datetime.utcnow(),
        billing_period_end=None,
    )
    db.session.add(cancel_sub)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Demo cancelled for {user.username}. Account downgraded to Basic.',
        'tier': 'basic',
    })


# ─────────────────────────────────────────────
#  Demo Request Management
# ─────────────────────────────────────────────

@admin_bp.route('/demos')
@admin_required
def demos():
    status_filter = request.args.get('status', '')
    q = DemoRequest.query
    if status_filter in ('pending', 'contacted', 'closed'):
        q = q.filter_by(status=status_filter)
    demo_list = q.order_by(DemoRequest.created_at.desc()).all()

    counts = {
        'pending':   DemoRequest.query.filter_by(status='pending').count(),
        'accepted':  DemoRequest.query.filter_by(status='accepted').count(),
        'rejected':  DemoRequest.query.filter_by(status='rejected').count(),
    }

    return render_template('admin/demos.html',
        demo_list=demo_list,
        status_filter=status_filter,
        counts=counts,
        admin_user=_get_admin_user(),
    )


@admin_bp.route('/demos/<int:demo_id>/status', methods=['POST'])
@admin_required
def update_demo_status(demo_id):
    demo = db.session.get(DemoRequest, demo_id)
    if not demo:
        return jsonify({'success': False, 'message': 'Demo request not found.'}), 404

    new_status = request.form.get('status', '').strip()
    if new_status not in ('pending', 'accepted', 'rejected'):
        return jsonify({'success': False, 'message': 'Invalid status.'}), 400

    demo.status = new_status
    db.session.commit()
    return jsonify({'success': True, 'status': new_status})


@admin_bp.route('/demos/<int:demo_id>/accept', methods=['POST'])
@admin_required
def accept_demo(demo_id):
    demo = db.session.get(DemoRequest, demo_id)
    if not demo:
        return jsonify({'success': False, 'message': 'Demo request not found.'}), 404

    tier = request.form.get('tier', 'pro').strip()
    try:
        days = int(request.form.get('days', 30))
        days = max(1, min(365, days))
    except (ValueError, TypeError):
        days = 30

    user = db.session.get(User, demo.user_id) if demo.user_id else None
    
    if user:
        user.tier = tier
        if tier == 'pro':
            user.tier_expires_at = datetime.utcnow() + timedelta(days=days)
        else:
            user.tier_expires_at = None
            days = 0

        # Log a subscription record
        sub = Subscription(
            user_id=user.id,
            plan=tier,
            status='active',
            amount=0,
            payment_method='demo',
            transaction_id=f'demo-accept-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            billing_period_start=datetime.utcnow(),
            billing_period_end=user.tier_expires_at,
        )
        db.session.add(sub)

    demo.status = 'accepted'
    db.session.commit()

    return jsonify({'success': True, 'message': f'Demo accepted with {tier.title()} tier for {days} days.', 'status': 'accepted'})


@admin_bp.route('/demos/<int:demo_id>/reject', methods=['POST'])
@admin_required
def reject_demo(demo_id):
    demo = db.session.get(DemoRequest, demo_id)
    if not demo:
        return jsonify({'success': False, 'message': 'Demo request not found.'}), 404

    demo.status = 'rejected'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Demo request rejected.', 'status': 'rejected'})


# ─────────────────────────────────────────────
#  Subscription Management
# ─────────────────────────────────────────────

@admin_bp.route('/subscriptions')
@admin_required
def subscriptions():
    plan_filter   = request.args.get('plan', '')
    status_filter = request.args.get('status', '')

    q = Subscription.query
    if plan_filter in ('basic', 'pro'):
        q = q.filter_by(plan=plan_filter)
    if status_filter in ('active', 'cancelled', 'expired'):
        q = q.filter_by(status=status_filter)

    subs = q.order_by(Subscription.created_at.desc()).all()

    # Revenue summary
    total_revenue  = db.session.query(db.func.sum(Subscription.amount)).scalar() or 0
    pro_revenue    = db.session.query(db.func.sum(Subscription.amount)).filter_by(plan='pro').scalar() or 0
    basic_revenue  = db.session.query(db.func.sum(Subscription.amount)).filter_by(plan='basic').scalar() or 0
    cutoff_30      = datetime.utcnow() - timedelta(days=30)
    monthly_rev    = db.session.query(db.func.sum(Subscription.amount)).filter(
        Subscription.created_at >= cutoff_30
    ).scalar() or 0

    # Attach user info
    for s in subs:
        s._user = db.session.get(User, s.user_id)

    return render_template('admin/subscriptions.html',
        subs=subs,
        plan_filter=plan_filter,
        status_filter=status_filter,
        total_revenue=total_revenue,
        pro_revenue=pro_revenue,
        basic_revenue=basic_revenue,
        monthly_rev=monthly_rev,
        admin_user=_get_admin_user(),
    )


# ─────────────────────────────────────────────
#  Product Overview
# ─────────────────────────────────────────────

@admin_bp.route('/products')
@admin_required
def products():
    search = request.args.get('q', '').strip()
    user_filter = request.args.get('user_id', '')

    q = Product.query
    if search:
        q = q.filter(
            (Product.name.ilike(f'%{search}%')) |
            (Product.sku.ilike(f'%{search}%')) |
            (Product.category.ilike(f'%{search}%'))
        )
    if user_filter:
        q = q.filter_by(user_id=int(user_filter))

    all_products = q.order_by(Product.created_at.desc()).all()

    # Attach owner info
    for p in all_products:
        p._owner = db.session.get(User, p.user_id)

    total_products = Product.query.count()
    all_users = User.query.filter_by(is_admin=False).order_by(User.username).all()

    return render_template('admin/products.html',
        products=all_products,
        search=search,
        user_filter=user_filter,
        total_products=total_products,
        all_users=all_users,
        admin_user=_get_admin_user(),
    )


# ─────────────────────────────────────────────
#  Live Stats API
# ─────────────────────────────────────────────

@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    return jsonify({
        'total_users':    User.query.filter_by(is_admin=False).count(),
        'pro_users':      User.query.filter_by(tier='pro', is_admin=False).count(),
        'pending_demos':  DemoRequest.query.filter_by(status='pending').count(),
        'total_products': Product.query.count(),
        'total_revenue':  db.session.query(db.func.sum(Subscription.amount)).scalar() or 0,
    })
