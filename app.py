import os

import redis
from flask import Flask, request

from fb_functions import send_menu

app = Flask(__name__)

@app.route('/', methods=['GET'])
def verify():
    """
    При верификации вебхука у Facebook он отправит запрос на этот адрес. На него нужно ответить VERIFY_TOKEN.
    """
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


def handle_start(sender_id, message_text):
    send_menu(sender_id, message_text)
    return "START"


def handle_users_reply(sender_id, message_text):
    db_password = os.environ["REDIS_PASSWORD"]
    db_host = os.environ['REDIS_HOST']
    db_port = os.environ['REDIS_PORT']

    db = get_database_connection(
        db_password,
        db_host,
        db_port
    )

    states_functions = {
        'START': handle_start,
    }

    db_key = f"facebookid_{sender_id}"
    recorded_state = db.get(db_key)
    
    if not recorded_state or recorded_state.decode("utf-8") not in states_functions.keys():
        user_state = "START"
    else:
        user_state = recorded_state.decode("utf-8")
    
    state_handler = states_functions[user_state]
    next_state = state_handler(sender_id, message_text)
    db.set(db_key, next_state)


def get_database_connection(password, host, port):
    database = redis.Redis(host=host, port=port, password=password)
    return database


@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                sender_id = messaging_event["sender"]["id"]
                recipient_id = messaging_event["recipient"]["id"]

                if messaging_event.get("message"):
                    message_text = 'main_pizzas'
                elif messaging_event.get("postback"):
                    message_text = messaging_event["postback"]["payload"]
                    
                if message_text:
                    handle_users_reply(sender_id, message_text)
    return "ok", 200


if __name__ == '__main__':
    app.run(debug=True)
