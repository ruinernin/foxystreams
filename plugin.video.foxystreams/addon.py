import functools
import inspect
import json
import urllib
import urlparse
import sys

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.foxydebrid import debrid, scrapers
from resources.lib import ui
from resources.lib.player import FoxyPlayer
from resources.lib.router import router



rarbg_categories = {
    'bd_remux': '46',
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


if router.handle > 0:
    xbmcplugin.setContent(router.handle, 'videos')


def migrate_config():
    """Changeable function that updates user config.

    If the settings change in settings.xml that are breaking between
    versions this function will migrate existing settings.
    """
    pass


def authenticate(user_debrid):
    debrid_auth = user_debrid.authenticate()
    if debrid_auth in (True, None):
        return True
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
    """Returns strings to be used when scraping for episodes."""
    string_templates = (
        's{season:02d}e{episode:02d}',
        '{season}x{episode:02d}',
        's{season:02d}',
    )
    return [template.format(season=season, episode=episode)
            for template in string_templates]


def episode_file_filter(season, episode):
    """Returns a function matching strings against season and episode.

    The need for this filter is generally encountered in 'Season Packs'
    where it is necessary to narrow down results to find the file we are
    interested in.
    """
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


def get_debrid_priority(debrid_name):
    """Get user set priority and add a fraction for stable sorting.

    The fraction added is the sum of ASCII values of debrid_name
    shifted 5 decimal places. We assume this is unique enough.
    """
    unique = sum(map(ord, debrid_name)) / (10.0 ** 5)
    return router.addon.getSettingInt('debrid_priority.' + debrid_name) + unique


def get_user_debrid_providers():
    providers = ['RealDebrid',
                 'Premiumize',
                 'AllDebrid']
    user_providers = [provider for provider in providers
                      if router.addon.getSettingBool(
                             'debrid_enabled.' + provider)]
    return sorted(user_providers, key=get_debrid_priority)


def get_debrid_provider(provider_name):
    """Returns a DebridProvider object created with saved settings."""
    provider = getattr(debrid, provider_name)
    cfg_str = '{}.{{}}'.format(provider_name)
    args, _, _, defaults = inspect.getargspec(provider.__init__)
    args = args[1:] # Strip self
    config_argvals = []
    for arg in args:
        config_setting = router.addon.getSetting(cfg_str.format(arg))
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
        router.addon.setSetting(cfg_str.format(arg),
                                str(getattr(provider, arg, '')))


def user_torrentapi_settings():
    cats = []
    for name, cat_id in rarbg_categories.iteritems():
        if router.addon.getSettingBool(name):
            cats.append(cat_id)
    category = ';'.join(cats)
    ranked = int(router.addon.getSettingBool('search_ranked'))
    return {
        'category': category,
        'ranked': ranked,
    }


def get_json_cache(name):
    addon_id = router.addon.getAddonInfo('id')
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
    return {k: v for k, v in cached_data.iteritems() if v}


def write_json_cache(name, cache):
    addon_id = router.addon.getAddonInfo('id')
    path = 'special://temp/{_id}.{name}.json'.format(_id=addon_id, name=name)
    path = xbmc.translatePath(path)
    try:
        with open(path, 'w') as cfile:
            json.dump(cache, cfile)
    except Exception:
        raise


@router.route('/history/delete')
def delhistory():
    write_json_cache('searches', dict())
    xbmc.executebuiltin('Container.Refresh()')


@router.route('/downloads')
def debrid_downloads():
    user_debrid = user_debrids[0]
    torrents = user_debrid.downloads()
    downloading = []
    downloaded = []
    for cached, name, url in torrents:
        if cached:
            # Premiumize DL list is direct link
            if not isinstance(user_debrid, debrid.Premiumize):
                url = router.build_url(debrid_resolve, link=url, _debrid=0)
            downloaded.append(('[COLOR green]'+name+'[/COLOR]', url))
        else:
            downloading.append(('[COLOR red]'+name+'[/COLOR]', ''))
    ui.directory_view(router.handle, downloading, more=True)
    ui.directory_view(router.handle, downloaded, videos=True)


@router.route('/debrid/play')
def debrid_resolve(_debrid=None, link=None, cache=None, magnet=None):
    user_debrid = user_debrids[int(_debrid)]
    if link:
        url = user_debrid.unrestrict(link)
    else:
        if isinstance(user_debrid, debrid.RealDebrid):
            fn_filter = cache
        else:
            fn_filter = None
        url = user_debrid.resolve_url(magnet, fn_filter)
    xbmcplugin.setResolvedUrl(router.handle,
                              True,
                              xbmcgui.ListItem(path=url))


@router.route('/torrent/add')
def get_torrent(magnet=None):
    ui.add_torrent(user_debrids[0], magnet)


@router.route('/play/movie')
def play_movie(**kwargs):
    root(metadata=False, mode='movie', **kwargs)


@router.route('/play/episode')
def play_episode(**kwargs):
    root(metadata=False, mode='tv', **kwargs)


@router.route('/reset_auth')
def reset_auth(provider=None):
    debrid_provider = getattr(debrid, provider)()
    save_debrid_settings(debrid_provider)


@router.route('/')
def root(mode=None, scraper=None, query=None, season=None, episode=None,
         metadata=True, **kwargs):
    """Business logic. `movie` and `tv` are from external plugins."""

    args = dict(urlparse.parse_qsl(sys.argv[2][1:]))

    # Set up scraper
    selected_scraper = scraper or router.addon.getSetting('scraper')
    cached_settings = get_json_cache(selected_scraper)
    scraper = getattr(scrapers, selected_scraper)()
    for attr in scraper.cache_attrs:
        if attr in cached_settings:
            setattr(scraper, attr, cached_settings[attr])
    if isinstance(scraper, scrapers.TorrentApi):
        find_magnets = functools.partial(scraper.find_magnets,
                                         **user_torrentapi_settings())
    else:
        find_magnets = scraper.find_magnets

    # Show root plugin directory
    searches = get_json_cache('searches').get('history', list())
    if mode is None:
        names_urls = []
        names_urls.append(('Downloads',
                           router.build_url(debrid_downloads)))
        names_urls.append(('List',
                           router.build_url(root, mode='list')))
        ui.directory_view(router.handle, names_urls, folders=True, more=True)
        names_urls = []
        names_urls.append(('Search',
                           router.build_url(root, mode='search')))
        names_urls.append(('Search History (Select to clear)',
                           router.build_url(delhistory)))
        ui.directory_view(router.handle, names_urls, folders=False, more=True)
        names_urls = []
        for search in searches:
            names_urls.append((search,
                               router.build_url(root,
                                                mode='search',
                                                query=search)))
        ui.directory_view(router.handle, names_urls, folders=True)
        return

    # Scraping
    fn_filter = None
    if mode == 'search':
        if not query:
            query = ui.get_user_input()
            if not query:
                return
            url = router.build_url(root, mode='search', query=query)
            xbmc.executebuiltin('Container.Update({})'.format(url))
            return
        names_magnets = find_magnets(query=query)
        try:
            searches.remove(query)
        except ValueError:
            pass
        searches.insert(0, query)
        write_json_cache('searches', {'history': searches})
    if mode == 'list':
        names_magnets = find_magnets()
    if mode == 'movie':
        names_magnets = find_magnets(movie=True, **args)
    if mode == 'tv':
        season = int(season)
        episode = int(episode)
        for query in episode_search_strings(season, episode):
            names_magnets = list(find_magnets(tv=True, query=query, **args))
            if names_magnets:
                break
        else:
            # Do something to say nothing found TV specific
            pass
        fn_filter = episode_file_filter(season, episode)
    # Save anything cachable for future runs (e.g. tokens, cookies, etc.)
    write_json_cache(scraper.__class__.__name__,
                     {attr: getattr(scraper, attr)
                      for attr in scraper.cache_attrs})

    # Providing
    if not names_magnets:
        ui.notify('No results found')
        router.fail()
        return
    names, magnets = zip(*names_magnets)
    names = list(names)
    magnets = list(magnets)
    cached = [(False, False)] * len(magnets)
    for debrid_idx, user_debrid in enumerate(user_debrids):
        to_check = [(idx, magnets[idx]) for idx, cache in enumerate(cached)
                    if not cache[1]]
        if not to_check:
            break
        caches = user_debrid.check_availability(zip(*to_check)[1],
                                                fn_filter=fn_filter)
        for (idx, _), cache in zip(to_check, caches):
            if cache:
                cached[idx] = (debrid_idx, cache)
    cached_names_magnets = []
    uncached_names_magnets = []
    for name, magnet, (debrid_idx, cache) in zip(names, magnets, cached):
        if cache:
            cached_names_magnets.append(('[COLOR green]'+name+'[/COLOR]',
                                         magnet, cache, debrid_idx))
        else:
            uncached_names_magnets.append(('[COLOR red]'+name+'[/COLOR]',
                                           magnet, cache, 0))
    if router.addon.getSettingBool('show_cached_only'):
        uncached_names_magnets = []

    # Display results
    if mode in ('movie', 'tv'):
        all_names_magnets = cached_names_magnets + uncached_names_magnets
        media_url = ''
        if all_names_magnets:
            selected = None
            if router.addon.getSettingBool('auto_select') and cached_names_magnets:
                for idx, name in enumerate(zip(*cached_names_magnets)[0]):
                    if '.hdr.' in name.lower():
                        selected = idx
                        break
                    if '.2160p.' in name.lower():
                        selected = idx
                        break
                    if '.1080p.' in name.lower():
                        selected = idx
                        break
                    if '.720p.' in name.lower():
                        selected = idx
                        break
                else:
                    selected = 0
            if selected is None:
                selected = ui.dialog_select(zip(*all_names_magnets)[0])
            if selected >= 0:
                _, magnet, cache, i = all_names_magnets[selected]
                user_debrid = user_debrids[i]
                if cache:
                    if isinstance(user_debrid, debrid.RealDebrid):
                        _fn_filter = cache
                    else:
                        _fn_filter = fn_filter
                    media_url = user_debrid.resolve_url(magnet,
                                                        fn_filter=_fn_filter)
                else:
                    ui.add_torrent(user_debrid, magnet, fn_filter=fn_filter)
        li = xbmcgui.ListItem(path=media_url)
        if metadata:
            mdata = ui.metadata_from(args)
            li.setInfo('video', mdata['info'])
            mediatype = mdata['info'].get('mediatype')
            if mediatype:
                li.setInfo('videos', {'mediatype': mediatype})
            li.setArt(mdata['art'])
            player = FoxyPlayer()
        xbmcplugin.setResolvedUrl(router.handle, bool(media_url), li)
        xbmcgui.Window(10000).setProperty('foxymeta.nativeplay', 'True')
        if media_url and metadata:
            player.run()
    if mode in ['list', 'search']:
        names_urls = [(name, router.build_url(debrid_resolve,
                                              magnet=magnet,
                                              cache=cache,
                                              _debrid=i))
                      for name, magnet, cache, i in cached_names_magnets]
        ui.directory_view(router.handle, names_urls, videos=True, more=True)
        names_urls = [(name, router.build_url(get_torrent, magnet=magnet))
                      for name, magnet, cache, i in uncached_names_magnets]
        ui.directory_view(router.handle, names_urls)


user_debrids = []
def run(url, handle, qs):
    global user_debrids
    user_debrids = []
    for provider in get_user_debrid_providers():
        user_debrid = get_debrid_provider(provider)
        if authenticate(user_debrid):
            save_debrid_settings(user_debrid)
            user_debrids.append(user_debrid)
        else:
            ui.notify(provider + " not active")
    if not user_debrids:
        ui.notify("No Debrid service active")
    router.run(url, handle, qs)
