from threading import Thread
from time import sleep
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import logging
import pytz
import datetime
import schedule
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

load_dotenv()
cred_obj = credentials.Certificate({
  "type":"service_account",
  "project_id": os.environ['PROJECT_ID'],
  "private_key": os.environ['PRIVATE_KEY'].replace(r'\n', '\n'),
  "private_key_id" : os.environ['PRIVATE_KEY_ID'],
  "client_email":os.environ['CLIENT_EMAIL'],
  "client_id": os.environ['CLIENT_ID'],
  "auth_uri": os.environ['AUTH_URI'],
  "token_uri": os.environ['TOKEN_URI'],
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",\
  "client_x509_cert_url": os.environ['CLIENT_x509_CERT_URL'],
  "universe_domain": "googleapis.com",
})

firebase_admin.initialize_app(cred_obj, {
    'databaseURL': os.environ['DATABASE_URL']
})
assignments_ref = db.reference('/public/assignments')

LAGOS_TIME = pytz.timezone('Africa/Lagos')
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ['BOT_TOKEN']
bot = telebot.TeleBot(BOT_TOKEN)  # type: ignore

ASSIGNMENTS_LIST = None

# HACK doesn't work 🤧
@bot.message_handler(func=lambda message: True, content_types=['new_chat_members'])
def welcome_message_when_added(message):
    """Message to be sent when bot is added to a group.

    Args:
        message (_type_): _description_
    """
    new_members = message.new_chat_members
    chat_id = message.chat.id
    for user in new_members:
        # Check if the new member is your bot
        if user.username == "YOUR_BOT_USERNAME":
            bot.send_message(
                chat_id, "Thank you for adding me to this group! I'm here to help admins manage assignments.")


@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Welcome message when user starts the bot in private chat.

    Args:
        message (_type_): _description_
    """
    bot.reply_to(message, "Welcome to the Assigments Bot! I'm here to help admins manage assignments. Please add me to a group and make me an admin to get started.")


@bot.message_handler(commands=['help'])
def send_help(message):
    """Help message when user requests for help.

    Args:
        message (_type_): _description_
    """
    if (message.chat.type == "private"):
        bot.reply_to(
            message, "I'm here to help admins manage assignments. Please add me to a group to get started.")
    elif (message.chat.type == "group"):
        bot.reply_to(message, "I'm here to help admins manage assignments.")


@bot.message_handler(commands=['addassignment'])
def create_assignment(message):
    """Set assignment message when user requests to set assignment.

    Args:
        message (_type_): _description_
    """
    # must be in a group to set assignment
    if (message.chat.type != "group"):
        bot.send_message(
            message.chat.id, "Please add me to a group to get started.")
        return
    # must be an admin of the group
    admin_ids = [
        admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]
    if (message.from_user.id not in admin_ids):
        bot.reply_to(message, "You must be an admin to set assignments.")
        return
    message_bot = bot.send_message(message.chat.id, """
