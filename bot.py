import logging
import redis
from textwrap import dedent

from environs import Env
from geopy import distance
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from moltin_api import add_product_to_cart, get_cart_and_full_price, remove_product_from_cart
from moltin_api import create_customers_address, get_image_url, get_products, get_product_by_id
from moltin_api import get_deliveryman_id_by_pizzeria_address, get_all_pizzerias
from yandex_api import fetch_coordinates

_database = None
logger = logging.getLogger(__name__)


def get_menu_keyboard():
    env = get_env()
    products = get_products(env['client_id'], env['client_secret'])

    keyboard = [
        [InlineKeyboardButton(product_name, callback_data=product_id)]
        for product_name, product_id 
        in products.items()
    ]

    keyboard.append([InlineKeyboardButton("Корзина", callback_data="cart")])

    return keyboard


def get_cart(cart_id):
    env = get_env()
    cart_items, full_price = get_cart_and_full_price(cart_id, env['client_id'], env['client_secret'])
    cart_items_display = [
        dedent(
            f"""\
            {item['name']}
            {item['description']}
            {item['quantity']} пицц в корзине на сумму {item['meta']['display_price']['with_tax']['value']['formatted']} рублей\
            """
        )
        for item in cart_items
    ]

    cart_items_display.append(f"К оплате: {full_price} рублей")

    text = (
        "\n\n".join(cart_items_display) if cart_items else
        "Корзина пуста. Заполните её чем-нибудь."
    )

    cart_keyboard = [
        [InlineKeyboardButton(f"Убрать из корзины '{item['name']}'", callback_data=item["id"])]
        for item in cart_items 
    ]

    cart_keyboard.append([InlineKeyboardButton("В меню", callback_data="return")])

    if cart_items:
        cart_keyboard.append([InlineKeyboardButton("Оплатить", callback_data="checkout")])

    return text, cart_keyboard


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


def start(update, context):
    keyboard = get_menu_keyboard()

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Пожалуйста, выберите:', reply_markup=reply_markup)
    
    return 'HANDLE_MENU'


def handle_menu(update, context):
    users_reply = update.callback_query.data

    env = get_env()

    if users_reply == "cart":
        update.callback_query.edit_message_reply_markup(reply_markup=None)
        
        text, cart_keyboard = get_cart(update.effective_chat.id)

        update.callback_query.message.reply_text(
            text=text,
            reply_markup = InlineKeyboardMarkup(cart_keyboard)
        )

        return 'HANDLE_CART'

    product_data = get_product_by_id(
        users_reply,
        env['client_id'],
        env['client_secret']
    )

    product_sku = product_data['data']['sku']
    image_url = get_image_url(
        product_data['data']['relationships']['main_image']['data']['id'],
        env['client_id'],
        env['client_secret']
    )

    product_price = product_data['data']['price'][0]['amount']

    text = dedent(
        f"""\
        {product_data['data']['name']}

        Стоимость: {product_price} рублей

        {product_data['data']['description']}\
        """
    )

    options_keyboard = [
        [
            InlineKeyboardButton("Положить в корзину", callback_data=f"{product_data['data']['id']}:1")
        ],
        [
            InlineKeyboardButton("Назад", callback_data="return"),
            InlineKeyboardButton("Корзина", callback_data="cart")
        ]
    ]

    update.callback_query.message.reply_photo(
        image_url,
        caption=text,
        reply_markup=InlineKeyboardMarkup(options_keyboard)
    )

    return 'HANDLE_DESCRIPTION'


def handle_description(update, context):
    if not update.callback_query:
        return 'HANDLE_DESCRIPTION'

    users_reply = update.callback_query.data

    env = get_env()

    if users_reply == "cart":
        update.callback_query.edit_message_reply_markup(reply_markup=None)
        
        text, cart_keyboard = get_cart(update.effective_chat.id)

        update.callback_query.message.reply_text(
            text=text,
            reply_markup = InlineKeyboardMarkup(cart_keyboard)
        )

        return 'HANDLE_CART'

    if users_reply == "return":
        update.callback_query.edit_message_reply_markup(reply_markup=None)
        keyboard = get_menu_keyboard()

        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.message.reply_text(
            'Что Вам интересно?',
            reply_markup=reply_markup
        )

        return 'HANDLE_MENU'

    product_id, quantity = users_reply.split(":")
    add_product_to_cart(
        update.effective_chat.id,
        product_id,
        int(quantity),
        env['client_id'],
        env['client_secret']
    )
    update.callback_query.answer(text="Товар добавлен в корзину")

    return 'HANDLE_DESCRIPTION'


