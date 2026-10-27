#!/usr/bin/env python3
"""Build permy/states/ (51 state pages + index) from Permy's StateRules.json.

Usage: python3 tools/build-state-pages.py [path/to/StateRules.json]
Standard library only. Output is deterministic: no timestamps, sorted order.
"""
import datetime
import html
import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DEFAULT_RULES = SITE.parent / "Permy/Permy/Resources/StateRules.json"
OUT = SITE / "permy/states"
APP_STORE = "https://apps.apple.com/app/id6820481576"
WARNING = ("Permy is an independent app, not affiliated with any state agency. "
           "Confirm the current requirements with your state agency before relying on them.")
NIGHT_TEXT = {
    "sunsetToSunrise": "Night runs from sunset to sunrise.",
    "sunset30ToSunrise30": "Night starts 30 minutes after sunset and ends 30 minutes before sunrise.",
    "sunsetMinus30ToSunrisePlus30": "Night starts 30 minutes before sunset and ends 30 minutes after sunrise.",
}
# Sentences in `notes` that are internal to the app team, not for parents.
INTERNAL = ("Source URL still needs", "Verified structured behavior")

e = html.escape


def hours(n):
    return f"{n} hour" + ("" if n == 1 else "s")


def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def place(name):
    return "the District of Columbia" if name == "District of Columbia" else name


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def clean_notes(text):
    parts = re.split(r"(?<=[.!?])\s+", text or "")
    return " ".join(p for p in parts if p and not p.startswith(INTERNAL))


