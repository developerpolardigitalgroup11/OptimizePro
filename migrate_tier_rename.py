"""One-time migration: rename 'free' tier to 'basic' in DB and add demo_requests table."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'optimize_pro.db')
con = sqlite3.connect(db_path)
cur = con.cursor()

# 1. Rename tier 'free' to 'basic' in users table
cur.execute("UPDATE users SET tier = 'basic' WHERE tier = 'free'")
print(f"Updated {cur.rowcount} user rows: free -> basic")

# 2. Rename plan 'free' to 'basic' in subscriptions table
cur.execute("UPDATE subscriptions SET plan = 'basic' WHERE plan = 'free'")
print(f"Updated {cur.rowcount} subscription rows: free -> basic")

# 3. Create demo_requests table if missing
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='demo_requests'")
if not cur.fetchone():
    cur.execute('''
        CREATE TABLE demo_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            username TEXT,
            email TEXT NOT NULL,
            phone TEXT,
            company TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("Created demo_requests table")
else:
    print("demo_requests table already exists")

con.commit()
con.close()
print("Migration complete!")
