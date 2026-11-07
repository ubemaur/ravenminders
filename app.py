import calendar
import math
from datetime import date, datetime, time, timedelta

from flask import Flask, make_response, render_template, request, url_for

app = Flask(__name__)

MIN_YEAR, MAX_YEAR = 1900, 2100
DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# view key -> (button label, number of days shown; None = month grid)
VIEWS = {
    "day": ("1 day", 1),
    "3day": ("3 days", 3),
    "week": ("1 week", 7),
    "month": ("Month", None),
}
DEFAULT_VIEW = "month"

# The colors for each theme live in style.css under [data-theme="<key>"].
THEMES = {
    "velvet": "Velvet red",
    "burgundy": "Burgundy",
    "burnt-orange": "Burnt orange",
    "amber": "Amber",
    "terracotta": "Terracotta",
    "rose": "Rose",
}
DEFAULT_THEME = "velvet"

# Page background; colors live in style.css under [data-bg="<key>"].
BACKGROUNDS = {
    "cream": "Cream",
    "beige": "Beige",
    "blush": "Blush",
    "sand": "Sand",
}
DEFAULT_BG = "cream"

# Appearance settings: URL param (= cookie name) -> (allowed values, default)
SETTINGS = {
    "theme": (THEMES, DEFAULT_THEME),
    "bg": (BACKGROUNDS, DEFAULT_BG),
}
SETTING_COOKIE_MAX_AGE = 365 * 24 * 60 * 60


# ---------------------------------------------------------------------------
# Fake data (to be replaced with Google Calendar / real storage later)
# ---------------------------------------------------------------------------

