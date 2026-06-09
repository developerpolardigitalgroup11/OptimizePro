# Marketplaces

The `marketplaces` templates handle the channels where you sell products.

## Pages in this directory
- `list.html`: Shows all connected marketplaces and allows adding new or editing existing ones.

## Functionalities
- **Marketplace Management**: Define the name, unique code, color identifier, and system priority for different eCommerce sites or physical store locations.
- **Priority Scaling**: Higher priority marketplaces will be favored in tight-stock situations by the Allocation Planner.
- **Aggregated Summaries**: View total products listed and total stock allocated inside these channels at a glance.

## How to Use
1. To change priority or visual color coding, simply click "Edit" on an existing marketplace in the list.
2. To add a new platform (e.g., Shopify, eBay), click "Add Marketplace" and fill in the details.

## Do's and Don'ts
*   **Do utilize color coding.** Make it visually obvious (e.g., Orange for Amazon) so charting and badges speed up your reading on other pages.
*   **Do adjust Priorities periodically.** If a marketplace suddenly pushes more volume or runs a promotional campaign, increase its priority.
*   **Don't mark a marketplace inactive** unless you've zeroed out its inventory first. This keeps data cleaner for historical reporting.
