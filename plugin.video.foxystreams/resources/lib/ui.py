import xbmc
import xbmcgui
import xbmcplugin


def build_listitems(names, videos=False):
    listitems = []
    for name in names:
        li = xbmcgui.ListItem(name)
        if videos:
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {
                'title': name,
                'mediatype': 'video',
            })
        listitems.append(li)
    return listitems


def get_user_input(title='Search'):
    return xbmcgui.Dialog().input(title)


def directory_view(handle, names_urls, videos=False, folders=False, more=False):
    if names_urls:
        names, urls = zip(*names_urls)
        true_list = [folders] * len(names)
        listitems = build_listitems(names, videos=videos)
        xbmcplugin.addDirectoryItems(handle=handle,
                                     items=zip(urls, listitems, true_list))
    if more:
        return
    xbmcplugin.endOfDirectory(handle=handle)


def dialog_select(names):
    listitems = build_listitems(names)
    return xbmcgui.Dialog().select('Select', listitems)


def notify(message):
    xbmc.executebuiltin('Notification(FoxyStreams, {})'.format(message))


def add_torrent(user_debrid, magnet, fn_filter=None):
    status = user_debrid.grab_torrent(magnet, fn_filter=fn_filter)
    if status:
        notify('Added Torrent to Debrid')
    else:
        xbmc.executebuiltin('Notification(FoxyStreams, FAILED)')
        notify('Failed to add to Debrid')


def metadata_from(args):
    metadata = {
        'info': {
            'title': args.get('title', ''),
            'plot': args.get('plot', ''),
            'genre': args.get('genre', ''),
            'votes': args.get('votes', ''),
            'rating': args.get('rating', ''),
            'year': args.get('year', ''),
            'mpaa': args.get('mpaa', ''),
        },
        'art': {
            'poster': args.get('poster', ''),
            'fanart': args.get('fanart', ''),
        },
    }
    info = metadata['info']
    if args['mode'] == 'imdb':
        info['mediatype'] = 'movie'
        info['originaltitle'] = args.get('originaltitle', '')
        info['premiered'] = args.get('premiered', '')
    elif args['mode'] == 'tvdb':
        info['mediatype'] = 'episode'
        info['episode'] = args.get('episode', '')
        info['season'] = args.get('season', '')
        info['tvshowtitle'] = args.get('tvshowtitle', '')
        info['originaltitle'] = args.get('tvshowtitle', '')
        info['aired'] = args.get('aired', '')
    return metadata
