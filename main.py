from threading import Thread
from time import sleep
import os
import logging
import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pytz
import schedule
import firebase_admin
from firebase_admin import credentials, db
from firebase_admin.exceptions import FirebaseError
from dotenv import load_dotenv
from utils import generate_assignment_reminder_message, generate_get_assignments_message

load_dotenv()
cred_obj = credentials.Certificate({
    "type": "service_account",
    "project_id": os.environ['PROJECT_ID'],
    "private_key": os.environ['PRIVATE_KEY'].replace(r'\n', '\n'),
    "private_key_id": os.environ['PRIVATE_KEY_ID'],
    "client_email": os.environ['CLIENT_EMAIL'],
    "client_id": os.environ['CLIENT_ID'],
    "auth_uri": os.environ['AUTH_URI'],
    "token_uri": os.environ['TOKEN_URI'],
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
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
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")  # type: ignore


@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Welcome message when user starts the bot in private chat.

    Args:
      message (_type_): _description_
    """
    if (message.chat.type == "private"):
        bot.reply_to(message, """Welcome to the Assigments Bot!
                     I'm here to help admins manage assignments. 
                     Please add me to a group and make me an admin to get started.""",
                     message_thread_id=message.message_thread_id)


@bot.message_handler(commands=['help'])
def send_help(message):
    """Help message when user requests for help.

    Args:
      message (_type_): _description_
    """
    if (message.chat.type == "private"):
        bot.reply_to(
            message, "I'm here to help admins manage assignments. Please add me to a group to get started.",
            message_thread_id=message.message_thread_id)
    elif (message.chat.type == "group"):
        bot.reply_to(message, "I'm here to help admins manage assignments.",
                     message_thread_id=message.message_thread_id)


@bot.message_handler(commands=['addassignment'])
def create_assignment(message):
    """Set assignment message when admin user requests to set assignment.

    Args:
      message (_type_): _description_
    """
    # must be in a group to set assignment
    if (message.chat.type == "private"):
        bot.send_message(
            message.chat.id, "Please add me to a group to get started.",
            message_thread_id=message.message_thread_id)
        return

    # must be an admin of the group
    admin_ids = [
        admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]
    if (message.from_user.id not in admin_ids):
        bot.reply_to(message, "You must be an admin to set assignments.",
                     message_thread_id=message.message_thread_id)
    elif (bot.get_me().id not in admin_ids):
        bot.reply_to(message, "Please make me an admin to set assignments.",
                     message_thread_id=message.message_thread_id)
        return
    assignment_details = message.text.replace(
        "/addassignment", "").strip().split(":")
    print(assignment_details)

    if (len(assignment_details) < 5):
        bot.reply_to(message,
                     """Please write the assignment details in the following format:\n\n
*Course Code*: __course code__\n
*Title*: __assignment title__\n
*Deadline*: dd/mm/yy\n
*Description*: __assignment description__""",
                     parse_mode="Markdown")
        return
    course_code = assignment_details[1].splitlines()[0].strip()
    title = assignment_details[2].splitlines()[0].strip()
    deadline = assignment_details[3].splitlines()[0].strip()
    description = assignment_details[4].strip()
    print(course_code, title, deadline, description, sep="\n")
    # validate deadline
    try:
        date = datetime.datetime.strptime(deadline, '%d/%m/%y')
        if (date.astimezone(LAGOS_TIME) < datetime.datetime.now(LAGOS_TIME)):
            bot.reply_to(
                message, "Please renter assignment with a future deadline.",
                message_thread_id=message.message_thread_id)
            return
    except ValueError:
        bot.reply_to(
            message, "Please renter assignment with the deadline in the right format: dd/mm/yy",
            message_thread_id=message.message_thread_id)
        return

    assignment_details = {
        "course_code": course_code,
        "title": title,
        "deadline": deadline,
        "description": description,
        "chat_id": message.chat.id,
    }

    logging.info(" creating assignment\n%s", assignment_details)
    try:
        assignments_ref.push().set(assignment_details)
        logging.info(
            'inserted assignment with title: %s', assignment_details["title"])
        bot.reply_to(message, "Assignment has been created successfully.",
                     message_thread_id=message.message_thread_id)
    except FirebaseError as e:
        bot.reply_to(
            message, "An error occurred while setting assignment. Please try again later.",
            message_thread_id=message.message_thread_id)
        logging.error("%s", e)


@bot.message_handler(commands=['getassignments'], func=lambda message: message.chat.type in ["supergroup", "group"])
def list_assignments(message):
    # HACK HANDLE PAGINATION
    try:
        assignments_list = assignments_ref.order_by_child(
            "chat_id").equal_to(message.chat.id).get()
    except FirebaseError as e:
        logging.error(e)
        bot.reply_to(
            message, "An error occurred while fetching assignments. Please try again later.",
            message_thread_id=message.message_thread_id)
        return
    if (assignments_list is not None and len(assignments_list) > 0):
        assignments = list(assignments_list.values())  # type:ignore
        response_message = generate_get_assignments_message(assignments)
        bot.reply_to(message, response_message)
    else:
        bot.send_message(message.chat.id, "No assignments found.",
                         message_thread_id=message.message_thread_id)


@bot.message_handler(commands=['manageassignments'], func=lambda message: message.chat.type in ["supergroup", "group"])
def manage_assignments(message):
    """_summary_

    Args:
      message (_type_): _description_
    """

    if (message.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]):
        bot.reply_to(message, "You must be an admin to edit assignments.",
                     message_thread_id=message.message_thread_id)
        return
    try:

        assignments_list = assignments_ref.order_by_child(
            "chat_id").equal_to(message.chat.id).get()

        if (assignments_list is not None and len(assignments_list) > 0):
            bot.reply_to(
                message, f"Found {len(assignments_list)} assignments. Listing all.",
                message_thread_id=message.message_thread_id)

            for assignment_id in assignments_list:
                keyboard = InlineKeyboardMarkup()
                keyboard.row(InlineKeyboardButton('Edit', callback_data=f'EDIT_{assignment_id}'),
                             InlineKeyboardButton('Delete', callback_data=f'DELETE_{assignment_id}'))
                keyboard.row(InlineKeyboardButton(
                    'View', callback_data=f'VIEW_{assignment_id}'))

                bot.reply_to(
                    message, f"""
Course Code: {assignments_list[assignment_id]['course_code']}\n
Title: {assignments_list[assignment_id]['title'] }\n
Deadline: {assignments_list[assignment_id]['deadline']}\n
Description: {assignments_list[assignment_id]['description'][:50]}
                    """, reply_markup=keyboard, message_thread_id=message.message_thread_id)

        else:
            bot.send_message(message.chat.id, "No assignments found.",
                             message_thread_id=message.message_thread_id)

    except FirebaseError as e:
        bot.reply_to(
            message, "An error occurred while fetching assignments. Please try again later.",
            message_thread_id=message.message_thread_id)

        logging.error("An error occurred while fetching assignments. %s", e)

    except telebot.apihelper.ApiTelegramException as e:
        logging.error(
            "An error occurred with telegram while assignments. %s", e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('VIEW_'))
def view_assignment(call):
    if (call.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(call.message.chat.id)]):
        return
    assignment_id = call.data[5:]
    assignments_list = assignments_ref.get()
    bot.send_message(
        call.message.chat.id, f"""
Course Code: {assignments_list[assignment_id]['course_code']}\n
Title: {assignments_list[assignment_id]['title'] }\n
Deadline: {assignments_list[assignment_id]['deadline']}\n
Description: {assignments_list[assignment_id]['description']}
    """, message_thread_id=call.message.message_thread_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('EDIT_'))
def edit_assignment(call):
    if (call.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(call.message.chat.id)]):
        return
    assignment_id = call.data[5:]
    message = bot.send_message(call.message.chat.id, """
Please reply to this message with the new assignment details in the following format:\n\n
*Course Code*: __course code__\n
*Title*: __assignment title__\n
*Deadline*: dd/mm/yy\n
*Description*: __assignment description__""", parse_mode="Markdown",
                               message_thread_id=call.message.message_thread_id)
    bot.register_for_reply(message, edit_assignment_reply,
                           assignment_id=assignment_id, user_id=call.from_user.id)


def edit_assignment_reply(message, assignment_id, user_id):
    if (message.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]):
        return
    if (user_id != message.from_user.id):
        bot.reply_to(message, "It seems you did not intiate this action.",
                     message_thread_id=message.message_thread_id)
        return

    assignment_details = message.text.replace(
        "/editassignment", "").strip().split(":")
    if (len(assignment_details) < 4):
        bot.reply_to(
            message, "Please enter the assignment details in the right format. All fields must be rentered for update. Please try again.",
            message_thread_id=message.message_thread_id)

    course_code = assignment_details[1].splitlines()[0].strip()
    title = assignment_details[2].splitlines()[0].strip()
    deadline = assignment_details[3].splitlines()[0].strip()
    description = assignment_details[4].strip()

    try:
        assignments_ref.child(assignment_id).update({
            "course_code": course_code,
            "title": title,
            "deadline": deadline,
            "description": description
        })

    except FirebaseError as e:
        bot.reply_to(
            message, "An error occurred while updating assignment. Please try again later.",
            message_thread_id=message.message_thread_id)
        logging.error(
            "An error occurred while updating assignment an assignment. %s", e)
    bot.reply_to(message, "Assignment has been updated successfully.",
                 message_thread_id=message.message_thread_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('DELETE_'))
def delete_assignment(call):
    if (call.from_user.id not in [admin.user.id for admin in bot.get_chat_administrators(call.message.chat.id)]):
        return
    assignment_id = call.data[7:]
    try:
        assignments_ref.child(assignment_id).delete()
        logging.info('deleted assignment with id: %s', assignment_id)
        bot.send_message(call.message.chat.id,
                         "Assignment has been deleted successfully.", message_thread_id=call.message.message_thread_id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except FirebaseError as e:
        bot.reply_to(
            call.message, "An error occurred while deleting assignment. Please try again later.",
            message_thread_id=call.message.message_thread_id)
        logging.error("An error occurred while deleting assignment. %s", e)


def send_assignment_reminders():
    logging.info('starting reminders')
    assignments_list = assignments_ref.get()
    assignment_dict = dict()
    for assignment_id in assignments_list:
        if datetime.datetime.strptime(assignments_list[assignment_id]['deadline'],'%d/%m/%y').astimezone(LAGOS_TIME) < datetime.datetime.now(LAGOS_TIME):
            assignments_ref.child(assignment_id).delete()
        #group assignments by chat id  
        if (assignments_list[assignment_id]['chat_id'] not in assignment_dict.keys()):
            assignment_dict[assignments_list[assignment_id]['chat_id']] = []
            assignment_dict[assignments_list[assignment_id]
                            ['chat_id']].append(assignments_list[assignment_id])
        else:
            assignment_dict[assignments_list[assignment_id]
                            ['chat_id']].append(assignments_list[assignment_id])
    for chat_id in assignment_dict:
        assignments = assignment_dict[chat_id]
        response_message = generate_assignment_reminder_message(assignments)
        try:
            bot.send_message(chat_id, response_message)
        except telebot.apihelper.ApiTelegramException as e:
            logging.error("An error occurred with telegram while sending reminders. to chat with id %s" 
                          "Exception: %s", str(chat_id), e)
            continue
        



schedule.every().day.at("09:12", LAGOS_TIME).do(  # type: ignore
    send_assignment_reminders)


def schedule_checker():
    while True:
        schedule.run_pending()
        sleep(1)


Thread(target=schedule_checker).start()

bot.infinity_polling(logger_level=logging.INFO)
