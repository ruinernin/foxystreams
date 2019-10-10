import functools
import inspect
import json
import urllib
import urlparse
import sys

import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib import debrid, ui, scrapers


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


def user_torrentapi_settings():
    cats = []
    for name, cat_id in rarbg_categories.iteritems():
        if addon.getSettingBool(name):
            cats.append(cat_id)
    category = ';'.join(cats)
    ranked = int(addon.getSettingBool('search_ranked'))
    return {
        'category': category,
        'ranked': ranked,
    }


def get_json_cache(name):
    addon_id = addon.getAddonInfo('id')
    path = 'special://temp/{_id}.{name}.json'.format(_id=addon_id, name=name)
    path = xbmc.translatePath(path)
    try:
        with open(path) as cfile:
            cached_data = json.load(cfile)
    except IOError as ioerr:
        if ioerr.errno == 2:
            cached_data = {}
        else:
            raise
    return cached_data


def write_json_cache(name, cache):
    cache = {k: v for k, v in cache.iteritems() if not k.startswith('_')}
    addon_id = addon.getAddonInfo('id')
    path = 'special://temp/{_id}.{name}.json'.format(_id=addon_id, name=name)
    path = xbmc.translatePath(path)
    try:
        with open(path, 'w') as cfile:
            json.dump(cache, cfile)
    except Exception:
        raise


def main():
    """Business logic. `imdb` and `tvdb` are from external plugins."""
    # Set up provider and scraper
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
    user_cfg_scraper = args.get('scraper') or addon.getSetting('scraper')
    cached_settings = get_json_cache(user_cfg_scraper)
    scraper = getattr(scrapers,
                      user_cfg_scraper + '_factory')(**cached_settings)
    if scraper.func_name == 'torrentapi':
        scraper = functools.partial(scraper, **user_torrentapi_settings())

    # Show root plugin directory
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
        return

    if mode == 'vid':
        if args.get('link'):
            url = user_debrid.unrestrict(args['link'])
        else:
            url = user_debrid.resolve_url(args['magnet'], args['cache'])
        li = xbmcgui.ListItem(path=url)
        xbmcplugin.setResolvedUrl(addon_handle, True, li)
        return

    elif mode == 'tor':
        ui.add_torrent(user_debrid, args['magnet'])
        return

    # Clears Debrid provider settings
    if mode == 'reset_auth':
        user_debrid = user_debrid.__class__()
        save_debrid_settings(user_debrid)
        return

    # Show Debrid downloads as directory
    if mode == 'downloads':
        torrents = user_debrid.downloads()
        downloading = []
        downloaded = []
        for cached, name, url in torrents:
            if cached:
                # Premiumize DL list is direct link
                if not isinstance(user_debrid, debrid.Premiumize):
                    url = build_url(mode='vid', link=url)
                downloaded.append(('[COLOR green]'+name+'[/COLOR]', url))
            else:
                downloading.append(('[COLOR red]'+name+'[/COLOR]',
                                    build_url(mode='noop')))
        ui.directory_view(addon_handle, downloading, more=True)
        ui.directory_view(addon_handle, downloaded, videos=True)
        return

    # Scraping
    def find_magnets(query=None, tv=False, movie=False, imdb=None, tvdb=None,
                     season=None, episode=None, title=None, year=None):
        """Return a list of tuples [(name, magnet)]."""
        if isinstance(scraper, functools.partial):
            scraper_name = scraper.func.func_name
        else:
            scraper_name = scraper.func_name
        if not (query or tv or movie):
            if scraper_name == 'torrentapi':
                results = scraper(mode='list')
            if scraper_name == 'bitlord':
                results = scraper()
        elif movie:
            if scraper_name == 'torrentapi':
                results = scraper(mode='search', search_imdb=imdb)
            if scraper_name == 'bitlord':
                results = scraper(query='{} {}'.format(title, year),
                                  filters_field='seeds',
                                  filters_sort='desc')
        elif tv:
            for querystr in episode_search_strings(season, episode):
                results = scraper(mode='search', search_tvdb=tvdb,
                                  search_string=querystr)
                if results.get('torrent_results'):
                    break
            else:
                results = []
        elif query:
            if scraper_name == 'torrentapi':
                results = scraper(mode='search', search_string=query)
            if scraper_name == 'bitlord':
                results = scraper(query=query)
        if results and scraper_name == 'torrentapi':
            return [(t['filename'], t['download'])
                    for t in results['torrent_results']]
        if results and scraper_name == 'bitlord':
            return [(t['name'], t['magnet'])
                    for t in results['content']
                    if t['seeds'] > 0]

    fn_filter = None
    if mode == 'search':
        query = args.get('search') or ui.get_user_input()
        torrents = find_magnets(query=query)
    if mode == 'list':
        torrents = find_magnets()
    if mode == 'imdb':
        torrents = find_magnets(movie=True, imdb=args['search'],
                                title=args.get('title'),
                                year=args.get('year'))
    if mode == 'tvdb':
        season = int(args['season'])
        episode = int(args['episode'])
        torrents = find_magnets(tv=True, tvdb=args['search'], season=season,
                                episode=episode)
        fn_filter = episode_file_filter(season, episode)

    cleaned_torrents = []
    for name, magnet in torrents:
        try:
            str(name)
            str(magnet)
        except UnicodeEncodeError:
            continue
        else:
            cleaned_torrents.append((name, magnet))
    # Providing
    names, magnets = zip(*cleaned_torrents)
    names = list(names)
    magnets = list(magnets)
    caches = user_debrid.check_availability(magnets, fn_filter=fn_filter)
    names_urls = []
    for name, magnet, cache in zip(names, magnets, caches):
        if cache:
            names_urls.append(('[COLOR green]'+name+'[/COLOR]',
                               build_url(mode='vid', magnet=magnet, cache=cache)))
        else:
            names_urls.append(('[COLOR red]'+name+'[/COLOR]',
                               build_url(mode='tor', magnet=magnet)))


    # Display results
    if mode in ['imdb', 'tvdb']:
        media_url = ''
        if names_urls:
            selected = ui.dialog_select(zip(*names_urls)[0])
            if selected >= 0:
                magnet = magnets[selected]
                cache = caches[selected]
                if cache:
                    if isinstance(user_debrid, debrid.RealDebrid):
                        fn_filter = cache
                    media_url = user_debrid.resolve_url(magnet,
                                                        fn_filter=fn_filter)
                else:
                    ui.add_torrent(user_debrid, magnet, fn_filter=fn_filter)
        li = xbmcgui.ListItem(path=media_url)
        xbmcplugin.setResolvedUrl(addon_handle, bool(media_url), li)
    if mode in ['list', 'search']:
        ui.directory_view(addon_handle, names_urls, videos=True)

    if isinstance(scraper, functools.partial):
        scraper = scraper.func
    write_json_cache(scraper.func_name, scraper.func_dict)

if __name__ == '__main__':
    main()
