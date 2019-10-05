import urlparse
import requests
import xbmcgui
import xbmcplugin
import xbmc

PM_URL = 'https://www.premiumize.me/api'
PM_KEY = {'apikey': None} 

def pm_api_get(path, **kwargs):
    kwargs.update(PM_KEY)
    return requests.get(PM_URL + path, params=kwargs).json()

def pm_api_post(path, **kwargs):
    real_args = {}
    for k, v in kwargs.iteritems():
        if k.startswith('_'):
            real_args[k[1:]+'[]'] = v
        else:
            real_args[k] = v
    return requests.post(PM_URL + path, params=PM_KEY, data=real_args).json()

def pm_availability(*hashes):
    path = '/cache/check'
    return pm_api_post(path, _items=hashes)

def pm_directdl(src):
    path = '/transfer/directdl'
    return pm_api_post(path, src=src)

def pm_create(src):
    path = '/transfer/create'
    return pm_api_post(path, src=src)

def pm_transfer_list():
    path = '/transfer/list'
    return pm_api_get(path)

def pm_folder_list(id=''):
    path = '/folder/list'
    return pm_api_get(path, id=id)

def extract_hash(magnet):
    query = urlparse.urlparse(magnet).query
    exact_topic = urlparse.parse_qs(query)['xt'][0]
    sha1 = exact_topic.split(':')[-1]
    return sha1

def get_largest_file(content):
    return max(content, key=lambda x: int(x['size']))['link']

def resolveUrl(handle, magnet, _):
    dls = pm_directdl(magnet)
    xbmc.log(str(dls), xbmc.LOGERROR)
    link = get_largest_file(dls['content'])
    li = xbmcgui.ListItem(path=link)
    xbmcplugin.setResolvedUrl(handle, True, listitem=li)

def check_availability(magnets, chunks=5):
    hashes = map(extract_hash, magnets)
    cached = []
    for i in range(0, len(hashes), chunks):
        chunk = hashes[i:i+chunks]
        cached.extend(pm_availability(*chunk)['response'])
    return cached

def grab_torrent(magnet):
    result = pm_create(magnet)
    if result.get('status') == 'success':
        return True
    else:
        return False

def downloads():
    torrents = pm_transfer_list()['transfers']
    results = []
    for torrent in torrents:
        if torrent['status'] in ['finished', 'seeding']:
            cached = True
            folder_id = torrent['folder_id']
            url = get_largest_file(pm_folder_list(id=folder_id)['content'])
            name = torrent['name']
        else:
            cached = False
            name = '['+str(int(torrent['progress']*100))+'%] '+torrent['name']
            url = ''
        results.append((cached, name, url))
    return results
