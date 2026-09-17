#!/usr/bin/env python3
"""Refresh auto-generated sections of README.md from public feeds.

Sections are delimited by HTML comment markers. When a source has nothing to
show (or is disabled), the section renders empty so nothing appears on the
profile.

Environment:
  ENABLE_WRITING  default "true"
  ENABLE_VIDEO    default "false"  (implemented, not yet shown)
  MAX_ITEMS       default "4"
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"

WRITING_FEED = "https://michaelstolarz.com/feed.xml"
VIDEO_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=UCFiN1FnTVWKX1G_UwgZHURA"

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"


def env_flag(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def fetch(url: str) -> ET.Element:
    req = urllib.request.Request(url, headers={"User-Agent": "SystemSculpt-profile-updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return ET.fromstring(resp.read())


def fmt_date(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y").replace(" 0", " ")
    except ValueError:
        return ""


def atom_entries(root: ET.Element, limit: int) -> list[dict]:
    items = []
    for e in root.findall(f"{ATOM}entry")[:limit]:
        title = (e.findtext(f"{ATOM}title") or "").strip()
        link = ""
        for l in e.findall(f"{ATOM}link"):
            if l.get("rel") in (None, "alternate"):
                link = l.get("href", "")
                break
        date = fmt_date(e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated"))
        video_id = e.findtext(f"{YT}videoId")
        if title and link:
            items.append({"title": title, "link": link, "date": date, "video_id": video_id})
    return items


def render_writing(items: list[dict]) -> str:
    if not items:
        return ""
    lines = ["## Latest writing", ""]
    for it in items:
        suffix = f" <sub>{it['date']}</sub>" if it["date"] else ""
        lines.append(f"- [{it['title']}]({it['link']}){suffix}")
    lines += ["", f"More at [michaelstolarz.com/writing](https://michaelstolarz.com/writing/)."]
    return "\n".join(lines)


def render_video(items: list[dict]) -> str:
    if not items:
        return ""
    latest = items[0]
    thumb = f"https://i.ytimg.com/vi/{latest['video_id']}/maxresdefault.jpg"
    lines = [
        "## Latest video",
        "",
        f'<a href="{latest["link"]}"><img alt="{latest["title"]}" src="{thumb}" width="480"></a>',
        "",
        f"**[{latest['title']}]({latest['link']})**" + (f" <sub>{latest['date']}</sub>" if latest["date"] else ""),
    ]
    if len(items) > 1:
        lines += [""] + [f"- [{it['title']}]({it['link']})" for it in items[1:]]
    lines += ["", "More on [YouTube](https://www.youtube.com/@systemsculpt)."]
    return "\n".join(lines)


def replace_section(text: str, name: str, body: str) -> str:
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        sys.exit(f"missing markers for {name}")
    inner = f"\n{body}\n" if body else "\n"
    return pattern.sub(lambda _: f"{start}{inner}{end}", text)


def main() -> int:
    limit = int(os.environ.get("MAX_ITEMS", "4"))
    text = README.read_text()

    writing = ""
    if env_flag("ENABLE_WRITING", True):
        try:
            writing = render_writing(atom_entries(fetch(WRITING_FEED), limit))
        except Exception as exc:  # keep the last good section on transient failures
            print(f"writing feed failed: {exc}", file=sys.stderr)
            writing = None

    video = ""
    if env_flag("ENABLE_VIDEO", False):
        try:
            video = render_video(atom_entries(fetch(VIDEO_FEED), limit))
        except Exception as exc:
            print(f"video feed failed: {exc}", file=sys.stderr)
            video = None

    if writing is not None:
        text = replace_section(text, "WRITING", writing)
    if video is not None:
        text = replace_section(text, "VIDEO", video)

    if text != README.read_text():
        README.write_text(text)
        print("README updated")
    else:
        print("README unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
