from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from datetime import datetime
import os
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import asyncio

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE')
SPREADSHEET_ID = os.getenv('GOOGLE_SHEET_ID')
ADMIN_ID = os.getenv('ADMIN_ID')
TIMEZONE = os.getenv('TIMEZONE')
if TIMEZONE is None or TIMEZONE == "" or TIMEZONE not in pytz.all_timezones:
    TIMEZONE = "UTC"
scheduler = BackgroundScheduler(timezone=pytz.timezone(TIMEZONE))
scheduler.start()

def get_sheet_service():
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE)
    return build('sheets', 'v4', credentials=credentials).spreadsheets()

def ensure_sheet_data(sheet, range):
    data = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range).execute().get('values', [])
    return data if data else [[]]

SELECT_NAME, SELECT_COLUMN, UPDATE_VALUE = range(3)

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        user_id = update.effective_user.id
        await update.message.reply_text(f"Your user ID is: {user_id}")
    else:
        await update.message.reply_text("This command can only be used in private chats to set up the bot.")
    return

async def update_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = get_sheet_service()
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="People!A1:A").execute()
    people_data = sheet.get('values', [])

    if not people_data:
        await update.message.reply_text("No names found in the People sheet. Please add names first.")
        return ConversationHandler.END

    names = [name[0] for name in people_data if len(name) > 0]

    keyboard = [[InlineKeyboardButton(name, callback_data=name)] for name in names]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the name:", reply_markup=reply_markup)
    return SELECT_NAME

async def select_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["name"] = query.data

    service = get_sheet_service()
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Daily Tracker!1:1").execute()
    headers = sheet.get('values', [[]])[0]

    if not headers:
        await query.message.reply_text("No columns found. Please add headers first.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(f"{header}", callback_data=header)] for header in headers[2:]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Select the column:", reply_markup=reply_markup)
    return SELECT_COLUMN

async def select_column(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["column"] = query.data

    service = get_sheet_service()
    today_date = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
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

    service = get_sheet_service()
    sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Daily Tracker!A1:Z").execute()
    data = sheet.get('values', [])
    headers = data[0]
    column_index = headers.index(column)
    today_date = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")

    row_index = next((i for i, row in enumerate(data) if len(row) > 1 and row[0] == today_date and row[1] == name), None)
    if row_index is None:
        new_row = [today_date, name] + [""] * (len(headers) - 2)
        data.append(new_row)
        row_index = len(data) - 1

    while len(data[row_index]) < len(headers):
        data[row_index].append("")

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
        
        today_date = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
        
        if not data or len(data) < 2:
            await update.message.reply_text("No entries found for today.")
            return

        headers = data[0]
        today_entries = [dict(zip(headers, row)) for row in data[1:] if len(row) > 0 and row[0] == today_date]
        
        if not today_entries:
            await update.message.reply_text("No entries found for today.")
            return

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
            service = get_sheet_service()
            sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="People!A1:A").execute()
            people_data = sheet.get('values', [])

            if not people_data:
                await update.message.reply_text("No names found. Please add names first.")
                return

            keyboard = [[InlineKeyboardButton(name[0], callback_data=f"weekly_{name[0]}")] for name in people_data]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Select a name to view weekly stats:", reply_markup=reply_markup)
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

async def view_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        name = ' '.join(context.args)
        if not name:
            service = get_sheet_service()
            sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="People!A1:A").execute()
            people_data = sheet.get('values', [])

            if not people_data:
                await update.message.reply_text("No names found. Please add names first.")
                return

            keyboard = [[InlineKeyboardButton(name[0], callback_data=f"viewgoals_{name[0]}")] for name in people_data]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Select a name to view goals:", reply_markup=reply_markup)
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

async def handle_weekly_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
   query = update.callback_query
   await query.answer()
   name = query.data.replace("weekly_", "")
   
   service = get_sheet_service()
   sheet = ensure_sheet_data(service, "Weekly Summary!A1:Z")

   stats = [row for row in sheet[1:] if row[1] == name]
   if not stats:
       await query.message.reply_text(f"No stats found for {name}.")
       return

   await query.message.reply_text(f"Weekly Stats for {name}:\n" + "\n".join([', '.join(row) for row in stats]))

