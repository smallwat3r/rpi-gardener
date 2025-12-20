from datetime import datetime, timedelta

from flask import Request

MIN_HOURS = 1
MAX_HOURS = 24
DEFAULT_HOURS = 3


class BadParameter(Exception): ...


def get_qs(request: Request) -> tuple[int, datetime]:
    try:
        hours = int(request.args.get("hours", DEFAULT_HOURS))
    except ValueError as err:
        raise BadParameter("Parameter needs to be an integer") from err
    if not (MIN_HOURS <= hours <= MAX_HOURS):
        raise BadParameter(f"Hours must be between {MIN_HOURS} and {MAX_HOURS}")
    return hours, datetime.utcnow() - timedelta(hours=hours)
