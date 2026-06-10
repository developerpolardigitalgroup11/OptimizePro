"""Migrate data from SQLite to PostgreSQL.

Usage:
  1. Set DATABASE_URL environment variable to your PostgreSQL connection string.
  2. Ensure the SQLite database exists at optimize_pro.db.
  3. Run this script: python db_migrate.py
"""

import os
import sqlite3
import pandas as pd
from sqlalchemy import create_engine, MetaData
from app import app, db
from models import User, Marketplace, Product, MarketplaceInventory, Sale, Alert, DailySalesSummary

def migrate():
    print("Starting migration from SQLite to PostgreSQL...")
    
    # 1. Determine database URLs
    base_dir = os.path.abspath(os.path.dirname(__file__))
    sqlite_path = os.path.join(base_dir, 'optimize_pro.db')
    
    if not os.path.exists(sqlite_path):
        print(f"Error: SQLite database not found at {sqlite_path}")
        return
        
    sqlite_url = f"sqlite:///{sqlite_path}"
    postgres_url = os.environ.get('DATABASE_URL')
    
    if not postgres_url:
        print("DATABASE_URL environment variable is not set. Falling back to default...")
        postgres_url = "postgresql://postgres:password@localhost:5432/optimize_pro"
        
    if postgres_url.startswith('postgres://'):
        postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)
        
    if not postgres_url.startswith('postgresql'):
        print(f"Error: DATABASE_URL does not appear to be a PostgreSQL URL: {postgres_url}")
        return

    print(f"Source: {sqlite_url}")
    print(f"Target: {postgres_url}")
    
    # 2. Setup engines
    sqlite_engine = create_engine(sqlite_url)
    postgres_engine = create_engine(postgres_url)
    
    # 3. Create schema in PostgreSQL
    print("\nCreating schema in PostgreSQL...")
    # Override app config to point to PostgreSQL to create tables
    app.config['SQLALCHEMY_DATABASE_URI'] = postgres_url
    with app.app_context():
        db.create_all()
        
    # 4. Tables to migrate (in order of dependencies)
    tables = [
        'user',
        'marketplace',
        'product',
        'marketplace_inventory',
        'sale',
        'alert',
        'daily_sales_summary'
    ]
    
    # 5. Copy data
    for table in tables:
        print(f"\nMigrating table: {table}...")
        try:
            # Read from SQLite
            df = pd.read_sql_table(table, sqlite_engine)
            if df.empty:
                print(f"  Table {table} is empty. Skipping.")
                continue
                
            print(f"  Found {len(df)} rows. Inserting into PostgreSQL...")
            
            # Write to PostgreSQL
            # We use if_exists='append' because create_all() already made the tables
            df.to_sql(table, postgres_engine, if_exists='append', index=False, method='multi', chunksize=1000)
            print(f"  Successfully migrated {table}.")
            
            # 6. Reset sequences in PostgreSQL
            # Postgres needs its autoincrement sequences updated to max(id) + 1
            if 'id' in df.columns:
                max_id = df['id'].max()
                if pd.notna(max_id):
                    seq_name = f"{table}_id_seq"
                    with postgres_engine.connect() as conn:
                        conn.execute(db.text(f"SELECT setval('{seq_name}', {max_id});"))
                        conn.commit()
                    print(f"  Reset sequence {seq_name} to {max_id}.")
                    
        except Exception as e:
            print(f"  Error migrating table {table}: {e}")
            
    print("\nMigration complete! You can now run the app with DATABASE_URL set.")

if __name__ == '__main__':
    migrate()
