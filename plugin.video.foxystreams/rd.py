import requests
import urlparse
import xbmcplugin
import xbmcgui
import xbmc

RD_URL = 'https://api.real-debrid.com/rest/1.0'
OAUTH_URL = 'https://api.real-debrid.com/oauth/v2'
RD_KEY = {'auth_token': None}
CLIENT_ID = 'X245A4XAIBGVM'
GRANT_TYPE = 'http://oauth.net/grant_type/device/1.0'
EP_STRS = ('s{0:02d}e{1:02d}',
           '{0:d}x{1:02d}')

def rd_code(client_id=CLIENT_ID):
    params = {
        'client_id': client_id,
        'new_credentials': 'yes',
    }
    return requests.get(OAUTH_URL + '/device/code', params=params).json()

def rd_credentials(code, client_id=CLIENT_ID):
    params = {
        'client_id': client_id,
        'code': code,
    }
    return requests.get(OAUTH_URL + '/device/credentials', params=params).json()

def rd_token(code, client_id, client_secret):
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': GRANT_TYPE,
    }
    return requests.post(OAUTH_URL + '/token', data=data).json()

def rd_api_get(path):
    return requests.get(RD_URL + path, params=RD_KEY)

def rd_api_post(path, **kwargs):
    return requests.post(RD_URL + path, params=RD_KEY, data=kwargs)

def rd_api_delete(path):
    return requests.delete(RD_URL + path, params=RD_KEY)

def rd_availability(*hashes):
    hpath = '/'.join(hashes)
    path = '/torrents/instantAvailability/' + hpath
    return rd_api_get(path).json()

def rd_addmagnet(magnet):
    path = '/torrents/addMagnet'
    return rd_api_post(path, magnet=magnet).json()

def rd_torrentinfo(tid):
    path = '/torrents/info/' + tid
    return rd_api_get(path).json()

def rd_torrents():
    path = '/torrents/'
    return rd_api_get(path).json()

def rd_selectfiles(tid, fids):
    path = '/torrents/selectFiles/' + tid
    fids = ','.join(fids)
    rd_api_post(path, files=fids)

def rd_deletetorrent(tid):
    path = '/torrents/delete/' + tid
    rd_api_delete(path)

def rd_unrestrict(link):
    path = '/unrestrict/link'
    return rd_api_post(path, link=link).json()

def extract_hash(magnet):
    query = urlparse.urlparse(magnet).query
    exact_topic = urlparse.parse_qs(query)['xt'][0]
    sha1 = exact_topic.split(':')[-1]
    return sha1

def get_single_fileid(varients, tv=None):
    single_file_varients = filter(lambda x: len(x.keys()) == 1, varients)
    if len(single_file_varients) == 0:
        return None
    else:
        if tv:
            for ep_str in EP_STRS:
                ep_str = ep_str.format(*tv)
                tmp_varients = filter(lambda x: ep_str in x.values()[0]['filename'].lower(), single_file_varients)
                if tmp_varients:
                    break
            else:
                return None
            single_file_varients = tmp_varients
        if not single_file_varients:
            return None
        return max(single_file_varients,
                   key=lambda x: x.values()[0]['filesize']).keys()[0]

def get_select_file(files, tv=None):
    for ep_str in EP_STRS:
        ep_str = ep_str.format(*tv)
        potentials = filter(lambda x: ep_str in x['path'].lower(), files)
        if potentials:
            break
    return potentials

def check_availability(magnets, chunks=5, tv=None):
    hashes = map(extract_hash, magnets)
    all_results = {}
    for i in range(0, len(hashes), chunks):
        chunk = hashes[i:i+chunks]
        all_results.update(rd_availability(*chunk))
    cached_fileids = []
    for _hash in hashes:
        result = all_results.get(_hash)
        if not result:
            cached_fileids.append(None)
            continue
        varients = result['rd']
        cached_fileids.append(get_single_fileid(varients, tv=tv))
    return cached_fileids

def resolveUrl(handle, magnet, fid):
    tor_id = rd_addmagnet(magnet)['id']
    rd_selectfiles(tor_id, [fid])
    info = rd_torrentinfo(tor_id)
    dl_link = rd_unrestrict(info['links'][0])
    link = dl_link['download']
    rd_deletetorrent(tor_id)
    li = xbmcgui.ListItem(path=link)
    xbmcplugin.setResolvedUrl(handle, True, listitem=li)

def resolveLink(handle, link):
    dl_link = rd_unrestrict(link)
    link = dl_link['download']
    li = xbmcgui.ListItem(path=link)
    xbmcplugin.setResolvedUrl(handle, True, listitem=li)

def grab_torrent(magnet, tv=None):
    tor_id = rd_addmagnet(magnet)['id']
    info = rd_torrentinfo(tor_id)
    tries = 0
    while not info.get('status') == 'waiting_files_selection' and not info.get('files'):
        if tries > 3:
            return
        tries += 1
        xbmc.sleep(2*1000)
        info = rd_torrentinfo(tor_id)
        if 'error' in info['status']:
            return
    files = info['files']
    if tv:
        files = get_select_file(files, tv=tv)
    files = sorted(files, key=lambda x: x['bytes'])
    rd_selectfiles(tor_id, [str(files[-1]['id'])])
    return True

def downloads():
    torrents = rd_torrents()
    results = []
    for torrent in torrents:
        if torrent['status'] == 'downloaded':
            cached = True
            name = torrent['filename']
            url = rd_unrestrict(torrent['links'][0])['download']
        else:
            cached = False
            name = '['+str(torrent['progress'])+'%] ' + torrent['filename']
            url = ''
        results.append((cached, name, url))
    return results
