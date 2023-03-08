import os

import redis
import requests
from flask import Flask, request

from moltin_api import get_image_url, get_products_by_category_id
from moltin_api import get_all_categories

app = Flask(__name__)
FACEBOOK_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]

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


def send_menu(recipient_id, message_text):
    params = {"access_token": FACEBOOK_TOKEN}
    headers = {"Content-Type": "application/json"}

    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": get_elements_for_generic(message_text)
                }
            }
        }
    }

    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def get_elements_for_generic(category_name):
    # В сообщении кнопки выводятся по три штуки в сообщении и только на 10 слайдах
    elements = []
    buttons = []

    client_id = os.environ["CLIENT_ID"]
    client_secret = os.environ["CLIENT_SECRET"]

    categories = get_all_categories(client_id, client_secret)

    # Основное меню пиццерии
    element = {
        "title": "Меню",
        "image_url": "https://img.freepik.com/premium-vector/pizza-logo-template-suitable-for-restaurant-and-cafe-logo_607277-267.jpg",
        "subtitle": "Здесь выможете выбрать один из вариантов",
        "buttons": [
            {
                "type": "postback",
                "title": "Корзина",
                "payload": "cart",
            },
            {
                "type": "postback",
                "title": "Акции",
                "payload": "promotion",
            },
            {
                "type": "postback",
                "title": "Сделать заказ",
                "payload": "make_order",
            }
        ]
    }

    elements.append(element)

    for category in categories['data']:
        if category['name'] == category_name:
            category_id = category['id']
            products = get_products_by_category_id(client_id, client_secret, category_id)
            for product in products["data"]:
                product_name = product["name"]
                price = product["price"][0]["amount"]
                title = f"{product_name} ({price} р.)"

                image_id = product["relationships"]["main_image"]["data"]["id"]
                image_url = get_image_url(image_id, client_id, client_secret)

                element = {
                    "title": title,
                    "image_url": image_url,
                    "subtitle": product["description"],
                    "buttons": [
                        {
                            "type": "postback",
                            "title": "Добавить в корзину",
                            "payload": product["id"],
                        }
                    ]
                }

                elements.append(element)
        else:
            button = {
                "type": "postback",
                "title": category['description'],
                "payload": category['name'],
            }

            buttons.append(button)

    element = {
        "title": "Не нашли нужную пиццу?",
        "image_url": "https://primepizza.ru/uploads/position/large_0c07c6fd5c4dcadddaf4a2f1a2c218760b20c396.jpg",
        "subtitle": "Остальные пиццы можно посмотреть в одной из категорий",
        "buttons": buttons
    }

    elements.append(element)

    return elements


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
