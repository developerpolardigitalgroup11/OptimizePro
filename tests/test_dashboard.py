import pytest

def test_dashboard_redirect_unauthenticated(client):
    """Test that unauthenticated users are redirected from the dashboard."""
    response = client.get('/dashboard', follow_redirects=True)
    # Should redirect to login
    assert b'Sign In' in response.data

def test_dashboard_access_authenticated(client, test_user):
    """Test that authenticated users can access the dashboard."""
    client.post('/auth/login', data={
        'login_id': 'testuser',
        'password': 'password123'
    })
    
    response = client.get('/dashboard')
    assert response.status_code == 200
    # Dashboard elements should be present
    assert b'Total Revenue' in response.data or b'Dashboard' in response.data
