import redis


def get_database_connection(password, host, port):
    database = redis.Redis(host=host, port=port, password=password)
    return database