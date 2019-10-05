import xbmcaddon
import xbmcgui
import xbmcplugin
import requests
import urlparse
import urllib
import sys
import time
import ui
import rd
import pm

searches = [
]

rarbg_categories = {
    '4kx265hdr': '52',
    '4kx265': '51',
    '4kx264': '50',
    '720x264': '45',
    '1080x264': '44',
    'sdx264': '17',
    'XXX': '4',
}

base_url = sys.argv[0]
xbmc.log(base_url,xbmc.LOGERROR)
addon_handle = int(sys.argv[1])
addon = xbmcaddon.Addon()
args = dict(urlparse.parse_qsl(sys.argv[2][1:]))
if addon_handle > 0:
    xbmcplugin.setContent(addon_handle, 'videos')

def build_url(**kwargs):
    return base_url + '?' + urllib.urlencode(kwargs)

mode = args.get('mode', None)

def authenticate():
    interface = xbmcgui.DialogProgress()
    code = rd.rd_code()
    start = time.time()
    xbmc.log(str(code),xbmc.LOGERROR)
    expire = start + code['expires_in']
    interface.create('Authenticate debrid', code['user_code'])
    while True:
        credentials = rd.rd_credentials(code['device_code'])
        if 'error' in credentials:
            xbmc.sleep(code['interval']*1000)
            delta = time.time() - start
            if delta >= code['expires_in']:
                interface.close()
                return
            interface.update(int(100 * delta / code['expires_in']))
            continue
        break
    refresh_token()
    rd_settings = [
        ('rd_clientid', credentials['client_id']),
        ('rd_clientsecret', credentials['client_secret']),
        ('rd_code', code['device_code']),
        ('rd_expires', int(time.time())),
    ]
    for setting_id, value in rd_settings:
        addon.setSetting(setting_id, str(value))
    addon.setSettingBool('rd_authed', True)

def refresh_token():
    if not addon.getSettingBool('rd_authed'):
        return
    expires = addon.getSetting('rd_expires')
    xbmc.log(str(expires), xbmc.LOGERROR)
    now = time.time()
    if now < int(expires):
        return addon.getSetting('rd_token')
    client_id = addon.getSetting('rd_clientid')
    client_secret = addon.getSetting('rd_clientsecret')
    code = addon.getSetting('rd_code')
    token = rd.rd_token(code, client_id, client_secret)
    expires = now + token['expires_in']
    addon.setSetting('rd_code', token['refresh_token'])
    addon.setSetting('rd_token', token['access_token'])
    return token['access_token']

token = refresh_token()
rd.RD_KEY['auth_token'] = token
pm.PM_KEY['apikey'] = addon.getSetting('pm_key')

provider = addon.getSetting('debrid_provider')
if provider == 'pm':
    debrid = pm
elif provider == 'rd':
    debrid = rd

def torrentapi_req(**kwargs):
    api_url = 'https://torrentapi.org/pubapi_v2.php'
    hdrs = {'user-agent': 'ruin/1.0'}
    params = {
        'token': addon.getSetting('torapikey'),
        'app_id': 'ruin',
        'limit': 100,
    }
    params.update(kwargs)
    resp = requests.get(api_url, params=params, headers=hdrs).json()
    if resp.get('error_code') in (2, 4):
        xbmc.log(str(resp), xbmc.LOGERROR)
        xbmc.sleep(2*1000)
        torrentapi_newtoken()
        time.sleep(2*1000)
        return torrentapi_req(**kwargs)
    return resp

def torrentapi_newtoken():
    resp = torrentapi_req(get_token='get_token')
    addon.setSetting('torapikey', resp['token'])

def search_dialog():
    return xbmcgui.Dialog().input('Search')

if mode is None:
    names_urls = []
    names_urls.append(('Downloads',
                      build_url(mode='downloads')))
    names_urls.append(('List',
                      build_url(mode='list')))
    names_urls.append(('Search',
                      build_url(mode='search')))
    for search in searches:
        names_urls.append((search,
                          build_url(mode='search', search=search)))
    ui.directory_view(addon_handle, names_urls, folders=True)

elif mode == 'auth':
    authenticate()

elif mode == 'downloads':
    torrents = debrid.downloads()
    for cached, name, url in torrents:
        if cached:
            li = xbmcgui.ListItem('[COLOR green]' + name + '[/COLOR]')
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': name,
                                 'mediatype': 'video',})
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)
        else:
            url = build_url(mode='noop')
            li = xbmcgui.ListItem('[COLOR red]'+name+'[/COLOR]')
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)
    xbmcplugin.endOfDirectory(addon_handle)

elif mode in ['list', 'search', 'imdb']:
    cats = []
    for name, cat_id in rarbg_categories.iteritems():
        if addon.getSettingBool(name):
            cats.append(cat_id)
    sstring = None
    category = ';'.join(cats)
    ranked = int(addon.getSettingBool('search_ranked'))
    if mode == 'list':
        torrents = torrentapi_req(mode='list', category=category, ranked=ranked)['torrent_results']
    if mode == 'search':
        if not args.get('search'):
            sstring = search_dialog()
        else:
            sstring = args['search']
        torrents = torrentapi_req(mode='search', category=category, search_string=sstring, ranked=ranked)['torrent_results']
    if mode == 'imdb':
        torrents = torrentapi_req(mode='search', category=category, search_imdb=args['search'], ranked=ranked)['torrent_results']
    caches = debrid.check_availability([tor['download'] for tor in torrents])
    names_urls = []
    for torrent, cache in zip(torrents, caches):
        if cache:
            names_urls.append(('[COLOR green]' + torrent['filename'] + '[/COLOR]',
                               build_url(mode='vid', magnet=torrent['download'], cache=cache)))
        else:
            names_urls.append(('[COLOR red]' + torrent['filename'] + '[/COLOR]',
                               build_url(mode='tor', magnet=torrent['download'])))
    if mode == 'imdb':
        selected = ui.dialog_select(zip(*names_urls)[0])
        failed = False
        if selected >= 0:
            xbmc.log(str(selected),xbmc.LOGERROR)
            torrent = torrents[selected]
            cache = caches[selected]
            if cache:
                debrid.resolveUrl(addon_handle, torrent['download'], cache)
            else:
                failed = True
                grab_torrent(torrent['download'])
                xbmc.executebuiltin('Notification(FoxyStreams, Added Torrent to Debrid)')
        else:
            failed = True
        if failed:
            li = xbmcgui.ListItem('Failed')
            xbmcplugin.setResolvedUrl(addon_handle, False, li)
    else:
        ui.directory_view(addon_handle, names_urls, videos=True)

elif mode == 'vid':
    debrid.resolveUrl(addon_handle, args['magnet'], args['cache'])

elif mode == 'tor':
    status = debrid.grab_torrent(args['magnet'])
    if status:
        xbmc.executebuiltin('Notification(FoxyStreams, Added Torrent to Debrid)')
    else:
        xbmc.executebuiltin('Notification(FoxyStreams, FAILED)')
