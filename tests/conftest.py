import os
import pytest
from app import create_app
from models import db, User
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test_secret'
    # Disable WAL mode for testing if the app overrides it
    IS_POSTGRES = False

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app(TestConfig)
    
    # Establish an application context before running the tests.
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def test_user(app):
    """Create a default test user."""
    import bcrypt
    with app.app_context():
        # Hash password 'password123'
        pw_hash = bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=pw_hash,
            tier='pro',
            is_admin=False
        )
        db.session.add(user)
        db.session.commit()
        return user
