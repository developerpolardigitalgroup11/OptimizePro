import pytest
from models import User, db

def test_login_page_loads(client):
    """Test that the login page loads correctly."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Sign In' in response.data

def test_successful_login(client, test_user):
    """Test login with valid credentials."""
    response = client.post('/auth/login', data={
        'login_id': 'testuser',
        'password': 'password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # The dashboard should load
    assert b'Dashboard' in response.data or b'Log Out' in response.data

def test_failed_login(client, test_user):
    """Test login with invalid credentials."""
    response = client.post('/auth/login', data={
        'login_id': 'testuser',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Invalid credentials' in response.data

def test_registration(client, app):
    """Test user registration step 1."""
    response = client.post('/auth/register', data={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'newpassword123',
        'confirm_password': 'newpassword123',
        'terms': 'y'
    }, follow_redirects=False)
    
    assert response.status_code == 302
    assert '/auth/select-tier' in response.location

def test_logout(client, test_user):
    """Test logging out."""
    client.post('/auth/login', data={
        'login_id': 'testuser',
        'password': 'password123'
    })
    
    response = client.get('/auth/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b'Sign In' in response.data
