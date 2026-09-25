"""Pure display helpers for the Streamlit UI (no Streamlit imports, easy to test)."""

import re
from datetime import datetime
from typing import Optional

_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$])")
_DETAIL_LINE = re.compile(r"^\s+([A-Z][A-Za-z]{1,15}(?: [a-z]{1,15})?):\s+(.+)$")
_OPTION_LINE = re.compile(r"^\s*\((\d+)\)\s+(.+)$")


def escape_markdown(text: str) -> str:
    """Escape characters Markdown (or Streamlit directives) would interpret."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)


def text_to_markdown(text: str) -> str:
    """Show user-typed text literally, keeping its line breaks."""
    return "  \n".join(escape_markdown(line) for line in text.split("\n"))


def to_markdown(text: str) -> str:
    """
    Render a bot reply as Markdown, preserving its line structure.

    "  Phone:  +31 ..." detail lines get a bold label and "(1) ..." option lines a
    bold number; everything else is shown literally.
    """
    paragraphs: list[str] = []
    lines: list[str] = []
    for raw in text.split("\n"):
        if not raw.strip():
            if lines:
                paragraphs.append("  \n".join(lines))
                lines = []
            continue
        detail = _DETAIL_LINE.match(raw)
        option = _OPTION_LINE.match(raw)
        if detail:
            lines.append(f"**{detail.group(1)}:** {escape_markdown(detail.group(2).strip())}")
        elif option:
            lines.append(f"**({option.group(1)})** {escape_markdown(option.group(2))}")
        else:
            lines.append(escape_markdown(raw.strip()))
    if lines:
        paragraphs.append("  \n".join(lines))
    return "\n\n".join(paragraphs)


def _local(iso: str) -> datetime:
    """Parse a stored UTC timestamp into local time."""
    return datetime.fromisoformat(iso).astimezone()


def _days_ago(moment: datetime, now: datetime) -> int:
    return (now.date() - moment.date()).days


def format_timestamp(iso: str, now: Optional[datetime] = None) -> str:
    """'Today, 14:32', 'Yesterday, 09:05', 'Sep 24, 14:32' or 'Sep 24 2025, 14:32'."""
    moment = _local(iso)
    now = now or datetime.now().astimezone()
    time = moment.strftime("%H:%M")
    days = _days_ago(moment, now)
    if days == 0:
        return f"Today, {time}"
    if days == 1:
        return f"Yesterday, {time}"
    day = f"{moment.strftime('%b')} {moment.day}"
    if moment.year != now.year:
        day += f" {moment.year}"
    return f"{day}, {time}"


def format_time(iso: str) -> str:
    """Just the local time of day, e.g. '14:32'."""
    return _local(iso).strftime("%H:%M")


def history_group(iso: str, now: Optional[datetime] = None) -> str:
    """Sidebar group for a conversation's last activity."""
    days = _days_ago(_local(iso), now or datetime.now().astimezone())
    if days <= 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    if days < 7:
        return "Previous 7 days"
    if days < 30:
        return "Previous 30 days"
    return "Older"
