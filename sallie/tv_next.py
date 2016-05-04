# -*- coding: UTF-8 -*-
""" Base class for tv checks """

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__author__ = "d01"
__copyright__ = "Copyright (C) 2014-16, Florian JUNG"
__license__ = "MIT"
__version__ = "0.5.3a0"
__date__ = "2016-05-04"
# Created: 2014-05-18 04:08

import datetime
from datetime import timedelta
import time
import os
import logging
from collections import OrderedDict
from abc import ABCMeta, abstractmethod

import pytz
from past.builtins import basestring
from future.utils import with_metaclass

from flotils.loadable import Loadable, DateTimeEncoder, DateTimeDecoder
from flotils.logable import ModuleLogable


class Logger(ModuleLogable):
    """ Module logger """
    pass


logger = Logger() # pylint: disable=invalid-name


class JSONDecoder(DateTimeDecoder):
    """ Extend DateTimeDecoder with tzinfo field """

    @staticmethod
    def _as_tzinfo(dct):
        if u"__pytzinfo__" in dct.keys():
            return pytz.timezone(dct['__pytzinfo__'])
        raise TypeError("Not pytzinfo")

    @staticmethod
    def decode(dct):
        try:
            return JSONDecoder._as_tzinfo(dct)
        except:
            return super(JSONDecoder, JSONDecoder).decode(dct)


class JSONEncoder(DateTimeEncoder):
    """ Extend DateTimeEncoder with tzinfo field """

    def default(self, obj):
        if isinstance(obj, datetime.tzinfo):
            return obj.zone
        else:
            return super(JSONEncoder, self).default(obj)


