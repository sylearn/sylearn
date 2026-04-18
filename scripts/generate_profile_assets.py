#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
import json
import os
import textwrap
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / ".github" / "assets"
USERNAME = "sylearn"
PROFILE_URL = f"https://github.com/{USERNAME}"
LOCAL_TZ = dt.timezone(dt.timedelta(hours=8))
USER_AGENT = "sylearn-profile-generator"
API_ACCEPT = "application/vnd.github+json"

FEATURED_REPOS = [
    {
        "name": "AIUsage",
        "eyebrow": "AI Dashboard",
        "pitch": "Subscription telemetry for quotas, costs, accounts, and Claude Code proxy.",
    },
    {
        "name": "AICode",
        "eyebrow": "Automation Library",
        "pitch": "A growing toolkit of AI utility scripts for faster development workflows.",
    },
    {
        "name": "Code-Composer",
        "eyebrow": "Workflow Engine",
        "pitch": "Composable prompt and project workflows for planning, coding, and review.",
    },
    {
        "name": "paper_copilot",
        "eyebrow": "Research Copilot",
        "pitch": "Vector-indexed literature analysis for faster academic reading and retrieval.",
    },
    {
        "name": "ActionAI",
        "eyebrow": "Agentic CLI",
        "pitch": "A model-switching terminal interface with MCP-powered tools and execution.",
    },
    {
        "name": "mp-search",
        "eyebrow": "Materials TUI",
        "pitch": "A terminal-native search interface for the Materials Project database.",
    },
]

FALLBACK_EXTERNAL_MERGES = [
    {
        "repo": "Significant-Gravitas/AutoGPT",
        "title": "Fix ImportError for validate_yaml_file function",
        "url": "https://github.com/Significant-Gravitas/AutoGPT/pull/7110",
    },
    {
        "repo": "FoundationAgents/OpenManus",
        "title": "Fix Pydantic V2 compatibility",
        "url": "https://github.com/FoundationAgents/OpenManus/pull/14",
    },
    {
        "repo": "aiming-lab/AutoResearchClaw",
        "title": "Stale import path and resource leak cleanups",
        "url": "https://github.com/aiming-lab/AutoResearchClaw/pull/102",
    },
    {
        "repo": "nguyenphutrong/quotio",
        "title": "Add Chinese README",
        "url": "https://github.com/nguyenphutrong/quotio/pull/11",
    },
]

LANGUAGE_COLORS = {
    "Python": "#7EE787",
    "Swift": "#F6A04D",
    "Shell": "#7AA2F7",
    "TypeScript": "#60A5FA",
    "Jupyter Notebook": "#F59E0B",
    "CSS": "#F472B6",
    "Go": "#2DD4BF",
}


def headers() -> dict[str, str]:
    values = {
        "Accept": API_ACCEPT,
        "User-Agent": USER_AGENT,
    }
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
    return f"{value:,}"


def short_text(value: str, width: int) -> str:
    return textwrap.shorten(" ".join(value.split()), width=width, placeholder="...")