def handle_cart(update, context):
    if not update.callback_query:
        return 'HANDLE_CART'

    users_reply = update.callback_query.data

    env = get_env()

    if users_reply == "return":
        update.callback_query.edit_message_reply_markup(reply_markup=None)

        product_keyboard = get_menu_keyboard()

        update.callback_query.message.reply_text(
            text="Что Вам интересно?",
            reply_markup=InlineKeyboardMarkup(product_keyboard)
        )

        return 'HANDLE_MENU'

    if users_reply == 'checkout':
        update.callback_query.edit_message_reply_markup(reply_markup=None)

        update.callback_query.message.reply_text(
            text="Хорошо. Пришлите нам ваш адрес текстом или геолокацию."
        )

        return 'WAITING_GEO'


    remove_product_from_cart(
        update.effective_chat.id,
        users_reply,
        env['client_id'],
        env['client_secret']
    )

    text, cart_keyboard = get_cart(update.effective_chat.id)

    update.callback_query.answer(text='Товар удалён из корзины')
    update.callback_query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(cart_keyboard)
    )

    return 'HANDLE_CART'


def waiting_geo(update, context):
    # global pizzeria_address, coords

    if update.message == None:
        users_reply = update.callback_query.data
    else:
        users_reply = update.message.text

    env = get_env()

    if users_reply == "return":
        update.callback_query.edit_message_reply_markup(reply_markup=None)
        keyboard = get_menu_keyboard()

        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.message.reply_text(
            'Что Вам интересно?',
            reply_markup=reply_markup
        )

        return 'HANDLE_MENU'

    wrong_address = False

    if not users_reply:
        coords = (update.message.location.latitude, update.message.location.longitude)
    else:
        coords = fetch_coordinates(env['apikey'], users_reply)

    if not coords:
        text = 'Такого адреса не существует. Введите адрес заново, либо вернитесь в меню.'
        wrong_address = True
    else:
        all_pizzerias = get_all_pizzerias(env['client_id'], env['client_secret'])
        
        for pizzeria in all_pizzerias:
            pizzeria['distance'] = distance.distance(
                coords,
                (pizzeria['latitude'], pizzeria['longitude'])
            ).km
    
        nearest_pizzeria = min(
            all_pizzerias,
            key=lambda pizzeria: pizzeria['distance']
        )
        
        text = get_text_of_delivery(
            nearest_pizzeria['distance'],
            nearest_pizzeria['address']
        )

    options_keyboard = get_delivery_options_keyboard(nearest_pizzeria['distance'])

    update.message.reply_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(options_keyboard)
    )


    context.user_data['latitude'], context.user_data['longitude'] = coords
    context.user_data['pizzeria_address'] = nearest_pizzeria['address']

    if wrong_address:
        state = 'WAITING_GEO'
    else:
        state = 'HANDLE_DELIVERY'
    
    return state


