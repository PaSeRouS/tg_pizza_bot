from time import time
import json
import os

import requests

from database_functions import get_database_connection
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
            "attachment": get_menu(message)
        }
    }

    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def send_cart_menu(recipient_id, message):
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
                    "elements": get_elements_for_cart(recipient_id, message)
                }
            }
        }
    }

    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params, headers=headers, json=request_content
    )
    response.raise_for_status()


def create_menu(message):
    elements = []
    buttons = []

    client_id = os.environ["CLIENT_ID"]
    client_secret = os.environ["CLIENT_SECRET"]

    categories = get_all_categories(client_id, client_secret)

    if message['type'] == 'message':
        category_id = get_last_category(client_id, client_secret)
    elif message['type'] == 'postback':
        if message['value'] == 'return':
            category_id = get_last_category(client_id, client_secret)
        else:
            category_id = message['value']

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

    menu = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "elements": elements
            }
        },
        'created_at': time()
    }

    return menu


def get_elements_for_cart(sender_id, message):
    elements = []

    client_id = os.environ["CLIENT_ID"]
    client_secret = os.environ["CLIENT_SECRET"]

    cart_id = f"facebookid_{sender_id}"
    cart_items, full_price = get_cart_and_full_price(cart_id, client_id, client_secret)

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
        
    for item in cart_items:
        element = {
            "title": item['name'],
            "image_url": item["image"]["href"],
            "subtitle": item["description"],
            "buttons": [
                {
                    "type": "postback",
                    "title": "Добавить ещё одну",
                    "payload": item["product_id"],
                },
                {
                    "type": "postback",
                    "title": "Убрать из корзины",
                    "payload": item["id"],
                }
            ]
        }

        elements.append(element)

    return elements


def get_menu(message):
    db_password = os.environ["REDIS_PASSWORD"]
    db_host = os.environ['REDIS_HOST']
    db_port = os.environ['REDIS_PORT']

    db = get_database_connection(
        db_password,
        db_host,
        db_port
    )

    if message['type'] == 'message' or message['value'] == 'return':
        menu_type = 'main'
    elif message['title'] == 'Основные пиццы':
        menu_type = 'main'
    elif message['title'] == 'Особые пиццы':
        menu_type = 'special'
    elif message['title'] == 'Сытные пиццы':
        menu_type = 'nourishing'
    elif message['title'] == 'Острые пиццы':
        menu_type = 'hot'

    cached_menu = db.get(menu_type)
    
    if cached_menu:
        cached_menu = json.loads(cached_menu)
        time_diff = time() - cached_menu['created_at']
        if time_diff > 3600:
            menu = create_menu(message)
            db.set(menu_type, json.dumps(menu))
            menu = menu['attachment']
        else:
            menu = cached_menu['attachment']
    else:
        menu = create_menu(message)
        db.set(menu_type, json.dumps(menu))
        menu = menu['attachment']

    return menu
