"""Profile blueprint — view/edit profile, change password, subscription management."""

import uuid
import os
from datetime import datetime, timedelta

import bcrypt
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user

from models import db, User, Subscription
from auth import get_tier_config, AVATAR_COLORS

profile_bp = Blueprint('profile', __name__, template_folder='../templates')

TIER_CONFIG = None  # lazily loaded via get_tier_config()


def _tier_config():
    return get_tier_config()


# ─────────────────────────────────────────────
#  PROFILE INDEX (tabbed page)
# ─────────────────────────────────────────────

@profile_bp.route('/', methods=['GET'])
@login_required
def index():
    subscriptions = current_user.subscriptions.limit(10).all()
    active_sub = current_user.subscriptions.filter_by(status='active').first()
    return render_template(
        'profile/index.html',
        tiers=_tier_config(),
        subscriptions=subscriptions,
        active_sub=active_sub,
        avatar_colors=AVATAR_COLORS,
        tab=request.args.get('tab', 'info'),
    )


# ─────────────────────────────────────────────
#  EDIT PROFILE INFO
# ─────────────────────────────────────────────

@profile_bp.route('/update', methods=['POST'])
@login_required
def update():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    company = request.form.get('company', '').strip()
    avatar_color = request.form.get('avatar_color', current_user.avatar_color)

    errors = []
    if not email or '@' not in email:
        errors.append('Please enter a valid email address.')

    # Check email uniqueness (allow same email for self)
    existing = User.query.filter(User.email == email, User.id != current_user.id).first()
    if existing:
        errors.append('That email is already in use by another account.')

    if avatar_color not in AVATAR_COLORS:
        avatar_color = current_user.avatar_color

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('profile.index', tab='info'))

    # Handle image upload
    avatar_upload = request.files.get('avatar_upload')
    if avatar_upload and avatar_upload.filename:
        ext = avatar_upload.filename.rsplit('.', 1)[-1].lower()
        if ext in ['jpg', 'jpeg', 'png']:
            filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars', filename)
            avatar_upload.save(upload_path)
            current_user.avatar_filename = filename
        else:
            flash('Invalid image format. Only JPG and PNG are allowed.', 'error')
            return redirect(url_for('profile.index', tab='info'))
    elif request.form.get('remove_avatar') == '1':
        # User clicked an avatar color, remove the custom photo
        current_user.avatar_filename = None

    current_user.full_name = full_name or None
    current_user.email = email
    current_user.phone = phone or None
    current_user.company = company or None
    current_user.avatar_color = avatar_color
    db.session.commit()

    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile.index', tab='info'))


# ─────────────────────────────────────────────
#  CHANGE PASSWORD
# ─────────────────────────────────────────────

@profile_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    errors = []
    if not bcrypt.checkpw(current_pw.encode('utf-8'), current_user.password_hash.encode('utf-8')):
        errors.append('Current password is incorrect.')
    if not new_pw or len(new_pw) < 6:
        errors.append('New password must be at least 6 characters.')
    if new_pw != confirm_pw:
        errors.append('New passwords do not match.')

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('profile.index', tab='security'))

    current_user.password_hash = bcrypt.hashpw(new_pw.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
    db.session.commit()
    flash('Password changed successfully!', 'success')
    return redirect(url_for('profile.index', tab='security'))


# ─────────────────────────────────────────────
#  UPGRADE SUBSCRIPTION (open payment modal — handled by JS)
# ─────────────────────────────────────────────

@profile_bp.route('/upgrade', methods=['POST'])
@login_required
def upgrade():
    """Process payment and upgrade user's tier."""
    tier_key = request.form.get('tier', '')
    tiers = _tier_config()

    if tier_key not in tiers or tier_key == 'free':
        return jsonify({'success': False, 'message': 'Invalid plan selected.'}), 400

    if current_user.tier == tier_key:
        return jsonify({'success': False, 'message': 'You are already on this plan.'}), 400

    card_number = request.form.get('card_number', '').replace(' ', '')
    # Simulate: card ending in 0000 = failure
    if card_number.endswith('0000'):
        return jsonify({'success': False, 'message': 'Payment declined. Please use a different card.'})

    # Mark old subscription as superseded
    old_subs = current_user.subscriptions.filter_by(status='active').all()
    for s in old_subs:
        s.status = 'cancelled'

    tier_info = tiers[tier_key]
    expires = datetime.utcnow() + timedelta(days=30)

    new_sub = Subscription(
        user_id=current_user.id,
        plan=tier_key,
        status='active',
        amount=tier_info['price'],
        payment_method='card',
        transaction_id=str(uuid.uuid4()),
        billing_period_start=datetime.utcnow(),
        billing_period_end=expires,
    )
    db.session.add(new_sub)

    current_user.tier = tier_key
    current_user.tier_expires_at = expires
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Upgraded to {tier_info["name"]} successfully!',
        'redirect': url_for('profile.index', tab='subscription'),
    })


# ─────────────────────────────────────────────
#  CANCEL SUBSCRIPTION (downgrade to free)
# ─────────────────────────────────────────────

@profile_bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    if current_user.tier == 'free':
        flash('You are already on the Free plan.', 'info')
        return redirect(url_for('profile.index', tab='subscription'))

    old_subs = current_user.subscriptions.filter_by(status='active').all()
    for s in old_subs:
        s.status = 'cancelled'

    # Add free entry
    free_sub = Subscription(
        user_id=current_user.id,
        plan='free',
        status='active',
        amount=0.0,
        payment_method='none',
        billing_period_start=datetime.utcnow(),
        billing_period_end=None,
    )
    db.session.add(free_sub)

    current_user.tier = 'free'
    current_user.tier_expires_at = None
    db.session.commit()

    flash('Your subscription has been cancelled. You are now on the Free plan.', 'info')
    return redirect(url_for('profile.index', tab='subscription'))
