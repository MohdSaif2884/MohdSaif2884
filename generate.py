
#!/usr/bin/env python3
"""Generate animated black-and-gold GitHub profile SVG cards."""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET

from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from html import escape

# ==========================================
# CONFIGURATION
# ==========================================

CONFIG = {
    "username": "MohdSaif2884",
    "name": "Mohd Saif",
    "tagline": "AI  ·  DEVOPS / CLOUD  ·  FULLSTACK DEVELOPER",
    "bio": "B.Tech AI @ KIET. AWS certified. Building, shipping, repeat.",
    "location": "Ghaziabad, India",
    "max_repos": 6,
    "title_repo_count": 3,
    "output_dir": "assets"
}

GOLD = "#f5c542"
GOLD2 = "#b8860b"
DIM = "#8a7a4a"
BG = "#0b0803"
LINE = "#3a2e10"
TXT = "#e8dfc4"

FONT = "'Segoe UI','Helvetica Neue',Arial,sans-serif"
MONO = "'Courier New',Consolas,monospace"

W = 840


# ==========================================
# HELPERS
# ==========================================

def esc(value):
    return escape(str(value), quote=True)


def truncate(value, limit):
    value = str(value or "")

    if len(value) <= limit:
        return value

    return value[:limit - 1].rstrip() + "…"


