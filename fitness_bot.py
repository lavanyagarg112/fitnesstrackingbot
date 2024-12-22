from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from datetime import datetime
import os

# Load environment variables
load_dotenv()

# Environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE')
SPREADSHEET_ID = os.getenv('GOOGLE_SHEET_ID')

# Google Sheets Service
def get_sheet_service():
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE)
    return build('sheets', 'v4', credentials=credentials).spreadsheets()

# Helper function to handle empty data
def ensure_sheet_data(sheet, range):
    data = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range).execute().get('values', [])
    return data if data else [[]]

# Conversation states
SELECT_NAME, SELECT_COLUMN, UPDATE_VALUE = range(3)

async def update_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fetch available names from the sheet
    service = get_sheet_service()
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Daily Tracker!A2:B").execute()
    data = sheet.get('values', [])

    if not data:
        await update.message.reply_text("No names found. Please add data first.")
        return ConversationHandler.END

    # Extract unique names
    names = list(set(row[1] for row in data if len(row) > 1))

    # Show names as buttons
    keyboard = [[InlineKeyboardButton(name, callback_data=name)] for name in names]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the name:", reply_markup=reply_markup)
    return SELECT_NAME

async def select_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["name"] = query.data

    # Fetch column headers
    service = get_sheet_service()
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Daily Tracker!1:1").execute()
    headers = sheet.get('values', [[]])[0]

    if not headers:
        await query.message.reply_text("No columns found. Please add headers first.")
        return ConversationHandler.END

    # Show columns as buttons
    keyboard = [
        [InlineKeyboardButton(f"{header}", callback_data=header)] for header in headers[2:]  # Exclude Date, Name
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Select the column:", reply_markup=reply_markup)
    return SELECT_COLUMN

async def select_column(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["column"] = query.data

    # Check if a value already exists
    service = get_sheet_service()
    today_date = datetime.now().strftime("%Y-%m-%d")
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Daily Tracker!A1:Z").execute()
    data = sheet.get('values', [])
    headers = data[0]
    column_index = headers.index(query.data)
    name = context.user_data["name"]

    row = next((row for row in data[1:] if len(row) > 1 and row[0] == today_date and row[1] == name), None)
    current_value = row[column_index] if row and len(row) > column_index else "None"

    await query.message.reply_text(
        f"The current value for '{query.data}' is: {current_value}\n\nPlease send the new value:"
    )
    return UPDATE_VALUE

async def update_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text
    name = context.user_data["name"]
    column = context.user_data["column"]

    # Update the Google Sheet
    service = get_sheet_service()
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Daily Tracker!A1:Z").execute()
    data = sheet.get('values', [])
    headers = data[0]
    column_index = headers.index(column)
    today_date = datetime.now().strftime("%Y-%m-%d")

    # Find or create the row for today and the name
    row_index = next((i for i, row in enumerate(data) if len(row) > 1 and row[0] == today_date and row[1] == name), None)
    if row_index is None:
        # Add a new row
        new_row = [today_date, name] + [""] * (len(headers) - 2)
        data.append(new_row)
        row_index = len(data) - 1

    # Ensure the row has enough columns
    while len(data[row_index]) < len(headers):
        data[row_index].append("")

    # Update the value
    data[row_index][column_index] = new_value
    service.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range="Daily Tracker!A1:Z",
        valueInputOption="RAW",
        body={"values": data}
    ).execute()

    await update.message.reply_text(
        f"Updated {name}'s {column} to {new_value} for {today_date}."
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Update cancelled.")
    return ConversationHandler.END

async def add_new_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = ' '.join(context.args)
        if not args:
            await update.message.reply_text("Usage: /addnewperson <name>")
            return

        service = get_sheet_service()
        service.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="People!A1",
            valueInputOption="RAW",
            body={"values": [[args]]}
        ).execute()
        await update.message.reply_text(f"Added new person: {args}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def view_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        service = get_sheet_service()
        sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Daily Tracker!A1:Z").execute()
        data = sheet.get('values', [])
        
        # Get today's date
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # Ensure headers and data exist
        if not data or len(data) < 2:
            await update.message.reply_text("No entries found for today.")
            return

        headers = data[0]
        today_entries = [dict(zip(headers, row)) for row in data[1:] if len(row) > 0 and row[0] == today_date]
        
        if not today_entries:
            await update.message.reply_text("No entries found for today.")
            return

        # Format today's entries for display
        response = "Today's Entries:\n"
        for entry in today_entries:
            response += "\n".join(f"{key}: {value}" for key, value in entry.items() if value)
            response += "\n---\n"

        await update.message.reply_text(response.strip())
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def add_columns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        column_name = ' '.join(context.args)
        if not column_name:
            await update.message.reply_text("Usage: /addcolumns <column name>")
            return

        service = get_sheet_service()
        headers = ensure_sheet_data(service, "Daily Tracker!1:1")[0]
        headers.append(column_name)

        service.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range="Daily Tracker!1:1",
            valueInputOption="RAW",
            body={"values": [headers]}
        ).execute()
        await update.message.reply_text(f"Added column: {column_name}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def weekly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        name = ' '.join(context.args)
        if not name:
            await update.message.reply_text("Usage: /weekly <name>")
            return

        service = get_sheet_service()
        sheet = ensure_sheet_data(service, "Weekly Summary!A1:Z")

        stats = [row for row in sheet[1:] if row[1] == name]
        if not stats:
            await update.message.reply_text(f"No stats found for {name}.")
            return

        await update.message.reply_text(f"Weekly Stats for {name}:\n" + "\n".join([', '.join(row) for row in stats]))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

SELECT_NAME_GOALS, ADD_GOAL_NAME, ADD_GOAL_DESCRIPTION, SELECT_GOAL_TO_EDIT, EDIT_GOAL_DESCRIPTION = range(5)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from datetime import datetime
import os

# Load environment variables
load_dotenv()

# Environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE')
SPREADSHEET_ID = os.getenv('GOOGLE_SHEET_ID')

# Google Sheets Service
def get_sheet_service():
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE)
    return build('sheets', 'v4', credentials=credentials).spreadsheets()

# Helper function to handle empty data
def ensure_sheet_data(sheet, range):
    data = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range).execute().get('values', [])
    return data if data else [[]]

