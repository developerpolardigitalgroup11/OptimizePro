"""Authentication blueprint — register, login, logout, forgot/reset password."""

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from models import db, User, Marketplace

auth_bp = Blueprint('auth', __name__, template_folder='templates')

DEFAULT_MARKETPLACES = [
    {'name': 'Amazon', 'code': 'amazon', 'color': '#FF9900', 'priority': 3},
    {'name': 'Flipkart', 'code': 'flipkart', 'color': '#2874F0', 'priority': 2},
    {'name': 'Meesho', 'code': 'meesho', 'color': '#570A57', 'priority': 1},
]


def _get_serializer():
    """Get a timed serializer for password reset tokens."""
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='password-reset')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validation
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

        # Create user
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
        user = User(username=username, email=email, password_hash=pw_hash)
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

        db.session.commit()
        login_user(user)
        flash('Welcome to OptimizePro! Your account has been created.', 'success')
        return redirect(url_for('dashboard.index'))


    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '')

        # Find user by username or email
        user = User.query.filter(
            (User.username == login_id) | (User.email == login_id.lower())
        ).first()

        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash('Welcome back!', 'success')
            return redirect(next_page or url_for('dashboard.index'))

        flash('Invalid credentials. Please try again.', 'error')
        return render_template('auth/login.html', login_id=login_id)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()

        if not login_id:
            flash('Please enter your username or email.', 'error')
            return render_template('auth/forgot_password.html')

        # Find user by username or email
        user = User.query.filter(
            (User.username == login_id) | (User.email == login_id.lower())
        ).first()

        if not user:
            flash('No account found with that username or email.', 'error')
            return render_template('auth/forgot_password.html', login_id=login_id)

        # Generate a signed token and store in session
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

    # Verify token exists in session
    token = session.get('reset_token')
    if not token:
        flash('Please verify your identity first.', 'error')
        return redirect(url_for('auth.forgot_password'))

    # Validate token (expires after 10 minutes)
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

        # Update password
        user.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
        db.session.commit()

        # Clear reset token
        session.pop('reset_token', None)

        flash('Password reset successfully! Please sign in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', username=user.username)
