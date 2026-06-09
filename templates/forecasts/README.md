# Forecasts

The `forecasts` templates provide views into the predictive ML modeling for future sales demand.

## Pages in this directory
- `overview.html`: A high-level list mapping products to their upcoming predicted demand.
- `view.html`: A detailed chart view for a specific product's future runway.

## Functionalities
- **Demand Forecasting**: Project sales velocity 14 days out using past sales data.
- **Visual Confidence Intervals**: Charts that display not just the expected number, but the upper/lower bounds of likelihood.
- **Inventory Runway Calculation**: Maps predicted demand against your current stock to estimate the exact day you will run out of inventory.

## How to Use
1. Visit the Forecasts page from the sidebar menu to see Top products and low-runway items.
2. Click "View Details" on any specific product to load the comprehensive graph for its prediction.
3. Compare the "Projected Runway" (days of stock left) against your supplier's lead time to make re-ordering decisions.

## Do's and Don'ts
*   **Do check "Low Runway Alerts"** section continuously to anticipate stockouts before they affect ranking algorithms on platforms like Amazon.
*   **Don't attempt to manually out-guess the model** without considering macro trends; the forecasting models aim to smooth out day-to-day volatility.
