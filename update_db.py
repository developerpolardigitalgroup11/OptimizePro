import sqlite3
import os

base_dir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(base_dir, 'optimize_pro.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE marketplaces ADD COLUMN logo_path VARCHAR(255);')
    print("Column 'logo_path' added to marketplaces table successfully.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'logo_path' already exists.")
    else:
        print(f"Error: {e}")

# Optionally set default values for existing ones
cursor.execute("UPDATE marketplaces SET logo_path = 'icons/logo_' || code || '.svg' WHERE logo_path IS NULL;")

conn.commit()
conn.close()
