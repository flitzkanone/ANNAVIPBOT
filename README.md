# Telegram Bot - Scam

## Core Functionality:

### User Interaction: 
The bot primarily interacts with users through inline keyboard buttons, guiding them through menus rather than relying on text commands.

### Content Selling:
It is structured to sell packages of pictures and videos, as well as services like live calls and in-person meetings. Prices are configurable within the script.

### Content Preview:
Users can view a limited number of preview media files (images and videos). The bot tracks the number of previews a user has clicked and enforces a limit (defaulting to 25).

### Payment Methods:
It supports three payment methods:

### PayPal:
Generates a paypal.me link for the user.

### Amazon Vouchers:
Prompts the user to send a voucher code, which is then forwarded to the admin for manual verification.

### Cryptocurrency:
Provides static Bitcoin and Ethereum wallet addresses for payment.

## Data Management

### File-Based Storage:
The bot uses JSON files (vouchers.json and stats.json) to persist data.

### vouchers.json:
Stores submitted Amazon voucher codes.

### stats.json:
Tracks user data (first start, last start, preview clicks, initiated payments, ban status), event statistics (like command usage), and admin log message IDs.
Discount Persistence via Telegram: In a unique approach, the bot saves and restores active user discounts by editing a specific message in a designated admin group. This acts as a remote, persistent storage, ensuring discounts are not lost if the bot restarts.

## Admin Features

### The bot includes a powerful, private admin panel accessible only to a specified ADMIN_USER_ID. The features include:

### Statistics:
View the total number of users and detailed click statistics for various events.

### Voucher Management:
See a list of all submitted Amazon voucher codes and download the list as a PDF report.

### User Management:
Ban or unban specific users by their ID.
Manage a user's preview click limit (reset to zero or increase).

### Discount Management:
Send custom discounts (percentage or fixed Euro value) to either all users or a specific user.
Apply discounts to specific packages (e.g., "10 Videos") or all packages at once.
View and delete active discounts for a specific user or clear all discounts across the entire user base.

## Automated Processes & Notifications

### Welcome-Back Discount:
Automatically sends a 10% discount offer to a user who returns to the bot after more than two hours of inactivity.

### Admin Logging:
Forwards detailed logs of user activity (e.g., starting the bot, viewing prices, initiating a payment) to a private notification group, allowing the admin to monitor user journeys in real-time.

### Payment/Voucher Notifications:
Sends immediate alerts to the admin group whenever a user initiates a payment or submits a voucher code, prompting the admin for necessary action.

### Meeting Booking Flow:
Guides the user through a multi-step process for booking a meeting, asking for the desired date and location before presenting a summary and payment options for a deposit.
