# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

__author__ = "d01"
__email__ = "jungflor@gmail.com"
__copyright__ = "Copyright (C) 2016, Florian JUNG"
__license__ = "MIT"
__version__ = "0.1.0"
__date__ = "2016-05-12"
# Created: 2016-05-12 18:04

import argparse
import datetime
import logging.config

import pytz
from flotils import ModuleLogable
from flotils.logable import default_logging_config

from . import TVNextTVDB


class Logger(ModuleLogable):
    pass


logger = Logger()


def shows_format(shows_list):
    """
    Format a list of shows

    :param shows_list: Show list
    :type shows_list: list
    :return: List of formatted text
    :rtype: list[unicode]
    """
    omit_date = True
    date = None
    res = []
    now = pytz.utc.localize(datetime.datetime.utcnow()).date()

    for show, info in shows_list:
        if not info:
            continue
        omit_date &= bool(info.get('aired'))
        if not omit_date:
            break
        if not date:
            date = info['aired'].date()
            continue
        omit_date &= date == info['aired'].date()
    for show, info in shows_list:
        if not info:
            continue
        txt = u""
        name = info.get('name', "")
        nr = info['id']
        if info.get('aired'):
            if omit_date:
                txt += u"{}: ".format(info['aired'].strftime("%H:%M"))
            else:
                dfmt = info['aired'].strftime("%Y-%m-%d %H:%M")
                d = (now - info['aired'].date()).days
                txt += u"{} ({}): ".format(
                    dfmt,
                    u"{}d".format(abs(d))
                    if d < 0 else
                    "today" if d == 0 else u"{}d ago".format(d)
                )
        txt += u"{} ({}".format(show.upper(), nr)

        if name:
            txt += u" - {}".format(name)
        txt += u")"
        res.append(txt)
    return res


def to_string(evs):
    if isinstance(evs, list):
        msg = ""
        last = None
        for ev in sorted(evs, key=lambda x: x[1].get('date')):
            d = ev[1].get('date')
            if d and last != d.date():
                msg += u"{}{}{}".format(
                    "",
                    "\n" + d.strftime("%Y-%m-%d (%a)") + "\n" + "="*10,
                    "\n"
                )
                last = d.date()
            msg += u"  {}{}{}".format(
                "",
                to_string(ev),
                "\n"
            )

        msg += ""
        return msg

    show, info = evs
    name = info.get('name', "")
    date = info.get('date')
    if date:
        date = date.strftime("%Y-%m-%d") + " "
    else:
        date = ""
    #date = ""
    nr = info['episode']
    feedTxt = u"{}{} ({}".format(date, show, nr)

    if name:
        feedTxt += u" - {}".format(name)

    feedTxt += ")"
    return feedTxt


def shows_check(s, autosave, forcecheck, min_delta, max_delta):
    """
    Check for new shows

    :param s: Sallie instance
    :type s: sallie.TVNext
    :param autosave: Save after every request
    :type autosave: bool
    :param forcecheck: Force reload
    :type forcecheck: bool
    :param min_delta: Delta in days into the past
    :type min_delta: None | int
    :param max_delta: Delta in days into the future
    :type max_delta: None | int
    :rtype: None
    """
    if min_delta is not None:
        min_delta = datetime.timedelta(days=min_delta)
    if max_delta is not None:
        max_delta = datetime.timedelta(days=max_delta)
    res = s.check_all(
        delta_max=max_delta,
        delta_min=min_delta,
        auto_save=autosave,
        force_check=forcecheck
    )

    for txt in sorted(shows_format(res)):
        logger.info(txt)
    # logging.info(u"\n{}".format(toString(res)))


def shows_list(
        s, select, sort_by="", reverse=False, list_all=False,
        min_delta=None, max_delta=None):
    """

    :param s: Sallie instance
    :type s: sallie.TVNext
    :param select:
    :type select:
    :param sort_by: Sorts separated by ; (values: date, state)
    :type sort_by: str
    :param reverse: Reverse order (default: False)
    :type reverse: bool
    :param list_all: List all infos (default: False)
    :type list_all: bool
    :param min_delta: Delta in days into the past
    :type min_delta: None | int
    :param max_delta: Delta in days into the future
    :type max_delta: None | int
    :rtype: None
    """
    now = pytz.UTC.localize(datetime.datetime.utcnow())

    def get_state(show):
        if not show:
            return None
        active = show['active']
        hiatus = show['hiatus']
        if not active:
            state = "inactive"
        elif hiatus:
            state = "hiatus"
        else:
            state = "active"
        return state

    def get_aired(ep):
        return ep.get('aired') or datetime.datetime(1, 1, 1, tzinfo=pytz.UTC)

    def in_range(min_delta, ep, max_delta):
        date = get_aired(ep)
        # None -> dont care
        if min_delta is not None and now > date:
            if (now - date) < min_delta:
                return True
            return False
        if max_delta is not None and now <= date:
            if max_delta < (date - now):
                return True
            return False
        return True

    if min_delta is not None:
        min_delta = datetime.timedelta(days=min_delta)
    if max_delta is not None:
        max_delta = datetime.timedelta(days=max_delta)

    shows = s.shows
    sort_by = sort_by.split(";")
    if list_all:
        l = []
        if "state":
            res = {
                "active": [],
                "hiatus": [],
                "inactive": []
            }
            for key in sorted(shows):
                # logger.debug(shows[key])
                state = get_state(shows[key])
                if not state:
                    continue
                res[state].append(key)
            l.extend(res['active'])
            l.extend(res['hiatus'])
            l.extend(res['inactive'])
        if reverse:
            l = reversed(l)
        for key in l:
            state = get_state(shows[key])
            logger.info(u"{} ({})".format(key, state.upper()))
        return

    if select != "all":
        if select not in shows:
            logger.error(u"Show {} not found".format(select))
            return
        keys = [select]
    else:
        keys = shows.keys()
    unformatted = []
    """ :type: list[(str, object)] """

    for key in keys:
        eps = sorted(
            filter(
                lambda x: in_range(min_delta, x, max_delta),
                s.show_episodes_flatten(key)
            ),
            key=get_aired
        )
        unformatted.extend([(key, ep) for ep in eps])

    formatted = shows_format(unformatted)
    if "date" in sort_by:
        formatted = sorted(formatted, reverse=True)
    if reverse:
        formatted = reversed(formatted)
    for txt in formatted:
        logger.info(txt)


