from datetime import datetime, timedelta, timezone
from mcp.server.fastmcp import FastMCP

_FORMATS = {
    "iso":      "%Y-%m-%dT%H:%M:%S",
    "date":     "%Y-%m-%d",
    "time":     "%H:%M:%S",
    "human":    "%B %d, %Y %I:%M %p",
    "short":    "%d/%m/%Y",
    "us":       "%m/%d/%Y",
    "log":      "%Y%m%d_%H%M%S",
}

_TIMEZONES = {
    "utc": 0, "gmt": 0,
    "est": -5, "edt": -4,
    "cst": -6, "cdt": -5,
    "mst": -7, "mdt": -6,
    "pst": -8, "pdt": -7,
    "london": 0, "paris": 1, "berlin": 1,
    "dubai": 4, "india": 5, "ist": 5,
    "singapore": 8, "sgt": 8, "cst_china": 8,
    "japan": 9, "jst": 9, "korea": 9,
    "sydney": 10, "aest": 10,
    "malaysia": 8, "myt": 8,
}


def register_datetime_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    def get_datetime(timezone_name: str = "utc", fmt: str = "human") -> str:
        """
        Get the current date and time in a given timezone.
        timezone_name: utc, est, pst, india, singapore, japan, malaysia, sydney, paris, dubai, etc.
        fmt: output format — 'iso', 'date', 'time', 'human' (default), 'short', 'us', 'log'.
        Returns formatted datetime string.
        """
        tz_key = timezone_name.lower().strip()
        offset = _TIMEZONES.get(tz_key)
        if offset is None:
            return f"Unknown timezone '{timezone_name}'. Available: {', '.join(_TIMEZONES.keys())}"
        tz = timezone(timedelta(hours=offset))
        now = datetime.now(tz)
        fmt_str = _FORMATS.get(fmt, _FORMATS["human"])
        return f"{now.strftime(fmt_str)} ({timezone_name.upper()}, UTC{'+' if offset >= 0 else ''}{offset})"

    @mcp.tool()
    def date_diff(date1: str, date2: str) -> str:
        """
        Calculate the difference between two dates.
        date1, date2: dates in YYYY-MM-DD format, e.g. '2024-01-01' and '2026-06-21'.
        Returns the difference in days, weeks, months, and years.
        """
        try:
            d1 = datetime.strptime(date1.strip(), "%Y-%m-%d")
            d2 = datetime.strptime(date2.strip(), "%Y-%m-%d")
            delta = abs((d2 - d1).days)
            direction = "after" if d2 >= d1 else "before"
            return (
                f"{date2} is {direction} {date1}\n"
                f"Days   : {delta}\n"
                f"Weeks  : {delta // 7} weeks, {delta % 7} days\n"
                f"Months : ~{delta // 30} months\n"
                f"Years  : ~{delta / 365.25:.2f} years"
            )
        except ValueError as e:
            return f"Error: invalid date format — use YYYY-MM-DD. ({e})"

    @mcp.tool()
    def add_days(date: str, days: int) -> str:
        """
        Add or subtract days from a date.
        date: starting date in YYYY-MM-DD format.
        days: number of days to add (use negative to subtract).
        Returns the resulting date in multiple formats.
        """
        try:
            d = datetime.strptime(date.strip(), "%Y-%m-%d")
            result = d + timedelta(days=days)
            direction = "Added" if days >= 0 else "Subtracted"
            return (
                f"{direction} {abs(days)} days from {date}:\n"
                f"ISO    : {result.strftime('%Y-%m-%d')}\n"
                f"Human  : {result.strftime('%B %d, %Y')}\n"
                f"Weekday: {result.strftime('%A')}"
            )
        except ValueError as e:
            return f"Error: invalid date — use YYYY-MM-DD. ({e})"

    @mcp.tool()
    def format_date(date: str, output_fmt: str = "human") -> str:
        """
        Convert a date string between formats.
        date: input date — accepts YYYY-MM-DD, DD/MM/YYYY, or MM/DD/YYYY.
        output_fmt: 'iso', 'date', 'human', 'short', 'us', 'log'.
        Returns the reformatted date string.
        """
        parsed = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed = datetime.strptime(date.strip(), fmt)
                break
            except ValueError:
                continue
        if not parsed:
            return f"Error: could not parse '{date}'. Try YYYY-MM-DD format."
        fmt_str = _FORMATS.get(output_fmt, _FORMATS["human"])
        return parsed.strftime(fmt_str)

    @mcp.tool()
    def timezone_convert(time_str: str, from_tz: str, to_tz: str) -> str:
        """
        Convert a time from one timezone to another.
        time_str: time in HH:MM format, e.g. '14:30'.
        from_tz: source timezone (utc, est, pst, india, singapore, japan, malaysia, etc.)
        to_tz: target timezone (same options).
        Returns the converted time with UTC offset info.
        """
        from_offset = _TIMEZONES.get(from_tz.lower())
        to_offset   = _TIMEZONES.get(to_tz.lower())
        if from_offset is None:
            return f"Unknown timezone '{from_tz}'. Available: {', '.join(_TIMEZONES.keys())}"
        if to_offset is None:
            return f"Unknown timezone '{to_tz}'. Available: {', '.join(_TIMEZONES.keys())}"
        try:
            h, m = map(int, time_str.strip().split(":"))
            total_minutes = h * 60 + m
            diff_minutes  = (to_offset - from_offset) * 60
            result_minutes = (total_minutes + diff_minutes) % (24 * 60)
            rh, rm = divmod(result_minutes, 60)
            return (
                f"{time_str} {from_tz.upper()} (UTC{'+' if from_offset >= 0 else ''}{from_offset})\n"
                f"= {rh:02d}:{rm:02d} {to_tz.upper()} (UTC{'+' if to_offset >= 0 else ''}{to_offset})"
            )
        except Exception as e:
            return f"Error: {e}. Use HH:MM format for time."
