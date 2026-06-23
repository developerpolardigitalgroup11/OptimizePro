import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), 'optimize_pro.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_filename VARCHAR(255)")
        print("Successfully added avatar_filename to users table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Column avatar_filename already exists.")
        else:
            print(f"Error: {e}")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
