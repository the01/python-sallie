# -*- coding: UTF-8 -*-
""" Base class for tv checks """

__author__ = "d01"
__copyright__ = "Copyright (C) 2014-20, Florian JUNG"
__license__ = "MIT"
__version__ = "0.6.8"
__date__ = "2020-05-11"
# Created: 2014-05-18 04:08

import abc
from collections import OrderedDict
import datetime
from datetime import timedelta
import os
import shutil
import threading
import time
import typing

import flotils
import pytz


logger = flotils.get_logger()


class TVNextException(Exception):
    """ Base exception for project """

    pass


class TVNextFatalException(Exception):
    """ Exception that can not be recovered from """

    pass


class TVNextNotFoundException(Exception):
    """ Show not found """

    pass


class JSONDecoder(flotils.loadable.DateTimeDecoder):
    """ Extend DateTimeDecoder with tzinfo field """

    @staticmethod
    def _as_tzinfo(dct):
        if "__pytzinfo__" in dct.keys():
            return pytz.timezone(dct['__pytzinfo__'])
        raise TypeError("Not pytzinfo")

    @staticmethod
    def decode(dct: typing.Any) -> typing.Any:
        """ Decode object """
        try:
            if isinstance(dct, dict):
                return JSONDecoder._as_tzinfo(dct)
        except Exception:
            pass
        res = super(JSONDecoder, JSONDecoder).decode(dct)
        if isinstance(res, datetime.datetime):
            res = res.replace(tzinfo=pytz.UTC)
        return res


class JSONEncoder(flotils.loadable.DateTimeEncoder):
    """ Extend DateTimeEncoder with tzinfo field """

    def default(self, obj: typing.Any) -> typing.Any:
        """ Encode object """
        if isinstance(obj, datetime.tzinfo):
            return obj.zone
        else:
            return super(JSONEncoder, self).default(obj)


