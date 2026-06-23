"""Authentication blueprint — register (2-step), login, logout, forgot/reset password."""

import uuid
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from models import db, User, Marketplace, Subscription

auth_bp = Blueprint('auth', __name__, template_folder='templates')

DEFAULT_MARKETPLACES = [
    {'name': 'Amazon', 'code': 'amazon', 'color': '#FF9900', 'priority': 3},
    {'name': 'Flipkart', 'code': 'flipkart', 'color': '#2874F0', 'priority': 2},
    {'name': 'Meesho', 'code': 'meesho', 'color': '#570A57', 'priority': 1},
]

TIER_CONFIG = {
    'basic': {
        'name': 'Basic',
        'price': 499,
        'price_display': '\u20b9499',
        'period': 'per month',
        'features': [
            '3 Marketplaces',
            'Up to 50 Products',
            'Basic Sales Tracking',
            'ML Demand Forecasting',
        ],
        'unavailable': [
            'Advanced Analytics',
            'Stock Allocation Planner',
            'Smart Alerts & Insights',
            'Priority Support',
            'CSV / Excel Export',
        ],
        'badge_class': 'tier-basic',
        'color': '#6b7280',
    },
    'pro': {
        'name': 'Pro',
        'price': 999,
        'price_display': '₹999',
        'period': 'per month',
        'features': [
            'Unlimited Marketplaces',
            'Unlimited Products',
            'Advanced Sales Analytics',
            'ML Demand Forecasting (30-Day)',
            'Smart Stock Allocation Planner',
            'Smart Alerts & Insights',
            'Priority Support',
            'CSV / Excel Export',
            'API Access',
        ],
        'unavailable': [],
        'badge_class': 'tier-pro',
        'color': '#6366f1',
        'popular': True,
    },
}

AVATAR_COLORS = ['#6366f1', '#14b8a6', '#f59e0b', '#ef4444', '#22c55e', '#3b82f6', '#a855f7', '#ec4899']


def _get_serializer():
    """Get a timed serializer for password reset tokens."""
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='password-reset')


def _create_user_and_login(username, email, password, tier='free'):
    """Helper: create a user, seed marketplaces, record subscription, log in."""
    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

    # Pick an avatar color based on username initial
    color_idx = ord(username[0].lower()) % len(AVATAR_COLORS)
    avatar_color = AVATAR_COLORS[color_idx]

    # Set expiry for paid tiers (1 month)
    tier_expires_at = datetime.utcnow() + timedelta(days=30)

    user = User(
        username=username,
        email=email,
        password_hash=pw_hash,
        tier=tier,
        tier_expires_at=tier_expires_at,
        avatar_color=avatar_color,
    )
    db.session.add(user)
    db.session.flush()  # get user.id

    # Seed default marketplaces
    for mp in DEFAULT_MARKETPLACES:
        marketplace = Marketplace(
            name=mp['name'],
            code=mp['code'],
            color=mp['color'],
            priority=mp['priority'],
            user_id=user.id,
        )
        db.session.add(marketplace)

    # Record free subscription entry
    tier_info = TIER_CONFIG[tier]
    sub = Subscription(
        user_id=user.id,
        plan=tier,
        status='active',
        amount=tier_info['price'],
        payment_method='card',
        transaction_id=str(uuid.uuid4()),
        billing_period_start=datetime.utcnow(),
        billing_period_end=tier_expires_at,
    )
    db.session.add(sub)
    db.session.commit()

    login_user(user)
    return user


