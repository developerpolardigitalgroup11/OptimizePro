# OptimizePro

**OptimizePro** is a smart multi-marketplace inventory management application with ML-powered forecasting. It enables sellers to streamline stock distribution, track sales across multiple platforms, and make data-driven allocation decisions.

## Functionalities

*   **Dashboard**: Offers a high-level overview of total products, warehouse stock, daily sales (revenue & units), active alerts, and marketplace performance.
*   **Marketplaces**: Allows users to configure multiple sales channels (e.g., Amazon, Flipkart, Meesho) tailored for their tracking needs.
*   **Products & Inventory**: Central repository to manage products (SKU, cost price, etc.). Users can view stock distribution, upload bulk changes via CSV, and adjust per-marketplace pricing and listed status.
*   **Sales**: Record sales manually per marketplace. History tracking is provided for auditing.
*   **Allocation Planner**: Powered by predictive algorithms, this helps sellers evenly and optimally distribute warehouse stock to different marketplaces based on velocity.
*   **Forecasts**: Machine Learning driven demand forecasting per product per marketplace, showing 14-day sales predictions to prevent stockouts or overstock situations.
*   **Alerts**: Real-time notifications for critical situations like understock, overstock, or opportunities for rebalancing inventory between marketplaces.
*   **Analytics**: Detailed breakdown of forecast accuracy, marketplace performance comparison, financial impacts (profits gained, losses saved), and revenue trend charts. Data can be exported to CSV.

## How to Use the App

1.  **Register / Login**: Start by creating an account. Default marketplaces (Amazon, Flipkart, Meesho) will be automatically seeded for you.
2.  **Add Marketplaces**: Head to the Marketplaces tab if you sell on additional platforms outside the defaults. Ensure you set their priority based on your sales volume.
3.  **Add Products**: Go to the Products tab. Use "Add Product" for a single item, or "Upload CSV" for bulk-importing multiple products and their stock quantities.
4.  **Allocate Stock**: Use the Allocation Planner when a new batch of stock arrives in your warehouse. The system will recommend how much to allocate to each marketplace to maximize profit and avoid stockouts.
5.  **Record Sales**: When orders happen, log them in the Sales section to decrement the stock from that specific marketplace. (For automated systems, this would be API-driven).
6.  **Monitor Forecasts and Analytics**: Check daily for new predictions and monitor the Analytics page to see how well predictions match actual demand.
7.  **Review Alerts**: Regularly check your alerts for action prompts. An alert might warn you to rebalance stock from Flipkart to Amazon if Amazon is selling faster than predicted.

## Do's and Don'ts

### Do's
*   **Do keep information updated:** Log sales data diligently (if manually entering). Accurate sales data fuels accurate forecasting.
*   **Do check forecasts regularly:** Adjust your reordering schedule based on the Forecasts page to ensure warehouse restocks happen before a marketplace goes out of stock.
*   **Do utilize CSV imports:** For faster onboarding, use the CSV upload utility instead of adding products manually.
*   **Do pay attention to Alerts:** Critical understock alerts mean you are actively losing revenue. Deal with them as quickly as possible.

### Don'ts
*   **Don't ignore the Rebalance Alerts:** Relocating stock from a poorly performing marketplace to a high-demand marketplace can save you from lost sales.
*   **Don't upload malformed CSV files:** Before uploading, ensure your CSV columns precisely match the requirements (`sku`, `name`, `cost_price`, `quantity`). See the Guidelines section during upload.
*   **Don't skip marketplace priority:** Set your highest volume marketplace with the highest priority so the allocation planner can optimize correctly.