def api(url, payload=None):

    headers = {
        "User-Agent": "github-title-sequence",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = None

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as ex:

        details = ex.read().decode(
            "utf-8", errors="replace"
        )

        if ex.code == 403 and "rate limit" in details.lower():
            raise RuntimeError(
                "GitHub API rate limit exceeded."
            )

        raise RuntimeError(
            f"GitHub API HTTP {ex.code}: {details}"
        )

    except urllib.error.URLError as ex:
        raise RuntimeError(f"Network error: {ex}")


# ==========================================
# FETCH REPOSITORIES
# ==========================================

def fetch_repositories(username):

    repos = []
    page = 1

    while True:

        query = urllib.parse.urlencode({
            "per_page": 100,
            "sort": "updated",
            "type": "owner",
            "page": page
        })

        batch = api(
            f"https://api.github.com/users/{username}/repos?{query}"
        )

        if not batch:
            break

        repos.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    # Exclude forked repositories
    return [
        repo for repo in repos
        if not repo.get("fork", False)
    ]


# ==========================================
# FETCH REAL LANGUAGE PERCENTAGES
# ==========================================

def fetch_languages(repos):

    totals = Counter()

    for repo in repos:

        try:

            languages = api(repo["languages_url"])

            if isinstance(languages, dict):
                totals.update(languages)

        except Exception as ex:
            print(
                f"Language fetch warning: "
                f"{repo['name']}: {ex}"
            )

    total = sum(totals.values())

    if not total:
        return []

    exact = {
        lang: count * 100 / total
        for lang, count in totals.items()
    }

    percentages = {
        lang: int(value)
        for lang, value in exact.items()
    }

    remainder = 100 - sum(percentages.values())

    order = sorted(
        exact,
        key=lambda lang: exact[lang] - percentages[lang],
        reverse=True
    )

    for lang in order[:remainder]:
        percentages[lang] += 1

    return sorted(
        percentages.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]


# ==========================================
# FETCH CONTRIBUTION CALENDAR
# ==========================================

def fetch_contributions(username):

    if not os.getenv("GITHUB_TOKEN"):
        print("Contribution heatmap requires GITHUB_TOKEN.")
        return None, "—", "—"

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    result = api(
        "https://api.github.com/graphql",
        {
            "query": query,
            "variables": {"login": username}
        }
    )

    if result.get("errors"):
        raise RuntimeError(result["errors"])

    user = result["data"]["user"]

    calendar = (
        user["contributionsCollection"]
        ["contributionCalendar"]
    )

    weeks = [
        [
            day["contributionCount"]
            for day in week["contributionDays"]
        ]
        for week in calendar["weeks"]
    ][-26:]

    # Longest active streak within displayed 26 weeks
    best = current = 0

    for day in (x for week in weeks for x in week):

        if day > 0:
            current += 1
            best = max(best, current)
        else:
            current = 0

    return (
        weeks,
        calendar["totalContributions"],
        best
    )


# ==========================================
# FETCH ALL PROFILE DATA
# ==========================================

def fetch_data():

    data = {
        "followers": "—",
        "repos_n": "—",
        "account_days": "—",
        "repos": [],
        "langs": [],
        "heat": None,
        "total": "—",
        "streak": "—",
        "rest_ok": False
    }

    username = CONFIG["username"]

    try:

        user = api(
            f"https://api.github.com/users/{username}"
        )

        data["followers"] = user["followers"]
        data["repos_n"] = user["public_repos"]

        created = datetime.fromisoformat(
            user["created_at"].replace("Z", "+00:00")
        )

        data["account_days"] = (
            datetime.now(timezone.utc) - created
        ).days

        repos = fetch_repositories(username)

        repos.sort(
            key=lambda r: (
                r["stargazers_count"],
                r["pushed_at"] or ""
            ),
            reverse=True
        )

        data["repos"] = [
            (
                r["name"],
                r["description"] or "No description",
                r["stargazers_count"]
            )
            for r in repos[:CONFIG["max_repos"]]
        ]

        data["langs"] = fetch_languages(repos)

        data["rest_ok"] = True

        print(
            f"REST API OK: {len(repos)} repositories"
        )

    except Exception as ex:
        print("REST API ERROR:", ex)

    if not data["repos"]:
        data["repos"] = [
            ("Data unavailable", "Check GitHub API", 0)
        ]

    if not data["langs"]:
        data["langs"] = [
            ("Language data unavailable", 0)
        ]

    if data["rest_ok"]:

        try:

            (
                data["heat"],
                data["total"],
                data["streak"]
            ) = fetch_contributions(username)

            if data["heat"] is not None:
                print("GraphQL contribution data loaded.")

        except Exception as ex:
            print("GraphQL ERROR:", ex)

    return data


# ==========================================
# SVG WRAPPER
# ==========================================

def wrap(height, body):

    return f'''<svg xmlns="http://www.w3.org/2000/svg"
width="{W}" height="{height}"
viewBox="0 0 {W} {height}">

<defs>

<linearGradient id="background" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#17120a"/>
<stop offset="1" stop-color="{BG}"/>
</linearGradient>

<linearGradient id="gold" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="{GOLD2}"/>
<stop offset=".5" stop-color="#ffe08a"/>
<stop offset="1" stop-color="{GOLD2}"/>

<animate attributeName="x1"
values="-1;1" dur="4s"
repeatCount="indefinite"/>

<animate attributeName="x2"
values="0;2" dur="4s"
repeatCount="indefinite"/>

</linearGradient>

<clipPath id="card">
<rect width="{W}" height="{height}" rx="16"/>
</clipPath>

</defs>

<style>

text {{
font-family:{FONT};
fill:{TXT};
}}

.m {{
font-family:{MONO};
}}

.lbl {{
font:700 10px {MONO};
letter-spacing:4px;
fill:{GOLD2};
}}

.fade {{
opacity:0;
animation:fade-in 1s ease forwards;
}}

@keyframes fade-in {{
to {{ opacity:1; }}
}}

</style>

<g clip-path="url(#card)">

<rect width="{W}" height="{height}"
fill="url(#background)"/>

<rect x=".5" y=".5"
width="{W-1}" height="{height-1}"
rx="16"
fill="none"
stroke="{LINE}"/>

{body}

</g>
</svg>'''


# ==========================================
# CARD 1: TITLE
# ==========================================

def title(d):

    lines = ""

    for i, (name, desc, stars) in enumerate(
        d["repos"][:CONFIG["title_repo_count"]]
    ):

        star = f" &#9733; {stars}" if stars else ""

        lines += f'''
<text class="fade m"
x="{W/2}" y="{186+i*24}"
text-anchor="middle"
font-size="14"
style="animation-delay:{1+i*.8}s">

starring

<tspan fill="{GOLD}" font-weight="700">
{esc(truncate(name, 38))}
</tspan>

{star}

</text>'''

    body = f'''
<text class="lbl"
x="{W/2}" y="52"
text-anchor="middle">
GITHUB PICTURES PRESENTS
</text>

<text x="{W/2}" y="120"
text-anchor="middle"
font-size="62"
font-weight="900"
letter-spacing="3"
style="fill:url(#gold);stroke:#000;stroke-width:1">

{esc(CONFIG["name"].upper())}

</text>

<text class="m"
x="{W/2}" y="152"
text-anchor="middle"
font-size="13"
letter-spacing="3"
style="fill:{DIM}">

{esc(CONFIG["tagline"])}

</text>

{lines}

<line x1="30" y1="262"
x2="{W-30}" y2="262"
stroke="{LINE}"/>

<text class="m" x="30" y="282"
font-size="11" style="fill:{DIM}">

{esc(d["total"])} contributions
· {esc(d["followers"])} followers
· {esc(d["repos_n"])} repos

</text>

<text class="m"
x="{W-30}" y="282"
text-anchor="end"
font-size="11"
style="fill:{DIM}">

github.com/{esc(CONFIG["username"])}

</text>
'''

    return wrap(300, body)


# ==========================================
# CARD 2: LEAD
# ==========================================

def lead(d):

    initials = "".join(
        word[0]
        for word in CONFIG["name"].split()[:2]
    ).upper()

    body = f'''
<text class="lbl" x="30" y="36">
THE LEAD
</text>

<text x="30" y="78"
font-size="26"
font-weight="700">

{esc(CONFIG["name"])}

</text>

<text x="30" y="104"
font-size="14"
style="fill:{DIM}">

{esc(CONFIG["bio"])}

</text>

<text class="m"
x="30" y="132"
font-size="11"
style="fill:{DIM}">

{esc(CONFIG["location"])}
· @{esc(CONFIG["username"])}
· {d["followers"]} followers
· {d["repos_n"]} repositories

</text>

<circle cx="760" cy="80"
r="46"
fill="#1d160a"
stroke="{GOLD}"
stroke-width="3">

<animate attributeName="stroke-opacity"
values="1;.4;1"
dur="3s"
repeatCount="indefinite"/>

</circle>

<text x="760" y="92"
text-anchor="middle"
font-size="32"
font-weight="800"
style="fill:{GOLD}">

{initials}

</text>
'''

    return wrap(160, body)


# ==========================================
# CARD 3: STARRING
# ==========================================

def starring(d):

    rows = ""

    for i, (name, desc, stars) in enumerate(d["repos"]):

        y = 80 + i * 40

        repo_name = esc(truncate(name, 33))
        description = esc(truncate(desc, 46))

        star = (
            f"&#9733; {stars}"
            if stars else "&#8212;"
        )

        rows += f'''
<g class="fade"
style="animation-delay:{i*.2}s">

<line x1="30" y1="{y-26}"
x2="810" y2="{y-26}"
stroke="{LINE}"/>

<text class="m"
x="30" y="{y}"
font-size="11"
style="fill:{DIM}">

{i+1:02d}

</text>

<text x="66" y="{y}"
font-size="13"
font-weight="700">

{repo_name}

</text>

<text x="405" y="{y}"
font-size="11"
style="fill:{DIM}">

{description}

</text>

<text class="m"
x="810" y="{y}"
text-anchor="end"
font-size="12"
style="fill:{GOLD}">

{star}

</text>

</g>
'''

    height = 80 + len(d["repos"]) * 40

    body = f'''
<text class="lbl" x="30" y="36">
STARRING · SELECTED REPOSITORIES
</text>

{rows}
'''

    return wrap(height, body)


# ==========================================
# CARD 4: CAST
# ==========================================

def cast(d):

    colors = [
        "#3178c6",
        "#f7df1e",
        "#41b883",
        "#7f8fc7",
        "#e44d26"
    ]

    rows = ""

    for i, (lang, pct) in enumerate(d["langs"]):

        y = 76 + i * 34
        bar_width = max(0, min(520, 520 * pct / 100))

        rows += f'''
<text x="30" y="{y+4}"
font-size="13"
font-weight="600">

{esc(lang)}

</text>

<rect x="190" y="{y-8}"
width="520"
height="12"
rx="6"
fill="#1d160a"/>

<rect x="190" y="{y-8}"
width="0"
height="12"
rx="6"
fill="{colors[i%5]}">

<animate attributeName="width"
from="0"
to="{bar_width}"
dur="1.4s"
begin="{i*.2}s"
fill="freeze"/>

</rect>

<text class="m"
x="810" y="{y+4}"
text-anchor="end"
font-size="12"
style="fill:{DIM}">

{pct}%

</text>
'''

    body = f'''
<text class="lbl" x="30" y="36">
THE CAST · LANGUAGE SHARE BY CODE BYTES
</text>

{rows}
'''

    return wrap(76 + len(d["langs"]) * 34, body)


# ==========================================
# CARD 5: SCENES
# ==========================================

def scenes(d):

    shades = [
        "#1d160a",
        "#4a3a10",
        "#7a5f12",
        "#b8860b",
        "#f5c542"
    ]

    weeks = d["heat"]

    if weeks is None:
        # Never display invented contribution activity.
        weeks = [[0] * 7 for _ in range(26)]

    cells = ""

    for wi, week in enumerate(weeks[-26:]):

        for di, count in enumerate(week):

            level = (
                0 if count == 0 else
                1 if count < 2 else
                2 if count < 4 else
                3 if count < 7 else 4
            )

            anim = ""

            if level >= 3:

                anim = f'''
<animate attributeName="opacity"
values="1;.55;1"
dur="{3+(wi*7+di)%5}s"
repeatCount="indefinite"/>
'''

            cells += f'''
<rect
x="{30+wi*17}"
y="{60+di*17}"
width="14"
height="14"
rx="3"
fill="{shades[level]}">

{anim}

</rect>
'''

    note = (
        "Current-year contribution calendar"
        if d["heat"] is not None
        else "Set GITHUB_TOKEN for real contribution data"
    )

    stats = [
        ("ACCOUNT AGE", f'{d["account_days"]} days'),
        ("LONGEST ACTIVE RUN · 26 WEEKS", f'{d["streak"]} days'),
        ("CONTRIBUTIONS · CURRENT YEAR", d["total"])
    ]

    stat_markup = ""

    for i, (label, value) in enumerate(stats):

        stat_markup += f'''
<text class="m"
x="520"
y="{78+i*50}"
font-size="9"
letter-spacing="1.5"
style="fill:{DIM}">

{esc(label)}

</text>

<text x="520"
y="{102+i*50}"
font-size="20"
font-weight="700">

{esc(value)}

</text>
'''

    body = f'''
<text class="lbl" x="30" y="36">
BEHIND THE SCENES · 26 WEEKS
</text>

{cells}

{stat_markup}

<text class="m"
x="520" y="190"
font-size="9"
style="fill:{DIM}">

{esc(note)}

</text>
'''

    return wrap(210, body)


# ==========================================
# GENERATE ALL FIVE SVG FILES
# ==========================================

def main():

    data = fetch_data()

    output = Path(CONFIG["output_dir"])
    output.mkdir(parents=True, exist_ok=True)

    cards = [
        ("title.svg", title),
        ("lead.svg", lead),
        ("starring.svg", starring),
        ("cast.svg", cast),
        ("scenes.svg", scenes)
    ]

    for filename, renderer in cards:

        svg = renderer(data)

        # Validate generated SVG XML
        ET.fromstring(svg)

        path = output / filename

        path.write_text(
            svg,
            encoding="utf-8",
            newline="\n"
        )

        print(f"Created: {path}")

    print("\nSUCCESS: All five SVG cards generated.")

    if not data["rest_ok"]:
        print("WARNING: GitHub REST data unavailable.")

    if data["heat"] is None:
        print("NOTE: Contribution heatmap needs a valid GITHUB_TOKEN.")


if __name__ == "__main__":
    main()
