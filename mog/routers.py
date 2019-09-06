import random
import threading

from django.conf import settings


current_request = threading.local()


class RouterMiddleware:
    """
    Took idea from https://djangosnippets.org/snippets/2037/
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'GET':
            # GET requests shouldn't modify the database (hopefully)
            current_request.database_used_to_read = \
                'replica%d' % random.randint(1, settings.NUMBER_OF_REPLICAS)
        else:
            # Requests other than GET might modify the database. In
            # those cases, lets the default database handle the entire
            # request.
            current_request.database_used_to_read = 'default'
        response = self.get_response(request)
        del current_request.database_used_to_read
        return response


class DefaultRouter:
    def db_for_read(self, model, **hints):
        return current_request.database_used_to_read

    def db_for_write(self, model, **hints):
        return 'default'