def page(title, desc, body, depth, current=""):
    up = "../" * depth
    cur = ' aria-current="page"' if current else ""
    nav = (f'<a href="{up}">Support</a><a href="{up}privacy.html">Privacy</a>'
           f'<a href="{up}states/"{cur}>States</a>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="stylesheet" href="{up}style.css">
</head>
<body>
<header>
  <a class="brand" href="{up}">Permy</a>
  <nav>{nav}</nav>
</header>
<main>
{body}
</main>
<footer>Permy is not affiliated with any state agency or DMV.</footer>
</body>
</html>
"""


def answer_items(v, name):
    """Short-answer list items for the default rule version."""
    items = []
    if v.get("noStateMinimum"):
        return [f"{name} has no state minimum for supervised hours in the sources Permy checked. "
                "Set your own goal. Permy suggests 50 total hours with 10 at night."]
    if not v["totalHours"]:
        return ["Which requirement applies depends on the learner. See the pathways below."]
    items.append(f"<b>Total:</b> {hours(v['totalHours'])} of supervised driving")
    if v["nightHours"]:
        items.append(f"<b>Night:</b> {hours(v['nightHours'])} of the total")
    elif not v.get("nightOrInclementHours"):
        items.append("<b>Night:</b> no separate night requirement listed")
    if v.get("inclementHours"):
        items.append(f"<b>Bad weather:</b> {hours(v['inclementHours'])} of the total")
    if v.get("nightOrInclementHours"):
        items.append(f"<b>Night or bad weather:</b> {hours(v['nightOrInclementHours'])} combined")
    for c in v.get("checkpoints", []):
        items.append(f"<b>{e(c['label'])}:</b> {hours(c['totalHours'])} total, "
                     f"{hours(c['nightHours'])} at night")
    return items


def cap_paragraph(v, name):
    """The Daily/weekly limit section, or '' when the state has none."""
    profile = v["requirementProfiles"][0]
    daily = v.get("dailyCapMinutes") or profile.get("dailyCapMinutes")
    weekly = v.get("weeklyCapMinutes") or profile.get("weeklyCapMinutes")
    if not (daily or weekly):
        return ""
    if daily:
        limit = f"{hours(daily // 60)} a day"
        what = "On a day you drive more than that"
    else:
        limit = f"{hours(weekly // 60)} a week"
        week = v.get("weekStartsOn") or profile.get("weekStartsOn")
        what = "In a week where you drive more than that"
    out = f"<h2>Daily/weekly limit in {e(place(name))}</h2>\n"
    out += f"<p>Only {limit} of driving counts toward the requirement. "
    if weekly and week:
        out += f"Permy counts weeks from {e(week.capitalize())}, because the state's rules don't say. "
    out += (f"{what}, Permy keeps every minute in your log and shows how much of it counts, "
            "so your totals match what the state allows.</p>\n")
    return out


def night_section(v, name):
    np_ = v["nightPolicy"]
    out = f"<h2>What counts as night in {e(place(name))}</h2>\n"
    out += f"<p>{NIGHT_TEXT[np_['calculationDefinition']]}"
    out += " Permy works out sunset and sunrise from where you drive.</p>\n"
    if np_.get("legalWording"):
        out += f"<p>The state's wording: “{e(np_['legalWording'])}”</p>\n"
    if np_.get("displayNote"):
        out += f"<p>{e(np_['displayNote'])}</p>\n"
    return out


def pathways_section(v):
    profiles = v["requirementProfiles"]
    if len(profiles) < 2:
        return ""
    out = "<h2>Pathways</h2>\n<p>This state has more than one set of requirements. Which one applies depends on the learner.</p>\n<ul>\n"
    for p in profiles:
        line = f"<b>{e(p['label'])}</b>: {e(p['summaryLabel'])}"
        if p.get("applicabilityNote"):
            line += f". {e(p['applicabilityNote'])}"
        out += f"  <li>{line}</li>\n"
    return out + "</ul>\n"


def sources_section(v, checked):
    out = "<h2>Sources</h2>\n"
    notes = clean_notes(v.get("notes"))
    if notes:
        out += f"<p>{e(notes)}</p>\n"
    if v.get("verifiedDetails"):
        out += "<ul>\n"
        for t in v["verifiedDetails"]:
            out += f"  <li>{e(t['rule'])} (<a href=\"{e(t['source'])}\" rel=\"noopener\">source</a>)</li>\n"
        out += "</ul>\n"
    if v.get("openQuestions"):
        out += "<p>Open questions: " + " ".join(e(q) for q in v["openQuestions"]) + "</p>\n"
    out += "<p>Official sources:</p>\n<ul>\n"
    for s in v["sources"]:
        out += f"  <li><a href=\"{e(s['url'])}\" rel=\"noopener\">{e(s['name'])}</a></li>\n"
    out += f"</ul>\n<p class=\"meta\">Checked {long_date(checked)}.</p>\n"
    return out


def state_page(j, all_states, data):
    name = j["name"]
    v = next(x for x in j["versions"] if x["versionID"] == j["defaultRuleVersionID"])
    checked = v.get("verifiedAt") or v.get("sourceLastCheckedAt") or data["asOf"]
    q = f"Teen permit driving hours in {place(name)} (2026): total, night, what counts"
    items = "".join(f"    <li>{i}</li>\n" for i in answer_items(v, place(name)))
    others = " ".join(f'<a href="../{slug(s["name"])}/">{e(s["name"])}</a>'
                      for s in all_states if s["stateCode"] != j["stateCode"])
    body = f"""  <h1>{e(q)}</h1>
  <div class="answer">
    <h2>Short answer</h2>
    <ul>
{items}    </ul>
  </div>
  <p class="warn">{e(WARNING)}</p>
{night_section(v, name)}{cap_paragraph(v, name)}{pathways_section(v)}{sources_section(v, checked)}
  <p class="cta">Permy counts these hours the way {e(place(name))} counts them and works out night from your local sunset. <a href="{APP_STORE}">Get Permy on the App Store</a>.</p>

  <h2>Other states</h2>
  <p class="states"><a href="../">All states</a> {others}</p>"""
    desc = (f"How many supervised driving hours a learner's permit holder logs in {place(name)}, "
            "how night is counted, and where the numbers come from.")
    return page(q, desc, body, 2)


def index_page(states):
    links = "".join(f'  <li><a href="{slug(s["name"])}/">{e(s["name"])}</a></li>\n' for s in states)
    body = f"""  <h1>Teen permit driving hours by state</h1>
  <p class="lead">Pick a state to see its supervised driving hours, how it counts night, and the official sources.</p>
  <p class="warn">{e(WARNING)}</p>
  <ul class="state-list">
{links}  </ul>
  <p class="cta">Permy counts these hours the way your state counts them. <a href="{APP_STORE}">Get Permy on the App Store</a>.</p>"""
    return page("Teen permit driving hours by state (2026)",
                "Supervised driving hours for learner's permit holders in all 50 states and DC.",
                body, 1, current="states")


def main():
    rules = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RULES
    data = json.loads(rules.read_text())
    states = sorted(data["jurisdictions"], key=lambda j: j["name"])
    assert len(states) == 51, len(states)
    for j in states:
        d = OUT / slug(j["name"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(state_page(j, states, data))
    (OUT / "index.html").write_text(index_page(states))
    print(f"wrote {len(states)} state pages + index to {OUT}")


if __name__ == "__main__":
    main()
