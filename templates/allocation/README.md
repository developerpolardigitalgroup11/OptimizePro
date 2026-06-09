# Allocation

The `allocation` templates handle intelligent distribution of warehouse stock to your connected marketplaces.

## Pages in this directory
- `planner.html`: The interactive tool to request an allocation plan.
- `history.html`: Shows past allocations that you've applied.

## Functionalities
- **AI-Driven Allocation Generation**: Choose a product and input the amount of stock you want to push to marketplaces. It returns recommendations based on 14-day forecasted demand and marketplace share.
- **Visual Breakdown**: Shows exactly how many units go to each marketplace, the demand confidence, and reasoning for the split.
- **One-Click Application**: Automatically updates the marketplace inventories once a plan is approved.

## How to Use
1. Navigate to the Allocation Planner.
2. Select a product from the dropdown.
3. Enter the total number of units you wish to disburse out of the main warehouse.
4. Click "Generate Plan" and review the AI suggestions.
5. If you're happy with the split, click "Apply Allocation".

## Do's and Don'ts
*   **Do trust the demand prediction** over manual guesswork, as the tool looks at historical velocity and upcoming trends across all your sales channels.
*   **Do check your Warehouse Stock** on the Products page before allocating. You cannot allocate more stock than you have.
*   **Don't ignore the reasoning provided.** It offers valuable insight into why one marketplace was favored over another.
