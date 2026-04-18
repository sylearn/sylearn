#!/usr/bin/env python3
"""Generate typography-led SVGs for the sylearn profile.

Two SVGs ship with the profile, because their layout and tone of
voice need human-grade typography that live services cannot provide:

  1. hero-card.svg    — wordmark + live GitHub metrics.
  2. oss-card.svg     — external open-source contributions
                        (merged PRs into other people's repositories),
                        queried through the GitHub Search API.

Everything else in the README (pin cards, stats cards, top langs,
streak, activity graph, shields badges) is pulled from live
services on every view.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import textwrap
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / ".github" / "assets"
USERNAME = "sylearn"
LOCAL_TZ = dt.timezone(dt.timedelta(hours=8))
USER_AGENT = "sylearn-profile-generator"
API_ACCEPT = "application/vnd.github+json"


FALLBACK_EXTERNAL_MERGES = [
    {
        "repo": "Significant-Gravitas/AutoGPT",
        "title": "Fix ImportError for validate_yaml_file function",
        "url": "https://github.com/Significant-Gravitas/AutoGPT/pull/7110",
        "number": 7110,
    },
    {
        "repo": "FoundationAgents/OpenManus",
        "title": "Fix Pydantic V2 compatibility",
        "url": "https://github.com/FoundationAgents/OpenManus/pull/14",
        "number": 14,
    },
    {
        "repo": "aiming-lab/AutoResearchClaw",
        "title": "Stale import path and resource leak cleanups",
        "url": "https://github.com/aiming-lab/AutoResearchClaw/pull/102",
        "number": 102,
    },
    {
        "repo": "nguyenphutrong/quotio",
        "title": "Add Chinese README",
        "url": "https://github.com/nguyenphutrong/quotio/pull/11",
        "number": 11,
    },
]


def headers() -> dict[str, str]:
    values = {"Accept": API_ACCEPT, "User-Agent": USER_AGENT}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        values["Authorization"] = f"Bearer {token}"
    return values


def fetch_json(url: str) -> dict | list:
    request = urllib.request.Request(url, headers=headers())
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def fmt_number(value: int) -> str:
    if value >= 1000:
        return f"{value / 1000:.1f}K".replace(".0K", "K")
    return str(value)


def xml(value: str) -> str:
    return html.escape(value, quote=True)


def short_text(value: str, width: int) -> str:
    return textwrap.shorten(" ".join(value.split()), width=width, placeholder="...")


def fetch_external_merges() -> tuple[list[dict], int]:
    """Return (top_items, total_count) of merged external PRs."""
    query = urllib.parse.quote(f"author:{USERNAME} type:pr is:merged -user:{USERNAME}")
    url = (
        "https://api.github.com/search/issues"
        f"?q={query}&per_page=30&sort=updated&order=desc"
    )
    try:
        data = fetch_json(url)
    except Exception:
        return FALLBACK_EXTERNAL_MERGES, len(FALLBACK_EXTERNAL_MERGES)

    items = data.get("items", []) or []
    total = int(data.get("total_count", len(items)) or 0)
    if not items:
        return FALLBACK_EXTERNAL_MERGES, max(total, len(FALLBACK_EXTERNAL_MERGES))

    merges: list[dict] = []
    for item in items:
        repo = item["repository_url"].split("/repos/")[-1]
        merges.append(
            {
                "repo": repo,
                "title": item["title"],
                "url": item["html_url"],
                "number": item.get("number", 0),
            }
        )
    return merges, total


def collect_data() -> dict:
    try:
        user = fetch_json(f"https://api.github.com/users/{USERNAME}")
        repos = fetch_json(
            f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated"
        )
    except Exception:
        user = {"followers": 0, "public_repos": 0, "created_at": "2019-01-01T00:00:00Z"}
        repos = []

    owned = [repo for repo in repos if not repo.get("fork")]
    now_utc = dt.datetime.now(dt.timezone.utc)
    cutoff_90 = now_utc - dt.timedelta(days=90)

    stars = sum(repo.get("stargazers_count", 0) for repo in owned)
    active_90 = sum(
        1
        for repo in owned
        if repo.get("pushed_at") and parse_iso(repo["pushed_at"]) >= cutoff_90
    )
    latest_ship = ""
    if owned:
        latest_ship = max(owned, key=lambda r: r.get("pushed_at", ""))["name"]

    merges, merges_total = fetch_external_merges()

    return {
        "followers": user.get("followers", 0),
        "stars": stars,
        "repos": user.get("public_repos", len(owned)),
        "active_90": active_90,
        "latest_ship": latest_ship,
        "external_merges": merges,
        "external_merges_total": merges_total,
        "generated_at_local": now_utc.astimezone(LOCAL_TZ),
    }


def hero_svg(data: dict) -> str:
    followers = fmt_number(data["followers"])
    stars = fmt_number(data["stars"])
    repos = fmt_number(data["repos"])
    active = fmt_number(data["active_90"])
    latest = data["latest_ship"] or "—"
    updated = data["generated_at_local"].strftime("%Y.%m.%d  %H:%M")

    metric_blocks = []
    metrics = [
        (followers, "FOLLOWERS"),
        (stars, "STARS"),
        (repos, "REPOS"),
        (active, "ACTIVE / 90D"),
    ]
    base_x = 640
    gap = 130
    for index, (value, label) in enumerate(metrics):
        x = base_x + index * gap
        metric_blocks.append(
            f"""
            <g transform="translate({x} 288)">
              <line x1="0" y1="0" x2="28" y2="0" stroke="#3A3A3C" stroke-width="1"/>
              <text x="0" y="42" class="num" font-size="38" font-weight="300" fill="#F5F5F7" letter-spacing="-1.2">{xml(value)}</text>
              <text x="0" y="62" class="mono" font-size="9" fill="#86868B" letter-spacing="1.4">{xml(label)}</text>
            </g>
            """
        )

    return f"""<svg width="1200" height="420" viewBox="0 0 1200 420" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">sylearn</title>
  <desc id="desc">Minimal profile hero for sylearn with live GitHub metrics.</desc>
  <defs>
    <radialGradient id="halo" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(980 120) rotate(140) scale(360 260)">
      <stop stop-color="#0A84FF" stop-opacity="0.22"/>
      <stop offset="0.55" stop-color="#0A84FF" stop-opacity="0.05"/>
      <stop offset="1" stop-color="#0A84FF" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="warm" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(180 420) rotate(-30) scale(300 220)">
      <stop stop-color="#FF9F0A" stop-opacity="0.10"/>
      <stop offset="1" stop-color="#FF9F0A" stop-opacity="0"/>
    </radialGradient>
    <style>
      .sans {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif; }}
      .mono {{ font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace; }}
      .num  {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif; font-variant-numeric: tabular-nums; }}
    </style>
  </defs>

  <rect width="1200" height="420" rx="24" fill="#0A0A0A"/>
  <rect width="1200" height="420" rx="24" fill="url(#halo)"/>
  <rect width="1200" height="420" rx="24" fill="url(#warm)"/>

  <circle cx="80" cy="78" r="3" fill="#30D158"/>
  <text x="92" y="82" class="mono" font-size="10" fill="#86868B" letter-spacing="1.6">AVAILABLE  ·  NANJING, CN</text>

  <text x="80" y="210" class="sans" font-size="140" font-weight="200" fill="#F5F5F7" letter-spacing="-6">sylearn</text>

  <text x="84" y="256" class="sans" font-size="19" font-weight="400" fill="#C7C7CC" letter-spacing="-0.3">AI products, research systems, and tools that disappear into the work.</text>

  <line x1="80" y1="300" x2="560" y2="300" stroke="#1C1C1E" stroke-width="1"/>

  {"".join(metric_blocks)}

  <text x="80" y="372" class="mono" font-size="10" fill="#636366" letter-spacing="1.4">LATEST  ·  {xml(latest.upper())}</text>
  <text x="1120" y="372" text-anchor="end" class="mono" font-size="10" fill="#636366" letter-spacing="1.4">SYNC  ·  {xml(updated)}  UTC+8</text>

  <text x="1120" y="82" text-anchor="end" class="mono" font-size="10" fill="#48484A" letter-spacing="2">— 01</text>
