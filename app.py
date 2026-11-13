"""AI Credit Watch entry point. Layout only; panels are added in later steps."""

from datetime import date, datetime, timezone
from pathlib import Path

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent
EVENTS_PATH = ROOT / "config" / "events.yaml"

st.set_page_config(
    page_title="AI Credit Watch",
    layout="wide",
)


def _watch_chips(today: date) -> list[str]:
    """Upcoming events with a source, hidden once the date has passed."""
    try:
        raw = yaml.safe_load(EVENTS_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    events = raw.get("events") if isinstance(raw, dict) else None
    if not isinstance(events, list):
        return []

    chips: list[str] = []
    for event in events:
        if not isinstance(event, dict) or not event.get("upcoming"):
            continue
        source = str(event.get("source") or "").strip()
        url = str(event.get("url") or "").strip()
        if not source or not url:
            continue
        try:
            event_date = date.fromisoformat(str(event.get("date") or ""))
        except ValueError:
            continue
        days_left = (event_date - today).days
        if days_left < 0:
            continue
        phrase = str(event.get("watch") or event.get("label") or "").strip()
        if not phrase:
            continue
        when = f"{event_date.strftime('%b')} {event_date.day}"
        chips.append(
            f"Watch: {phrase} {when} ({days_left} days) · [{source}]({url})"
        )
    return chips


def render_header() -> None:
    refreshed = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title_col, button_col = st.columns([5, 1])
    with title_col:
        st.title("AI Credit Watch: Is credit repricing NVIDIA?")
        st.caption(f"Last refreshed {refreshed}")
        for chip in _watch_chips(date.today()):
            st.caption(chip)
    with button_col:
        st.write("")
        st.write("")
        if st.button("Refresh", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


render_header()
