import os

import requests
from flask import Flask, request

from moltin_api import get_products_for_facebook, get_image_url

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
    
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    recipient_id = messaging_event["recipient"]["id"]
                    send_menu(sender_id)
    return "ok", 200


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

    client_id = os.environ["CLIENT_ID"]
    client_secret = os.environ["CLIENT_SECRET"]

    products = get_products_for_facebook(client_id, client_secret)

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

    for product in products["data"]:
        product_name = product["name"]
        price = product["price"][0]["amount"]
        title = f"{product_name} ({price} р.)"

        if index < 5:
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

        index += 1

    return elements


if __name__ == '__main__':
    app.run(debug=True)
