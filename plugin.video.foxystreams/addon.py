import inspect
import urllib
import urlparse
import sys
import time

import requests
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib import debrid, ui


searches = [
]

rarbg_categories = {
    '4kx265hdr': '52',
    '4kx265': '51',
    '4kx264': '50',
    '720x264': '45',
    '1080x264': '44',
    'sdx264': '17',
    'tvuhd': '49',
    'tvhd': '41',
    'tvsd': '18',
    'XXX': '4',
}

TORRENT_API_LAST_REQ = 0

base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
addon = xbmcaddon.Addon()
if addon_handle > 0:
    xbmcplugin.setContent(addon_handle, 'videos')


def build_url(**kwargs):
    return base_url + '?' + urllib.urlencode(kwargs)


def authenticate(user_debrid):
    debrid_auth = user_debrid.authenticate()
    if debrid_auth in (True, None):
        return debrid_auth
    if isinstance(debrid_auth, basestring):
        interface = xbmcgui.DialogProgress()
        interface.create('Authenticate Debrid', debrid_auth)
        while True:
            xbmc.sleep(5*1000)
            progress = user_debrid.authenticate()
            if isinstance(progress, bool):
                interface.close()
                return progress
            elif isinstance(progress, int):
                interface.update(progress)
            else:
                # This should not happen
                xbmc.log(
                    'catastrophic debrid auth failure: %s' % str(progress),
                    xbmc.LOGEROR)
                interface.close()
    return False


def torrentapi_req(**kwargs):
    api_url = 'https://torrentapi.org/pubapi_v2.php'
    hdrs = {'user-agent': 'ruin/1.0'}
    params = {
        'token': addon.getSetting('torapikey'),
        'app_id': 'ruin',
        'limit': 100,
    }
    params.update(kwargs)
    global TORRENT_API_LAST_REQ
    while TORRENT_API_LAST_REQ + 2 > time.time():
        xbmc.sleep(1*1000)
    resp = requests.get(api_url, params=params, headers=hdrs).json()
    TORRENT_API_LAST_REQ = time.time()
    if resp.get('error_code') in (2, 4):
        torrentapi_newtoken()
        return torrentapi_req(**kwargs)
    return resp


def torrentapi_newtoken():
    resp = torrentapi_req(get_token='get_token')
    addon.setSetting('torapikey', resp['token'])


def episode_search_strings(season, episode):
    string_templates = (
        's{season:02d}e{episode:02d}',
        '{season}x{episode:02d}',
        's{season:02d}',
    )
    return [template.format(season=season, episode=episode)
            for template in string_templates]


def episode_file_filter(season, episode):
    string_templates = (
        's{season:02d}e{episode:02d}',
        '{season}x{episode:02d}',
    )
    search_strings = [template.format(season=season, episode=episode)
                      for template in string_templates]
    def is_in(filename):
        for search_string in search_strings:
            if search_string in filename.lower():
                return True
        return False
    return is_in


def get_user_input(title='Search'):
    return xbmcgui.Dialog().input(title)


def get_debrid_provider(provider_name):
    """Returns a DebridProvider object created with saved settings."""
    provider = getattr(debrid, provider_name)
    cfg_str = '{}.{{}}'.format(provider_name)
    args, _, _, defaults = inspect.getargspec(provider.__init__)
    args = args[1:] # Strip self
    config_argvals = []
    for arg in args:
        config_setting = addon.getSetting(cfg_str.format(arg))
        if config_setting == 'None':
            config_setting = None
        config_argvals.append(config_setting)
    kwargs = {arg: cfg or default
              for arg, cfg, default in zip(args, config_argvals, defaults)}
    return provider(**kwargs)


def save_debrid_settings(provider):
    """Saves provider debrid settings to settings.xml."""
    provider_name = provider.__class__.__name__
    cfg_str = '{}.{{}}'.format(provider_name)
    args, _, _, _ = inspect.getargspec(provider.__init__)
    args = args[1:] # Strip self
    for arg in args:
        addon.setSetting(cfg_str.format(arg), str(getattr(provider, arg, '')))


def add_torrent(user_debrid, magnet, fn_filter=None):
    status = user_debrid.grab_torrent(magnet, fn_filter=fn_filter)
    if status:
        ui.notify('Added Torrent to Debrid')
    else:
        xbmc.executebuiltin('Notification(FoxyStreams, FAILED)')
        ui.notify('Failed to add to Debrid')


