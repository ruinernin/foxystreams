from .router import router

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


def directory_view(names_urls, contexts=False, videos=False, folders=False,
                   more=False):
    if names_urls:
        if contexts:
            names, urls, contexts = zip(*names_urls)
        else:
            names, urls = zip(*names_urls)
            contexts = []
        true_list = [folders] * len(names)
        listitems = build_listitems(names, videos=videos)
        for context in contexts:
            for li in listitems:
                li.addContextMenuItems(context)
        xbmcplugin.addDirectoryItems(handle=router.handle,
                                     items=zip(urls, listitems, true_list))
    if videos:
        xbmcplugin.setContent(router.handle, 'videos')
    if more:
        return
    xbmcplugin.endOfDirectory(handle=router.handle)


def dialog_select(names):
    listitems = build_listitems(names)
    return xbmcgui.Dialog().select('Select', listitems)


def notify(message):
    xbmc.executebuiltin('Notification(FoxyStreams, {})'.format(message))


def add_torrent(user_debrid, magnet, fn_filter=None):
    dialog = xbmcgui.DialogProgressBG()
    dialog.create('Adding To Debrid')
    status = user_debrid.grab_torrent(magnet, fn_filter=fn_filter)
    dialog.close()
    if status:
        notify('Added Torrent to Debrid')
    else:
        notify('Failed to add to Debrid')