def rel_time(value: str, now_utc: dt.datetime) -> str:
    delta = now_utc - parse_iso(value)
    if delta.days >= 365:
        years = delta.days // 365
        return f"{years}y ago"
    if delta.days >= 30:
        months = delta.days // 30
        return f"{months}mo ago"
    if delta.days >= 1:
        return f"{delta.days}d ago"
    hours = max(delta.seconds // 3600, 1)
    return f"{hours}h ago"


def xml(value: str) -> str:
    return html.escape(value, quote=True)


def collect_data() -> dict:
    user = fetch_json(f"https://api.github.com/users/{USERNAME}")
    repos = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated")
    owned = [repo for repo in repos if not repo["fork"]]
    by_name = {repo["name"]: repo for repo in repos}

    now_utc = dt.datetime.now(dt.timezone.utc)
    cutoff_90 = now_utc - dt.timedelta(days=90)
    active_90 = sum(parse_iso(repo["pushed_at"]) >= cutoff_90 for repo in owned)

    language_counts = Counter(repo["language"] for repo in owned if repo["language"])
    external_merges = fetch_external_merges()

    featured = []
    for entry in FEATURED_REPOS:
        repo = by_name.get(entry["name"])
        if not repo:
            continue
        featured.append(
            {
                **entry,
                "url": repo["html_url"],
                "stars": repo["stargazers_count"],
                "forks": repo["forks_count"],
                "language": repo["language"] or "Mixed",
                "updated": rel_time(repo["pushed_at"], now_utc),
            }
        )

    totals = {
        "followers": user["followers"],
        "public_repos": user["public_repos"],
        "owned_repos": len(owned),
        "repo_stars": sum(repo["stargazers_count"] for repo in owned),
        "repo_forks": sum(repo["forks_count"] for repo in owned),
        "active_90": active_90,
        "external_merges": len(external_merges),
        "since": parse_iso(user["created_at"]).year,
        "languages": language_counts.most_common(5),
        "latest_ship": max(owned, key=lambda repo: repo["pushed_at"])["name"],
    }

    return {
        "user": user,
        "featured": featured,
        "external_merges": external_merges,
        "totals": totals,
        "generated_at_local": now_utc.astimezone(LOCAL_TZ),
        "generated_at_utc": now_utc,
    }


def fetch_external_merges() -> list[dict]:
    query = urllib.parse.quote(f"author:{USERNAME} type:pr is:merged -user:{USERNAME}")
    url = (
        "https://api.github.com/search/issues"
        f"?q={query}&per_page=4&sort=updated&order=desc"
    )
    try:
        data = fetch_json(url)
    except Exception:
        return FALLBACK_EXTERNAL_MERGES

    items = data.get("items", [])
    if not items:
        return FALLBACK_EXTERNAL_MERGES

    merges = []
    for item in items[:4]:
        repo = item["repository_url"].split("/repos/")[-1]
        merges.append(
            {
                "repo": repo,
                "title": item["title"],
                "url": item["html_url"],
            }
        )
    return merges


def render_grid(width: int, height: int, x_step: int, y_step: int) -> str:
    lines: list[str] = []
    for x in range(0, width + 1, x_step):
        lines.append(
            f'<line x1="{x}" y1="0" x2="{x}" y2="{height}" stroke="#9CCBFF" stroke-opacity="0.06"/>'
        )
    for y in range(0, height + 1, y_step):
        lines.append(
            f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" stroke="#9CCBFF" stroke-opacity="0.06"/>'
        )
    return "\n".join(lines)


def render_language_pills(languages: list[tuple[str, int]], start_x: int, y: int) -> str:
    pills = []
    x = start_x
    for language, count in languages:
        label = f"{language} {count}"
        width = 34 + len(label) * 7
        color = LANGUAGE_COLORS.get(language, "#7DD3FC")
        pills.append(
            "\n".join(
                [
                    f'<rect x="{x}" y="{y}" width="{width}" height="32" rx="16" fill="#102034" fill-opacity="0.86" stroke="{color}" stroke-opacity="0.35"/>',
                    f'<circle cx="{x + 16}" cy="{y + 16}" r="5" fill="{color}"/>',
                    f'<text x="{x + 28}" y="{y + 21}" class="sans" font-size="13" font-weight="600" fill="#DCEEFF">{xml(label)}</text>',
                ]
            )
        )
        x += width + 12
    return "\n".join(pills)


def hero_svg(data: dict) -> str:
    totals = data["totals"]
    featured = data["featured"][:4]
    updated = data["generated_at_local"].strftime("%Y.%m.%d %H:%M UTC+8")
    featured_rows = []
    for index, repo in enumerate(featured):
        y = 166 + index * 78
        lang_color = LANGUAGE_COLORS.get(repo["language"], "#7DD3FC")
        featured_rows.append(
            f"""
            <g transform="translate(758 {y})">
              <rect width="366" height="60" rx="18" fill="#0F1C2E" fill-opacity="0.78" stroke="#36506E" stroke-opacity="0.55"/>
              <text x="20" y="24" class="mono" font-size="10.5" fill="#7DD3FC" letter-spacing="1.8">{xml(repo["eyebrow"].upper())}</text>
              <text x="20" y="43" class="sans" font-size="22" font-weight="700" fill="#F3F8FF">{xml(repo["name"])}</text>
              <circle cx="218" cy="38" r="4.5" fill="{lang_color}"/>
              <text x="230" y="42" class="mono" font-size="11" fill="#93A9C2">{xml(repo["language"])}</text>
              <text x="304" y="42" class="mono" font-size="11" fill="#93A9C2">{fmt_number(repo["stars"])}★</text>
              <text x="20" y="58" class="mono" font-size="10.5" fill="#6F88A4">{xml(repo["updated"])}</text>
            </g>
            """
        )

    metrics = [
        (fmt_number(totals["followers"]), "followers"),
        (fmt_number(totals["repo_stars"]), "repo stars"),
        (fmt_number(totals["public_repos"]), "public repos"),
        (fmt_number(totals["active_90"]), "active / 90d"),
    ]
    metric_rows = []
    for index, (value, label) in enumerate(metrics):
        x = 72 + index * 150
        metric_rows.append(
            f"""
            <g transform="translate({x} 404)">
              <rect width="132" height="86" rx="22" fill="#0F1C2E" fill-opacity="0.76" stroke="#36506E" stroke-opacity="0.48"/>
              <rect x="18" y="17" width="32" height="2.5" rx="1.25" fill="#7DD3FC"/>
              <text x="18" y="56" class="sans" font-size="30" font-weight="700" fill="#F3F8FF">{xml(value)}</text>
              <text x="18" y="73" class="mono" font-size="10.5" fill="#7F96B1" letter-spacing="1.1">{xml(label.upper())}</text>
            </g>
            """
        )

    return f"""<svg width="1200" height="560" viewBox="0 0 1200 560" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">sylearn profile hero</title>
  <desc id="desc">Live GitHub profile hero card for sylearn with featured repositories and current GitHub metrics.</desc>
  <defs>
    <linearGradient id="hero-bg" x1="66" y1="34" x2="1127" y2="529" gradientUnits="userSpaceOnUse">
      <stop stop-color="#07111D"/>
      <stop offset="0.52" stop-color="#091725"/>
      <stop offset="1" stop-color="#050B12"/>
    </linearGradient>
    <radialGradient id="hero-glow-a" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(988 128) rotate(136.81) scale(296 238)">
      <stop stop-color="#54D0FF" stop-opacity="0.95"/>
      <stop offset="0.52" stop-color="#235DFF" stop-opacity="0.38"/>
      <stop offset="1" stop-color="#235DFF" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="hero-glow-b" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(786 472) rotate(20.42) scale(326 226)">
      <stop stop-color="#54D0FF" stop-opacity="0.28"/>
      <stop offset="1" stop-color="#54D0FF" stop-opacity="0"/>
    </radialGradient>
    <filter id="hero-blur" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="32"/>
    </filter>
    <style>
      .sans {{
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
      }}
      .mono {{
        font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      }}
    </style>
  </defs>

  <rect x="0.5" y="0.5" width="1199" height="559" rx="32" fill="url(#hero-bg)" stroke="#1A3147"/>
  <g filter="url(#hero-blur)">
    <ellipse cx="984" cy="132" rx="228" ry="164" fill="url(#hero-glow-a)"/>
    <ellipse cx="812" cy="468" rx="236" ry="128" fill="url(#hero-glow-b)"/>
  </g>
  <g opacity="0.7">
    {render_grid(1200, 560, 120, 80)}
  </g>

  <rect x="722" y="60" width="424" height="438" rx="28" fill="#0B1624" fill-opacity="0.58" stroke="#36506E" stroke-opacity="0.55"/>
  <text x="76" y="92" class="mono" font-size="12" fill="#7DD3FC" letter-spacing="2.4">PROFILE // LIVE SURFACE</text>
  <text x="76" y="162" class="sans" font-size="90" font-weight="760" fill="#F6FAFF" letter-spacing="-3.4">sylearn</text>
  <text x="76" y="206" class="sans" font-size="28" font-weight="600" fill="#DDEBFF" letter-spacing="-0.6">Software should disappear into the work.</text>
  <text x="76" y="250" class="sans" font-size="20" font-weight="500" fill="#8FA6C4">
    <tspan x="76" dy="0">Building AI products, research systems, and developer tooling</tspan>
    <tspan x="76" dy="30">across Python, Swift, shell, and computational materials science.</tspan>
  </text>
  <text x="76" y="332" class="mono" font-size="12" fill="#6D86A2" letter-spacing="1.6">NANJING UNIVERSITY  ·  AI × COMPUTATIONAL MATERIALS SCIENCE</text>
  <text x="76" y="356" class="mono" font-size="12" fill="#6D86A2" letter-spacing="1.6">LIVE LINK  ·  SUCLOUD.VIP  ·  GITHUB.COM/SYLEARN</text>

  {"".join(metric_rows)}

  <text x="758" y="98" class="mono" font-size="12" fill="#7DD3FC" letter-spacing="2.2">FEATURED REPOSITORIES</text>
  <text x="758" y="124" class="sans" font-size="18" font-weight="600" fill="#DDEBFF">A tighter surface for the projects carrying the strongest signal.</text>
  {"".join(featured_rows)}

  <rect x="758" y="484" width="172" height="28" rx="14" fill="#102238" fill-opacity="0.9" stroke="#35506E" stroke-opacity="0.5"/>
  <text x="772" y="502" class="mono" font-size="11" fill="#9BC9FF">UPDATED {xml(updated)}</text>
</svg>
"""


def project_wall_svg(data: dict) -> str:
    cards = []
    width = 516
    height = 164
    card_positions = [
        (48, 92),
        (636, 92),
        (48, 284),
        (636, 284),
        (48, 476),
        (636, 476),
    ]
    for index, repo in enumerate(data["featured"][:6]):
        x, y = card_positions[index]
        lang_color = LANGUAGE_COLORS.get(repo["language"], "#7DD3FC")
        desc = short_text(repo["pitch"], 66)
        cards.append(
            f"""
            <g transform="translate({x} {y})">
              <rect width="{width}" height="{height}" rx="28" fill="#0E1A2B" fill-opacity="0.92" stroke="#324A67" stroke-opacity="0.68"/>
              <text x="26" y="30" class="mono" font-size="11" fill="#7DD3FC" letter-spacing="1.8">{xml(repo["eyebrow"].upper())}</text>
              <text x="26" y="66" class="sans" font-size="29" font-weight="760" fill="#F4F8FF">{xml(repo["name"])}</text>
              <text x="26" y="102" class="sans" font-size="15" font-weight="500" fill="#A9BED7">
                <tspan x="26" dy="0">{xml(desc)}</tspan>
              </text>
              <line x1="26" y1="120" x2="{width - 26}" y2="120" stroke="#23384F" stroke-opacity="0.9"/>
              <circle cx="31" cy="138" r="5" fill="{lang_color}"/>
              <text x="43" y="142" class="mono" font-size="11" fill="#DDEBFF">{xml(repo["language"])}</text>
              <text x="26" y="151" class="mono" font-size="10.5" fill="#6F88A4">UPDATED {xml(repo["updated"].upper())}</text>
              <text x="{width - 122}" y="142" class="mono" font-size="11" fill="#93A9C2" text-anchor="end">{fmt_number(repo["stars"])}★</text>
              <text x="{width - 26}" y="142" class="mono" font-size="11" fill="#93A9C2" text-anchor="end">{fmt_number(repo["forks"])} FORKS</text>
            </g>
            """
        )

    return f"""<svg width="1200" height="672" viewBox="0 0 1200 672" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">sylearn featured work</title>
  <desc id="desc">Featured projects with live GitHub statistics and descriptions.</desc>
  <defs>
    <linearGradient id="wall-bg" x1="72" y1="36" x2="1114" y2="595" gradientUnits="userSpaceOnUse">
      <stop stop-color="#07111D"/>
      <stop offset="1" stop-color="#050C14"/>
    </linearGradient>
    <radialGradient id="wall-glow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(1023 87) rotate(140.568) scale(242 158)">
      <stop stop-color="#53D0FF" stop-opacity="0.38"/>
      <stop offset="1" stop-color="#53D0FF" stop-opacity="0"/>
    </radialGradient>
    <style>
      .sans {{
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
      }}
      .mono {{
        font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      }}
    </style>
  </defs>
  <rect x="0.5" y="0.5" width="1199" height="671" rx="28" fill="url(#wall-bg)" stroke="#1A3147"/>
  <ellipse cx="1036" cy="96" rx="216" ry="144" fill="url(#wall-glow)"/>
  <text x="48" y="48" class="mono" font-size="12" fill="#7DD3FC" letter-spacing="2.4">FEATURED WORK</text>
  <text x="48" y="72" class="sans" font-size="18" font-weight="600" fill="#DDEBFF">The projects that best describe the intersection of AI product work, tooling systems, and research infrastructure.</text>
  {"".join(cards)}
</svg>
"""


def stats_svg(data: dict) -> str:
    totals = data["totals"]
    updated = data["generated_at_local"].strftime("%Y.%m.%d %H:%M")
    cards = [
        (fmt_number(totals["followers"]), "followers"),
        (fmt_number(totals["owned_repos"]), "original repos"),
        (fmt_number(totals["repo_stars"]), "repo stars"),
        (fmt_number(totals["repo_forks"]), "repo forks"),
        (fmt_number(totals["external_merges"]), "external merges"),
        (str(totals["since"]), "on github since"),
    ]
    metric_cards = []
    for index, (value, label) in enumerate(cards):
        x = 48 + index * 184
        metric_cards.append(
            f"""
            <g transform="translate({x} 88)">
              <rect width="160" height="126" rx="24" fill="#0E1B2C" fill-opacity="0.88" stroke="#344E6C" stroke-opacity="0.6"/>
              <rect x="18" y="18" width="26" height="2.5" rx="1.25" fill="#7DD3FC"/>
              <text x="18" y="72" class="sans" font-size="38" font-weight="760" fill="#F4F8FF">{xml(value)}</text>
              <text x="18" y="97" class="mono" font-size="10.5" fill="#7B93AF" letter-spacing="1.3">{xml(label.upper())}</text>
            </g>
            """
        )

    language_pills = render_language_pills(totals["languages"], 48, 246)

    return f"""<svg width="1200" height="330" viewBox="0 0 1200 330" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">sylearn telemetry</title>
  <desc id="desc">Live GitHub telemetry including followers, repositories, stars, forks, external merges, and top languages.</desc>
  <defs>
    <linearGradient id="stats-bg" x1="70" y1="34" x2="1112" y2="316" gradientUnits="userSpaceOnUse">
      <stop stop-color="#08111D"/>
      <stop offset="1" stop-color="#060C13"/>
    </linearGradient>
    <style>
      .sans {{
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
      }}
      .mono {{
        font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      }}
    </style>
  </defs>

  <rect x="0.5" y="0.5" width="1199" height="329" rx="28" fill="url(#stats-bg)" stroke="#1A3147"/>
  <text x="48" y="48" class="mono" font-size="12" fill="#7DD3FC" letter-spacing="2.4">SYSTEM TELEMETRY</text>
  <text x="48" y="72" class="sans" font-size="18" font-weight="600" fill="#DDEBFF">Generated from public GitHub APIs, then refreshed into this repository automatically.</text>
  {"".join(metric_cards)}
  {language_pills}
  <text x="48" y="302" class="mono" font-size="11" fill="#7B93AF" letter-spacing="1.2">ACTIVE IN LAST 90 DAYS  ·  {xml(str(totals["active_90"]))}  ·  LATEST SHIP  ·  {xml(totals["latest_ship"])}  ·  UPDATED  ·  {xml(updated)} UTC+8</text>
</svg>
"""


def oss_svg(data: dict) -> str:
    merges = data["external_merges"][:4]
    rows = []
    for index, item in enumerate(merges):
        y = 84 + index * 38
        rows.append(
            f"""
            <g transform="translate(424 {y})">
              <circle cx="8" cy="12" r="4" fill="#7DD3FC"/>
              <text x="24" y="15" class="sans" font-size="15" font-weight="700" fill="#F3F8FF">{xml(item["repo"])}</text>
              <text x="24" y="32" class="mono" font-size="11" fill="#85A1BE">{xml(short_text(item["title"], 74))}</text>
            </g>
            """
        )

    return f"""<svg width="1200" height="292" viewBox="0 0 1200 292" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">sylearn open source merges</title>
  <desc id="desc">Merged pull requests into external open-source repositories by sylearn.</desc>
  <defs>
    <linearGradient id="oss-bg" x1="70" y1="28" x2="1109" y2="232" gradientUnits="userSpaceOnUse">
      <stop stop-color="#07111D"/>
      <stop offset="1" stop-color="#060C13"/>
    </linearGradient>
    <radialGradient id="oss-glow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(1021 59) rotate(140.743) scale(176 118)">
      <stop stop-color="#56D3FF" stop-opacity="0.42"/>
      <stop offset="1" stop-color="#56D3FF" stop-opacity="0"/>
    </radialGradient>
    <style>
      .sans {{
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
      }}
      .mono {{
        font-family: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      }}
    </style>
  </defs>

  <rect x="0.5" y="0.5" width="1199" height="291" rx="28" fill="url(#oss-bg)" stroke="#1A3147"/>
  <ellipse cx="1016" cy="84" rx="152" ry="94" fill="url(#oss-glow)"/>
  <rect x="400" y="52" width="748" height="188" rx="24" fill="#0E1A2B" fill-opacity="0.86" stroke="#324A67" stroke-opacity="0.68"/>
  <line x1="368" y1="56" x2="368" y2="236" stroke="#23384F" stroke-opacity="0.9"/>
  <text x="48" y="48" class="mono" font-size="12" fill="#7DD3FC" letter-spacing="2.4">OPEN SOURCE SIGNAL</text>
  <text x="48" y="82" class="sans" font-size="60" font-weight="780" fill="#F4F8FF">{xml(fmt_number(len(merges)))}</text>
  <text x="48" y="112" class="mono" font-size="12" fill="#7B93AF" letter-spacing="1.7">MERGED PRS INTO EXTERNAL PROJECTS</text>
  <text x="48" y="158" class="sans" font-size="18" font-weight="600" fill="#DDEBFF">
    <tspan x="48" dy="0">Contributions across agent frameworks, research tooling,</tspan>
    <tspan x="48" dy="28">and developer products beyond this profile.</tspan>
  </text>
  <text x="424" y="78" class="mono" font-size="11" fill="#7DD3FC" letter-spacing="1.8">LATEST EXTERNAL MERGES</text>
  {"".join(rows)}
</svg>
"""


def write_asset(filename: str, content: str) -> None:
    path = ASSET_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
    path.write_text(normalized, encoding="utf-8")


def main() -> None:
    data = collect_data()
    write_asset("hero-card.svg", hero_svg(data))
    write_asset("project-wall.svg", project_wall_svg(data))
    write_asset("stats-card.svg", stats_svg(data))
    write_asset("oss-card.svg", oss_svg(data))


if __name__ == "__main__":
    main()