async def handle_viewgoals_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
   query = update.callback_query
   await query.answer()
   name = query.data.replace("viewgoals_", "")
   
   service = get_sheet_service()
   sheet = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Goals!A1:Z").execute()
   data = sheet.get('values', [])

   if not data or len(data) < 2:
       await query.message.reply_text(f"No goals found for {name}.")
       return

   headers = data[0]
   goals = [dict(zip(headers, row)) for row in data[1:] if row[0] == name]

   if not goals:
       await query.message.reply_text(f"No goals found for {name}.")
       return

   response = f"Goals for {name}:\n"
   for goal in goals:
       response += "\n".join(f"{key}: {value}" for key, value in goal.items() if value)
       response += "\n---\n"

   await query.message.reply_text(response.strip())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
   await update.message.reply_text(
       "\U0001F44B Welcome to the Fitness Tracking Bot! \U0001F3CB\n\n"
       "Here to help you track your fitness journey effortlessly.\n"
       "Type /help to see the list of available commands!"
   )

SELECT_NAME, INPUT_UPDATES = range(2)

async def batch_update_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = get_sheet_service()
    sheet_data = service.values().get(spreadsheetId=SPREADSHEET_ID, range="People!A1:A").execute()
    people_data = sheet_data.get('values', [])

    if not people_data:
        await update.message.reply_text("No names found in the 'People' sheet. Please add names first.")
        return ConversationHandler.END

    names = [row[0] for row in people_data if len(row) > 0]
    keyboard = [[InlineKeyboardButton(name, callback_data=name)] for name in names]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the person you want to update:", reply_markup=reply_markup)
    return SELECT_NAME


async def batch_update_columns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["name"] = query.data

    service = get_sheet_service()
    sheet_response = service.values().get(spreadsheetId=SPREADSHEET_ID, range="Daily Tracker!A1:Z").execute()
    sheet_data = sheet_response.get('values', [])

    if not sheet_data or len(sheet_data) < 1:
        await query.message.reply_text("No data found in the tracker. Please add headers first.")
        return ConversationHandler.END

    headers = sheet_data[0]

    if len(headers) < 2:
        await query.message.reply_text("No valid headers found in the tracker. Please check your spreadsheet.")
        return ConversationHandler.END

    name = context.user_data["name"]
    today_date = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")

    rows = sheet_data[1:]
    row_index = next(
        (i for i, row in enumerate(rows, 1) if len(row) > 1 and row[0] == today_date and row[1] == name),
        None
    )

    if row_index is None:
        row_to_update = [today_date, name] + [""] * (len(headers) - 2)
        sheet_data.append(row_to_update)
    else:
        row_to_update = rows[row_index - 1]

    while len(row_to_update) < len(headers):
        row_to_update.append("")

    columns = headers[2:]
    template = "\n".join(
        [f"{column}: {row_to_update[headers.index(column)]}" for column in columns]
    )

    await query.message.reply_text(
        name + ": Here’s a template you can use to update your data. Copy it, add or edit the relevant values, and send it back."
    )

    await query.message.reply_text(template)
    context.user_data["sheet_data"] = sheet_data
    context.user_data["row_index"] = len(sheet_data) - 1 if row_index is None else row_index
    context.user_data["columns"] = columns
    return INPUT_UPDATES



async def batch_update_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        updates = update.message.text.split("\n")
        updates = {item.split(":", 1)[0].strip(): item.split(":", 1)[1].strip() for item in updates if ":" in item and item.split(":", 1)[1].strip()}

        sheet_data = context.user_data["sheet_data"]
        row_index = context.user_data["row_index"]
        headers = sheet_data[0]

        for column, value in updates.items():
            if column in headers:
                column_index = headers.index(column)
                sheet_data[row_index][column_index] = value

        service = get_sheet_service()
        service.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range="Daily Tracker!A1:Z",
            valueInputOption="RAW",
            body={"values": sheet_data}
        ).execute()

        await update.message.reply_text(f"Batch updates successfully saved for {context.user_data['name']}.")
    except Exception as e:
        await update.message.reply_text(f"Error processing batch update: {e}")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Update operation cancelled.")
    return ConversationHandler.END

