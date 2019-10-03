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

def directory_view(handle, names_urls, videos=False, folders=False, more=False):
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
