import calendar
from datetime import datetime

TRIAL_MONTHS = 6
TRIAL_SLOTS = 50


def add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def trial_end_date(start: datetime) -> datetime:
    return add_months(start, TRIAL_MONTHS)
