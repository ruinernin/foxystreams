import re

import requests


def torrentapi_factory(token=None, ratelimit=0.5):
    """Returns torrentapi function.

    token -- API token, if not provided or invalid it will be requested.
    ratelimit -- reqs/s allowed, default 1req/2s
    """
    wait_time = 1/ratelimit
    def torrentapi(**kwargs):
        api_url = 'https://torrentapi.org/pubapi_v2.php'
        hdrs = {'user-agent': 'ruin/1.0'}
        params = {
            'token': torrentapi.token,
            'app_id': 'ruin',
            'limit': 100,
        }
        params.update(kwargs)
        while torrentapi.last_req + wait_time > time.time():
            xbmc.sleep(int((wait_time/3.0)*1000))
        resp = requests.get(api_url, params=params, headers=hdrs).json()
        torrentapi.last_req = time.time()
        if resp.get('error_code') in (2, 4):
            torrentapi.token = torrentapi(get_token='get_token')['token']
            return torrentapi(**kwargs)
        return resp
    torrentapi.last_req = 0
    torrentapi.token = token
    return torrentapi


def bitlord_factory(token=None, cookies=None):
    """Returns bitlord function.

    token -- API token, if not provided or invalid it will be requested.
    cookies -- cookies attached to token.
    """
    url = 'https://bitlordsearch.com'
    tkn_var_re = r'token: (.*)\n'
    tkn_re = r"{} \+?= '(.*)'"
    def bitlord(**kwargs):
        """Performs requests against bitlord's AJAX service.

        Common useful args:
        query -- string of search query to perform.
        filters_category -- int of selected bitlord category.
            3 - Movies
            4 - TV
        filters_field -- sort field e.g. 'added', 'seeds'.
        filters_sort -- string 'asc' or 'dsc'.
        limit -- int of max items to return.
        offset -- int offset of items for pagination.
        """
        if not bitlord.token or not bitlord.cookies:
            if bitlord.errors > 1:
                return None
            main_page = requests.get(url)
            var = re.findall(tkn_var_re, main_page.text)[0]
            bitlord.token = ''.join(re.findall(tkn_re.format(var),
                                               main_page.text))
            bitlord.cookies = main_page.cookies
            return bitlord(**kwargs)
        data = {
            'query': None,
            'offset': 0,
            'limit': 25,
            'filters[field]': 'added',
            'filters[sort]': 'asc',
            'filters[time]': 0,
            'filters[category]': 3,
            'filters[adult]': False,
            'filters[risky]': False,
        }
        headers = {
            'X-Request-Token': bitlord.token,
        }
        for key, value in kwargs.iteritems():
            # Translate filters e.g. `filters_category` -> `filters[category]`
            if key.startswith('filters_'):
                key = 'filters[{}]'.format(key[8:])
            data[key] = value
        req = requests.post(url+'/get_list',
                            data=data,
                            headers=headers,
                            cookies=bitlord.cookies)
        if req.status_code >= 400:
            bitlord.token = None
            bitlord.cookies = None
            bitlord.errors += 1
            return bitlord(**kwargs)
        bitlord.errors = 0
        return req.json()
    bitlord.token = token
    bitlord.cookies = cookies
    bitlord.errors = 0
    return bitlord
