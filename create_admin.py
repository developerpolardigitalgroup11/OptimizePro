import argparse
import bcrypt
import sys
from app import app
from models import db, User

def create_admin(username, email, password):
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"Error: A user with email '{email}' already exists.")
            sys.exit(1)
            
        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            print(f"Error: A user with username '{username}' already exists.")
            sys.exit(1)

        # Hash password securely
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
        
        # Pick avatar color
        avatar_colors = ['#6366f1', '#14b8a6', '#f59e0b', '#ef4444', '#22c55e', '#3b82f6', '#a855f7', '#ec4899']
        color_idx = ord(username[0].lower()) % len(avatar_colors)
        avatar_color = avatar_colors[color_idx]

        # Create user
        admin_user = User(
            username=username,
            email=email,
            password_hash=pw_hash,
            tier=None,  # Admin has no tier, they are the master controller
            is_admin=True,
            avatar_color=avatar_color,
        )
        
        db.session.add(admin_user)
        try:
            db.session.commit()
            print(f"Success! Admin user '{username}' created successfully.")
            
            # Security feature: Delete this script after successful execution
            import os
            try:
                os.remove(__file__)
                print("Security measure: The script has automatically deleted itself.")
            except Exception as e:
                print(f"Warning: Could not auto-delete the script. Please delete it manually. ({e})")
                
        except Exception as e:
            db.session.rollback()
            print(f"Failed to create admin user. Error: {e}")
            sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Create an admin user for OptimizePro")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    
    args = parser.parse_args()
    
    create_admin(args.username, args.email, args.password)
