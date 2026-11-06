#!/usr/bin/env python3
"""Render the profile card (assets/card-dark.svg, assets/card-light.svg).

One GraphQL call, no dependencies. Needs GH_TOKEN with `repo` + `read:user`
so private contributions and private-repo languages are counted.
"""
import datetime as dt
import html
import json
import os
import sys
import urllib.request

USER = os.environ.get("GH_USER", "yecandir")
TOKEN = os.environ["GH_TOKEN"]
OUT = os.environ.get("OUT_DIR", "assets")
IGNORED_LANGS = {"HTML", "CSS", "SCSS", "Shell", "Makefile", "Dockerfile",
                 "Batchfile", "PowerShell", "Procfile", "Smarty", "Blade",
                 "Hack", "CMake", "Objective-C", "Ruby", "C", "Kotlin"}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      restrictedContributionsCount
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        sys.exit(f"graphql error: {body['errors']}")
    return body["data"]["user"]


THEMES = {
    "dark": dict(fg="#e6edf3", muted="#8b949e", border="#30363d", empty="#161b22",
                 levels=["#0e4429", "#006d32", "#26a641", "#39d353"]),
    "light": dict(fg="#1f2328", muted="#656d76", border="#d0d7de", empty="#ebedf0",
                  levels=["#9be9a8", "#40c463", "#30a14e", "#216e39"]),
}

W, PAD = 840, 28
CELL, GAP = 11, 3
STEP = CELL + GAP


def level(count, q):
    if count == 0:
        return -1
    for i, t in enumerate(q):
        if count <= t:
            return i
    return 3


def render(user, theme):
    t = THEMES[theme]
    cc = user["contributionsCollection"]
    cal = cc["contributionCalendar"]
    total = cal["totalContributions"]
    private = cc["restrictedContributionsCount"]
    weeks = cal["weeks"][-53:]

    counts = sorted(d["contributionCount"] for w in weeks for d in w["contributionDays"]
                    if d["contributionCount"] > 0)
    q = [counts[int(len(counts) * p)] for p in (0.25, 0.5, 0.75)] if counts else [1, 2, 3]

    # streaks
    days = [d for w in weeks for d in w["contributionDays"]]
    best = cur = 0
    for d in days:
        cur = cur + 1 if d["contributionCount"] else 0
        best = max(best, cur)

    # languages, by bytes across owned non-fork repos (private included with PAT)
    langs = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            if n in IGNORED_LANGS:
                continue
            langs.setdefault(n, [0, e["node"]["color"] or t["muted"]])
            langs[n][0] += e["size"]
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]
    lang_total = sum(v[0] for _, v in top) or 1

    s = []
    a = s.append
    font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

    # --- header numbers
    y = PAD + 30
    a(f'<text x="{PAD}" y="{y}" class="big">{total:,}</text>')
    a(f'<text x="{PAD}" y="{y + 22}" class="mut">contributions in the last year</text>')
    stats = [
        (f"{private / total:.0%}" if total else "0%", "in private repos"),
        (f"{sum(1 for d in days if d['contributionCount'])}", "active days"),
        (f"{best} days", "longest streak"),
        (f"{max(d['contributionCount'] for d in days)}", "busiest day"),
    ]
    x = W - PAD
    for val, label in reversed(stats):
        a(f'<text x="{x}" y="{y}" class="mid" text-anchor="end">{val}</text>')
        a(f'<text x="{x}" y="{y + 22}" class="mut" text-anchor="end">{label}</text>')
        x -= 130

    # --- heatmap
    gx = PAD + 26
    gy = y + 62
    month_seen = None
    for wi, w in enumerate(weeks):
        first = dt.date.fromisoformat(w["contributionDays"][0]["date"])
        if first.month != month_seen and first.day <= 7 and wi < len(weeks) - 2:
            month_seen = first.month
            a(f'<text x="{gx + wi * STEP}" y="{gy - 8}" class="sm">{first.strftime("%b")}</text>')
        elif month_seen is None:
            month_seen = first.month
        for d in w["contributionDays"]:
            wd = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7  # Sun=0
            lv = level(d["contributionCount"], q)
            fill = t["empty"] if lv < 0 else t["levels"][lv]
            a(f'<rect x="{gx + wi * STEP}" y="{gy + wd * STEP}" width="{CELL}" height="{CELL}" '
              f'rx="2" fill="{fill}"><title>{d["date"]}: {d["contributionCount"]}</title></rect>')
    for wd, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        a(f'<text x="{PAD}" y="{gy + wd * STEP + 9}" class="sm">{name}</text>')

    # --- languages
    ly = gy + 7 * STEP + 34
    a(f'<text x="{PAD}" y="{ly}" class="lab">Languages</text>')
    by = ly + 12
    bw = W - 2 * PAD
    a(f'<clipPath id="bar"><rect x="{PAD}" y="{by}" width="{bw}" height="8" rx="4"/></clipPath>')
    a('<g clip-path="url(#bar)">')
    bx = PAD
    for name, (size, color) in top:
        seg = bw * size / lang_total
        a(f'<rect x="{bx:.1f}" y="{by}" width="{seg + 0.5:.1f}" height="8" fill="{color}"/>')
        bx += seg
    a('</g>')
    lx, legy = PAD, by + 30
    for name, (size, color) in top:
        label = f"{html.escape(name)} {size / lang_total:.0%}"
        a(f'<circle cx="{lx + 5}" cy="{legy - 4}" r="5" fill="{color}"/>')
        a(f'<text x="{lx + 16}" y="{legy}" class="mut">{label}</text>')
        lx += 16 + len(label) * 7.4 + 22

    h = legy + PAD - 6
    css = (f"text{{font-family:{font};fill:{t['fg']}}}"
           f".big{{font-size:32px;font-weight:600}}.mid{{font-size:22px;font-weight:600}}"
           f".mut{{font-size:13px;fill:{t['muted']}}}.sm{{font-size:10px;fill:{t['muted']}}}"
           f".lab{{font-size:13px;font-weight:600}}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
            f'role="img" aria-label="{total:,} contributions in the last year">'
            f'<style>{css}</style>'
            f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="10" fill="none" stroke="{t["border"]}"/>'
            + "".join(s) + "</svg>\n")


def main():
    user = fetch()
    os.makedirs(OUT, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(OUT, f"card-{theme}.svg"), "w") as f:
            f.write(render(user, theme))
    print("ok")


if __name__ == "__main__":
    main()
