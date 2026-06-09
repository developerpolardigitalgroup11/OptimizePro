"""Stock Allocation Engine — demand-proportional allocation across marketplaces."""

from models import db, AllocationPlan, AllocationLine, MarketplaceInventory, Marketplace, Product, RecommendationOutcome
from services.forecast_service import forecast_demand_all_marketplaces
from flask import current_app
from datetime import date


def generate_allocation(product_id, total_units, user_id):
    """Generate a stock allocation plan across all active marketplaces."""
    try:
        min_alloc = current_app.config.get('MIN_ALLOCATION_PER_MARKETPLACE', 5)
    except RuntimeError:
        min_alloc = 5

    product = Product.query.get(product_id)
    if not product:
        raise ValueError('Product not found')

    # Get active marketplace listings
    mi_list = MarketplaceInventory.query.filter_by(
        product_id=product_id, is_listed=True
    ).all()

    if not mi_list:
        raise ValueError('Product is not listed on any marketplace')

    # Step 1: Forecast demand per marketplace
    forecasts = forecast_demand_all_marketplaces(product_id)

    # Step 2: Calculate allocation weights
    allocations = []
    total_weight = 0

    for mi in mi_list:
        mp = Marketplace.query.get(mi.marketplace_id)
        if not mp or not mp.is_active:
            continue

        forecast = forecasts.get(mi.marketplace_id)
        predicted_demand = forecast.total_demand if forecast else 1.0

        # Weight = predicted_demand × margin_factor × priority_factor
        margin = max(mi.selling_price - product.cost_price, 0.01)
        margin_factor = 1.0 + (margin / max(mi.selling_price, 1)) * 0.2  # up to 20% bonus for high margin
        priority_factor = 1.0 + (mp.priority - 1) * 0.1  # up to 20% bonus for high priority

        weight = predicted_demand * margin_factor * priority_factor
        total_weight += weight

        allocations.append({
            'marketplace': mp,
            'mi': mi,
            'forecast': forecast,
            'predicted_demand': predicted_demand,
            'weight': weight,
            'margin': margin,
        })

    if total_weight == 0:
        total_weight = len(allocations)
        for a in allocations:
            a['weight'] = 1.0

    # Step 3: Proportional allocation with minimum guarantee
    remaining = total_units
    for a in allocations:
        share = a['weight'] / total_weight
        raw_qty = int(total_units * share)
        a['qty'] = max(raw_qty, min(min_alloc, total_units // len(allocations)))
        a['share_pct'] = round(share * 100, 1)

    # Adjust to exactly match total_units
    allocated_sum = sum(a['qty'] for a in allocations)
    diff = total_units - allocated_sum

    # Distribute remainder to highest-weight marketplaces
    allocations.sort(key=lambda x: x['weight'], reverse=True)
    idx = 0
    while diff != 0:
        if diff > 0:
            allocations[idx % len(allocations)]['qty'] += 1
            diff -= 1
        elif diff < 0 and allocations[idx % len(allocations)]['qty'] > 0:
            allocations[idx % len(allocations)]['qty'] -= 1
            diff += 1
        idx += 1
        if idx > total_units + len(allocations):
            break

    # Step 4: Build reasoning
    for a in allocations:
        forecast = a.get('forecast')
        model = forecast.model_used if forecast else 'n/a'
        reasons = []
        if a['predicted_demand'] > 0:
            reasons.append(f"Predicted {a['predicted_demand']:.0f} units demand (14d)")
        reasons.append(f"Margin: ₹{a['margin']:.0f}/unit")
        reasons.append(f"Priority: {a['marketplace'].priority}")
        reasons.append(f"Model: {model}")
        a['reasoning'] = '. '.join(reasons)

    # Step 5: Create plan in DB
    plan = AllocationPlan(
        product_id=product_id,
        total_units_to_allocate=total_units,
        status='draft',
        user_id=user_id,
    )
    db.session.add(plan)
    db.session.flush()

    for a in allocations:
        line = AllocationLine(
            allocation_plan_id=plan.id,
            marketplace_id=a['marketplace'].id,
            recommended_qty=a['qty'],
            predicted_demand_14d=a['predicted_demand'],
            marketplace_share_pct=a['share_pct'],
            reasoning=a['reasoning'],
        )
        db.session.add(line)

    db.session.commit()
    return plan


def apply_allocation(plan_id):
    """Apply an allocation plan — update marketplace inventories."""
    plan = AllocationPlan.query.get(plan_id)
    if not plan:
        raise ValueError('Plan not found')
    if plan.status == 'applied':
        raise ValueError('Plan already applied')

    product = Product.query.get(plan.product_id)

    for line in plan.lines:
        mi = MarketplaceInventory.query.filter_by(
            product_id=plan.product_id,
            marketplace_id=line.marketplace_id,
        ).first()

        if mi:
            mi.allocated_qty = line.recommended_qty
        else:
            mi = MarketplaceInventory(
                product_id=plan.product_id,
                marketplace_id=line.marketplace_id,
                allocated_qty=line.recommended_qty,
                selling_price=0,
                is_listed=True,
            )
            db.session.add(mi)

        # Create recommendation outcome for tracking
        outcome = RecommendationOutcome(
            product_id=plan.product_id,
            marketplace_id=line.marketplace_id,
            recommendation_type='ALLOCATION',
            recommendation_date=date.today(),
            recommended_qty=line.recommended_qty,
            predicted_demand=line.predicted_demand_14d,
            followed=True,
        )
        db.session.add(outcome)

    plan.status = 'applied'
    db.session.commit()
    return plan


def get_allocation_history(user_id):
    """Get past allocation plans for a user."""
    return AllocationPlan.query.filter_by(user_id=user_id).order_by(
        AllocationPlan.created_at.desc()
    ).limit(50).all()
