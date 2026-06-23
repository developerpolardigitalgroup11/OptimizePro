"""Patch NULL values in existing rows that were created before the migration."""
import sqlite3
import datetime

db = r'D:\Downloads\v3\optimize-pro-main\optimize-pro-main\optimize_pro.db'
con = sqlite3.connect(db)
cur = con.cursor()

now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
default_color = '#6366f1'
default_tier  = 'free'

cur.execute('UPDATE subscriptions SET created_at = ? WHERE created_at IS NULL', (now,))
print(f'Fixed {cur.rowcount} subscription rows with NULL created_at')

cur.execute('UPDATE users SET created_at = ? WHERE created_at IS NULL', (now,))
print(f'Fixed {cur.rowcount} user rows with NULL created_at')

cur.execute('UPDATE users SET avatar_color = ? WHERE avatar_color IS NULL', (default_color,))
print(f'Fixed {cur.rowcount} user rows with NULL avatar_color')

cur.execute('UPDATE users SET tier = ? WHERE tier IS NULL', (default_tier,))
print(f'Fixed {cur.rowcount} user rows with NULL tier')

con.commit()
con.close()
print('Patch complete!')