def _fake_date(day, months_ahead=0):
    """ISO date string for `day` in the current month (or a later one), so the
    sample events always show up no matter when the app is run."""
    today = date.today()
    month_index = today.month - 1 + months_ahead
    return date(today.year + month_index // 12, month_index % 12 + 1, day).isoformat()


# "time" = start ("" = all day), "end" = end time ("" = assume 1 hour).
# "location" and "notes" are optional.
FAKE_EVENTS = [
    {"date": _fake_date(2), "time": "10:00", "end": "12:00", "title": "Study group", "color": "green",
     "location": "Library, room 3B", "notes": "Bring the chapter 4 problem set."},
    {"date": _fake_date(5), "time": "09:30", "end": "09:45", "title": "Team standup", "color": "blue",
     "location": "Online"},
    {"date": _fake_date(5), "time": "13:00", "end": "14:30", "title": "Lunch with Sam", "color": "orange",
     "location": "Campus café"},
    {"date": _fake_date(5), "time": "14:00", "end": "15:00", "title": "Call with advisor", "color": "purple",  # overlaps lunch
     "notes": "Ask about the thesis timeline and summer funding."},
    {"date": _fake_date(5), "time": "18:00", "end": "", "title": "Gym", "color": "green"},  # no end -> 1 hour
    {"date": _fake_date(9), "time": "", "end": "", "title": "Mom's birthday", "color": "pink"},
    {"date": _fake_date(9), "time": "", "end": "", "title": "Pay rent", "color": "orange"},
    {"date": _fake_date(9), "time": "17:00", "end": "19:00", "title": "Birthday dinner", "color": "pink",
     "location": "Mom's place", "notes": "Pick up the cake at 4."},
    {"date": _fake_date(12), "time": "14:00", "end": "", "title": "Dentist", "color": "blue",
     "location": "Downtown dental clinic", "notes": "Bring insurance card."},
    {"date": _fake_date(15), "time": "16:30", "end": "17:30", "title": "Project demo", "color": "purple",
     "location": "Engineering building, room 210"},
    {"date": _fake_date(20), "time": "11:00", "end": "11:30", "title": "Library: return books", "color": "orange"},
    {"date": _fake_date(24), "time": "22:30", "end": "01:00", "title": "Movie night", "color": "pink",  # past midnight
     "notes": "Your turn to pick the movie."},
    {"date": _fake_date(28), "time": "", "end": "", "title": "Assignment due", "color": "purple"},
    {"date": _fake_date(3, months_ahead=1), "time": "15:00", "end": "16:00", "title": "Haircut", "color": "blue"},
    {"date": _fake_date(10, months_ahead=1), "time": "", "end": "", "title": "Trip", "color": "green"},
]

FAKE_TASKS = [
    {"title": "Buy pet food", "done": False},
    {"title": "Read chapter 3", "done": True},
    {"title": "Email professor", "done": False},
    {"title": "Clean desk", "done": False},
]

FAKE_PET = {"name": "Raven", "level": 3, "xp": 140, "xp_max": 200}

FAKE_STATS = {"xp_today": 35, "streak_days": 4}

USER_NAME = "Khalaf"  # later: from the signed-in Google account


def to_template_event(raw):
    """Convert one source event into the shape the template uses:
    {"date": date, "time": "HH:MM" or "" (all day), "end": "HH:MM" or "",
     "title": str, "color": str, "location": str, "notes": str}.

    This is the only place that knows the source format. When we switch to
    Google Calendar, change this to read its fields (summary, start.dateTime /
    start.date, end.dateTime, colorId, location, description) and leave the
    rest of the app alone.
    """
    return {
        "date": date.fromisoformat(raw["date"]),
        "time": raw.get("time") or "",
        "end": raw.get("end") or "",
        "title": raw["title"],
        "color": raw.get("color") or "blue",
        "location": raw.get("location") or "",
        "notes": raw.get("notes") or "",
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _add_months(d, delta):
    """Same day `delta` months away, clamped to the month's length (Jan 31 -> Feb 28)."""
    index = d.month - 1 + delta
    year, month = d.year + index // 12, index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _parse_date(value, fallback):
    try:
        d = date.fromisoformat(value or "")
    except ValueError:
        return fallback
    return d if MIN_YEAR <= d.year <= MAX_YEAR else fallback


def _in_range(d):
    return MIN_YEAR <= d.year <= MAX_YEAR


def _visible_days(view, selected):
    """Days shown as columns in the day / 3-day / week views."""
    if view == "week":
        start = selected - timedelta(days=(selected.weekday() + 1) % 7)  # back to Sunday
        return [start + timedelta(days=i) for i in range(7)]
    return [selected + timedelta(days=i) for i in range(VIEWS[view][1])]


MINUTES_PER_DAY = 24 * 60
DEFAULT_SCROLL_MINUTE = 8 * 60  # timeline opens at 8 AM on days other than today


def _minutes(hhmm):
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _clock(minute_of_day):
    """1:05 PM style time (works on Windows, unlike strftime's %-I)."""
    hours, minutes = divmod(minute_of_day % MINUTES_PER_DAY, 60)
    return f"{hours % 12 or 12}:{minutes:02d} {'AM' if hours < 12 else 'PM'}"


HOUR_LABELS = [f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}" for h in range(24)]


def _event_span(event):
    """(start, end) of a timed event in minutes from midnight.
    No end time -> 1 hour; ending at/before the start -> runs past midnight,
    so it's cut off at 24:00."""
    start = _minutes(event["time"])
    end = _minutes(event["end"]) if event["end"] else start + 60
    if end <= start:
        end = MINUTES_PER_DAY
    return start, min(end, MINUTES_PER_DAY)


def _time_range(event):
    if not event["time"]:
        return "All day"
    start, end = _event_span(event)
    return f"{_clock(start)} – {_clock(end)}"


def _layout_timeline(events):
    """Split one day's events into all-day events and positioned timed blocks.

    Each block gets start/end in minutes from midnight, plus lane/lanes so
    overlapping events sit side by side: a group of events that overlap each
    other shares the width, and each event takes the first free lane.
    """
    all_day = [e for e in events if not e["time"]]

    blocks = []
    for event in events:
        if not event["time"]:
            continue
        start, end = _event_span(event)
        blocks.append({**event, "start": start, "end": end, "time_range": _time_range(event)})
    blocks.sort(key=lambda b: (b["start"], -b["end"]))

    group, group_end, lane_ends = [], 0, []

    def finish(group):
        for b in group:
            b["lanes"] = len(lane_ends)

    for block in blocks:
        if group and block["start"] >= group_end:  # no overlap with the group: start a new one
            finish(group)
            group, lane_ends = [], []
        for lane, lane_end in enumerate(lane_ends):
            if lane_end <= block["start"]:
                block["lane"], lane_ends[lane] = lane, block["end"]
                break
        else:
            block["lane"] = len(lane_ends)
            lane_ends.append(block["end"])
        group.append(block)
        group_end = max(group_end, block["end"])
    if group:
        finish(group)

    return all_day, blocks


def _greeting_part(hour):
    """Part of the day for the greeting (clock.js uses the same rule)."""
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    return "evening"


def _start_datetime(event):
    start = time.fromisoformat(event["time"]) if event["time"] else time()
    return datetime.combine(event["date"], start)


def _countdown(start, now, all_day=False):
    """How long until `start`: "in 25 min", "in 2 h 15 min", "tomorrow at 3:00 PM",
    "Thursday", "Nov 28 at 9:00 AM". clock.js keeps the same-day text current."""
    days = (start.date() - now.date()).days
    at = "" if all_day else f" at {_clock(start.hour * 60 + start.minute)}"
    if days == 0:
        minutes = math.ceil((start - now).total_seconds() / 60)
        if minutes <= 0:
            return "now"
        if minutes < 60:
            return f"in {minutes} min"
        hours, minutes = divmod(minutes, 60)
        return f"in {hours} h {minutes} min" if minutes else f"in {hours} h"
    if days == 1:
        return f"tomorrow{at}"
    if days < 7:
        return f"{start:%A}{at}"
    return f"{start:%b} {start.day}{at}"


def _up_next(events, now):
    """The next event starting after `now` (all-day events start at midnight,
    so today's are skipped), with display text for the glance panel."""
    upcoming = [e for e in events if _start_datetime(e) > now]
    if not upcoming:
        return None
    event = min(upcoming, key=_start_datetime)
    start = _start_datetime(event)
    days = (event["date"] - now.date()).days
    day_label = "Today" if days == 0 else "Tomorrow" if days == 1 else f"{event['date']:%a, %b} {event['date'].day}"
    return {
        **event,
        "when": f"{day_label} · {event['time_range']}",
        "countdown": _countdown(start, now, all_day=not event["time"]),
        "start_iso": start.isoformat(timespec="minutes"),
    }


def _week_bars(today, events_by_date):
    """Sun-Sat of the current week with event counts, for the "This week" strip."""
    start = today - timedelta(days=(today.weekday() + 1) % 7)
    days = [start + timedelta(days=i) for i in range(7)]
    counts = [len(events_by_date.get(d, [])) for d in days]
    most = max(counts) or 1
    return [
        {
            "date": d,
            "letter": DAY_NAMES[i][0],
            "count": n,
            "percent": round(100 * n / most),
            "is_today": d == today,
            "label": f"{d:%a, %b} {d.day}: {n} event{'s' if n != 1 else ''}",
        }
        for i, (d, n) in enumerate(zip(days, counts))
    ]


def _title(view, selected, days):
    """(main, muted) parts of the heading, e.g. ("November", "2026")."""
    if view == "month":
        return selected.strftime("%B"), str(selected.year)
    if view == "day":
        return f"{selected:%A, %B} {selected.day}", str(selected.year)
    first, last = days[0], days[-1]
    if first.year != last.year:
        # e.g. "Dec 27, 2026 – Jan 2, 2027" (years are part of the main text)
        return f"{first:%b} {first.day}, {first.year} – {last:%b} {last.day}, {last.year}", ""
    if first.month == last.month:
        return f"{first:%b} {first.day} – {last.day}", str(first.year)
    return f"{first:%b} {first.day} – {last:%b} {last.day}", str(first.year)


@app.route("/")
def index():
    now = datetime.now()
    today = now.date()
    now_minute = now.hour * 60 + now.minute

    selected = _parse_date(request.args.get("date"), today)
    view = request.args.get("view")
    if view not in VIEWS:
        view = DEFAULT_VIEW

    # Appearance settings: ?<name>= wins (and gets saved in a cookie of the
    # same name), else that cookie, else the default. Unknown values are ignored.
    settings, to_save = {}, {}
    for name, (allowed, default) in SETTINGS.items():
        from_url = request.args.get(name)
        from_cookie = request.cookies.get(name)
        if from_url in allowed:
            settings[name] = to_save[name] = from_url
        elif from_cookie in allowed:
            settings[name] = from_cookie
        else:
            settings[name] = default
    theme, bg = settings["theme"], settings["bg"]

    def link(**changes):
        """URL for the current page state with some parts changed."""
        params = {"date": selected, "view": view, **settings, **changes}
        params["date"] = params["date"].isoformat()
        return url_for("index", **params)

    events_by_date = {}
    all_events = []
    for raw in FAKE_EVENTS:
        event = to_template_event(raw)
        event["time_range"] = _time_range(event)
        all_events.append(event)
        events_by_date.setdefault(event["date"], []).append(event)
    for events in events_by_date.values():
        events.sort(key=lambda e: e["time"])  # all-day ("") first

    def day_info(d):
        return {
            "date": d,
            "in_month": d.month == selected.month,
            "is_today": d == today,
            "is_selected": d == selected,
            "is_weekend": d.weekday() >= 5,
            "events": events_by_date.get(d, []),
        }

    if view == "month":
        weeks = [
            [day_info(d) for d in week]
            for week in calendar.Calendar(firstweekday=calendar.SUNDAY)
            .monthdatescalendar(selected.year, selected.month)
        ]
        columns = []
        prev_date, next_date = _add_months(selected, -1), _add_months(selected, 1)
    else:
        weeks = []
        columns = [day_info(d) for d in _visible_days(view, selected)]
        step = timedelta(days=VIEWS[view][1])
        prev_date, next_date = selected - step, selected + step

    title_main, title_sub = _title(view, selected, [c["date"] for c in columns])
    all_day, blocks = _layout_timeline(events_by_date.get(selected, []))
    is_today = selected == today

    pet = dict(FAKE_PET)
    pet["xp_percent"] = round(100 * pet["xp"] / pet["xp_max"]) if pet["xp_max"] else 0

    tasks_done = sum(1 for t in FAKE_TASKS if t["done"])
    progress = {
        "done": tasks_done,
        "total": len(FAKE_TASKS),
        "percent": round(100 * tasks_done / len(FAKE_TASKS)) if FAKE_TASKS else 0,
        **FAKE_STATS,
    }

    response = make_response(render_template(
        "index.html",
        link=link,
        view=view,
        views=[(key, label) for key, (label, _) in VIEWS.items()],
        theme=theme,
        themes=THEMES.items(),
        bg=bg,
        backgrounds=BACKGROUNDS.items(),
        title_main=title_main,
        title_sub=title_sub,
        day_names=DAY_NAMES,
        weeks=weeks,
        columns=columns,
        today=today,
        selected=selected,
        is_today=is_today,
        all_day=all_day,
        blocks=blocks,
        hour_labels=HOUR_LABELS,
        now=now,
        now_minute=now_minute,
        clock_time=_clock(now_minute),
        clock_date=f"{today:%A, %B} {today.day}",
        scroll_minute=now_minute if is_today else DEFAULT_SCROLL_MINUTE,
        prev_date=prev_date if _in_range(prev_date) else None,
        next_date=next_date if _in_range(next_date) else None,
        tasks=FAKE_TASKS,
        pet=pet,
        user_name=USER_NAME,
        greeting_part=_greeting_part(now.hour),
        up_next=_up_next(all_events, now),
        progress=progress,
        week_bars=_week_bars(today, events_by_date),
    ))
    for name, value in to_save.items():
        response.set_cookie(name, value, max_age=SETTING_COOKIE_MAX_AGE, samesite="Lax")
    return response


if __name__ == "__main__":
    app.run(debug=True)
