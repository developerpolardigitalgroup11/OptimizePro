"""One-time migration: add new User columns and create subscriptions table."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'optimize_pro.db')
con = sqlite3.connect(db_path)
cur = con.cursor()

# ─── 1. Check existing columns on users table
cur.execute('PRAGMA table_info(users)')
cols = [r[1] for r in cur.fetchall()]
print('Existing user columns:', cols)

migrations = [
    ('full_name',       'ALTER TABLE users ADD COLUMN full_name TEXT'),
    ('phone',           'ALTER TABLE users ADD COLUMN phone TEXT'),
    ('company',         'ALTER TABLE users ADD COLUMN company TEXT'),
    ('avatar_color',    "ALTER TABLE users ADD COLUMN avatar_color TEXT DEFAULT '#6366f1'"),
    ('tier',            "ALTER TABLE users ADD COLUMN tier TEXT DEFAULT 'free'"),
    ('tier_expires_at', 'ALTER TABLE users ADD COLUMN tier_expires_at TIMESTAMP'),
]

for col, sql in migrations:
    if col not in cols:
        cur.execute(sql)
        print(f'  [+] Added column: {col}')
    else:
        print(f'  [=] Column already exists: {col}')

con.commit()

# ─── 2. Create subscriptions table if missing
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subscriptions'")
if not cur.fetchone():
    cur.execute('''
        CREATE TABLE subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            plan TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            amount REAL DEFAULT 0.0,
            currency TEXT DEFAULT 'INR',
            payment_method TEXT,
            transaction_id TEXT,
            billing_period_start TIMESTAMP,
            billing_period_end TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute(
        'CREATE INDEX IF NOT EXISTS ix_subscription_user_created '
        'ON subscriptions (user_id, created_at)'
    )
    con.commit()
    print('[+] Created subscriptions table')
else:
    print('[=] subscriptions table already exists')

# ─── 3. Seed free subscription for any existing users who have none
cur.execute('SELECT id FROM users')
user_ids = [r[0] for r in cur.fetchall()]
for uid in user_ids:
    cur.execute('SELECT id FROM subscriptions WHERE user_id = ?', (uid,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO subscriptions (user_id, plan, status, amount) VALUES (?, 'free', 'active', 0.0)",
            (uid,)
        )
        print(f'  [+] Seeded free subscription for user {uid}')

con.commit()
con.close()
print('\nMigration complete!')
