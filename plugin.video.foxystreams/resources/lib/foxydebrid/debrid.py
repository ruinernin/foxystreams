import time
try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

import requests


class DebridProvider(object):

    rest_url = None

    def __init__(self):
        self.timeout = 20

    def auth_params(self):
        """Returns dict of auth params for requests."""
        raise NotImplementedError

    def authenticate(self):
        """Authenticates with provider.

        If curent authentication is considered valid returns `None`.

        On key renewal or new authentication `True` indicates sucess,
        `False` is a failure,

        Returns string if auth requires code entry on an external device.

        Returns int betweeen 0-100 if auth countdown timer.

        """

        raise NotImplementedError

    def check_availability(self, magnets, chunks=5, fn_filter=None):
        """Returns a list of truthful items in the same order as magnets."""
        raise NotImplementedError

    def grab_torrent(self, magnet, fn_filter=None):
        """Returns sucess of adding magnet to provider."""
        raise NotImplementedError

    def resolve_url(self, magnet, fn_filter=None):
        """Returns a playable URL or None."""
        raise NotImplementedError

    def downloads(self):
        """Returns provider downloads as (cached, name, url).  """
        raise NotImplementedError

    def rest_api_get(self, path, **kwargs):
        kwargs.update(self.auth_params())
        return requests.get(self.rest_url + path,
                            params=kwargs,
                            timeout=self.timeout)

    def rest_api_post(self, path, params=None, _files=None, **kwargs):
        if params is None:
            params = {}
        params.update(self.auth_params())
        return requests.post(self.rest_url + path,
                             params=params,
                             data=kwargs,
                             files=_files,
                             timeout=self.timeout)

    def rest_api_delete(self, path, **kwargs):
        kwargs.update(self.auth_params())
        return requests.delete(self.rest_url + path,
                               params=kwargs,
                               timeout=self.timeout)



class RealDebrid(DebridProvider):

    _base_url = 'https://api.real-debrid.com'
    rest_url = _base_url + '/rest/1.0'
    _oauth_url = _base_url + '/oauth/v2'
    _grant_type = 'http://oauth.net/grant_type/device/1.0'

    def __init__(self,
                 api_key=None,
                 refresh_token=None,
                 client_id='X245A4XAIBGVM',
                 client_secret=None,
                 expires=0):
        super(RealDebrid, self).__init__()
        self.api_key = api_key
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.expires = int(expires)
        self.lifetime = 600

    def authenticate(self):
        if self.api_key:
            return self.refresh_keys()
        if not self.api_key and self.refresh_token:
            return self.get_secrets()
        self.client_id = 'X245A4XAIBGVM'
        path = '/device/code'
        params = {
            'client_id': self.client_id,
            'new_credentials': 'yes',
        }
        code = requests.get(self._oauth_url + path,
                            params=params,
                            timeout=self.timeout).json()
        self.lifetime = code['expires_in']
        self.expires = int(time.time()) + self.lifetime
        self.refresh_token = code['device_code']
        return code['user_code']

    def get_secrets(self):
        path = '/device/credentials'
        params = {
            'client_id': self.client_id,
            'code': self.refresh_token,
        }
        result = requests.get(self._oauth_url + path,
                              params=params,
                              timeout=self.timeout).json()
        if 'error' in result:
            pct = 1 - (self.expires - time.time()) / self.lifetime
            if pct >= 1:
                return False
            return min(int(pct*100), 100)
        self.client_id = result['client_id']
        self.client_secret = result['client_secret']
        self.expires = 0
        return self.refresh_keys()

    def refresh_keys(self):
        if self.expires > time.time():
            return None
        path = '/token'
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': self.refresh_token,
            'grant_type': self._grant_type,
        }
        result = requests.post(self._oauth_url + path,
                               data=params,
                               timeout=self.timeout).json()
        self.api_key = result['access_token']
        self.expires = result['expires_in'] + int(time.time())
        self.refresh_token = result['refresh_token']
        return True

    def auth_params(self):
        return {'auth_token': self.api_key}

    def unrestrict(self, link):
        path = '/unrestrict/link'
        return self.rest_api_post(path, link=link).json()['download']

    def add_magnet(self, magnet):
        path = '/torrents/addMagnet'
        return self.rest_api_post(path, magnet=magnet).json()['id']

    def torrent_info(self, torrent_id):
        path = '/torrents/info/' + torrent_id
        return self.rest_api_get(path).json()

    def delete_torrent(self, torrent_id):
        path = '/torrents/delete/' + torrent_id
        self.rest_api_delete(path)

    def select_files(self, torrent_id, file_id=None):
        if file_id is None:
            raise NotImplementedError
        path = '/torrents/selectFiles/' + torrent_id
        self.rest_api_post(path, files=file_id)

    def downloads(self):
        torrents = self.rest_api_get('/torrents', limit=100).json()
        results = []
        for torrent in torrents:
            if torrent['status'] == 'downloaded':
                cached = True
                name = torrent['filename']
                url = torrent['links'][0]
            else:
                cached = False
                name = '['+str(torrent['progress'])+'%] ' + torrent['filename']
                url = ''
            results.append((cached, name, url))
        return results

    @staticmethod
    def get_cached_fileid(varients, fn_filter=None):
        """Returns a single file ID from the list of varients.

        varients -- list of varients as returned by instantAvailability query.
        fn_filter -- optional filter function applied on filenames.

        First all non single file varients are removed, then varients where
        filename does not match the fn_filter function. Of the remaining
        varients the largest is returned.
        """
        def varient_filter(varient):
            if len(varient) != 1:
                return False
            if callable(fn_filter):
                if not fn_filter(varient.values()[0]['filename']):
                    return False
            return True
        varients = [varient for varient in varients if varient_filter(varient)]
        if not varients:
            return False
        varient = max(varients, key=lambda x: x.values()[0]['filesize'])
        return varient.keys()[0]

    @staticmethod
    def get_fileid(files, fn_filter=None):
        """Returns a single file ID from the list of files.

        files -- list of files as returned by torrents/info query.
        fn_filter -- optional filter function applied on paths.

        All files where path does not match the fn_filter function are removed.
        Of the remaining files the largest is returned.
        """
        if callable(fn_filter):
            files = [_file for _file in files if fn_filter(_file['path'])]
        if not files:
            return None
        largest = max(files, key=lambda x: x['bytes'])
        return largest['id']

    def check_availability(self, magnets, chunks=10, fn_filter=None):
        hashes = map(extract_hash, magnets)
        all_results = {}
        for i in range(0, len(hashes), chunks):
            chunk = hashes[i:i+chunks]
            path = '/torrents/instantAvailability/'
            path = path + '/'.join(chunk)
            all_results.update(self.rest_api_get(path).json())
        cached_fileids = []
        for _hash in hashes:
            result = all_results.get(_hash)
            if result:
                varients = result['rd']
                result = self.get_cached_fileid(varients,
                                                fn_filter=fn_filter)
            cached_fileids.append(result)
        return cached_fileids

    def grab_torrent(self, magnet, fn_filter=None):
        torrent_id = self.add_magnet(magnet)
        while True:
            time.sleep(2)
            info = self.torrent_info(torrent_id)
            if info['status'] == 'waiting_files_selection':
                break
            elif info['status'] == 'magnet_conversion':
                continue
            else:
                return False
        file_id = self.get_fileid(info['files'])
        self.select_files(torrent_id, file_id)
        return True

    def resolve_url(self, magnet, fn_filter=None):
        """Returns string of direct HTTP(S) URI for magenet.

        fn_filter differs from standard and should be a cached file_id.

        """

        _id = self.add_magnet(magnet)
        self.select_files(_id, file_id=fn_filter)
        link = self.torrent_info(_id)['links'][0]
        url = self.unrestrict(link)
        self.delete_torrent(_id)
        return url


