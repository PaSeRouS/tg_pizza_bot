import os

import requests

from moltin_api import get_image_url, get_products_by_category_id
from moltin_api import get_all_categories, get_last_category
from moltin_api import get_cart_and_full_price

FACEBOOK_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]


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


def send_menu(recipient_id, message):
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
                    "elements": get_elements_for_generic(recipient_id, message)
                }
            }
        }
    }

    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def get_elements_for_generic(sender_id, message):
    # В сообщении кнопки выводятся по три штуки в сообщении и только на 10 слайдах
    elements = []

    client_id = os.environ["CLIENT_ID"]
    client_secret = os.environ["CLIENT_SECRET"]

    categories = get_all_categories(client_id, client_secret)

    if message['value'] == 'cart':
        cart_id = f"facebookid_{sender_id}"
        cart_items, full_price = get_cart_and_full_price(cart_id, client_id, client_secret)
    elif message['type'] == 'message':
        category_id = get_last_category(client_id, client_secret)
    elif message['type'] == 'postback':
        if message['value'] == 'return':
            category_id = get_last_category(client_id, client_secret)
        else:
            category_id = message['value']

    if message['value'] == 'cart':
        element = {
            "title": f"Ваш заказ на сумму {full_price} рублей",
            "image_url": "https://img.freepik.com/premium-vector/wicker-basket-on-white-background_43633-1813.jpg?w=740",
            "subtitle": "",
            "buttons": [
                {
                    "type": "postback",
                    "title": "Самовывоз",
                    "payload": "pickup",
                },
                {
                    "type": "postback",
                    "title": "Доставка",
                    "payload": "delivery",
                },
                {
                    "type": "postback",
                    "title": "К меню",
                    "payload": "return",
                }
            ]
        }

        elements.append(element)
        return elements
    else:
        element = {
            "title": "Меню",
            "image_url": "https://img.freepik.com/premium-vector/pizza-logo-template-suitable-for-restaurant-and-cafe-logo_607277-267.jpg",
            "subtitle": "Здесь вы можете выбрать один из вариантов",
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
    buttons = []

    for category in categories['data']:
        if category_id == category['id']:
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
                "payload": category['id'],
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