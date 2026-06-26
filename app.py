"""Flask application factory for OptimizePro."""

from flask import Flask, redirect, url_for
from flask_login import LoginManager
from config import Config
from models import db, User


login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.setdefault('MAX_CONTENT_LENGTH', 2 * 1024 * 1024)  # 2 MB upload limit
    
    # Ensure upload directory exists
    import os
    upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'avatars')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    os.makedirs(upload_dir, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Enable WAL mode for SQLite concurrent reads (skip for Postgres)
    if not app.config.get('IS_POSTGRES', False):
        @app.before_request
        def _enable_wal():
            if not getattr(app, '_wal_enabled', False):
                with db.engine.connect() as conn:
                    conn.execute(db.text("PRAGMA journal_mode=WAL"))
                    conn.execute(db.text("PRAGMA synchronous=NORMAL"))
                    conn.commit()
                app._wal_enabled = True


    # Register blueprints
    from auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from routes.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)

    from routes.marketplaces import marketplaces_bp
    app.register_blueprint(marketplaces_bp, url_prefix='/marketplaces')

    from routes.products import products_bp
    app.register_blueprint(products_bp, url_prefix='/products')

    from routes.sales import sales_bp
    app.register_blueprint(sales_bp, url_prefix='/sales')

    from routes.alerts import alerts_bp
    app.register_blueprint(alerts_bp, url_prefix='/alerts')

    from routes.forecasts import forecasts_bp
    app.register_blueprint(forecasts_bp, url_prefix='/forecasts')

    from routes.allocation import allocation_bp
    app.register_blueprint(allocation_bp, url_prefix='/allocation')

    from routes.analytics import analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    from routes.export import export_bp
    app.register_blueprint(export_bp, url_prefix='/export')

    from routes.profile import profile_bp
    app.register_blueprint(profile_bp, url_prefix='/profile')

    from routes.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Create tables and seed defaults
    with app.app_context():
        db.create_all()
        try:
            from schema_migrate import run_migrations
            run_migrations(app)
        except Exception as e:
            print(f"Error running migrations from app.py: {e}")
            
        _seed_defaults(app)


    # Root redirect
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated and current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dashboard.index'))

    # Restrict admin from accessing client routes
    @app.before_request
    def restrict_admin_access():
        from flask import request
        from flask_login import current_user
        if current_user.is_authenticated and current_user.is_admin:
            # Allow static files, auth routes, admin routes, and the root index
            if request.endpoint and request.endpoint.startswith('static'):
                return
            if request.blueprint not in ('admin', 'auth') and request.endpoint != 'index':
                return redirect(url_for('admin.dashboard'))

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        from flask_login import current_user
        if current_user.is_authenticated and current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dashboard.index'))

    return app


def _seed_defaults(app):
    """Seed default marketplaces for new users on first run."""
    # This is handled per-user at registration time
    pass


# Entry point
app = create_app()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
