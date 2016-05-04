# -*- coding: UTF-8 -*-
""" TVNext implementation for tvdb """

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__author__ = "d01"
__copyright__ = "Copyright (C) 2016, Florian JUNG"
__license__ = "MIT"
__version__ = "0.1.0"
__date__ = "2016-04-29"
# Created: 2015-04-29 19:15

import datetime

import dateutil
import pytz
import tvdb_api
from tvdb_api import BaseUI
from tvdb_api import tvdb_attributenotfound, tvdb_episodenotfound, \
    tvdb_seasonnotfound, tvdb_shownotfound, tvdb_userabort

from .tv_next import TVNext


class TVNextTVDB(TVNext, BaseUI):
    """
    Check tv shows with tvdb
    """

    class TVDBUI(BaseUI):
        """ Class to select a show based on year """
        # pylint: disable=invalid-name

        def selectSeries(self, allSeries):
            key = self.getSearchKey()
            spl = key.split()
            if spl[-1].startswith("(") and spl[-1].endswith(")"):
                year = spl[-1][1:-1]
                for series in allSeries:
                    if series['firstaired'].split('-')[0] == year:
                        # Same year -> assume this one
                        return series
            return allSeries[0]

    def __init__(self, settings=None):
        if settings is None:
            settings = {}
        super(TVNextTVDB, self).__init__(settings)

        cache = True
        if self._cache_path:
            cache = self._cache_path
        self._tvdb = tvdb_api.Tvdb(cache=cache, custom_ui=self.TVDBUI)

    def show_update(self, key, autosave=False):
        """
        Update show (and adds it if not already present)

        :param key: Show name
        :type key: str
        :param autosave: Save after update (default: False)
        :type autosave: bool
        :rtype: None
        """
        def _get_search_key(other): # pylint: disable=unused-argument
            return key
        self.debug(u"Updating {}".format(key))
        show = self._shows.setdefault(key, {})
        now = pytz.utc.localize(datetime.datetime.utcnow())
        self.TVDBUI.getSearchKey = _get_search_key
        try:
            tvdb_show = self._tvdb[key]
        except tvdb_shownotfound as e:
            self.error(u"Show {}: {}".format(key, e))
            year = key.split()[-1]
            if year.startswith("(") and year.endswith(")"):
                # Assume year info
                new_key = key.rstrip(" " + year)
                self.info(u"Trying {} instead".format(new_key))
                # Try without year info
                try:
                    tvdb_show = self._tvdb[new_key]
                except tvdb_shownotfound as e2:
                    self.error(u"Show {}: {}".format(new_key, e2))
                    return
            else:
                return
        # for item in tvdb_show[0][1].keys():
        #    self.debug(u"\n     {}: {}".format(item, tvdb_show[0][1][item]))
        # self.debug(u"{}".format(tvdb_show))
        show['id_tvdb'] = tvdb_show['id']
        show['id_imdb'] = tvdb_show['imdb_id']
        show['name'] = tvdb_show['seriesname']
        show['overview'] = tvdb_show['overview']
        show['status'] = tvdb_show.get('status', "").upper()
        show['active'] = show['status'] != "ENDED"
        show['hiatus'] = False
        show['air_duration'] = tvdb_show['runtime']
        show['air_day'] = tvdb_show['airs_dayofweek']
        show['air_time'] = tvdb_show['airs_time']
        show.setdefault('air_timezone', self._timezone)
        if isinstance(show['air_timezone'], basestring):
            show['air_timezone'] = pytz.timezone(show['air_timezone'])
        if show['air_time']:
            show['air_time'] = dateutil.parser.parse(show['air_time']).time()
        # Either correct time
        # or last possible second on that day (-> upper bound)
        air_time = show['air_time'] or datetime.time(23, 59, 59)
        episodes = {}
        for season_nr in tvdb_show:
            episodes.setdefault(season_nr, {})
            # episode db id name: id_<unique_name_for_source>
            for episode_nr in tvdb_show[season_nr]:
                episodes[season_nr][episode_nr] = {
                    'id_tvdb': tvdb_show[season_nr][episode_nr]['id'],
                    'id_imdb': tvdb_show[season_nr][episode_nr]['imdb_id'],
                    'aired': None,
                    'name': tvdb_show[season_nr][episode_nr]['episodename'],
                    'id': u"{:02d}x{:02d}".format(season_nr, episode_nr)
                }
                aired = tvdb_show[season_nr][episode_nr]['firstaired']
                if aired:
                    # Use datetime instead of date for tz info localization
                    aired = dateutil.parser.parse(aired)
                if aired and air_time:
                    aired = datetime.datetime.combine(
                        aired.date(), air_time
                    )
                    # Set origin tz
                    aired = show['air_timezone'].localize(aired)
                    # Convert to utc
                    aired = aired.astimezone(pytz.utc)
                episodes[season_nr][episode_nr]['aired'] = aired

        show['episodes'] = episodes
        show['accessed'] = now
        show['errors'] = 0

        if autosave and self._cache_file:
            self.show_save_all()