</svg>
"""


def oss_svg(data: dict) -> str:
    merges = data.get("external_merges") or FALLBACK_EXTERNAL_MERGES
    shown = merges[:4]
    total = data.get("external_merges_total") or len(merges)
    display_total = fmt_number(total)
    updated = data["generated_at_local"].strftime("%Y.%m.%d  %H:%M")

    rows = []
    for index, item in enumerate(shown):
        y = 110 + index * 56
        repo = short_text(item["repo"], 36)
        title = short_text(item["title"], 58).upper()
        number = f"#{item.get('number', 0)}" if item.get("number") else ""
        rows.append(
            f"""
            <g transform="translate(620 {y})">
              <circle cx="0" cy="12" r="3" fill="#30D158"/>
              <text x="16" y="16" class="sans" font-size="17" font-weight="500" fill="#F5F5F7" letter-spacing="-0.2">{xml(repo)}</text>
              <text x="480" y="16" text-anchor="end" class="mono" font-size="10" fill="#636366" letter-spacing="1.2">{xml(number)}</text>
              <text x="16" y="37" class="mono" font-size="10" fill="#86868B" letter-spacing="0.9">{xml(title)}</text>
              <line x1="16" y1="48" x2="480" y2="48" stroke="#1C1C1E" stroke-width="1"/>
            </g>
            """
        )

    return f"""<svg width="1200" height="420" viewBox="0 0 1200 420" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">sylearn external merges</title>
  <desc id="desc">Merged pull requests into external open-source projects.</desc>
  <defs>
    <radialGradient id="green-halo" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(220 120) rotate(30) scale(360 240)">
      <stop stop-color="#30D158" stop-opacity="0.16"/>
      <stop offset="0.55" stop-color="#30D158" stop-opacity="0.04"/>
      <stop offset="1" stop-color="#30D158" stop-opacity="0"/>
    </radialGradient>
    <style>
      .sans {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif; }}
      .mono {{ font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace; }}
      .num  {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif; font-variant-numeric: tabular-nums; }}
    </style>
  </defs>

  <rect width="1200" height="420" rx="24" fill="#0A0A0A"/>
  <rect width="1200" height="420" rx="24" fill="url(#green-halo)"/>

  <circle cx="80" cy="78" r="3" fill="#30D158"/>
  <text x="92" y="82" class="mono" font-size="10" fill="#86868B" letter-spacing="1.6">OPEN SOURCE  ·  MERGED UPSTREAM</text>

  <text x="80" y="228" class="num" font-size="180" font-weight="200" fill="#F5F5F7" letter-spacing="-8">{xml(display_total)}</text>

  <text x="84" y="266" class="sans" font-size="18" font-weight="400" fill="#C7C7CC" letter-spacing="-0.2">Pull requests merged into external projects.</text>
  <text x="84" y="290" class="mono" font-size="10" fill="#636366" letter-spacing="1.3">AGENTS  ·  RESEARCH TOOLING  ·  DEVELOPER PRODUCTS</text>

  <line x1="80" y1="336" x2="540" y2="336" stroke="#1C1C1E" stroke-width="1"/>

  <text x="620" y="78" class="mono" font-size="10" fill="#86868B" letter-spacing="1.6">RECENT MERGES</text>
  {"".join(rows)}

  <text x="80" y="372" class="mono" font-size="10" fill="#636366" letter-spacing="1.4">SYNC  ·  {xml(updated)}  UTC+8</text>
  <text x="1120" y="82" text-anchor="end" class="mono" font-size="10" fill="#48484A" letter-spacing="2">— 03</text>
</svg>
"""


def write_asset(filename: str, content: str) -> None:
    path = ASSET_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
    path.write_text(normalized, encoding="utf-8")


def cleanup_legacy_assets() -> None:
    # oss-card.svg is now actively generated above, so only clear the older ones.
    for name in ("stats-card.svg", "project-wall.svg"):
        path = ASSET_DIR / name
        if path.exists():
            path.unlink()


def main() -> None:
    data = collect_data()
    write_asset("hero-card.svg", hero_svg(data))
    write_asset("oss-card.svg", oss_svg(data))
    cleanup_legacy_assets()


if __name__ == "__main__":
    main()
