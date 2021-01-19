# from datetime_manipulation import create_count_week, strip_future_dates, convert_date_to_obsdt
# from datetime_manipulation import normalize_date_for_visits, normalize_date_for_details

from typing import List
import pandas as pd
from datetime import datetime
import dateutil.parser as parser


# We use parser liberally to avoid having lots more routines

def normalize_date_for_visits(date_str: str) -> str:
    # visits has e.g. obsDt 26 Dec 2020, with no leading zero for day
    # (e.g. 4 Jan 2020 not 04 Jan 2020)
    # was: convert_date_to_obsdt
    xdate = parser.parse(date_str).strftime('%d %b %Y')
    if xdate.startswith('0'):
        xdate = xdate[1:]

    return xdate


def normalize_date_for_details(date_str: str, date_only=True) -> str:
    # Parameters expects format '%Y-%m-%d'
    # returned from get_details: obsDt and creationDt: 2020-12-26 10:18
    # (e.g. 4 Jan 2020 not 04 Jan 2020)
    # was: convert_date_to_obsdt
    fmt = '%Y-%m-%d' if date_only else '%Y-%m-%d %H:%M'
    xdate = parser.parse(date_str).strftime(fmt)

    return xdate


def convert_date_range_to_date_str(drange) -> List[str]:
    return [ds.strftime('%Y-%m-%d') for ds in drange]


def strip_future_dates(dates: List[str]) -> List[str]:
    # dates is e.g. ['2020-12-18', '2020-12-19', '2020-12-20']
    non_future_dates = []
    now = datetime.now()
    for dd in dates:
        if datetime.strptime(dd, '%Y-%m-%d') <= now:
            non_future_dates.append(dd)

    return non_future_dates


def create_count_week(xstart: str, xend: str) -> List[str]:
    # e.g. start="2020-12-18",end="2020-12-24"
    drange = pd.date_range(start=xstart, end=xend)
    count_week = strip_future_dates(convert_date_range_to_date_str(drange))

    return count_week