# Conversation states
SELECT_NAME_GOALS, ADD_GOAL_NAME, ADD_GOAL_DESCRIPTION, SELECT_GOAL_TO_EDIT, EDIT_GOAL_DESCRIPTION = range(5)

async def view_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        name = ' '.join(context.args)
        if not name:
            await update.message.reply_text("Usage: /viewgoals <name>")
            return

        service = get_sheet_service()
        sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Goals!A1:Z").execute()
        data = sheet.get('values', [])

        if not data or len(data) < 2:
            await update.message.reply_text(f"No goals found for {name}.")
            return

        headers = data[0]
        goals = [dict(zip(headers, row)) for row in data[1:] if row[0] == name]

        if not goals:
            await update.message.reply_text(f"No goals found for {name}.")
            return

        response = f"Goals for {name}:\n"
        for goal in goals:
            response += "\n".join(f"{key}: {value}" for key, value in goal.items() if value)
            response += "\n---\n"

        await update.message.reply_text(response.strip())
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def add_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = get_sheet_service()
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="People!A1:A").execute()
    people_data = sheet.get('values', [])

    if not people_data:
        await update.message.reply_text("No names found in the 'People' sheet. Please add names first.")
        return ConversationHandler.END

    names = [row[0] for row in people_data if len(row) > 0]
    keyboard = [[InlineKeyboardButton(name, callback_data=name)] for name in names]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the person for whom you want to add a goal:", reply_markup=reply_markup)
    return SELECT_NAME_GOALS

async def add_goal_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["person_name"] = query.data

    await query.message.reply_text("Please send the name of the new goal.")
    return ADD_GOAL_NAME

async def add_goal_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goal_name = update.message.text
    context.user_data["goal_name"] = goal_name

    await update.message.reply_text("Please send the description for this goal.")
    return ADD_GOAL_DESCRIPTION

