import pytest
from models import Product, db

def test_add_product(client, test_user, app):
    """Test adding a new product."""
    client.post('/auth/login', data={
        'login_id': 'testuser',
        'password': 'password123'
    })
    
    response = client.post('/products/add', data={
        'sku': 'TEST-SKU-001',
        'name': 'Test Product 1',
        'category': 'Electronics',
        'cost_price': '10.50',
        'quantity': '100'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Test Product 1' in response.data or b'TEST-SKU-001' in response.data
    
    with app.app_context():
        product = Product.query.filter_by(sku='TEST-SKU-001').first()
        assert product is not None
        assert product.name == 'Test Product 1'
        assert product.total_warehouse_qty == 100

def test_edit_product(client, test_user, app):
    """Test editing an existing product."""
    client.post('/auth/login', data={
        'login_id': 'testuser',
        'password': 'password123'
    })
    
    with app.app_context():
        # First ensure test_user has an id
        user = db.session.merge(test_user)
        product = Product(sku='EDIT-SKU', name='To Edit', category='Gen', cost_price=5, total_warehouse_qty=10, user_id=user.id)
        db.session.add(product)
        db.session.commit()
        product_id = product.id
        
    response = client.post(f'/products/{product_id}/edit', data={
        'name': 'Edited Name',
        'category': 'New Category',
        'cost_price': '15.0',
        'quantity': '20'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    with app.app_context():
        edited_product = Product.query.get(product_id)
        assert edited_product.name == 'Edited Name'
        assert edited_product.category == 'New Category'
        assert edited_product.cost_price == 15.0
        assert edited_product.total_warehouse_qty == 20
