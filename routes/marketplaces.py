"""Marketplace management routes."""

import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, Marketplace

marketplaces_bp = Blueprint('marketplaces', __name__)

# Allowed logo extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg', 'webp', 'gif'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_logo(file_storage) -> str | None:
    """Save an uploaded logo and return its path relative to static/."""
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed_file(file_storage.filename):
        return None

    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    unique_name = f"uploads/logos/{uuid.uuid4().hex}.{ext}"
    abs_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
    os.makedirs(abs_dir, exist_ok=True)
    file_storage.save(os.path.join(abs_dir, os.path.basename(unique_name)))
    return unique_name  # stored path is relative to static/


@marketplaces_bp.route('/')
@login_required
def list_marketplaces():
    mps = Marketplace.query.filter_by(user_id=current_user.id).order_by(Marketplace.priority.asc()).all()
    return render_template('marketplaces/list.html', marketplaces=mps)


@marketplaces_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_marketplace():
    if request.method == 'POST':
        marketplace_type = request.form.get('marketplace_type', 'ecommerce')
        priority = int(request.form.get('priority', 1))

        # ── E-commerce path ─────────────────────────────────────────
        if marketplace_type == 'ecommerce':
            platform = request.form.get('platform', '').strip().lower()

            platforms = {
                'amazon':    {'name': 'Amazon',    'color': '#FF9900'},
                'flipkart':  {'name': 'Flipkart',  'color': '#2874F0'},
                'meesho':    {'name': 'Meesho',    'color': '#F43397'},
                'myntra':    {'name': 'Myntra',    'color': '#E72E77'},
                'ajio':      {'name': 'Ajio',      'color': '#2C3E50'},
                'nykaa':     {'name': 'Nykaa',     'color': '#FC2779'},
                'tatacliq':  {'name': 'Tata CLiQ', 'color': '#DA1A35'},
                'snapdeal':  {'name': 'Snapdeal',  'color': '#E40046'},
                'jiomart':   {'name': 'JioMart',   'color': '#0088CC'},
                'blinkit':   {'name': 'Blinkit',   'color': '#F8CB46'},
                'firstcry':  {'name': 'FirstCry',  'color': '#F19A21'},
                'pepperfry': {'name': 'Pepperfry', 'color': '#F15A22'},
            }

            if platform not in platforms:
                flash('Please select a valid marketplace platform.', 'error')
                return render_template('marketplaces/add.html')

            name      = platforms[platform]['name']
            code      = platform
            color     = platforms[platform]['color']
            logo_path = f"icons/logo_{code}.svg"

            existing = Marketplace.query.filter_by(code=code, user_id=current_user.id).first()
            if existing:
                flash(f'Marketplace "{name}" is already added.', 'error')
                return render_template('marketplaces/add.html')

            mp = Marketplace(
                name=name, code=code, color=color,
                priority=priority, logo_path=logo_path,
                user_id=current_user.id
            )
            db.session.add(mp)
            db.session.commit()
            flash(f'{name} marketplace added!', 'success')
            return redirect(url_for('marketplaces.list_marketplaces'))

        # ── Other (custom) path ──────────────────────────────────────
        else:
            custom_name = request.form.get('custom_name', '').strip()
            if not custom_name:
                flash('Please enter a marketplace name.', 'error')
                return render_template('marketplaces/add.html')

            # Derive a short code from the name (slug-like, max 30 chars)
            code = custom_name.lower().replace(' ', '_')[:30]

            # Check duplicate code for this user
            suffix, attempt = '', 1
            base_code = code
            while Marketplace.query.filter_by(code=code + suffix, user_id=current_user.id).first():
                attempt += 1
                suffix = f'_{attempt}'
            code = code + suffix

            # Color (from picker / auto-extracted and submitted as hex field)
            color = request.form.get('custom_color', '#6366f1').strip()
            if not color.startswith('#') or len(color) not in (4, 7):
                color = '#6366f1'

            # Logo upload
            logo_file = request.files.get('logo_file')
            logo_path = _save_logo(logo_file)

            mp = Marketplace(
                name=custom_name, code=code, color=color,
                priority=priority, logo_path=logo_path,
                user_id=current_user.id
            )
            db.session.add(mp)
            db.session.commit()
            flash(f'"{custom_name}" marketplace added!', 'success')
            return redirect(url_for('marketplaces.list_marketplaces'))

    return render_template('marketplaces/add.html')


@marketplaces_bp.route('/<int:mp_id>/edit', methods=['POST'])
@login_required
def edit_marketplace(mp_id):
    mp = Marketplace.query.get_or_404(mp_id)
    if mp.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('marketplaces.list_marketplaces'))

    mp.name     = request.form.get('name', mp.name).strip()
    mp.color    = request.form.get('color', mp.color)
    mp.priority = int(request.form.get('priority', mp.priority))
    db.session.commit()
    flash(f'{mp.name} updated.', 'success')
    return redirect(url_for('marketplaces.list_marketplaces'))


@marketplaces_bp.route('/<int:mp_id>/toggle', methods=['POST'])
@login_required
def toggle_marketplace(mp_id):
    mp = Marketplace.query.get_or_404(mp_id)
    if mp.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('marketplaces.list_marketplaces'))

    mp.is_active = not mp.is_active
    db.session.commit()
    status = 'activated' if mp.is_active else 'deactivated'
    flash(f'{mp.name} {status}.', 'success')
    return redirect(url_for('marketplaces.list_marketplaces'))
