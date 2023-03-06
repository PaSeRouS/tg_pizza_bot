import os

import requests
from flask import Flask, request

from moltin_api import get_products

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


@app.route('/', methods=['POST'])
def webhook():
    """
    Основной вебхук, на который будут приходить сообщения от Facebook.
    """
    data = request.get_json()
    # print(data)
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    recipient_id = messaging_event["recipient"]["id"]
                    send_menu(sender_id)
    return "ok", 200


def send_message(recipient_id, message_text):
    params = {"access_token": FACEBOOK_TOKEN}
    headers = {"Content-Type": "application/json"}
    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    }
    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def send_menu(recipient_id):
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
                    "elements": get_elements_for_generic()
                }
            }
        }
    }

    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def get_elements_for_generic():
    # В сообщении кнопки выводятся по три штуки в сообщении и только на 10 слайдах
    elements = []
    buttons = []
    index = 0

    products = get_products(os.environ["CLIENT_ID"], os.environ["CLIENT_SECRET"])

    for product_name, product_id in products.items():
        if index % 3 == 0 and index != 0 and index < 30:
            element = {
                "title": "Меню пиццерии",
                "buttons": buttons
            }

            elements.append(element)

            buttons = []

        index += 1

        button = {
            "type": "postback",
            "title": product_name,
            "payload": product_id,
        }

        buttons.append(button)

    if index < 30:
        element = {
            "title": "Меню пиццерии",
            "buttons": buttons
        }

        elements.append(element)

    return elements


if __name__ == '__main__':
    app.run(debug=True)