def run_async(coroutine, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coroutine(*args, **kwargs))

def daily_reminder_wrapper(chat_id, context):
    try:
        run_async(daily_reminder, chat_id, context)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(daily_reminder(chat_id, context))
        finally:
            loop.close()

def water_reminder_wrapper(chat_id, context):
    try:
        run_async(water_reminder, chat_id, context)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(water_reminder(chat_id, context))
        finally:
            loop.close()

async def daily_reminder(chat_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Good evening! Don't forget to update your fitness tracker today. 🏋️‍♂️"
        )
    except Exception as e:
        print(f"Error in daily reminder: {e}")

async def water_reminder(chat_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Time to hydrate! Drink some water now. 🥤"
        )
    except Exception as e:
        print(f"Error in water reminder: {e}")

async def start_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    scheduler.add_job(
        daily_reminder_wrapper,
        CronTrigger(hour=19, minute=0, timezone=pytz.timezone(TIMEZONE)),
        id=f"daily_reminder_{chat_id}",
        replace_existing=True,
        kwargs={"chat_id": chat_id, "context": context},
    )

    for hour in range(7, 24):  # From 7 AM to 11 PM
        scheduler.add_job(
            water_reminder_wrapper,
            CronTrigger(hour=hour, minute=0, timezone=pytz.timezone(TIMEZONE)),
            id=f"water_reminder_{chat_id}_{hour}",
            replace_existing=True,
            kwargs={"chat_id": chat_id, "context": context},
        )


    await update.message.reply_text("Reminders started! You'll get daily reminders at 7:00 PM and hourly water reminders.")

async def stop_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    try:
        scheduler.remove_job(f"daily_reminder_{chat_id}")
    except Exception:
        pass

    for hour in range(7, 24):
        try:
            scheduler.remove_job(f"water_reminder_{chat_id}_{hour}")
        except Exception:
            pass

    try:
        await update.message.reply_text("Reminders stopped!")
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            print("Event loop was closed unexpectedly, retrying in a new loop.")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(update.message.reply_text("Reminders stopped!"))

