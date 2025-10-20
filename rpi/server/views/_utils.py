from datetime import datetime, timedelta

from flask import Request


class BadParameter(Exception): ...


def get_qs(request: Request) -> tuple[int, datetime]:
    try:
        hours = int(request.args.get("hours", 3))
    except ValueError as err:
        raise BadParameter("Parameter needs to be an integer") from err
    if hours > 24:
        raise BadParameter("Can't look past 24 hours")
    return hours, datetime.utcnow() - timedelta(hours=hours)