# ─────────────────────────────────────────────
#  STEP 1 — Register (collect user info)
# ─────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if User.query.filter_by(username=username).first():
            errors.append('Username already taken.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('auth/register.html', username=username, email=email)

        # Store in session and move to Step 2
        session['pending_reg'] = {'username': username, 'email': email, 'password': password}
        return redirect(url_for('auth.select_tier'))

    return render_template('auth/register.html')


# ─────────────────────────────────────────────
#  STEP 2 — Select Tier
# ─────────────────────────────────────────────

@auth_bp.route('/select-tier', methods=['GET', 'POST'])
def select_tier():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    pending = session.get('pending_reg')
    if not pending:
        flash('Please complete registration first.', 'error')
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        tier = request.form.get('tier', 'basic')
        if tier not in TIER_CONFIG:
            tier = 'basic'

        # Store tier in session, render payment modal
        session['pending_tier'] = tier
        return redirect(url_for('auth.payment_page'))

    return render_template('auth/select_tier.html', tiers=TIER_CONFIG, pending=pending)


# ─────────────────────────────────────────────
#  PAYMENT PAGE (mock gateway)
# ─────────────────────────────────────────────

@auth_bp.route('/payment', methods=['GET'])
def payment_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    pending = session.get('pending_reg')
    tier_key = session.get('pending_tier')

    if not pending or not tier_key or tier_key not in TIER_CONFIG:
        return redirect(url_for('auth.select_tier'))

    tier = TIER_CONFIG[tier_key]
    return render_template('auth/payment.html', tier=tier, tier_key=tier_key, pending=pending)


@auth_bp.route('/process-payment', methods=['POST'])
def process_payment():
    """Mock payment processor — simulates success/failure."""
    pending = session.get('pending_reg')
    tier_key = session.get('pending_tier')

    if not pending or not tier_key or tier_key not in TIER_CONFIG:
        return jsonify({'success': False, 'message': 'Session expired. Please start over.'}), 400

    card_number = request.form.get('card_number', '').replace(' ', '')
    # Simulate: card ending in 0000 = failure, anything else = success
    if card_number.endswith('0000'):
        return jsonify({'success': False, 'message': 'Payment declined. Please use a different card.'})

    # Create account with paid tier
    try:
        user = _create_user_and_login(
            username=pending['username'],
            email=pending['email'],
            password=pending['password'],
            tier=tier_key,
        )
        session.pop('pending_reg', None)
        session.pop('pending_tier', None)
        tier_name = TIER_CONFIG[tier_key]['name']
        return jsonify({
            'success': True,
            'message': f'Payment successful! Welcome to OptimizePro {tier_name}.',
            'redirect': url_for('dashboard.index'),
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Account creation failed. Please try again.'}), 500


# ─────────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter(
            (User.username == login_id) | (User.email == login_id.lower())
        ).first()

        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            if user.is_admin:
                flash('Please use the Admin Portal to log in.', 'error')
                return redirect(url_for('admin.login'))
            
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash('Welcome back!', 'success')
            return redirect(next_page or url_for('dashboard.index'))

        flash('Invalid credentials. Please try again.', 'error')
        return render_template('auth/login.html', login_id=login_id)

    return render_template('auth/login.html')


# ─────────────────────────────────────────────
#  LOGOUT
# ─────────────────────────────────────────────

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────
#  FORGOT / RESET PASSWORD
# ─────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()

        if not login_id:
            flash('Please enter your username or email.', 'error')
            return render_template('auth/forgot_password.html')

        user = User.query.filter(
            (User.username == login_id) | (User.email == login_id.lower())
        ).first()

        if not user:
            flash('No account found with that username or email.', 'error')
            return render_template('auth/forgot_password.html', login_id=login_id)

        s = _get_serializer()
        token = s.dumps(user.id)
        session['reset_token'] = token

        flash(f'Account verified: {user.username}. Please set your new password.', 'success')
        return redirect(url_for('auth.reset_password'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    token = session.get('reset_token')
    if not token:
        flash('Please verify your identity first.', 'error')
        return redirect(url_for('auth.forgot_password'))

    s = _get_serializer()
    try:
        user_id = s.loads(token, max_age=600)
    except SignatureExpired:
        session.pop('reset_token', None)
        flash('Your reset session has expired. Please try again.', 'error')
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        session.pop('reset_token', None)
        flash('Invalid reset session. Please try again.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = db.session.get(User, user_id)
    if not user:
        session.pop('reset_token', None)
        flash('Account not found.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        errors = []
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('auth/reset_password.html', username=user.username)

        user.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
        db.session.commit()
        session.pop('reset_token', None)

        flash('Password reset successfully! Please sign in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', username=user.username)


# ─────────────────────────────────────────────
#  TIER CONFIG API (for profile upgrade)
# ─────────────────────────────────────────────

def get_tier_config():
    return TIER_CONFIG


# ─────────────────────────────────────────────
#  BOOK A DEMO (Basic tier upsell)
# ─────────────────────────────────────────────

@auth_bp.route('/book-demo', methods=['POST'])
def book_demo():
    """Save a demo request. If pending_reg is in session (registration flow),
    also create a Basic account and log the user in automatically."""
    from models import DemoRequest
    from datetime import timedelta

    phone   = request.form.get('phone',   '').strip()
    company = request.form.get('company', '').strip()
    message = request.form.get('message', '').strip()

    # ── Case 1: User came from registration (Step 2 — Choose Plan)
    pending = session.get('pending_reg')
    if pending and not current_user.is_authenticated:
        email    = request.form.get('email', pending.get('email', '')).strip()
        username = pending.get('username', '')
        password = pending.get('password', '')

        if not email or '@' not in email:
            return jsonify({'success': False, 'message': 'Please provide a valid email.'}), 400

        # Create the account with Basic tier initially (admin will grant Pro upon demo acceptance)
        try:
            user = _create_user_and_login(
                username=username,
                email=email,
                password=password,
                tier='basic',
            )
        except Exception:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Account creation failed. Please try again.'}), 500

        # Fix subscription record: demo access is free, not a paid ₹999 sub
        from models import Subscription
        demo_sub = Subscription.query.filter_by(user_id=user.id).order_by(Subscription.id.desc()).first()
        if demo_sub:
            demo_sub.amount = 0
            demo_sub.payment_method = 'demo'

        # Save extra contact info to profile
        if phone:
            user.phone = phone
        if company:
            user.company = company

        # Clear registration session
        session.pop('pending_reg', None)
        session.pop('pending_tier', None)

        user_id = user.id

        # Book the demo request
        demo = DemoRequest(
            user_id  = user_id,
            username = username,
            email    = email,
            phone    = phone or None,
            company  = company or None,
            message  = message or None,
        )
        db.session.add(demo)
        db.session.commit()

        return jsonify({
            'success':  True,
            'message':  'Account created & demo request received! Our team will reach out within 24 hours.',
            'redirect': url_for('dashboard.index'),
        })

    # ── Case 2: Already logged-in user (profile page upsell)
    if current_user.is_authenticated:
        email    = request.form.get('email', current_user.email).strip()
        username = current_user.username
        user_id  = current_user.id
    else:
        # ── Case 3: Fully anonymous visitor
        email    = request.form.get('email', '').strip()
        username = request.form.get('name', '').strip()
        user_id  = None

    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'Please provide a valid email.'}), 400

    # Prevent duplicate submissions within 24 h
    cutoff = datetime.utcnow() - timedelta(hours=24)
    if user_id:
        existing = DemoRequest.query.filter(
            DemoRequest.user_id == user_id,
            DemoRequest.created_at >= cutoff,
        ).first()
    else:
        existing = DemoRequest.query.filter(
            DemoRequest.email == email,
            DemoRequest.created_at >= cutoff,
        ).first()

    if existing:
        return jsonify({'success': True, 'message': "We've already received your request! Our team will contact you within 24 hours."})

    demo = DemoRequest(
        user_id  = user_id,
        username = username or None,
        email    = email,
        phone    = phone or None,
        company  = company or None,
        message  = message or None,
    )
    db.session.add(demo)

    if current_user.is_authenticated:
        # Sync extra contact info back to profile if not already set
        if not current_user.phone and phone:
            current_user.phone = phone
        if not current_user.company and company:
            current_user.company = company

    db.session.commit()
    return jsonify({'success': True, 'message': 'Thank you! Our team will reach out to you shortly to schedule your demo.'})


# ─────────────────────────────────────────────
#  UPGRADE CONTACT
# ─────────────────────────────────────────────

@auth_bp.route('/contact-upgrade', methods=['POST'])
def contact_upgrade():
    from models import UpgradeRequest

    email = request.form.get('email', '').strip()
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    company = request.form.get('company', '').strip()
    message = request.form.get('message', '').strip()

    if current_user.is_authenticated:
        user_id = current_user.id
        if not email:
            email = current_user.email
    else:
        user_id = None
        if not email:
            return jsonify({'success': False, 'message': 'Please provide a valid email.'}), 400

    req = UpgradeRequest(
        user_id=user_id,
        name=name,
        email=email,
        phone=phone or None,
        company=company or None,
        message=message or None,
    )
    db.session.add(req)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Thank you! Our team will reach out to you shortly.'})


def pro_required(f):
    """Decorator: redirect Basic-tier users to dashboard with upgrade prompt."""
    import functools
    from flask import redirect, url_for, flash
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, render_template, jsonify
        if current_user.is_authenticated and current_user.tier == 'basic':
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Premium feature. Upgrade to Pro required.'}), 403
            return render_template('upsell.html')
        return f(*args, **kwargs)
    return decorated
