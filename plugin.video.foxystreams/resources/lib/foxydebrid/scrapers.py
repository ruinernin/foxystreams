import re
import time

import requests


class Scraper(object):

    api_url = None
    default_headers = ()
    default_params = ()
    default_data = ()
    cache_attrs = ()

    def __init__(self, ratelimit=1):
        self.ratelimit = ratelimit
        self._last_request = 0
        self.cookies = None
        self.timeout = 20

    def find_magnets(self, query=None, tv=False, movie=False, **kwargs):
        """Returns iterable of tuples (name, magnet_uri)."""
        raise NotImplementedError

    def _api_req(self, func='GET', path='', headers=(), params=(), data=()):
        _params = dict(self.default_params)
        _params.update(params)
        _headers = dict(self.default_headers)
        _headers.update(headers)
        _data = dict(self.default_data)
        _data.update(data)
        # Sleep in 34% intervals of total wait time.
        while time.time() < (self._last_request + (1.0 / self.ratelimit)):
            time.sleep(0.34/self.ratelimit)
        self._last_request = time.time()
        if func == 'GET':
            return requests.get(self.api_url + path, params=_params,
                                headers=_headers, cookies=self.cookies,
                                timeout=self.timeout).json()
        elif func == 'POST':
            return requests.post(self.api_url + path, headers=_headers,
                                 params=_params, data=_data,
                                 cookies=self.cookies,
                                 timeout=self.timeout).json()

    def api_get(self, path='', headers=(), **params):
        return self._api_req(path=path, headers=headers, params=params)

    def api_post(self, path='', headers=(), params=(), **data):
        return self._api_req(func='POST', path=path, headers=headers,
                             params=params, data=data)


class TorrentApi(Scraper):

    api_url = 'https://torrentapi.org/pubapi_v2.php'
    default_headers = (('user-agent', 'ruin/1.0'),)
    default_params = (('app_id', 'ruin'),
                      ('limit', 100),
                      ('token', None),)
    cache_attrs = ('token',)

    def __init__(self, token=None, ratelimit=0.5):
        super(TorrentApi, self).__init__(ratelimit=ratelimit)
        self.token = token

    def api_get(self, path='', headers=(), **params):
        result = super(TorrentApi, self).api_get(path=path, headers=headers,
                                                 token=self.token, **params)
        if result.get('error_code') in (1, 2, 4):
            self.token = super(TorrentApi, self).api_get(
                get_token='get_token')['token']
            return self.api_get(path=path, headers=headers, **params)
        return result

    def find_magnets(self, query=None, tv=False, movie=False, **kwargs):
        """Returns iterable of tuples (name, magnet_uri)."""
        ranked = int(kwargs.get('ranked', True))
        category = kwargs.get('category')
        if movie:
            result = self.api_get(mode='search', search_imdb=kwargs['imdb'],
                                  category=category, ranked=ranked)
        elif tv:
            result = self.api_get(mode='search', search_tvdb=kwargs['id'],
                                  search_string=query, category=category,
                                  ranked=ranked)
        elif query:
            result = self.api_get(mode='search', search_string=query,
                                  category=category, ranked=ranked)
        else:
            result = self.api_get(mode='list', category=category,
                                  ranked=ranked)
        result = result.get('torrent_results')
        if not result:
            return None
        return ((t['filename'], t['download']) for t in result)


class BitLord(Scraper):

    api_url = 'https://bitlordsearch.com'
    default_data = (('query', None),
                    ('offset', 0),
                    ('limit', 100),
                    ('filters[field]', 'added'),
                    ('filters[sort]', 'asc'),
                    ('filters[time]', 4),
                    ('filters[category]', 3),
                    ('filters[adult]', False),
                    ('filters[risky]', False),)
    default_headers = (('X-Request-Token', None),)

    def __init__(self, token=None, cookies=None, ratelimit=0.5):
        super(BitLord, self).__init__(ratelimit=ratelimit)
        self.token = token
        self.cookies = cookies

    def authenticate(self):
        tkn_var_re = r'token: (.*)\n'
        tkn_re = r"{} \+?= '(.*)'"
        main_page = requests.get(self.api_url, timeout=self.timeout)
        var = re.findall(tkn_var_re, main_page.text)[0]
        self.token = ''.join(re.findall(tkn_re.format(var),
                                        main_page.text))
        self.cookies = main_page.cookies.get_dict()

    def api_post(self, path='/get_list', headers=(), params=(), **data):
        if not (self.cookies and self.token):
            self.authenticate()
        _headers = dict(headers)
        _headers['X-Request-Token'] = self.token
        _data = {}
        for key, value in data.items():
            # Translate filters e.g. `filters_category` -> `filters[category]`
            if key.startswith('filters_'):
                key = 'filters[{}]'.format(key[8:])
            _data[key] = value
        return super(BitLord, self).api_post(path=path, headers=_headers,
                                             params=params, **_data)

    @staticmethod
    def filter_ascii_only(names_magnets):
        for name, magnet in names_magnets:
            try:
                str(name)
                str(magnet)
            except UnicodeEncodeError:
                continue
            else:
                yield (name, magnet.lower())

    def find_magnets(self, query=None, tv=False, movie=False, **kwargs):
        if movie:
            query = '{} {}'.format(kwargs['title'], kwargs['year'])
            results = self.api_post(query=query, filters_category=3,
                                    filters_field='seeds', filter_sort='desc')
        elif tv:
            query = '{} {}'.format(kwargs['showname'], query)
            results = self.api_post(query=query, filters_category=4)
        elif query:
            results = self.api_post(query=query)
        else:
            results = self.api_post()
        results = results.get('content')
        if not results:
            return None
        return self.filter_ascii_only(
            ((t['name'], t['magnet']) for t in results
             if t['seeds'] > 0))
