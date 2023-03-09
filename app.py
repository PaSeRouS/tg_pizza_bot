import os

import redis
from flask import Flask, request

from fb_functions import send_menu, send_message, send_cart_menu
from moltin_api import add_product_to_cart, get_product_by_id
from moltin_api import remove_product_from_cart

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


def handle_start(sender_id, message):
    send_menu(sender_id, message)
    return "MENU"


def handle_menu(sender_id, message):
    if message['title'] == 'Добавить в корзину':
        client_id = os.environ["CLIENT_ID"]
        client_secret = os.environ["CLIENT_SECRET"]

        cart_id = f"facebookid_{sender_id}"
        add_product_to_cart(
            cart_id,
            message['value'],
            1,
            client_id,
            client_secret
        )

        pizza = get_product_by_id(message['value'], client_id, client_secret)
        pizza_name = pizza['data']['name']
        message_text = f"В корзину добавлена пицца {pizza_name}"
        send_message(sender_id, message_text)
    elif message['value'] == 'cart':
        send_cart_menu(sender_id, message)
        return 'CART'
    else:
        send_menu(sender_id, message)
    
    return "MENU"


def handle_cart(sender_id, message):
    client_id = os.environ["CLIENT_ID"]
    client_secret = os.environ["CLIENT_SECRET"]

    cart_id = f"facebookid_{sender_id}"

    if message['value'] == 'return':
        send_menu(sender_id, message)
        return 'MENU'
    elif message['title'] == 'Добавить ещё одну':
        add_product_to_cart(
            cart_id,
            message['value'],
            1,
            client_id,
            client_secret
        )

        pizza = get_product_by_id(message['value'], client_id, client_secret)
        pizza_name = pizza['data']['name']
        message_text = f"В корзину добавлена пицца {pizza_name}"
        send_message(sender_id, message_text)
    elif message['title'] == 'Убрать из корзины':
        remove_product_from_cart(
            cart_id,
            message['value'],
            client_id,
            client_secret
        )

        message_text = "Пицца удалена из корзины"
        send_message(sender_id, message_text)

    send_cart_menu(sender_id, message)

    return 'CART'


def handle_users_reply(sender_id, message):
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
        'MENU': handle_menu,
        'CART': handle_cart,
    }

    db_key = f"facebookid_{sender_id}"
    recorded_state = db.get(db_key)
    
    if not recorded_state or recorded_state.decode("utf-8") not in states_functions.keys():
        user_state = "START"
    else:
        user_state = recorded_state.decode("utf-8")
    
    state_handler = states_functions[user_state]
    next_state = state_handler(sender_id, message)
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
                    message = {
                        'type':  'message',
                        'title': 'Сообщение',
                        'value': messaging_event["message"]["text"]
                    }
                elif messaging_event.get("postback"):
                    message = {
                        'type':  'postback',
                        'title': messaging_event["postback"]["title"],
                        'value': messaging_event["postback"]["payload"]
                    }
                    
                if message:
                    handle_users_reply(sender_id, message)
    return "ok", 200


if __name__ == '__main__':
    app.run(debug=True)
