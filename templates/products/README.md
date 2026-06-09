# Products

The `products` templates manage the foundational inventory data.

## Pages in this directory
- `list.html`: View all your catalogue's Master SKUs and overall stock positions.
- `add.html`: Form to manually add a single new product to the catalogue.
- `upload.html`: Bulk-import mechanism via CSV files.
- `view.html`: Detailed page for a single product showing its cost, category, total warehouse stock, and how it is distributed across different marketplaces with localized pricing.
- `manage_listings.html`: Page strictly to enable/disable or update selling prices of a product across multiple marketplaces simultaneously.

## Functionalities
- **Central Inventory Management**: Maintains a 'single source of truth' for what you own and how much it costs.
- **Bulk Upload**: Import massive sets of inventory data to start using the system instantly.
- **Marketplace Listing toggles**: Easily flip a switch to list or delist a product from specific platforms.

## How to Use
1. Start by navigating to Products -> "Upload CSV" (if you have bulk data) or "Add Product" if you are just testing.
2. Ensure you accurately log the `cost_price` to allow the analytics dashboard to calculate profit properly.
3. Once products are in your warehouse via the system, use "Manage Listings" to set up your specific selling prices per marketplace.

## Do's and Don'ts
*   **Do ensure SKU names are strictly identical** to what you use in your external systems to avoid mapping issues later on.
*   **Do double-check cost prices.** Profit calculations rely entirely on this metric being accurate.
*   **Don't forget to enable listings.** A product may be in warehouse stock, but if it is not toggled "Listed" on a marketplace, the Allocation planner and forecaster won't allocate to it.