Please reply to this message with the assignment details in the following format:\n\n
*Course Code*: __course code__
*Title*: __assignment title__
*Deadline*: dd/mm/yy
*Description*: __assignment description__
\n
*Please enter values in the right order on separate lines.*
""", parse_mode="Markdown")
    bot.register_for_reply(
        message_bot, create_assignment_reply, user_id=message.from_user.id)


def create_assignment_reply(message, user_id):
    """Create assignment when user replies to bot's message.
    Args:
        message (_type_): _description_
    """
    if (message.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]):
        return

    if (user_id != message.from_user.id):
        bot.reply_to(message, "It seems you did not intiate this action.")
        return
    assignment_details = message.text.splitlines()
    logging.info(assignment_details)
    if ((len(assignment_details) != 5)):
        bot_message = bot.reply_to(message, "Please reply to this message with the assignment details in the following format:\n\n*Course Code*: __course code__\n*Title*: __assignment title__\n*Deadline*: dd/mm/yy\n*Description*: __assignment description__", parse_mode="Markdown")
        bot.register_for_reply(
            bot_message, create_assignment_reply, user_id=message.from_user.id)
        return

    course_code = assignment_details[0].split(":")[1].strip()
    title = assignment_details[1].split(":")[1].strip()
    deadline = assignment_details[2].split(":")[1].strip()
    description = assignment_details[3].split(":")[1].strip()

    # validate deadline format
    try:
        datetime.datetime.strptime(deadline, '%d/%m/%y')
    except ValueError:
        bot_message = bot.reply_to(
            message, "Please renter assignment by replying to this message with the deadline in the right format: dd/mm/yy")
        bot.register_for_reply(
            bot_message, create_assignment_reply, user_id=message.from_user.id)
        return

    assignment_details = {
        "course_code": course_code,
        "title": title,
        "deadline": deadline,
        "description": description,
        "chat_id": message.chat.id,
    }
    logging.info(assignment_details)
    try:
        assignments_ref.push().set(assignment_details)
        logging.info(
            f'inserted assignment with title {assignment_details["title"]}')
        bot.reply_to(message, "Assignment has been created successfully.")
    except Exception as e:
        bot.reply_to(
            message, "An error occured while setting assignment. Please try again later.")
        logging.error(e)


@bot.message_handler(commands=['getassignments'], func=lambda message: message.chat.type == "group")
def list_assignments(message):
    if (message.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]):
        bot.reply_to(message, "You must be an admin to list assignments.")
        return
    # HACK HANDLE PAGINATION
    ASSIGNMENTS_LIST = assignments_ref.get()
    if (len(ASSIGNMENTS_LIST) > 0):
        bot.reply_to(
            message, f"Found {len(ASSIGNMENTS_LIST)} assignments. Listing all.")
        for assignment_id in ASSIGNMENTS_LIST:
            keyboard = InlineKeyboardMarkup()
            keyboard.row(InlineKeyboardButton('Edit', callback_data=f'EDIT_{assignment_id}'),
                         InlineKeyboardButton('Delete', callback_data=f'DELETE_{assignment_id}'))
            keyboard.row(InlineKeyboardButton(
                'View', callback_data=f'VIEW_{assignment_id}'))
            bot.reply_to(
                message, f"Course Code: {ASSIGNMENTS_LIST[assignment_id]['course_code']}\n Title: {ASSIGNMENTS_LIST[assignment_id]['title'] }\n Deadline: {ASSIGNMENTS_LIST[assignment_id]['deadline']}\n Description: {ASSIGNMENTS_LIST[assignment_id]['description'][:50]}", reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, "No assignments found.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('VIEW_'))
def view_assignment(call):
    global ASSIGNMENTS_LIST
    if (call.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(call.message.chat.id)]):
        # just ignore none admin users
        return
    assignment_id = call.data[5:]
    if (ASSIGNMENTS_LIST is None):
        ASSIGNMENTS_LIST = assignments_ref.get()
    print(ASSIGNMENTS_LIST)
    bot.reply_to(
        call.message, f"Course Code: {ASSIGNMENTS_LIST[assignment_id]['course_code']}\n Title: {ASSIGNMENTS_LIST[assignment_id]['title'] }\n Deadline: {ASSIGNMENTS_LIST[assignment_id]['deadline']}\n Description: {ASSIGNMENTS_LIST[assignment_id]['description']}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('EDIT_'))
def edit_assignment(call):
    if (call.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(call.message.chat.id)]):
        # maybe just ignore?
        return
    assignment_id = call.data[5:]
    message = bot.send_message(call.message.chat.id, "Please reply to this message with the new assignment details in the following format:\n\n*Course Code*: __course code__\n*Title*: __assignment title__\n*Deadline*: dd/mm/yy\n*Description*: __assignment description__", parse_mode="Markdown")
    bot.register_for_reply(message, edit_assignment_reply,
                           assignment_id=assignment_id, user_id=call.from_user.id)


def edit_assignment_reply(message, assignment_id, user_id):
    if (message.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]):
        return
    if (user_id != message.from_user.id):
        bot.reply_to(message, "It seems you did not intiate this action.")
        return

    assignment_details = message.text.splitlines()
    if (len(assignment_details) != 4):
        bot.reply_to(
            message, "Please enter the assignment details in the right format. All fields must be rentered for update. Please try again.")
    course_code = assignment_details[0].split(":")[1].strip()
    title = assignment_details[1].split(":")[1].strip()
    deadline = assignment_details[2].split(":")[1].strip()
    description = assignment_details[3].split(":")[1].strip()

    assignments_ref.child(assignment_id).update({
        "course_code": course_code,
        "title": title,
        "deadline": deadline,
        "description": description
    })
    bot.reply_to(message, "Assignment has been updated successfully.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('DELETE_'))
def delete_assignment(call):
    global ASSIGNMENTS_LIST
    if (call.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(call.message.chat.id)]):
        # maybe just ignore?
        return
    assignment_id = call.data[7:]
    assignments_ref.child(assignment_id).delete()
    ASSIGNMENTS_LIST = assignments_ref.get()
    bot.reply_to(call.message, "Assignment has been deleted successfully.")
    bot.delete_message(call.message.chat.id, call.message.message_id)


def send_assignment_reminders():
    logging.info('starting reminders')
    global ASSIGNMENTS_LIST
    if (ASSIGNMENTS_LIST is None):
        ASSIGNMENTS_LIST = assignments_ref.get()
    for assignment in ASSIGNMENTS_LIST:
        # filter out/delete expired assigments
        # calculate time left for assignment and send notification
        assignment_deadline = datetime.datetime.strptime(
            ASSIGNMENTS_LIST[assignment]['deadline'], '%d/%m/%y').astimezone(LAGOS_TIME)
        current_time = datetime.datetime.now(LAGOS_TIME)
        time_left = assignment_deadline - current_time
        days = time_left.days
        hours = time_left.seconds//3600
        if (assignment_deadline < current_time):
          try:
            bot.send_message(ASSIGNMENTS_LIST[assignment]['chat_id'],
                             f"Assignment with title {ASSIGNMENTS_LIST[assignment]['title']} is overdue by {hours} hours. It has been deleted.")
            assignments_ref.child(assignment).delete()
            ASSIGNMENTS_LIST = assignments_ref.get()
          except Exception as e:
              logging.error(e)
          continue
        if (days == 0):
          try:
            bot.send_message(ASSIGNMENTS_LIST[assignment]['chat_id'],
                             f"Assignment with title {ASSIGNMENTS_LIST[assignment]['title']} is due in {hours} hours. Please submit on time. ⌛")
            logging.info(f"sent reminder for assignment with title {ASSIGNMENTS_LIST[assignment]['title']}")
          except Exception as e:
              logging.error(e)
        else:
          try:
            bot.send_message(ASSIGNMENTS_LIST[assignment]['chat_id'],
                             f"Assignment with {ASSIGNMENTS_LIST[assignment]['title']} is due in {days} days. Please submit on timee. ⌛")
            logging.info(f"sent reminder for assignment with title {ASSIGNMENTS_LIST[assignment]['title']}")
          except Exception as e:
              logging.error(e)

schedule.every().day.at("09:10",LAGOS_TIME).do(send_assignment_reminders) #type: ignore
def schedule_checker():
  while True:
    schedule.run_pending()
    sleep(1)
    
Thread(target=schedule_checker).start()

bot.infinity_polling(logger_level=logging.INFO)
