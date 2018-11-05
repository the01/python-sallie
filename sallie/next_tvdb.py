# -*- coding: UTF-8 -*-
""" TVNext implementation for tvdb """

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__author__ = "d01"
__copyright__ = "Copyright (C) 2016-18, Florian JUNG"
__license__ = "MIT"
__version__ = "0.2.4"
__date__ = "2018-11-05"
# Created: 2015-04-29 19:15

import datetime

from flotils import get_logger
import dateutil
import pytz
import tvdb_api
from tvdb_api import BaseUI
from tvdb_api import tvdb_attributenotfound, tvdb_episodenotfound, \
    tvdb_seasonnotfound, tvdb_shownotfound, tvdb_userabort

from .tv_next import TVNext


logger = get_logger()


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
                    if series.get('firstaired') and \
                                    series['firstaired'].split('-')[0] == year:
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
        self.debug("Using cache at {}".format(self._cache_path))
        self.debug("Using cache file {}".format(self._cache_file))
        self._tvdb_cache = cache
        self._tvdb = None
        self._init_tvdb()

    def _init_tvdb(self):
        self.info("Initializing tvdb instance")
        self._tvdb = tvdb_api.Tvdb(
            cache=self._tvdb_cache, custom_ui=self.TVDBUI
        )

    def _key_error_retry(self, key):
        if self._tvdb is None:
            self._init_tvdb()
        try:
            return self._tvdb[key]
        except KeyError as e:
            self.warning("{}: Key error '{}'".format(key, e))
            self._init_tvdb()
            return self._tvdb[key]

    def _show_update(self, key):
        """
        Update show (and adds it if not already present)

        :param key: Show name
        :type key: str
        :rtype: None
        """
        def _get_search_key(other):  # pylint: disable=unused-argument
            return key
        self.debug("Updating {}".format(key))
        show = self._shows.setdefault(key, {})
        now = pytz.utc.localize(datetime.datetime.utcnow())
        self.TVDBUI.getSearchKey = _get_search_key
        try:
            tvdb_show = self._key_error_retry(key)
        except tvdb_shownotfound as e:
            self.error("Show {}: {}".format(key, e))
            year = key.split()[-1]
            if year.startswith("(") and year.endswith(")"):
                # Assume year info
                new_key = key.rstrip(" " + year)
                self.info("Trying {} instead".format(new_key))
                # Try without year info
                try:
                    tvdb_show = self._tvdb[new_key]
                except tvdb_shownotfound as e2:
                    self.error("Show {}: {}".format(new_key, e2))
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