def main():
    args = dict(urlparse.parse_qsl(sys.argv[2][1:]))
    mode = args.get('mode', None)
    user_selected_debrid = addon.getSetting('debrid_provider')
    if user_selected_debrid:
        user_debrid = get_debrid_provider(user_selected_debrid)
    else:
        user_debrid = debrid.DebridProvider()
    try:
        auth = authenticate(user_debrid)
    except NotImplementedError:
        auth = False
    else:
        if auth is True:
            save_debrid_settings(user_debrid)
    if auth is False:
        ui.notify("Debrid not active")

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

    elif mode == 'reset_auth':
        user_debrid = user_debrid.__class__()
        save_debrid_settings(user_debrid)

    elif mode == 'downloads':
        torrents = user_debrid.downloads()
        for cached, name, url in torrents:
            if cached:
                li = xbmcgui.ListItem('[COLOR green]' + name + '[/COLOR]')
                li.setProperty('IsPlayable', 'true')
                li.setInfo('video', {'title': name,
                                     'mediatype': 'video',})
                # Premiumize DL list is direct link
                if not isinstance(user_debrid, debrid.Premiumize):
                    url = build_url(mode='vid', link=url)
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)
            else:
                url = build_url(mode='noop')
                li = xbmcgui.ListItem('[COLOR red]'+name+'[/COLOR]')
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)
        xbmcplugin.endOfDirectory(addon_handle)

    elif mode in ['list', 'search', 'imdb', 'tvdb']:
        cats = []
        for name, cat_id in rarbg_categories.iteritems():
            if addon.getSettingBool(name):
                cats.append(cat_id)
        sstring = None
        category = ';'.join(cats)
        ranked = int(addon.getSettingBool('search_ranked'))
        fn_filter = None
        if mode == 'list':
            torrents = torrentapi_req(mode='list', category=category, ranked=ranked)['torrent_results']
        if mode == 'search':
            if not args.get('search'):
                sstring = get_user_input()
            else:
                sstring = args['search']
            torrents = torrentapi_req(mode='search', category=category, search_string=sstring, ranked=ranked)['torrent_results']
        if mode == 'imdb':
            torrents = torrentapi_req(mode='search', category=category, search_imdb=args['search'], ranked=ranked)['torrent_results']
        if mode == 'tvdb':
            episode = int(args['episode'])
            season = int(args['season'])
            for sstring in episode_search_strings(season, episode):
                torrents = torrentapi_req(mode='search', category=category, search_tvdb=args['search'], search_string=sstring, ranked=ranked).get('torrent_results')
                if torrents:
                    break
            else:
                raise Exception('No Torrents Found')
            fn_filter = episode_file_filter(season, episode)
        caches = user_debrid.check_availability([tor['download'] for tor in torrents], fn_filter=fn_filter)
        names_urls = []
        for torrent, cache in zip(torrents, caches):
            if cache:
                names_urls.append(('[COLOR green]' + torrent['filename'] + '[/COLOR]',
                                   build_url(mode='vid', magnet=torrent['download'], cache=cache)))
            else:
                names_urls.append(('[COLOR red]' + torrent['filename'] + '[/COLOR]',
                                   build_url(mode='tor', magnet=torrent['download'])))
        if mode in ['imdb', 'tvdb']:
            media_url = ''
            if names_urls:
                selected = ui.dialog_select(zip(*names_urls)[0])
                failed = False
                if selected >= 0:
                    torrent = torrents[selected]
                    cache = caches[selected]
                    if cache:
                        # RealDebrid is single file only, use cached fileid
                        if isinstance(user_debrid, debrid.RealDebrid):
                            fn_filter = cache
                        media_url = user_debrid.resolve_url(torrent['download'], fn_filter=fn_filter)
                    else:
                        failed = True
                        add_torrent(user_debrid, torrent['download'], fn_filter=fn_filter)
                else:
                    failed = True
            else:
                failed = True
            li = xbmcgui.ListItem(path=media_url)
            xbmcplugin.setResolvedUrl(addon_handle, not failed, li)
        else:
            ui.directory_view(addon_handle, names_urls, videos=True)

    elif mode == 'vid':
        if args.get('link'):
            url = user_debrid.unrestrict(args['link'])
        else:
            url = user_debrid.resolve_url(args['magnet'], args['cache'])
        li = xbmcgui.ListItem(path=url)
        xbmcplugin.setResolvedUrl(addon_handle, True, li)

    elif mode == 'tor':
        add_torrent(user_debrid, args['magnet'])

if __name__ == '__main__':
    main()
