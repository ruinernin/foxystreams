"""Kodi plugin URI Rooting tool.

Known issues:
  * cache functions are name dependant, do not attempt to decorate functions
    with cache decorators where function names will clash. i.e. caches are
    namespaced by function names only.

"""

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
import xbmcplugin


class Router(object):
    """Router class intended to be used as a singleton.

    This class is instantiated as an object within this module and it is not
    intended that any consumers will construct objects from this class. Instead
    importing the instance `router` created below.

    """

    def __init__(self):
        self.paths = {}
        self.addon = xbmcaddon.Addon()
        self.id_ = self.addon.getAddonInfo('id')
        self.handle = int(sys.argv[1])
        self.cache_dir = xbmc.translatePath(
            'special://temp/{}'.format(self.id_))
        try:
            os.makedirs(self.cache_dir)
        except os.error as e:
            pass
        # store cache on (funcname, hash(args + sorted_kwargs))
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

    def _load_cache(self, name):
        """Attempt to load stored cache of `name`.

        Returns `True` if any cached data is loaded.

        """
        cache_path = '{}/{}.json'.format(self.cache_dir, name)
        if os.path.isfile(cache_path):
            with open(cache_path, 'r') as cache_file:
                try:
                    self._cache[name] = json.load(cache_file)
                except:
                    return None
                else:
                    return True

    def _write_cache(self, name):
        """Persist cache data for `name` to disk."""
        cache_path = '{}/{}.json'.format(self.cache_dir, name)
        with open(cache_path, 'w') as cache_file:
            json.dump(self._cache[name], cache_file)

    def _cache_get(self, name, *args, **kwargs):
        """Returns value for cache hit, None for a miss."""
        if name not in self._cache:
            if not self._load_cache(name):
                return None
        _hash = self.cache_hash(*args, **kwargs)
        return self._cache[name].get(_hash)

    def _cache_set(self, name, val, *args, **kwargs):
        """Sets `val` for params in cache and flags as updated."""
        _hash = self.cache_hash(*args, **kwargs)
        self._cache.setdefault(name, dict())[_hash] = val
        self.cache_keys_updated.add(name)

    def cache(self, func):
        """Function wrapper to persist results to disk.

        Use with caution! There are *no* TTLs. This should only be used
        where the data returned is never reasonably expected to change.

        """
        def wrapper(*args, **kwargs):
            cached = self._cache_get(func.__name__, *args, **kwargs)
            if cached is None:
                result = func(*args, **kwargs)
                self._cache_set(func.__name__, result, *args, **kwargs)
                return result
            return cached
        return wrapper

    def route(self, path):
        """Function wrapper to route a function to a path.

        Intended to be used with `build_url` function for callers,
        kwargs from `build_url` will be supplied to decorated function.

        """
        path = path.lstrip('/')
        if path in self.paths:
            raise ValueError('Route already definted')
        def wrapper(func):
            self.paths[path] = func
            return func
        return wrapper

    def run(self, url, handle, qs):
        """Main run method to be called on execution."""
        self.handle = int(handle)
        full_path = url + qs
        parsed = urlparse(full_path)
        path = parsed.path.lstrip('/')
        kwargs = dict(parse_qsl(parsed.query))
        kwargs.pop('reload', None)
        func = self.paths[path]
        func(**kwargs)
        for updated in self.cache_keys_updated:
            self._write_cache(updated)

    def build_url(self, func, **kwargs):
        """Returns URL as a string to wanted method with kwargs."""
        inverted = {v: k for k, v in self.paths.items()}
        path = inverted[func]
        url = 'plugin://{}/{}'.format(self.id_, path)
        if kwargs:
            query = urlencode(kwargs)
            url += '?' + query
        return url

    def fail(self):
        xbmcplugin.endOfDirectory(self.handle, False)


router = Router()
