# Alerts

The `alerts` templates provide a view into real-time operational notifications and warnings.

## Pages in this directory
- `list.html`: Displays a list of active alerts, categorized by priority (HIGH, MEDIUM, LOW).

## Functionalities
- **View Active Warnings**: Shows products that are low in stock, overstocked, or require rebalancing across marketplaces.
- **Dismiss Alerts**: Quickly acknowledge an alert once action has been taken.
- **Refresh Alerts**: Evaluates current stock conditions against rules (like order velocity) to generate new real-time alerts.

## How to Use
1. Access the alerts from the dashboard or sidebar navigation.
2. Read the high-priority alerts first (e.g. "UNDERSTOCK" warnings).
3. Take the necessary action (e.g., utilize the Allocation Planner to shift stock).
4. Dismiss the alert to clear your inbox.

## Do's and Don'ts
*   **Do check alerts daily:** Missing a critical alert might lead to lost revenue.
*   **Do click "Refresh Alerts"** if you've just made significant changes to inventory to see if your actions resolved the ongoing issues.
*   **Don't dismiss an alert without taking action** unless it's a known non-issue. Once dismissed, you'll need the system to trigger it again if the condition persists.
