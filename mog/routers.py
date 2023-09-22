import random
import threading

from django.conf import settings


current_request = threading.local()


def get_database_for_request(request):
    if request.method == "GET" and "needs_master" not in request.COOKIES:
        # GET requests shouldn't modify the database (hopefully)
        n = random.randint(0, settings.NUMBER_OF_REPLICAS)
        return "replica%d" % n if n else "default"
    else:
        # Requests other than GET might modify the database. In
        # those cases, lets the default database handle the entire
        # request.
        return "default"


def set_needs_master_cookie(request, response):
    if request.method == "GET":
        response.delete_cookie("needs_master")
    else:
        response.set_cookie("needs_master", 1)


class RouterMiddleware:
    """
    Took idea from https://djangosnippets.org/snippets/2037/
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        current_request.database_used_to_read = get_database_for_request(request)
        response = self.get_response(request)
        del current_request.database_used_to_read
        set_needs_master_cookie(request, response)
        return response


class DefaultRouter:
    def db_for_read(self, model, **hints):
        return current_request.database_used_to_read

    def db_for_write(self, model, **hints):
        return "default"