class TVNext(flotils.Loadable, flotils.StartStopable, abc.ABC):
    """ Abstract checker for new tv episodes """

    def __init__(
            self,
            settings: typing.Optional[typing.Dict[str, typing.Any]] = None
    ) -> None:
        """
        Initialise instance

        :param settings: Settings
        """
        if settings is None:
            settings = {}
        super().__init__(settings)

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
        """ Refresh interval for shows marked as hiatus in days (default: None)
        :type : None | int """
        self._access_interval_inactive = settings.get(
            'update_interval_inactive', None
        )
        """ Refresh interval for shows marked as inactive in days (default: None)
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

        self._timezone = settings.get('timezone_default', "US/Pacific")
        """ Timezone to be used if not provided for show
            :type : datetime.timezone """

        if isinstance(self._timezone, str):
            # If given as name -> convert to timezone with pytz
            self._timezone = pytz.timezone(self._timezone)

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
            self._cache_path = self.join_path_prefix(self._cache_path)

            if self._cache_file:
                self._cache_file = os.path.join(
                    self._cache_path, self._cache_file
                )

        self._lock_update = threading.RLock()
        """ Lock to prevent concurrent access
            :type : threading.RLock """

    def start(self, blocking: bool = False) -> None:
        """
        Start the interface

        :param blocking: Should the call block until stop() is called
            (default: False)
        """
        if self._cache_file and os.path.exists(self._cache_file):
            shows = self._load_json_file(
                self._cache_file, decoder=JSONDecoder
            )
            shows.update(self._shows)
            self._shows.update(shows)
        # Don't care whether cache file exitsts -> generate it
        # else:
        #    raise IOError("File '{}' not found".format(self._showPath))
        if self._show_file:
            self.show_name_file_load()
        super(TVNext, self).start(blocking)

    def stop(self) -> None:
        """ Stop the interface """
        self.debug("()")
        super(TVNext, self).stop()
        # self.show_save_all()

    def show_name_file_load(self) -> None:
        """
        Load file containing show names

        :raises IOError: File not found
        :raises IOError: Failed to load
        """
        self._show_file = self.join_path_prefix(self._show_file)

        if os.path.exists(self._show_file):
            show_names: typing.List[
                typing.Union[str, typing.Tuple[str, str]]
            ] = self._load_json_file(
                self._show_file, decoder=JSONDecoder
            )
            """ :type : list[str | (str, str)] """

            for name in show_names:
                timezone = self._timezone
                if isinstance(name, list):
                    name, timezone = name
                if isinstance(timezone, str):
                    timezone = pytz.timezone(timezone)
                self._shows.setdefault(name, {})
                self._shows[name]['air_timezone'] = timezone
        else:
            raise IOError("File '{}' not found".format(self._show_file))
        self.debug("Loaded show names from {}".format(self._show_file))

    def show_add(self, show: str, timezone: typing.Optional = None) -> None:
        """
        Add new show with default params

        :param show: Name of show
        :param timezone: Timezone to add - None means no timezone
            (Default: None)
        """
        if isinstance(timezone, str):
            timezone = pytz.timezone(timezone)
        with self._lock_update:
            self._shows.setdefault(show, {})
            if timezone:
                self._shows[show]['air_timezone'] = timezone

    def show_remove(self, show: str) -> None:
        """
        Remove show

        :param show: Name of show
        """
        with self._lock_update:
            if show in self._shows:
                del self._shows[show]

    @property
    def shows(self) -> typing.Dict[str, typing.Dict[str, typing.Union[
        str, bool, datetime.time, datetime.datetime, int,
        typing.Dict[
            str, typing.Dict[str, typing.Union[str, datetime.datetime]]
        ]
    ]]]:
        """
        Show information

        :return: Shows being watched watching
        """
        return self._shows

    def show_save_all(self, path: typing.Optional[str] = None) -> None:
        """
        Save shows cache

        :param path: Path to save to (default: None)
            if None -> use cache_file
        """
        if not path:
            path = self._cache_file
        temp_path = path + "temp.json"
        try:
            self._save_json_file(
                temp_path,
                self._shows,
                pretty=True,
                sort=True,
                encoder=JSONEncoder
            )
            shutil.move(temp_path, path)
            self.info("Saved shows to {}".format(path))
        except Exception:
            self.exception("Failed to save shows to {}".format(path))

    def show_episodes_flatten(
            self, key: str, show: typing.Optional = None
    ) -> typing.List[typing.Dict[str, typing.Union[str, datetime.datetime]]]:
        """
        Get a (flat) list of this shows episodes

        :param key: Show key
        :param show: Show information (default: None)
            if None -> use key to retrieve show information
        :type show: dict[unicode, bool | unicode | datetime.time | \
            datetime.datetime | int | dict[unicode, dict[\
            unicode, unicode | datetime.datetime]]
        :return: Episode list
        """
        if not show:
            show = self._shows[key]
        eps = show['episodes']
        return [eps[s_nr][e_nr] for s_nr in eps for e_nr in eps[s_nr]]

    def show_update_should(self, key: str, force_check: bool = False) -> bool:
        """
        Decide if show needs updating

        :param key: Show key
        :param force_check: Force checking
        :return: Should show be updated
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
            self.info("Never accessed {}".format(key))
            return True
        # Update if errors last time
        if show.get('errors', 0) >= 3 and \
                (diff.days >= self._access_interval_error or force_check):
            self.info("Error retry {}".format(key))
            # Only retry once
            show['errors'] = max(1, self._max_retries - 1)
            return True

        if force_check:
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
                    self.warning("Unset tzinfo in {} ({})".format(
                        key, ep['id']
                    ))
                    aired = pytz.utc.localize(aired)
                if aired > now:
                    # Skip not aired yet
                    continue
                if (aired - accessed).days >= self._access_interval_aired:
                    # Last access before aired
                    self.debug("Aired {} ago {}".format(now - aired, key))
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

    def show_update(
            self, key: str, force_check: bool = False, auto_save: bool = False
    ) -> bool:
        """
        Update show (and adds it if not already present)

        :param key: Show name
        :param force_check: Force information load (default: False)
        :param auto_save: Save after update (default: False)
        :return: Changed
        """
        if not self.show_update_should(key, force_check):
            # Show information already up to date
            return False
        changed = False
        retry = True
        error_sleep = self._error_sleep_time
        self.shows[key].setdefault('errors', 0)

        while retry \
                and self.shows[key]['errors'] < self._max_retries:
            retry = False

            # TODO: move into implementation (Backoff exception?) - fatal
            try:
                changed = self._show_update(key)
            except TVNextNotFoundException:
                # Show not found
                self.shows[key]['errors'] = self._max_retries
                self.shows[key]['accessed'] = pytz.utc.localize(
                    datetime.datetime.utcnow()
                )
                changed = True
                break
            except Exception as e:
                if "connection reset by peer" in "{}".format(e).lower():
                    # Connection reset by peer -> exponential backoff
                    self.warning(
                        "Connection reset by peer (Sleeping {})".format(
                            error_sleep
                        )
                    )
                    time.sleep(error_sleep)
                    error_sleep *= 2.0
                else:
                    self.exception("Failed to load {}".format(key))
                self.shows[key]['errors'] += 1
                retry = self._should_retry
                changed = True

        if auto_save and changed:
            self.show_save_all()
        return changed

    @abc.abstractmethod
    def _show_update(self, key: str) -> bool:
        """
        Update show (and adds it if not already present)

        Overwrite to implement

        :param key: Show name
        :return: Changed
        """
        raise NotImplementedError

    def show_update_all(
            self, force_check: bool = False, auto_save: bool = False,
    ) -> None:
        """
        Update information for all shows

        :param force_check: Force information load (default: False)
        :param auto_save: Save after each update (default: False)
        """
        shows = self._shows
        changed = False
        for key in sorted(shows):
            changed = self.show_update(key, force_check, auto_save) or changed
        if not auto_save and changed:
            self.show_save_all()

    def check(
            self,
            key: str,
            force_check: bool = False,
            delta_min: typing.Optional[typing.Union[
                int, datetime.date, datetime.timedelta
            ]] = None,
            delta_max: typing.Optional[typing.Union[
                int, datetime.date, datetime.timedelta
            ]] = None,
            auto_save: bool = False,
    ) -> typing.List[typing.Tuple[str, typing.Dict]]:
        """
        Check a single show for updates in a period
        (adds it if not already present and updates info)

        :param key: Show to check
        :param force_check:  Force information load (default: False)
        :param delta_min: Time in the past (either date or delta from now)
        :param delta_max: Time in the future (either date or delta from now)
        :param auto_save: Save after each update (default: False)
        :return: Show, episode pair matching the query
        """
        if not self.is_running:
            self.warning("Not running")
        # Delta as ints = days
        if isinstance(delta_min, int):
            delta_min = timedelta(days=delta_min)
        if isinstance(delta_max, int):
            delta_max = timedelta(days=delta_max)
        # Delta defaults
        if delta_min is None:
            delta_min = timedelta()
        if delta_max is None:
            delta_max = timedelta()

        now = pytz.utc.localize(datetime.datetime.utcnow()).date()
        if isinstance(delta_min, datetime.date):
            # Delta as date
            day_min = delta_min
        else:
            # Delta as timedelta
            day_min = now - delta_min
        if isinstance(delta_max, datetime.date):
            # Delta as date
            day_max = delta_max
        else:
            # Delta as timedelta
            day_max = now + delta_max

        # Wrong order
        if day_min > day_max:
            day_min, day_max = day_max, day_min

        with self._lock_update:
            if key not in self.shows:
                # Add missing
                self.show_add(key)
            # Update info
            self.show_update(key, force_check, auto_save)

            # self.info("Searching between {} and {}".format(day_min, day_max))
            show = self.shows[key]
            episodes = self.show_episodes_flatten(key, show)
            results = []

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
                results.append((key, ep.copy()))
            return results

    def check_all(
            self,
            keys: typing.Optional[typing.List[str]] = None,
            delta_min: typing.Optional[typing.Union[
                int, datetime.date, datetime.timedelta
            ]] = None,
            delta_max: typing.Optional[typing.Union[
                int, datetime.date, datetime.timedelta
            ]] = None,
            force_check: bool = False,
            auto_save: bool = False,
    ) -> typing.List[typing.Tuple[str, typing.Dict]]:
        """
        Check multiple shows for updates in a period
        (adds it if not already present and updates info)

        :param keys: Shows to check; None -> check all (default: None)
        :param force_check:  Force information load (default: False)
        :param delta_min: Time in the past (either date or delta from now)
        :param delta_max: Time in the future (either date or delta from now)
        :param auto_save: Save after each update (default: False)
        :return: Show, episode pair matching the query
        """
        if not self._is_running:
            self.warning("Not running")
        results = []
        with self._lock_update:
            if keys is None:
                keys = sorted(list(self.shows))
                self.show_update_all(force_check, auto_save)
                # All updates allready done
                force_check = False
                auto_save = False
            for key in keys:
                results.extend(
                    self.check(
                        key, force_check=force_check, auto_save=auto_save,
                        delta_min=delta_min, delta_max=delta_max
                    )
                )
        return results
