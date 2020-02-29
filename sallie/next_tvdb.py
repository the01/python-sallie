# -*- coding: UTF-8 -*-
""" TVNext implementation for tvdb """

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__author__ = "d01"
__copyright__ = "Copyright (C) 2016-20, Florian JUNG"
__license__ = "MIT"
__version__ = "0.2.8"
__date__ = "2020-02-29"
# Created: 2015-04-29 19:15

import datetime
import difflib

import flotils
import dateutil
import dateutil.parser
import pytz
from past.builtins import basestring
import tvdb_api

from .tv_next import TVNext, TVNextNotFoundException


logger = flotils.get_logger()


class TVNextTVDB(TVNext):
    """
    Check tv shows with tvdb
    """

    class TVDBUI(tvdb_api.BaseUI):
        """ Class to select a show based on year """
        # pylint: disable=invalid-name

        current = None

        def selectSeries(self, allSeries):
            tvnext = self.config['tvnext']
            """ :type : TVNextTVDB """

            key = self.current['key']
            year = self.current.get('year')
            allSeries = [
                (
                    series,
                    difflib.SequenceMatcher(
                        None, key, series.get('seriesName', "")
                    ).ratio()
                )
                for series in allSeries
            ]
            allSeries.sort(key=lambda x: x[1], reverse=True)
            tvnext.debug(
                "Options: {}".format(",".join([
                    "{} ({:.2f})".format(series.get('seriesName'), ratio)
                    for series, ratio in allSeries
                ])
            ))
            parts = key.split()

            if year:
                year = parts[-1][1:-1]
                for series, ratio in allSeries:
                    if series.get('firstAired') and \
                            series['firstAired'].split('-')[0] == year:
                        # Same year -> assume this one
                        return series
            return allSeries[0][0]

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
        self.debug("Initializing tvdb instance..")
        self._tvdb = tvdb_api.Tvdb(
            cache=self._tvdb_cache, custom_ui=self.TVDBUI
        )
        if self._tvdb_cache:
            # Fix tvdb_api bug
            self._tvdb.config['cache_enabled'] = True
        else:
            self._tvdb.config['cache_enabled'] = False
        self._tvdb.config['tvnext'] = self
        self.info("TVDB instance initialized")

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
        :return: Changed (Might not really have changed - but successfull read)
        :rtype: bool
        """
        self.debug("Updating {}..".format(key))
        changed = False
        show = self._shows.setdefault(key, {})
        now = pytz.utc.localize(datetime.datetime.utcnow())
        year = None
        year_part = key.split()[-1]

        if year_part.startswith("(") and year_part.endswith(")"):
            # Assume year info
            year = year_part[1:-1]

        self.TVDBUI.current = {
            'key': key,
            'year': year,
        }

        try:
            tvdb_show = self._key_error_retry(key)
        except tvdb_api.tvdb_shownotfound as e:
            if year:
                # Assume year info
                new_key = " ".join(key.split()[:-1])
                self.info("Trying {} instead..".format(new_key))
                # Try without year info
                try:
                    tvdb_show = self._tvdb[new_key]
                except tvdb_api.tvdb_shownotfound as e2:
                    self.error("Show {}: {}".format(new_key, e2))
                    raise TVNextNotFoundException(new_key)
            else:
                self.error("Show {}: {}".format(key, e))
                raise TVNextNotFoundException(key)

        # self.debug("{}".format(tvdb_show))
        # for key, item in tvdb_show.data.items():
        #    self.debug("\n {}: {}".format(key, item))
        # for key, item in tvdb_show.items():
        #    self.debug("\n {}: {}".format(key, item))
        # for item in tvdb_show[0][1].keys():
        #    self.debug("\n     {}: {}".format(item, tvdb_show[0][1][item]))
        show['id_tvdb'] = tvdb_show['id']
        show['id_imdb'] = tvdb_show['imdbId']
        show['name'] = tvdb_show['seriesname']
        show['overview'] = tvdb_show['overview']
        show['status'] = tvdb_show.data.get('status', "").upper()
        show['active'] = show['status'] != "ENDED"
        show['hiatus'] = False
        show['air_duration'] = tvdb_show['runtime']
        show['air_day'] = tvdb_show['airsDayOfWeek']
        show['air_time'] = tvdb_show['airsTime']
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
                # for key, item in tvdb_show[season_nr][episode_nr].items():
                #     self.debug("\nep:  {}: {}".format(key, item))
                episodes[season_nr][episode_nr] = {
                    'id_tvdb': tvdb_show[season_nr][episode_nr]['id'],
                    'id_imdb': tvdb_show[season_nr][episode_nr]['imdbId'],
                    'aired': None,
                    'name': tvdb_show[season_nr][episode_nr]['episodeName'],
                    'id': u"{:02d}x{:02d}".format(season_nr, episode_nr)
                }
                aired = tvdb_show[season_nr][episode_nr]['firstAired']
                if aired:
                    # Use datetime instead of date for tz info localization
                    try:
                        aired = dateutil.parser.parse(aired)
                    except:
                        if aired == "0000-00-00":
                            self.error("Invalid aired date: {}-{}x{}".format(
                                key, season_nr, episode_nr
                            ))
                        else:
                            self.exception("Failed to parse date: {}".format(
                                aired
                            ))
                        aired = None
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
        # Might not really have changed - but successfull read
        return True