class TVNext(with_metaclass(ABCMeta, Loadable)):
    """
    Abstract checker for new tv episodes
    """

    def __init__(self, settings=None):
        """
        Initialise instance

        :param settings: Settings
        :type settings: None | dict
        :rtype: None
        """
        if settings is None:
            settings = {}
        super(TVNext, self).__init__(settings)

        self._shows = OrderedDict(settings.get('shows', {}))
        """ Show information
            :type : dict[unicode, dict[unicode, bool | unicode | \
            datetime.time | datetime.datetime | int | dict[unicode, dict[\
            unicode, unicode | datetime.datetime]]] """
        self._cache_path = settings.get('cache_path', None)
        """ Path to cache directory (default: None)
            :type _cache_path: None | str """
        self._cache_file = settings.get('cache_file', "sallie.tmp.json")
        """ Cache information file on shows (default: sallie.tmp.json)
            :type : str """
        self._show_file = settings.get('show_file', None)
        """ File of show names (default: None)
            :type : None | str """

        self._access_interval = settings.get('update_interval', 7)
        """ Refresh data every x days for active shows (default: 1)
            :type : int """
        self._access_interval_hiatus = settings.get(
            'update_interval_hiatus', None
        )
        """ Refresh interval for shows marked as hiatus (default: None)
        :type : None | int """
        self._access_interval_inactive = settings.get(
            'update_interval_inactive', None
        )
        """ Refresh interval for shows marked as inactive (default: None)
        :type : None | int """
        self._access_interval_aired = settings.get(
            'update_interval_aired', None
        )
        """ Refresh interval for shows after a new episode aired within \
            the last x days (default: None)
            :type : None | int """
        self._access_interval_error = settings.get(
            'update_interval_error', 10
        )
        """ Refresh interval for shows with error loading (min) (default: 10)
        :type : int """

        self._requests_per_minute = settings.get(
            'update_requests_per_minute', 0
        )
        """ Request per minute using the api - 0 means unlimited (default: 0)
            :type : int """

        self._timezone = settings.get('timezone_default', "US/Pacific")
        """ Timezone to be used if not provided for show
            :type : datetime.timezone """

        if isinstance(self._timezone, basestring):
            # If given as name -> convert to timezone with pytz
            self._timezone = pytz.timezone(self._timezone)

        self._requests = []
        self._error_sleep_time = settings.get('update_retry_delay', 2.0)
        """ Time to sleep after error
            :type : float """
        self._max_retries = settings.get('update_retry_num', 3)
        """ Maximum number of retries on load failure
            :type : int """
        self._should_retry = settings.get('update_retry', True)
        """ Should be retried
            :type : bool """

        if self._cache_path:
            self._cache_path = self.joinPathPrefix(self._cache_path)
        if self._cache_file:
            self._cache_file = os.path.join(self._cache_path, self._cache_file)

            if os.path.exists(self._cache_file):
                shows = self._loadJSONFile(
                    self._cache_file, decoder=JSONDecoder
                )
                shows.update(self._shows)
                self._shows.update(shows)
            # Don't care whether cache file exitsts -> generate it
            # else:
            #    raise IOError(u"File '{}' not found".format(self._showPath))
        if self._show_file:
            self.show_name_file_load()

    def show_name_file_load(self):
        """
        Load file containing show names

        :rtype: None
        :raises IOError: File not found
        :raises IOError: Failed to load
        """
        self._show_file = self.joinPathPrefix(self._show_file)

        if os.path.exists(self._show_file):
            show_names = self._loadJSONFile(
                self._show_file, decoder=JSONDecoder
            )
            """ :type : list[str | (str, str)] """

            for name in show_names:
                timezone = self._timezone
                if isinstance(name, list):
                    name, timezone = name
                if isinstance(timezone, basestring):
                    timezone = pytz.timezone(timezone)
                self._shows.setdefault(name, {})
                self._shows[name]['air_timezone'] = timezone
        else:
            raise IOError(u"File '{}' not found".format(self._show_file))
        self.debug(u"Loaded show names from {}".format(self._show_file))

    @property
    def shows(self):
        """
        Show information

        :return: Shows being watched watching
        :rtype: dict[unicode, dict[unicode, bool | unicode | datetime.time | \
        datetime.datetime | int | dict[unicode, dict[\
        unicode, unicode | datetime.datetime]]]
        """
        return self._shows

    def show_save_all(self, path=None):
        """
        Save shows

        :param path: Path to save to (default: None)
            if None -> use cache_file
        :type path: None | unicode
        :rtype: None
        """
        if not path:
            path = self._cache_file
        try:
            self._saveJSONFile(
                path,
                self._shows,
                pretty=True,
                sort=True,
                encoder=JSONEncoder
            )
            self.info(u"Saved shows to {}".format(path))
        except:
            self.exception(u"Failed to save shows to {}".format(path))

    def show_episodes_flatten(self, key, show=None):
        """
        Get a (flat) list of this shows episodes

        :param key: Show key
        :type key: unicode
        :param show: Show information (default: None)
            if None -> use key to retrieve show information
        :type show: dict[unicode, bool | unicode | datetime.time | \
        datetime.datetime | int | dict[unicode, dict[\
        unicode, unicode | datetime.datetime]]
        :return: Episode list
        :rtype: list[dict[unicode, unicode | datetime.datetime]]
        """
        if not show:
            show = self._shows[key]
        eps = show['episodes']
        return [eps[s_nr][e_nr] for s_nr in eps for e_nr in eps[s_nr]]

    def show_update_should(self, key):
        """
        Decide if show needs updating

        :param key: Show key
        :type key: unicode
        :return: Should show be updated
        :rtype: bool
        """
        show = self._shows[key]
        now = pytz.utc.localize(datetime.datetime.utcnow())

        # set defaults
        show.setdefault('active', True)
        show.setdefault('hiatus', False)
        show.setdefault('episodes', {})
        accessed = show.get('accessed', None)
        episodes = self.show_episodes_flatten(key, show)

        diff = None
        """ :type : datetime.timedelta """

        if accessed:
            diff = now - accessed
        else:
            self.info(u"Never accessed {}".format(key))
            return True
        # Update if errors last time
        if show.get('errors', 0) >= 3 and \
                diff.total_seconds() / 60 >= self._access_interval_error:
            self.info(u"Error retry {}".format(key))
            # Only retry once
            show['errors'] = max(1, self._max_retries - 1)
            return True

        if self._access_interval_aired is not None:
            # Update after new episode aired (in last x days)
            # Reverse list (newest first)
            for ep in episodes[::-1]:
                aired = ep['aired']
                """ :type : datetime.datetime """
                if not aired:
                    # Skip with no air dates
                    continue
                # TODO: make sure tzinfo is correctly loaded
                if aired.tzinfo is None:
                    self.warning(u"Unset tzinfo in {} ({})".format(
                        key, ep['id']
                    ))
                    aired = pytz.utc.localize(aired)
                if aired > now:
                    # Skip not aired yet
                    continue
                if (aired - accessed).days >= self._access_interval_aired:
                    # Last access before aired
                    self.debug(u"Aired {} ago {}".format(now - aired, key))
                    return True
                else:
                    # Out of reach
                    break
        if not show['active']:
            # Update inactive shows every so often in case they were mislabeled
            if diff is not None and self._access_interval_inactive:
                # self.debug("Inactive {} ago {}".format(diff, key))
                return diff.days >= self._access_interval_inactive
            # self.debug("{} inactive".format(key))
            return False
        if show['hiatus']:
            # Update shows on hiatus every so often in case episodes got added
            if diff is not None and self._access_interval_hiatus:
                # self.debug("Hiatus {} ago {}".format(diff, key))
                return diff.days >= self._access_interval_hiatus
            # self.debug("{} hiatus".format(key))
            return False

        # self.debug("Last access {} ago {}".format(diff, key))
        # Use generic access interval
        return diff.days >= self._access_interval

    @abstractmethod
    def show_update(self, key, autosave=False):
        """
        Update show (and adds it if not already present)

        :param key: Show name
        :type key: unicode
        :param autosave: Save after update (default: False)
        :type autosave: bool
        :rtype: None
        """
        raise NotImplementedError

    def show_update_all(self, forcecheck=False, autosave=False):
        """
        Update information for all shows

        :param forcecheck: Force information load (default: False)
        :type forcecheck: bool
        :param autosave: Save after each update (default: False)
        :type autosave: bool
        :rtype: None
        """
        shows = self._shows
        for key in sorted(shows):
            if not (forcecheck or self.show_update_should(key)):
                continue
            retry = True
            error_sleep = self._error_sleep_time
            shows[key].setdefault('errors', 0)

            while retry \
                    and shows[key]['errors'] < self._max_retries:
                retry = False

                # TODO: move into implementation (Backoff exception?)
                try:
                    self.show_update(key, autosave)
                except Exception as e:
                    if "connection reset by peer" in str(e).lower():
                        # Connection reset by peer -> exponential backoff
                        self.warning(
                            u"Connection reset by peer (Sleeping {})".format(
                                error_sleep
                            )
                        )
                        time.sleep(error_sleep)
                        error_sleep *= 2.0
                    else:
                        self.exception(u"Failed to load {}".format(key))
                    shows[key]['errors'] += 1
                    retry = self._should_retry
        if not autosave:
            self.show_save_all()

    def check(self, force_check=False, delta_min=None, delta_max=None,
              autosave=False):
        results = []
        if delta_min is None:
            delta_min = timedelta()
        if delta_max is None:
            delta_max = timedelta()

        self._requests = []
        self.show_update_all(force_check, autosave)
        now = pytz.utc.localize(datetime.datetime.utcnow()).date()
        day_min = now - delta_min
        day_max = now + delta_max
        if day_min > day_max:
            day_min, day_max = day_max, day_min
        # self.info("Searching between {} and {}".format(day_min, day_max))
        for key in sorted(self._shows):
            show = self._shows[key]
            episodes = self.show_episodes_flatten(key, show)
            temp = []

            # More likely that recent epsiode selected -> backwards
            for ep in episodes[::-1]:
                d = ep['aired']
                if not d:
                    # self.debug(u"No aired: {}.{}".format(key, ep['id']))
                    continue
                d = d.date()
                # if d < day_min:
                #    break
                if d > day_max or d < day_min:
                    # Out of range
                    continue
                temp.append(ep.copy())
            results.extend([(key, ep) for ep in temp])

        return results
