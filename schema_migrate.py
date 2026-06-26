"""Database schema migration script."""

from models import db

def run_migrations(app=None):
    if app is None:
        from app import create_app
        app = create_app()
    with app.app_context():
        print("Starting schema migrations...")
        if app.config.get('IS_POSTGRES', False):
            print("Detected PostgreSQL database. Running migrations...")
            with db.engine.begin() as conn:
                try:
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(150);"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company VARCHAR(150);"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_color VARCHAR(7) DEFAULT '#6366f1';"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_filename VARCHAR(255);"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS tier VARCHAR(20) DEFAULT 'basic';"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS tier_expires_at TIMESTAMP;"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS default_currency VARCHAR(10) DEFAULT '₹';"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_categories TEXT DEFAULT '[]';"))
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS product_columns TEXT DEFAULT '[]';"))
                    conn.execute(db.text("ALTER TABLE products ADD COLUMN IF NOT EXISTS custom_attributes TEXT DEFAULT '{}';"))
                    conn.execute(db.text("ALTER TABLE marketplaces ADD COLUMN IF NOT EXISTS logo_path VARCHAR(255);"))
                    print("PostgreSQL migrations completed successfully.")
                except Exception as e:
                    print(f"Error auto-migrating columns: {e}")
        else:
            print("Detected SQLite database. Running migrations...")
            with db.engine.begin() as conn:
                try:
                    res_users = conn.execute(db.text("PRAGMA table_info(users)")).fetchall()
                    user_cols = [r[1] for r in res_users]
                    
                    if 'full_name' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN full_name VARCHAR(150);"))
                    if 'phone' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN phone VARCHAR(20);"))
                    if 'company' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN company VARCHAR(150);"))
                    if 'avatar_color' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN avatar_color VARCHAR(7) DEFAULT '#6366f1';"))
                    if 'avatar_filename' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN avatar_filename VARCHAR(255);"))
                    if 'tier' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN tier VARCHAR(20) DEFAULT 'basic';"))
                    if 'tier_expires_at' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN tier_expires_at TIMESTAMP;"))
                    if 'is_admin' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;"))
                    if 'default_currency' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN default_currency VARCHAR(10) DEFAULT '₹';"))
                    if 'custom_categories' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN custom_categories TEXT DEFAULT '[]';"))
                    if 'product_columns' not in user_cols: conn.execute(db.text("ALTER TABLE users ADD COLUMN product_columns TEXT DEFAULT '[]';"))

                    res_prods = conn.execute(db.text("PRAGMA table_info(products)")).fetchall()
                    prod_cols = [r[1] for r in res_prods]
                    if 'custom_attributes' not in prod_cols: conn.execute(db.text("ALTER TABLE products ADD COLUMN custom_attributes TEXT DEFAULT '{}';"))

                    res_mps = conn.execute(db.text("PRAGMA table_info(marketplaces)")).fetchall()
                    mp_cols = [r[1] for r in res_mps]
                    if 'logo_path' not in mp_cols: conn.execute(db.text("ALTER TABLE marketplaces ADD COLUMN logo_path VARCHAR(255);"))
                    print("SQLite migrations completed successfully.")
                except Exception as e:
                    print(f"Error migrating SQLite: {e}")

if __name__ == '__main__':
    run_migrations()
