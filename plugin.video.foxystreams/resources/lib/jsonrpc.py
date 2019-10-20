import json

import xbmc


def rpc(method, **params):
    """JSON-RPC call function.

    method -- string containing method to call.
    params -- keyword args translated to params object.

    JSON serialisation and deserialisation is handled.
    """
    data = {
        'jsonrpc': '2.0',
        'id': '1',
    }
    data['method'] = method
    if params:
        data['params'] = params
    return json.loads(xbmc.executeJSONRPC(json.dumps(data)))


def is_filter(field, value):
    """Returns exact string matching filter."""
    return {
        'field': field,
        'operator': 'is',
        'value': value,
    }


def and_filters(filters):
    """Returns and filter object for list of filters."""
    if len(filters) == 1:
        return filters[0]
    return {
        'and': filters,
    }


def get_episodes(tvshowid=None, properties=('showtitle',), **field_value):
    """Convenience function for `VideoLibrary.GetEpisodes` method."""
    params = {
        'properties': list(properties),
    }
    if tvshowid:
        params['tvshowid'] = tvshowid
    if field_value:
        params.update({
            'filter': and_filters([is_filter(field, value)
                                   for field, value in field_value.items()]),
        })
    return rpc('VideoLibrary.GetEpisodes', **params)['result']


def get_shows(**field_value):
    """Convenience function for `VideoLibrary.GetTVShows` method."""
    params = {
        'filter': and_filters([is_filter(field, value)
                               for field, value in field_value.items()]),
    }
    return rpc('VideoLibrary.GetTVShows', **params)['result']


def get_movies(**field_value):
    """Convenience function for `VideoLibrary.GetMovies` method."""
    params = {
        'filter': and_filters([is_filter(field, value)
                               for field, value in field_value.items()]),
    }
    return rpc('VideoLibrary.GetMovies', **params)['result']


def episode_library_id(showtitle, season, episode):
    """Returns library episodeid."""
    shows = get_shows(title=showtitle)['tvshows']
    if len(shows) != 1:
        return None
    tvshowid = shows[0]['tvshowid']
    result = get_episodes(tvshowid, season=str(season), episode=str(episode))
    episodes = result['episodes']
    if len(episodes) != 1:
        return None
    return episodes[0]['episodeid']


def movie_library_id(title):
    """Returns library movieid."""
    result = get_movies(title=title)
    if result['limits']['total'] != 1:
        return None
    return result['movies'][0]['movieid']


def set_episode_resume(episodeid, seconds):
    """Convienence function to set resume time."""
    params = {
        'episodeid': episodeid,
        'resume': {
            'position': seconds,
        },
    }
    return rpc('VideoLibrary.SetEpisodeDetails', **params)


def get_episode_resume(episodeid):
    """Convienence function to get resume time."""
    params = {
        'episodeid': episodeid,
        'properties': ['resume'],
    }
    result = rpc('VideoLibrary.GetEpisodeDetails', **params)['result']
    if 'resume' in result['episodedetails']:
        return result['episodedetails']['resume']['position']
    return None


def set_movie_resume(movieid, seconds):
    """Convienence function to set resume time."""
    params = {
        'movieid': movieid,
        'resume': {
            'position': seconds,
        },
    }
    return rpc('VideoLibrary.SetMovieDetails', **params)


def get_movie_resume(movieid):
    """Convienence function to get resume time."""
    params = {
        'movieid': movieid,
        'properties': ['resume'],
    }
    result = rpc('VideoLibrary.GetMovieDetails', **params)['result']
    if 'resume' in result['moviedetails']:
        return result['moviedetails']['resume']['position']
    return None


def set_movie_watched(movieid):
    """Convienence function to mark as watched."""
    params = {
        'movieid': movieid,
        'playcount': 1,
    }
    return rpc('VideoLibrary.SetMovieDetails', **params)


def set_episode_watched(episodeid):
    """Convienence function to mark as watched."""
    params = {
        'episodeid': episodeid,
        'playcount': 1,
    }
    return rpc('VideoLibrary.SetEpisodeDetails', **params)