def handle_delivery(update, context):
    users_reply = update.callback_query.data

    env = get_env()

    if users_reply == "return":
        update.callback_query.edit_message_reply_markup(reply_markup=None)
        keyboard = get_menu_keyboard()

        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.message.reply_text(
            'Что Вам интересно?',
            reply_markup=reply_markup
        )

        return 'HANDLE_MENU'

    if users_reply == 'delivery':
        chat_id = update.callback_query.message.chat.id

        create_customers_address(
            env['client_id'], 
            env['client_secret'],
            chat_id,
            context.user_data['latitude'],
            context.user_data['longitude']
        )

        deliveryman_id = get_deliveryman_id_by_pizzeria_address(
            env['client_id'], 
            env['client_secret'],
            context.user_data['pizzeria_address']
        )

        text, cart_keyboard = get_cart(chat_id)

        context.bot.send_message(
            chat_id = deliveryman_id,
            text=text
        )

        context.bot.send_location(
            chat_id = deliveryman_id,
            latitude = context.user_data['latitude'],
            longitude = context.user_data['longitude']
        )

        text = 'Заказ передан в службу доставки.'

    if users_reply == 'pickup':
        text = dedent(
            f"""\
            Отлично. Ваш заказ будет ждать вас по адресу: {pizzeria_address}.\
            """
        )

    update.callback_query.edit_message_reply_markup(reply_markup=None)

    options_keyboard = [
        [InlineKeyboardButton("Оплатить", callback_data="pay")]
    ]
    reply_markup = InlineKeyboardMarkup(options_keyboard)

    update.callback_query.message.reply_text(
        text=text,
        reply_markup=reply_markup
    )

    return 'HANDLE_PAYMENT'


def handle_payment(update, context):
    users_reply = update.callback_query.data

    env = get_env()

    if users_reply == "return":
        update.callback_query.edit_message_reply_markup(reply_markup=None)
        keyboard = get_menu_keyboard()

        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.message.reply_text(
            'Что Вам интересно?',
            reply_markup=reply_markup
        )

        return 'HANDLE_MENU'

    chat_id = update.callback_query.message.chat.id
    title = "Оплата заказа"
    description = "Оплата заказа пиццы"
    payload = "Custom-Payload"
    provider_token = env['payment_token']
    currency = "rub"

    cart_items, full_price = get_cart_and_full_price(
        chat_id,
        env['client_id'],
        env['client_secret']
    )

    full_price = full_price.replace(',', '')
    price = int(full_price)
    prices = [LabeledPrice("Сумма заказа", price * 100)]

    context.bot.send_invoice(
        chat_id, title, description, payload, provider_token, currency, prices
    )

    options_keyboard = [
        [InlineKeyboardButton("В меню", callback_data="return")]
    ]
    reply_markup = InlineKeyboardMarkup(options_keyboard)

    update.callback_query.message.reply_text(
        text='Оплата прошла успешно!',
        reply_markup=reply_markup
    )

    context.job_queue.run_once(
        write_to_user,
        3600,
        context=chat_id
    )

    return 'HANDLE_PAYMENT'


def precheckout_callback(update, context):
    query = update.pre_checkout_query
    if query.invoice_payload != 'Custom-Payload':
        query.answer(ok=False, error_message="Что-то пошло не так...")
    else:
        query.answer(ok=True)


def write_to_user(context):
    text = dedent(
        f"""\
        Приятного аппетита! *место для рекламы*

        *сообщение что делать если пицца не пришла*\
        """
    )

    context.bot.send_message(
        context.job.context,
        text=text
    )


def handle_users_reply(update, context):
    env = get_env()
    db = get_database_connection(
        env['database_password'],
        env['database_host'],
        env['database_port']
    )
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'WAITING_GEO': waiting_geo,
        'HANDLE_DELIVERY': handle_delivery,
        'HANDLE_PAYMENT': handle_payment
    }
    state_handler = states_functions[user_state]

    try:
        next_state = state_handler(update, context)
        db.set(chat_id, next_state)
    except Exception as err:
        print(err)


def get_database_connection(password, host, port):
    global _database
    if not _database:
        _database = redis.Redis(host=host, port=port, password=password)
    return _database


def get_env():
    env = Env()
    env.read_env()

    return {
        'tg_token': env("TELEGRAM_TOKEN"),
        'client_id': env('CLIENT_ID'),
        'client_secret': env('CLIENT_SECRET'),
        'database_password': env("REDIS_PASSWORD"),
        'database_host': env("REDIS_HOST"),
        'database_port': env("REDIS_PORT"),
        'apikey': env('YANDEX_API'),
        'payment_token': env('PAYMENT_PROVIDER_TOKEN')
    }


def handle_error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    env = get_env()
    updater = Updater(env['tg_token'])
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.location, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    dispatcher.add_error_handler(handle_error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()