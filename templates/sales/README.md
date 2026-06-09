# Sales

The `sales` templates record transactional outflow.

## Pages in this directory
- `record.html`: A quick point-of-sale interface to decrement stock manually for a specific marketplace.
- `history.html`: A tabular ledger showing all past sales.

## Functionalities
- **Inventory Decrementing**: Instantly deducts sold units from a marketplace's allocated stock pool.
- **Revenue tracking**: Logs exactly when and for how much an item was sold, feeding directly into analytics and forecasting.
- **Historical Audit**: Ability to filter past sales by marketplace and download them to CSV.

## How to Use
1. During normal operations, navigate to Sales -> "Record Sale".
2. Select the Product and then the Marketplace it sold on.
3. Verify the auto-populated selling price and adjust if the item was sold at a discount.
4. Finalize to record the sale.

## Do's and Don'ts
*   **Do verify the selling price.** If you ran a lightning deal or coupon, override the selling price on the recording screen so profit calculations don't become artificially inflated.
*   **Do record sales promptly.** The longer a sale goes unrecorded, the more inaccurate your active allocations and incoming forecasts become.
*   **Don't try to record a sale if stock is zero.** The system explicitly prevents negative allocations. If it claims you have 0 stock but you made a sale, your warehouse stock and allocations need auditing and correcting first.
