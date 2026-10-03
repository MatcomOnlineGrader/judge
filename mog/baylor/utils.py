import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from django.conf import settings
from django.contrib.auth.hashers import make_password
from hashlib import sha256

from api.models import User

ICPCID_GUEST_PREFIX = "guestid_"

CSV_GUEST_HEADER = (
    "team_name,institution,coach,participant1,participant2,participant3,group"
)

CSV_PERMISSION_HEADER = "username,role,granted"


def generate_secret_password(user_id):
    """
    Generate password
    """
    return sha256(
        (settings.PASSWORD_GENERATOR_SECRET_KEY + str(user_id)).encode()
    ).hexdigest()[:10]


def set_passwords(users_passwords):
    """
    Hash and save the passwords of many (user, raw password) pairs at once.
    Each hash takes up to a second (Django's PBKDF2 iterations), so hashing
    them one by one makes big imports exceed the request timeout. They run in
    forked processes: threads are slower than one by one, because OpenSSL 3's
    PBKDF2 contends on locks shared between threads. The children only hash;
    they never touch the parent's database connection.
    """
    if not users_passwords:
        return
    workers = min(len(users_passwords), os.cpu_count())
    fork = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(workers, mp_context=fork) as pool:
        hashes = list(pool.map(make_password, [p for _, p in users_passwords]))
    users = [user for user, _ in users_passwords]
    for user, encoded in zip(users, hashes):
        user.password = encoded
    User.objects.bulk_update(users, ["password"])


def hash_string(value):
    return sha256(value.encode()).hexdigest()[:20]


def generate_username(prefix: str, id: int):
    return "%s%03d" % (prefix, id)