def shows_next(s, select, sort_by="", reverse=False, max_delta=None):
    """
    Show next aired episode of show(s)

    :param s: Sallie instance
    :type s: sallie.TVNext
    :param sort_by: Sorts separated by ; (values: date, state)
    :type sort_by: str
    :param reverse: Reverse order (default: False)
    :type reverse: bool
    :param max_delta: Delta in days into the future
    :type max_delta: None | int
    :rtype: None
    """
    now = pytz.UTC.localize(datetime.datetime.utcnow())

    def get_aired(ep):
        return ep.get('aired') or datetime.datetime(1, 1, 1, tzinfo=pytz.UTC)

    def in_range(min_delta, ep, max_delta):
        date = get_aired(ep)
        # None -> dont care
        if min_delta is not None and now > date:
            if (now - date) < min_delta:
                return True
            return False
        if max_delta is not None and now <= date:
            if max_delta < (date - now):
                return True
            return False
        return True

    min_delta = datetime.timedelta(days=0)
    if max_delta is not None:
        max_delta = datetime.timedelta(days=max_delta)

    shows = s.shows

    if select != "all":
        if select not in shows:
            logger.error(u"Show {} not found".format(select))
            return
        keys = [select]
    else:
        keys = shows.keys()
    unformatted = []
    """ :type: list[(str, object)] """

    for key in keys:
        eps = sorted(
            filter(
                lambda x: in_range(min_delta, x, max_delta),
                s.show_episodes_flatten(key)
            ),
            key=get_aired
        )
        if eps:
            unformatted.append((key, eps[0]))

    formatted = shows_format(unformatted)
    if "date" in sort_by:
        formatted = sorted(formatted, reverse=True)
    if reverse:
        formatted = reversed(formatted)
    for txt in formatted:
        logger.info(txt)


def setup_parser():
    """
    Create and init argument parser

    :return: Argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(prog="sallie")
    parser.add_argument(
        "--debug", action="store_true",
        help="Use debug level output"
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )
    parser.add_argument(
        "-s", "--settings", nargs="?", default="sallie.json",
        help="Settings file"
    )
    parser.add_argument(
        "--pre_path", nargs="?", default=None,
        help="Base path to use"
    )
    parser.add_argument(
        "-c", "--check", nargs="?", const=True, default=False,
        help="Check for new shows in given period"
    )
    parser.add_argument(
        "--min", nargs="?", type=int, const=None, default=None,
        help="How many days in the past to check"
    )
    parser.add_argument(
        "--max", nargs="?", type=int, const=1, default=None,
        help="How many days in the future to check"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force updates independently from update rules"
    )
    parser.add_argument(
        "--autosave", action="store_true",
        help="Auto save after every show"
    )
    parser.add_argument(
        "--missing", action="store_true",
        help="Which shows have no episodes"
    )
    parser.add_argument(
        "--update", nargs="?", const="all", default=None,
        help="Run a show update; Default: all - check for all shows or "
             "specify a show"
    )
    parser.add_argument(
        "--shows", nargs="?", const=True, default=False,
        help="List all monitored shows"
    )
    parser.add_argument(
        "--list", nargs="?", const="all", default=None,
        help="List episodes; Default: all - check for all shows or "
             "specify a show"
    )
    parser.add_argument(
        "--next", nargs="?", const="all", default=None,
        help="Show next upcoming episode; Default: all - check for all shows "
             "or specify a show"
    )
    parser.add_argument(
        "--sort", nargs="?", type=str, const="date;state", default="date;state",
        help="Order to sort outout; Default: date;state"
    )
    parser.add_argument(
        "--reverse", action="store_false",
        help="Reverse order"
    )
    parser.add_argument(
        "--all", nargs="?", const=True, default=False,
        help="Do to all"
    )

    return parser


def main():
    logging.config.dictConfig(default_logging_config)
    logging.getLogger().setLevel(logging.INFO)

    parser = setup_parser()
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    tv = TVNextTVDB({
        'settings_file': args.settings,
        'path_prefix': args.pre_path
    })

    tv.start(blocking=False)
    check = args.check
    if args.update:
        check = False
        if args.update == "all":
            tv.show_update_all(force_check=args.force, auto_save=args.autosave)
            check = True
        elif args.update not in tv.shows:
            logger.error(u"Show {} not found".format(args.update))
        else:
            tv.show_update(args.update, auto_save=args.autosave)
    if args.list:
        shows_list(
            tv, args.list, args.sort, args.reverse, args.all,
            args.min, args.max
        )
    elif args.next:
        shows_next(tv, args.next, args.sort, args.reverse, args.max)
    elif args.shows:
        for key in sorted(tv.shows, reverse=not args.reverse):
            logger.info(u"{}".format(key))
    elif args.missing:
        for key in sorted(tv.shows, reverse=not args.reverse):
            if len(tv.show_episodes_flatten(key)) == 0:
                logger.info(u"Missing episodes for {}".format(key))
    else:
        check = True
    if check:
        shows_check(
            tv,
            autosave=args.autosave, forcecheck=args.force,
            min_delta=args.min, max_delta=args.max
        )
