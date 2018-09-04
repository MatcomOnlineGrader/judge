from django.core.cache import cache


def parse_int(s, default=0):
    try:
        return int(s)
    except:
        return default


class CachedResult:
    def __init__(self, key, timeout=30):
        self.key = key
        self.timeout = timeout
    
    def hashed_arguments(self, *args, **kwargs):
        return hash((hash(tuple(args)), hash(frozenset(kwargs.items()))))

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            key = '%s/%d' % (
                self.key, self.hashed_arguments(*args, **kwargs)
            )
            data = cache.get(key)
            if not data:
                data = func(*args, **kwargs)
                cache.set(key, data, self.timeout)
            return data
        return wrapper
