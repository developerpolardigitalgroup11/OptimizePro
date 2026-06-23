import pytest
from models import Marketplace, db

def test_add_marketplace(client, test_user, app):
    """Test adding an ecommerce marketplace."""
    client.post('/auth/login', data={
        'login_id': 'testuser',
        'password': 'password123'
    })
    
    response = client.post('/marketplaces/add', data={
        'marketplace_type': 'ecommerce',
        'platform': 'amazon',
        'priority': '5'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    with app.app_context():
        user = db.session.merge(test_user)
        mp = Marketplace.query.filter_by(user_id=user.id, code='amazon').first()
        assert mp is not None
        assert mp.name == 'Amazon'
        assert mp.priority == 5

def test_add_custom_marketplace(client, test_user, app):
    """Test adding a custom marketplace."""
    client.post('/auth/login', data={
        'login_id': 'testuser',
        'password': 'password123'
    })
    
    response = client.post('/marketplaces/add', data={
        'marketplace_type': 'other',
        'custom_name': 'My Custom Store',
        'custom_color': '#ff0000',
        'priority': '1'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    with app.app_context():
        user = db.session.merge(test_user)
        mp = Marketplace.query.filter_by(user_id=user.id, name='My Custom Store').first()
        assert mp is not None
        assert mp.color == '#ff0000'
        assert mp.code.startswith('my_custom_store')