async def check_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    active_reminders = []
    for job in scheduler.get_jobs():
        if str(chat_id) in job.id:
            next_run = job.next_run_time
            if next_run:
                next_run = next_run.strftime("%Y-%m-%d %H:%M:%S")
                if "water_reminder" in job.id:
                    reminder_type = "Water reminder"
                elif "daily_reminder" in job.id:
                    reminder_type = "Daily fitness tracker reminder"
                active_reminders.append(f"{reminder_type}: Next run at {next_run}")
    
    if active_reminders:
        message = "Active reminders:\n" + "\n".join(active_reminders)
    else:
        message = "No active reminders found. Use /startreminders to set them up."
        
    await update.message.reply_text(message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
   await update.message.reply_text(
       """
Here are the available commands:

General:
/start - Start the bot and get a welcome message
/help - Show this help message

Spreadsheet commands:
/addnewperson - Add a new person to the fitness tracking sheet
/addcolumns - Add a new column to the sheet

Data tracking:
/viewtoday - View today's stats for all people
/update - Update today's data per column for a person
/batchupdate - Update today's data for a person in batch
/weekly - View weekly stats for a person

Goals:
/viewgoals - View goals for a person
/addgoal - Add a new goal for a person
/editgoal - Edit an existing goal for a person

Reminders Management:
/startreminders - Daily reminders once to update the sheet and hourly water reminders
/stopreminders - Stop reminders
/checkreminders - Check active reminders

Admin commands:
/checktime - Check the current time in your set timezone
/getuserid - Get your user ID
/cancel - Cancel current operation

You may need to reply to bot's messages explicitly in order to reply to the bot, depending on your group settings, \
as the bot may not be able to read messages without being replied to.
"""
   )

async def check_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_time = datetime.now(pytz.timezone(TIMEZONE))
    await update.message.reply_text(
        f"Current time in {TIMEZONE}: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

def require_auth():
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            
            if update.effective_chat.type == "private":
                if str(user_id) != str(ADMIN_ID):
                    await update.message.reply_text("You are not authorized to use this bot.")
                    return ConversationHandler.END if isinstance(func, ConversationHandler) else None
            else:
                if str(chat_id) != str(ADMIN_ID):
                    await update.message.reply_text("This bot is not authorized in this group.")
                    return ConversationHandler.END if isinstance(func, ConversationHandler) else None

            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Apply decorator to all command handlers
    update_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("update", require_auth()(update_start))],
        states={
            SELECT_NAME: [CallbackQueryHandler(select_name)],
            SELECT_COLUMN: [CallbackQueryHandler(select_column)],
            UPDATE_VALUE: [CommandHandler("cancel", require_auth()(cancel)), 
                         MessageHandler(filters.TEXT & ~filters.COMMAND, update_value)],
        },
        fallbacks=[CommandHandler("cancel", require_auth()(cancel))],
    )

    add_goal_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addgoal", require_auth()(add_goal_start))],
        states={
            SELECT_NAME_GOALS: [CallbackQueryHandler(add_goal_name)],
            ADD_GOAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal_description)],
            ADD_GOAL_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_goal_description)],
        },
        fallbacks=[CommandHandler("cancel", require_auth()(cancel))],
    )

    edit_goal_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("editgoal", require_auth()(edit_goal_start))],
        states={
            SELECT_GOAL_TO_EDIT: [CallbackQueryHandler(select_goal_to_edit)],
            EDIT_GOAL_DESCRIPTION: [
                CallbackQueryHandler(edit_goal_description),
                MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_edit_goal),
            ],
        },
        fallbacks=[CommandHandler("cancel", require_auth()(cancel))],
    )

    batch_update_handler = ConversationHandler(
        entry_points=[CommandHandler("batchupdate", require_auth()(batch_update_start))],
        states={
            SELECT_NAME: [CallbackQueryHandler(batch_update_columns)],
            INPUT_UPDATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, batch_update_process)],
        },
        fallbacks=[CommandHandler("cancel", require_auth()(cancel))],
    )

    application.add_handler(CommandHandler("start", require_auth()(start)))
    application.add_handler(CommandHandler("help", require_auth()(help_command)))
    application.add_handler(CommandHandler("addnewperson", require_auth()(add_new_person)))
    application.add_handler(CommandHandler("viewtoday", require_auth()(view_today)))
    application.add_handler(CommandHandler("addcolumns", require_auth()(add_columns)))
    application.add_handler(CommandHandler("weekly", require_auth()(weekly_stats)))
    application.add_handler(CommandHandler("viewgoals", require_auth()(view_goals)))
    application.add_handler(CommandHandler("startreminders", require_auth()(start_reminders)))
    application.add_handler(CommandHandler("stopreminders", require_auth()(stop_reminders)))
    application.add_handler(CommandHandler("checktime", require_auth()(check_time)))
    application.add_handler(CommandHandler("checkreminders", require_auth()(check_reminders)))
    application.add_handler(batch_update_handler)
    application.add_handler(add_goal_conv_handler)
    application.add_handler(edit_goal_conv_handler)
    application.add_handler(update_conv_handler)
    application.add_handler(CallbackQueryHandler(handle_weekly_callback, pattern='^weekly_'))
    application.add_handler(CallbackQueryHandler(handle_viewgoals_callback, pattern='^viewgoals_'))

    application.add_handler(CommandHandler("getuserid", get_user_id))

    application.run_polling()

if __name__ == "__main__":
   main()