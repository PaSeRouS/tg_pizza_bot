from textwrap import dedent

from geopy import distance
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from moltin_api import get_all_pizzerias


def find_nearest_pizzeria(client_id, client_secret, coords):
    pizzerias = get_all_pizzerias(client_id, client_secret)

    min_distance = 999999
    pizzeria_address = ''

    for pizzeria in pizzerias['data']:
        pizzeria_pos = (pizzeria['latitude'], pizzeria['longitude'])
        distance_between_two_points = distance.distance(coords, pizzeria_pos).km

        if distance_between_two_points < min_distance:
            min_distance = distance_between_two_points
            pizzeria_address = pizzeria['address']

    return min_distance, pizzeria_address


def get_text_of_delivery(min_distance, pizzeria_address):
    if min_distance <= 0.5:
        min_distance = int(min_distance * 1000)

        text = dedent(
            f"""\
            Может, заберёте пиццу из нашей пиццерии не подалеку?
            Она всего в {min_distance} метрах от вас!
            Вот её адрес: {pizzeria_address}.

            А можем и бесплатно доставить с:\
            """
        )
    elif min_distance <= 5:
        text = dedent(
            f"""\
            Похоже, придётся ехать до вас на самокате.
            Доставка будет стоить 100 рублей. Доставляем или самовывоз?\
            """
        )
    elif min_distance <= 20:
        text = dedent(
            f"""\
            Похоже, придётся ехать до вас на машинке.
            Доставка будет стоить 300 рублей. Доставляем или самовывоз?\
            """
        )
    elif min_distance <= 50:
        text = dedent(
            f"""\
            Вы находитесь от нас очень далеко, а именно в {min_distance} км.
            Мы можем предложить вам только самовывоз.\
            """
        )
    else:
        min_distance = int(min_distance)

        text = dedent(
            f"""\
            Вы находитесь от нас очень далеко, а именно в {min_distance} км.
            Мы не сможем доставить пиццу :(\
            """
        )

    return text


def get_delivery_options_keyboard(min_distance):
    if min_distance <= 20:
        options_keyboard = [
            [InlineKeyboardButton("Доставка", callback_data="delivery")],
            [InlineKeyboardButton("Самовывоз", callback_data="pickup")],
            [InlineKeyboardButton("В меню", callback_data="return")]
        ]
    elif min_distance <= 50:
        options_keyboard = [
            [InlineKeyboardButton("Самовывоз", callback_data="pickup")],
            [InlineKeyboardButton("В меню", callback_data="return")]
        ]
    else:
        options_keyboard = [
            [InlineKeyboardButton("В меню", callback_data="return")]
        ]

    return options_keyboard