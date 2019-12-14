try:
    from urllib.parse import urlencode, urlparse, parse_qsl
except ImportError:
    from urllib import urlencode
    from urlparse import urlparse, parse_qsl
import hashlib
import json
import os
import os.path
import sys

import xbmc
import xbmcaddon



ADDON_URL, ADDON_HANDLE, ADDON_QS = sys.argv[:3]


class Router(object):
    def __init__(self):
        self.paths = {}
        self.addon = xbmcaddon.Addon()
        self.id_ = self.addon.getAddonInfo('id')
        self.handle = int(ADDON_HANDLE)
        self.cache_dir = xbmc.translatePath(
            'special://temp/{}'.format(self.id_))
        try:
            os.makedirs(self.cache_dir)
        except os.error as e:
            pass
        # store cache on (funname, hash(args + sorted_kwargs))
        self._cache = {}
        self.cache_keys_updated = set()

    @staticmethod
    def cache_hash(*args, **kwargs):
        h_list = list(args)
        h_list.extend(sorted(kwargs.items()))
        return hashlib.md5(str(h_list)).hexdigest()

    def memcache(self, func):
        cache = {}
        def wrapper(*args, **kwargs):
            _hash = self.cache_hash(*args, **kwargs)
            cached = cache.get(_hash)
            if cached:
                return cached
            result = func(*args, **kwargs)
            cache[_hash] = result
            return result
        return wrapper

    def load_cache(self, name):
        cache_path = '{}/{}.json'.format(self.cache_dir, name)
        if os.path.isfile(cache_path):
            with open(cache_path, 'r') as cache_file:
                try:
                    self._cache[name] = json.load(cache_file)
                except:
                    return None
                else:
                    return True

    def write_cache(self, name):
        cache_path = '{}/{}.json'.format(self.cache_dir, name)
        with open(cache_path, 'w') as cache_file:
            json.dump(self._cache[name], cache_file)

    def cache_get(self, name, *args, **kwargs):
        if name not in self._cache:
            if not self.load_cache(name):
                return None
        _hash = self.cache_hash(*args, **kwargs)
        return self._cache[name].get(_hash)

    def cache_set(self, name, val, *args, **kwargs):
        _hash = self.cache_hash(*args, **kwargs)
        self._cache.setdefault(name, dict())[_hash] = val
        self.cache_keys_updated.add(name)

    def cache(self, func):
        def wrapper(*args, **kwargs):
            cached = self.cache_get(func.__name__, *args, **kwargs)
            if cached is None:
                result = func(*args, **kwargs)
                self.cache_set(func.__name__, result, *args, **kwargs)
                return result
            return cached
        return wrapper

    def route(self, path):
        path = path.lstrip('/')
        if path in self.paths:
            raise ValueError('Route already definted')
        def wrapper(func):
            self.paths[path] = func
            return func
        return wrapper

    def run(self):
        full_path = ADDON_URL + ADDON_QS
        parsed = urlparse(full_path)
        path = parsed.path.lstrip('/')
        kwargs = dict(parse_qsl(parsed.query))
        kwargs.pop('reload', None)
        func = self.paths[path]
        func(**kwargs)
        for updated in self.cache_keys_updated:
            self.write_cache(updated)

    def build_url(self, func, **kwargs):
        inverted = {v: k for k, v in self.paths.items()}
        path = inverted[func]
        url = 'plugin://{}/{}'.format(self.id_, path)
        if kwargs:
            query = urlencode(kwargs)
            url += '?' + query
        return url


router = Router()
