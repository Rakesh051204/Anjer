#!/usr/bin/env python3
"""
Daily auto-poster for Vivaldi Social (Mastodon-compatible API).

Pulls one fresh tech/AI news item from an RSS feed and posts it to your
Vivaldi Social account. Designed to be run once a day (via cron or
GitHub Actions). Keeps a local log of already-posted links so it never
repeats a story.

Setup:
1. On Vivaldi Social, go to Preferences > Development > New Application.
   - Name: anything (e.g. "daily-poster")
   - Scopes: at least `write:statuses`
   - Save, then copy the "Your access token" value.
2. Set two environment variables before running:
     VIVALDI_ACCESS_TOKEN = the token from step 1
     VIVALDI_INSTANCE_URL = https://vivaldi.social   (or your instance URL)
3. pip install requests feedparser
4. Run manually to test:  python daily_poster.py
5. Automate with cron or GitHub Actions (see README.md in this folder).
"""

import os
import sys
import json
import random
from pathlib import Path

import requests
import feedparser

# ---- Config ----------------------------------------------------------

# Rotate through a few free, no-key-needed RSS feeds relevant to AI/tech.
FEEDS = [
    "https://hnrss.org/frontpage",          # Hacker News front page
    "https://www.artificialintelligence-news.com/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
]

POSTED_LOG = Path(__file__).parent / "posted_links.json"
MAX_POST_LENGTH = 480  # Mastodon default limit is 500; leave headroom

# ------------------------------------------------------------------------


def load_posted() -> set:
    if POSTED_LOG.exists():
        return set(json.loads(POSTED_LOG.read_text()))
    return set()


def save_posted(posted: set) -> None:
    # Keep the log from growing forever — retain the most recent 500 links
    trimmed = list(posted)[-500:]
    POSTED_LOG.write_text(json.dumps(trimmed))


def pick_story(posted: set):
    """Try each feed in random order, return the first unposted entry."""
    feeds = FEEDS[:]
    random.shuffle(feeds)
    for feed_url in feeds:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries:
            link = entry.get("link")
            title = entry.get("title")
            if link and title and link not in posted:
                return title, link
    return None, None


def build_status(title: str, link: str) -> str:
    text = f"{title}\n\n{link}\n\n#AI #tech #news"
    if len(text) > MAX_POST_LENGTH:
        # trim the title, not the link/hashtags
        overflow = len(text) - MAX_POST_LENGTH
        title = title[: len(title) - overflow - 1] + "…"
        text = f"{title}\n\n{link}\n\n#AI #tech #news"
    return text


def post_status(instance_url: str, token: str, text: str) -> dict:
    resp = requests.post(
        f"{instance_url.rstrip('/')}/api/v1/statuses",
        headers={"Authorization": f"Bearer {token}"},
        data={"status": text, "visibility": "public"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    token = os.environ.get("VIVALDI_ACCESS_TOKEN")
    instance_url = os.environ.get("VIVALDI_INSTANCE_URL", "https://vivaldi.social")

    if not token:
        print("ERROR: set VIVALDI_ACCESS_TOKEN environment variable.", file=sys.stderr)
        sys.exit(1)

    posted = load_posted()
    title, link = pick_story(posted)

    if not title:
        print("No fresh unposted story found today. Skipping.")
        return

    status_text = build_status(title, link)
    result = post_status(instance_url, token, status_text)

    posted.add(link)
    save_posted(posted)

    print(f"Posted: {result.get('url', '(no url returned)')}")


if __name__ == "__main__":
    main()