class Premiumize(DebridProvider):

    rest_url = 'https://www.premiumize.me/api'

    def __init__(self, api_key=None):
        super(Premiumize, self).__init__()
        self.api_key = api_key

    def authenticate(self):
        if self.api_key:
            return None
        return False

    def auth_params(self):
        return {'apikey': self.api_key}

    def check_availability(self, magnets, chunks=None, fn_filter=None):
        hashes = [extract_hash(magnet) for magnet in magnets]
        path = '/cache/check'
        # Need to create dict for args because some jackass used [] as a key
        data = {'items[]': hashes}
        return self.rest_api_post(path, **data).json()['response']

    def grab_torrent(self, magnet, fn_filter=None):
        path = '/transfer/create'
        result = self.rest_api_post(path, src=magnet).json()
        return result.get('status') == 'success'

    def add_torrent(self, torrent_path):
        path = '/transfer/create'
        files = {'file': open(torrent_path, 'rb')}
        result = self.rest_api_post(path, _files=files).json()
        return result.get('status') == 'success'

    def cached_content(self, magnet, fn_filter=None):
        path = '/transfer/directdl'
        content = self.rest_api_post(path, src=magnet).json()['content']
        if fn_filter:
            content = [item for item in content if fn_filter(item['path'])]
        content.sort(key=lambda x: int(x['size']))
        return content

    def resolve_url(self, magnet, fn_filter=None):
        return self.cached_content(magnet, fn_filter)[-1]['link']

    def downloads(self):
        path = '/transfer/list'
        transfers = self.rest_api_get(path).json()['transfers']
        results = []
        for transfer in transfers:
            if transfer['status'] in ('finished', 'seeding'):
                cached = True
                path = '/folder/list'
                folder = self.rest_api_get(path,
                                           id=transfer['folder_id']).json()
                content = folder['content']
                content.sort(key=lambda x: int(x['size']))
                url = content[-1]['link']
                name = transfer['name']
            else:
                cached = False
                name = '[{0[progress]:3.0%}] {0[name]}'.format(transfer)
                url = ''
            results.append((cached, name, url))
        return results

def extract_hash(magnet):
    """Returns sha1 hash from a magnet link."""
    query = urlparse.urlparse(magnet).query
    exact_topic = urlparse.parse_qs(query)['xt'][0]
    sha1 = exact_topic.split(':')[-1]
    return sha1.lower()
