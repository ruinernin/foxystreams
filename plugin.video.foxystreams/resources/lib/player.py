"""
This module is purely for providing resume functionality for videos played by
external launches (e.g. OpenMeta).
"""

import datetime
import time
from functools import wraps

import xbmc
import xbmcgui

from . import jsonrpc


def cache(func):
    """Cache wrapper for when Player has stopped."""

    cache_attr = '__cache_{}'.format(func.__name__)

    @wraps(func)
    def wrapper(self):
        """If player is stopped return last value."""
        if self.isPlaying():
            setattr(self, cache_attr, func(self))
        return getattr(self, cache_attr, None)
    return wrapper


class FoxyPlayer(xbmc.Player):
    """xbmc.Player object used for resume functionality."""

    def run(self):
        """Loop to keep script alive and update resume time."""
        start = time.time()
        timeout = 20
        while True:
            if self.isPlayingVideo():
                xbmc.sleep(2 * 1000)
                break
            if time.time() > start + timeout:
                break
            xbmc.sleep(1 * 1000)
        while self.isPlayingVideo():
            if not self.library_id:
                # There's nothing to do
                break
            self.resume_time = int(self.getTime())
            xbmc.sleep(60 * 1000)

    @property
    @cache
    def library_id(self):
        """Kodi libraryID of video being played.

        Returns the last return value from a previous call if playback
        is stopped.
        """
        info_tag = self.getVideoInfoTag()
        if self.is_episode:
            return jsonrpc.episode_library_id(info_tag.getTVShowTitle(),
                                              info_tag.getSeason(),
                                              info_tag.getEpisode())
        elif self.is_movie:
            return jsonrpc.movie_library_id(info_tag.getTitle())
        return None

    @property
    @cache
    def is_episode(self):
        """True if currently playing item has 'episode' InfoTag.

        Returns the last return value from a previous call if playback
        is stopped.
        """
        return self.getVideoInfoTag().getMediaType() == 'episode'

    @property
    @cache
    def is_movie(self):
        """True if currently playing item has 'movie' InfoTag.

        Returns the last return value from a previous call if playback
        is stopped.
        """
        return self.getVideoInfoTag().getMediaType() == 'movie'

    @property
    @cache
    def resume_time(self):
        """Resume time for currently playing item in library.

        Returns the last return value from a previous call if playback
        is stopped.
        """
        if self.library_id:
            if self.is_movie:
                return jsonrpc.get_movie_resume(self.library_id)
            elif self.is_episode:
                return jsonrpc.get_episode_resume(self.library_id)
        return None

    @resume_time.setter
    def resume_time(self, value):
        if self.library_id:
            if self.is_movie:
                jsonrpc.set_movie_resume(self.library_id, value)
            elif self.is_episode:
                jsonrpc.set_episode_resume(self.library_id, value)

    def watched(self):
        if self.library_id:
            if self.is_movie:
                jsonrpc.set_movie_watched(self.library_id)
            elif self.is_episode:
                jsonrpc.set_episode_watched(self.library_id)

    def onAVStarted(self):
        """Ask user if they want to resume if a resume time is found."""
        xbmc.sleep(2 * 1000)
        seconds = self.resume_time
        if seconds:
            human_timestamp = str(datetime.timedelta(seconds=seconds))
            self.pause()
            if xbmcgui.Dialog().yesno("Resume at", human_timestamp):
                self.seekTime(seconds)
            self.pause()

    def onPlayBackPaused(self):
        self.resume_time = int(self.getTime())

    def onPlayBackEnded(self):
        self.resume_time = 0
        self.watched()
