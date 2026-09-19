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
2. Set two environment variables before running (BOTH are required, no
   defaults are assumed — a wrong/missing instance URL is what caused
   every run to silently fail against the wrong server last time):
     VIVALDI_ACCESS_TOKEN  = the token from step 1
     VIVALDI_INSTANCE_URL  = https://social.vivaldi.net
3. pip install requests feedparser
4. Run manually to test:  python daily_poster.py
5. Automate with cron or GitHub Actions (see README.md in this folder).
"""

import os
import sys
import json
import random
from pathlib import Path
from urllib.parse import urlparse

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
REQUEST_TIMEOUT = 30

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
        if parsed.bozo:
            print(f"WARNING: couldn't parse feed {feed_url}: {parsed.bozo_exception}",
                  file=sys.stderr)
            continue
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


def validate_instance_url(instance_url: str) -> str:
    """Make sure the instance URL is well-formed and looks intentional,
    instead of silently posting to the wrong server."""
    parsed = urlparse(instance_url)
    if not parsed.scheme or not parsed.netloc:
        print(
            f"ERROR: VIVALDI_INSTANCE_URL '{instance_url}' doesn't look like a "
            "valid URL (expected something like https://social.vivaldi.net).",
            file=sys.stderr,
        )
        sys.exit(1)
    return instance_url.rstrip("/")


def post_status(instance_url: str, token: str, text: str) -> dict:
    url = f"{instance_url}/api/v1/statuses"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            data={"status": text, "visibility": "public"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        print(f"ERROR: request to {url} failed: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code == 401:
        print(
            f"ERROR: 401 Unauthorized posting to {url}. This almost always means "
            "either the access token is wrong/expired, or it was generated on a "
            "different instance than VIVALDI_INSTANCE_URL points to. "
            "Double-check both values match the SAME Vivaldi Social account.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: {url} returned {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)

    return resp.json()


def main():
    token = os.environ.get("VIVALDI_ACCESS_TOKEN")
    instance_url = os.environ.get("VIVALDI_INSTANCE_URL")

    if not token:
        print("ERROR: set VIVALDI_ACCESS_TOKEN environment variable.", file=sys.stderr)
        sys.exit(1)

    if not instance_url:
        print(
            "ERROR: set VIVALDI_INSTANCE_URL environment variable "
            "(e.g. https://social.vivaldi.net). No default is assumed on purpose — "
            "a silently-wrong instance URL is what broke every run last time.",
            file=sys.stderr,
        )
        sys.exit(1)

    instance_url = validate_instance_url(instance_url)

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