async def finalize_goal_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goal_description = update.message.text
    person_name = context.user_data.get("person_name")
    goal_name = context.user_data.get("goal_name")

    try:
        service = get_sheet_service()
        sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Goals!A1:Z").execute()
        data = sheet.get('values', [])

        if not data:
            headers = ["Name", "Goal Name", "Description"]
            data = [headers]

        headers = data[0]
        new_row = ["" for _ in headers]
        new_row[0] = person_name
        new_row[1] = goal_name
        new_row[2] = goal_description

        data.append(new_row)

        service.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range="Goals!A1:Z",
            valueInputOption="RAW",
            body={"values": data}
        ).execute()

        await update.message.reply_text(f"Goal '{goal_name}' added for {person_name}.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

    return ConversationHandler.END

async def edit_goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = get_sheet_service()
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="People!A1:A").execute()
    people_data = sheet.get('values', [])

    if not people_data:
        await update.message.reply_text("No names found in the 'People' sheet. Please add names first.")
        return ConversationHandler.END

    names = [row[0] for row in people_data if len(row) > 0]
    keyboard = [[InlineKeyboardButton(name, callback_data=name)] for name in names]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the person whose goal you want to edit:", reply_markup=reply_markup)
    return SELECT_GOAL_TO_EDIT

async def select_goal_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["person_name"] = query.data

    service = get_sheet_service()
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Goals!A1:Z").execute()
    data = sheet.get('values', [])

    goals = [row for row in data[1:] if row[0] == query.data]

    if not goals:
        await query.message.reply_text(f"No goals found for {query.data}.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(row[1], callback_data=row[1])] for row in goals]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Select the goal to edit:", reply_markup=reply_markup)
    return EDIT_GOAL_DESCRIPTION

async def edit_goal_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["goal_name"] = query.data

    await query.message.reply_text("Please send the updated description for this goal:")
    return EDIT_GOAL_DESCRIPTION

async def finalize_edit_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    updated_description = update.message.text
    person_name = context.user_data.get("person_name")
    goal_name = context.user_data.get("goal_name")

    try:
        service = get_sheet_service()
        sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Goals!A1:Z").execute()
        data = sheet.get('values', [])

        headers = data[0]
        goal_index = next((i for i, row in enumerate(data[1:], start=1) if row[0] == person_name and row[1] == goal_name), None)

        if goal_index is None:
            await update.message.reply_text(f"Goal '{goal_name}' for {person_name} not found.")
            return ConversationHandler.END

        while len(data[goal_index]) < len(headers):
            data[goal_index].append("")

        data[goal_index][2] = updated_description

        service.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range="Goals!A1:Z",
            valueInputOption="RAW",
            body={"values": data}
        ).execute()

        await update.message.reply_text(f"Goal '{goal_name}' for {person_name} updated successfully.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001F44B Welcome to the Fitness Tracking Bot! \U0001F3CB\n\n"
        "Here to help you track your fitness journey effortlessly.\n"
        "Type /help to see the list of available commands!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """
Here are the available commands:
/start - Start the bot and get a welcome message
/help - Show this help message
/addnewperson - Add a new person to the fitness tracking sheet
/viewtoday - View today's stats for a person
/addcolumns - Add a new column to the sheet
/update - Update today's data for a person
/weekly - View weekly stats for a person
/viewgoals - View goals for a person
/addgoal - Add a new goal for a person
/editgoal - Edit an existing goal for a person
/cancel - Cancel current operation
"""
    )

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Conversation handler for /update
    update_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("update", update_start)],
        states={
            SELECT_NAME: [CallbackQueryHandler(select_name)],
            SELECT_COLUMN: [CallbackQueryHandler(select_column)],
            UPDATE_VALUE: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, update_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    add_goal_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addgoal", add_goal_start)],
        states={
            SELECT_NAME_GOALS: [CallbackQueryHandler(add_goal_name)],
            ADD_GOAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_description)],
            ADD_GOAL_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_goal_description)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    edit_goal_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("editgoal", edit_goal_start)],
        states={
            SELECT_GOAL_TO_EDIT: [CallbackQueryHandler(select_goal_to_edit)],
            EDIT_GOAL_DESCRIPTION: [
                CallbackQueryHandler(edit_goal_description),  # For selecting the goal
                MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_edit_goal),  # For entering the updated description
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )



    # Register Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addnewperson", add_new_person))
    application.add_handler(CommandHandler("viewtoday", view_today))
    application.add_handler(CommandHandler("addcolumns", add_columns))
    application.add_handler(CommandHandler("weekly", weekly_stats))
    application.add_handler(CommandHandler("viewgoals", view_goals))
    application.add_handler(add_goal_conv_handler)
    application.add_handler(edit_goal_conv_handler)
    application.add_handler(update_conv_handler)

    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()
