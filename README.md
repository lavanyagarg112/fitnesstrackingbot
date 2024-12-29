# Fitness Tracker Telegram Bot

This project is a private Telegram bot designed to help users track their fitness activities, goals, and progress using Google Sheets. The bot supports group and individual usage.

---

## Latest: New Features!

### Reminder System
The bot now includes an automated reminder system with the following commands:
- `/startreminders`: Start both daily fitness tracking reminders and hourly water reminders
- `/stopreminders`: Stop all active reminders
- `/checkreminders`: View all active reminders and their next scheduled times
- `/checktime`: Check the current time in your configured timezone

To configure timezone, add the following to your `.env` file:
```env
TIMEZONE=<Your Timezone>  # e.g., "Asia/Kolkata" or "America/New_York"
```

### Batch Update System
The new batch update feature allows you to update multiple metrics at once:
1. Use `/batchupdate` command
2. Select the person to update
3. Receive a template with current values
4. Edit the values as needed and send back
5. All values are updated simultaneously

---

## Features

1. **Daily Tracking**: Update and view daily fitness stats.
2. **Goal Management**: Add, view, and edit fitness goals.
3. **Weekly Summaries**: Generate weekly statistics of activities.
4. **Group and Individual Use**: Add the bot to your Telegram group or use it personally. You can use it for either one of them, but not both.
5. **Secure**: No other chat can access your bot, other than your individual chat or group chat.
6. **Automated Reminders**: 
   - Daily reminder at 7 PM to update fitness tracker
   - Hourly water reminders from 7 AM to 11 PM
   - Easily start/stop reminders with commands
7. **Batch Updates**: Update multiple fitness metrics at once using a template-based system.
8. **Timezone Support**: All reminders and timestamps are based on your configured timezone.

---

## Setup Instructions

### Prerequisites

1. **Python**: Ensure Python 3.8+ is installed.
2. **Google Account**: Required for Google Sheets and Google Cloud Console.
3. **Telegram Account**: To create a bot using BotFather.

### Step 1: Download the source code

1. Go to the [releases page](https://github.com/lavanyagarg112/fitnesstracking/releases) and download the latest release as a ZIP file.
2. Extract the ZIP file to a folder on your machine.

### Step 2: Prepare Google Sheets

1. Create a new Google Sheet with the following tabs:
   - **Daily Tracker**: For daily fitness entries.
   - **People**: To store names of users.
   - **Goals**: To manage fitness goals.
   - **Weekly Summary**: To store weekly summaries.
2. [Optional] Download `sample_sheet.xlsx` in the repository for an example structure.

#### Sample Sheet
- For daily tracker sheet, the Date and Name column is compulsory, other columns are based on what you want to track
- The weekly tracker should remain as in the sample shet
- The goals sheet can be empty, as the code will self add columns
- The rewards sheet is for self use, it is not used by the bot, so you can modify it however you want
- The people sheet should be empty before starting
- The sheet names should be exactly as they are in the sample_sheet

### Step 3: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Enable the **Google Sheets API** and **Google Drive API** for your project.
4. Navigate to **APIs & Services > Credentials**.
5. Click **Create Credentials** > **Service Account**.
6. Fill in the required details and create a JSON key file.
7. Ideally you would have to give it editor access in order to write to the google sheet.
8. Save the `credentials.json` file securely.
   - Ensure it is placed in the same folder as `fitness_bot.py`.
9. Go to your google sheet, and share it with the Service Account email found in the `credentials.json` file. Give it editor access.

### Step 4: Set Up a Telegram Bot

1. Open Telegram and search for [BotFather](https://t.me/BotFather).
2. Start a conversation and type `/newbot`.
3. Follow the instructions to set up your bot and get the API token.
4. Save the API token securely.

### Step 5: Configure `.env` File

1. In the project folder, create a `.env` file.
2. Add the following keys:
   ```env
   TELEGRAM_API_TOKEN=<Your Telegram Bot Token>
   CREDENTIALS_FILE=</path/to/json/credentials.json>
   GOOGLE_SHEET_ID=<Your Google Sheet ID>
   ADMIN_ID=<your individual or group chat id>
   TIMEZONE=<your timezone>
   ```
   - Replace `<Your Telegram Bot Token>` with the token from BotFather.
   - Replace `<Your Google Sheet ID>` with the ID from your Google Sheet URL.
     - Example: If your sheet URL is `https://docs.google.com/spreadsheets/d/abc123/edit`, the ID is `abc123`.
   - Example for TIMEZONE is 'Asia/Singapore'. If the given timezone is invalid, the application will default to UTC.

#### Getting the Admin ID (If you are using it for a group)
1. Go to [telegram web](https://web.telegram.org/)
2. Open the Group you wish to access
3. In the url, the last part has the format /#\<Chat ID>_\<Topic ID>
4. Thus, you have now obtained your Chat ID

#### Getting the Admin ID (if you are using it for individual use)
1. You can leave your ADMIN_ID empty for now, or put in a random one digit number.
2. After your bot is set and running, run the `/getuserid` command on the private chat with the bot. Our application does not store your userid at all.
3. You will obtain your user id. Set your ADMIN_ID to be this user id.
4. You can now run your bot!

If you have any alternatives, you can feel free to do so. You can even use some public bots to find your userid straight away!


### Step 6: Install Dependencies

To install the required libraries, you will need to first create a virtual environment and then install the dependencies from the `requirements.txt` file.

1. **Create a virtual environment:**

   In your project directory, run the following command to create a virtual environment:

   ```bash
   python -m venv venv
   ```

2. **Activate the virtual environment:**

   - **For Windows (Command Prompt):**
     ```bash
     venv\Scripts\activate
     ```

   - **For macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

3. **Install dependencies:**

   Once the virtual environment is activated, run:

   ```bash
   pip install -r requirements.txt
   ```

### Step 7: Run the Bot

1. Execute the bot with:
   ```bash
   python fitness_bot.py
   ```
2. The bot will start and can be used in your Telegram group or individually.

---

## Weekly Summaries

Weekly summaries are generated automatically using data from the `Weekly Summary` tab in your Google Sheet. No additional code is required for this feature. Ensure your Google Sheet follows the structure of the provided `sample_sheet.xlsx`.

---

## Notes

1. **Private Bot**: This bot is not open-source and does not accept contributions.
2. **Group Usage**: The bot can be added to Telegram groups to track multiple users.
3. **Individual Usage**: Use the bot personally for solo fitness tracking.

---

## Troubleshooting

1. **Missing `credentials.json`**:
   - Navigate to the Google Cloud Console.
   - Go to **APIs & Services > Credentials**.
   - Locate your Service Account and download the JSON key file.
   - Save it as `credentials.json` in the bot's folder.

2. **Google Sheet Permissions**:
   - Share your Google Sheet with the Service Account email found in the `credentials.json` file, with editor access.

3. **Dependencies Issue**:
   - Ensure you have Python 3.8+.
   - Run `pip install -r requirements.txt` to install missing packages.

4. **Not Authorized to Use the Bot**:
   - Ensure that you have set your ADMIN_ID correctly.
   - Ensure that you have followed the steps in [Configure `.env` File Section](#step-5-configure-env-file)

5. **How to understand the commands?**:
   - Use `/help` once you start your bot to see a full description of the commands

---

## Disclaimer

This bot is a personal project and is provided "as-is" without warranties or support. This is not an open source project, and is intended for personal and internal use only.

