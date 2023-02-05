import time
import requests

expires_on = 0
access_token = None


def get_headers(client_id, client_secret):
    global expires_on, access_token

    now = time.time()

    if access_token and now < expires_on:
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials',
    }

    response = requests.post('https://api.moltin.com/oauth/access_token', data=data)
    response.raise_for_status()

    access_data = response.json()
    access_token = access_data['access_token']
    expires_on = now + access_data['expires_in']

    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }


def get_products(client_id, client_secret):
    headers = get_headers(client_id, client_secret)

    response = requests.get('https://api.moltin.com/v2/products', headers=headers)
    response.raise_for_status()

    product_data = response.json()

    return {
            product['name']: product['id'] 
            for product in product_data['data']
        }

def get_product_by_id(product_id, client_id, client_secret):
    headers = get_headers(client_id, client_secret)

    url = f'https://api.moltin.com/v2/products/{product_id}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()


def get_image_url(image_id, client_id, client_secret):
    headers = get_headers(client_id, client_secret)

    url = f'https://api.moltin.com/v2/files/{image_id}'

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()['data']['link']['href']


def add_product_to_cart(
    cart_id,
    product_id,
    quantity,
    client_id,
    client_secret
):
    headers = get_headers(client_id, client_secret)

    url = f'https://api.moltin.com/v2/carts/{cart_id}/items'

    json = {
        'data':{
            'id': product_id,
            'type': 'cart_item',
            'quantity': quantity
        }
    }

    response = requests.post(url, headers=headers, json=json)
    response.raise_for_status()


def get_cart_and_full_price(cart_id, client_id, client_secret):
    headers = get_headers(client_id, client_secret)

    url = f'https://api.moltin.com/v2/carts/{cart_id}/items'

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    items_info = response.json()

    return (
        items_info['data'], 
        items_info['meta']['display_price']['with_tax']['formatted']
    )


def remove_product_from_cart(cart_id, item_id, client_id, client_secret):
    headers = get_headers(client_id, client_secret)

    url = f'https://api.moltin.com/v2/carts/{cart_id}/items/{item_id}'

    response = requests.delete(url, headers=headers)
    response.raise_for_status()


def get_all_pizzerias(client_id, client_secret):
    headers = get_headers(client_id, client_secret)

    response = requests.get('https://api.moltin.com/v2/flows/pizzeria/entries?page[limit]=100', headers=headers)
    response.raise_for_status()

    return response.json()


def create_customers_address(
    client_id,
    client_secret,
    chat_id,
    latitude,
    longitude
):
    headers = get_headers(client_id, client_secret)

    json = {
        'data': {
            'type': 'entry',
            'customer-id': chat_id,
            'latitude': latitude,
            'longitude': longitude
        }
    }

    response = requests.post(
        'https://api.moltin.com/v2/flows/customer-address/entries', 
        headers=headers, 
        json=json
    )
    response.raise_for_status()


def get_deliveryman_id_by_pizzeria_address(client_id, client_secret, address):
    headers = get_headers(client_id, client_secret)

    response = requests.get('https://api.moltin.com/v2/flows/pizzeria/entries?page[limit]=100', headers=headers)
    response.raise_for_status()

    pizzerias = response.json()

    for pizzeria in pizzerias['data']:
        if address == pizzeria['address']:
            return pizzeria['deliveryman-id']