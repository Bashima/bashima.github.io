#!/usr/bin/env python3
"""
prerender.py  --  Make bashima.github.io (personal site) readable by LLMs & crawlers.

index.html fills its News, Collaborators, Funding, and Publications sections in the
browser with JavaScript (fetching JSON from the lab site bashlab.github.io + the
GitHub publications.bib). Tools that don't run JS see empty sections. This script
fetches the same data at build time and bakes the rendered content straight into
index.html (between <!--PRERENDER:name--> markers, idempotently), and writes
llms.txt, sitemap.xml, robots.txt, a meta description and schema.org JSON-LD.

Run whenever the content changes:   python3 prerender.py
Standard library only -- no dependencies.
"""

import html
import json
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "https://bashimaislam.com"
LAB = "https://bashlab.github.io"          # shared data lives on the lab site
BIB_URL = "https://raw.githubusercontent.com/BASHLab/publications/main/publications.bib"


# --------------------------------------------------------------------------- #
def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def red(s):
    """[red]..[/red] -> blue bold, matching the page's processRedTags()."""
    s = html.escape("" if s is None else str(s), quote=False)
    return re.sub(r"\[red\](.*?)\[/red\]", r'<b style="color: #2066a1;">\1</b>', s)


def plain(s):
    return re.sub(r"\[/?red\]", "", "" if s is None else str(s)).strip()


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bashima-prerender"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bashima-prerender"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def read_file(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def write_file(name, content):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        f.write(content)


# --------------------------------------------------------------------------- #
# idempotent injection between markers
# --------------------------------------------------------------------------- #
def inject_into(html_text, element_id, name, block):
    wrapped = "\n<!--PRERENDER:%s-->\n%s\n<!--/PRERENDER:%s-->" % (name, block, name)
    open_re = r'(<[a-zA-Z][^>]*\bid="%s"[^>]*>)' % re.escape(element_id)
    strip_re = re.compile(open_re + r"\s*<!--PRERENDER:%s-->.*?<!--/PRERENDER:%s-->" % (re.escape(name), re.escape(name)), re.DOTALL)
    html_text = strip_re.sub(r"\1", html_text)
    new_text, n = re.subn(re.compile(open_re), lambda m: m.group(1) + wrapped, html_text, count=1)
    if n == 0:
        raise RuntimeError("element id=%r not found" % element_id)
    return new_text


def inject_before(html_text, anchor, name, block):
    wrapped = "<!--PRERENDER:%s-->\n%s\n<!--/PRERENDER:%s-->\n" % (name, block, name)
    strip_re = re.compile(r"<!--PRERENDER:%s-->.*?<!--/PRERENDER:%s-->\s*" % (re.escape(name), re.escape(name)), re.DOTALL)
    html_text = strip_re.sub("", html_text)
    idx = html_text.find(anchor)
    if idx == -1:
        raise RuntimeError("anchor %r not found" % anchor[:40])
    return html_text[:idx] + wrapped + html_text[idx:]


# --------------------------------------------------------------------------- #
# renderers (mirror the page's own JS output)
# --------------------------------------------------------------------------- #
def render_recent_news(news):
    news = [n for n in news if n.get("category") != "internship"]  # personal site excludes internships
    items = []
    for it in news[:10]:
        url = it.get("url") or ""
        tgt = ' target="_blank"' if url else ""
        items.append('<a href="%s"%s><p class="u-mb-10">%s</p></a>' % (esc(url), tgt, red(it.get("title"))))
    return "".join(items)


def render_grants(funding):
    grants = funding.get("grants", [])
    return "".join(
        '<p class="u-mb-10">%d. %s, %s, Role: %s</p>' % (i + 1, esc(g.get("title")), esc(g.get("amount")), esc(g.get("role")))
        for i, g in enumerate(grants)
    )


def render_collaborators(team):
    cells = []
    for c in team.get("collaborators", []):
        cells.append(
            '<div class="collaborator-item">'
            '<img src="%s/img/%s" alt="%s" class="collaborator-logo" onerror="this.style.display=\'none\'">'
            '<p class="collaborator-name">%s</p></div>'
            % (LAB, esc(c.get("logo")), esc(c.get("name")), esc(c.get("name")))
        )
    return "".join(cells)


# ---- BibTeX (same parser as the lab site) ---------------------------------- #
def clean_tex(v):
    v = re.sub(r"\s+", " ", v.replace("\n", " ")).strip().replace("~", " ")
    v = v.replace("{\\%}", "%").replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("\\#", "#").replace("\\$", "$")
    v = re.sub(r"\\[`'^\"~=.]\{?([A-Za-z])\}?", r"\1", v)
    v = re.sub(r"\\[A-Za-z]+", "", v)
    v = v.replace("{", "").replace("}", "").replace("--", "\u2013")
    return v.strip().strip(",. ")


def format_authors(a):
    out = []
    for p in re.split(r"\s+and\s+", a.replace("\n", " ")):
        p = p.strip().strip(",").replace("{", "").replace("}", "")
        if not p:
            continue
        if "," in p:
            last, first = p.split(",", 1)
            p = first.strip() + " " + last.strip()
        p = clean_tex(p)
        if p:
            out.append(p)
    return ", ".join(out)


def parse_bibtex(text):
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("%"))
    entries, i = [], 0
    while True:
        at = text.find("@", i)
        if at < 0:
            break
        brace = text.find("{", at)
        if brace < 0:
            break
        etype = text[at + 1 : brace].strip().lower()
        depth, j = 0, brace
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        body = text[brace + 1 : j]
        i = j + 1
        if etype in ("comment", "string", "preamble"):
            continue
        comma = body.find(",")
        if comma < 0:
            continue
        fields = {}
        for m in re.finditer(r'(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|"[^"]*"|[^,\n]+)', body[comma + 1 :]):
            fields[m.group(1).lower()] = m.group(2).strip().strip('{}"')
        if "year" in fields:
            entries.append(fields)
    return entries


def render_publications(entries):
    by_year = {}
    for e in entries:
        y = clean_tex(e.get("year", "")) or "Other"
        by_year.setdefault(y, []).append(e)

    def yk(y):
        m = re.search(r"\d{4}", y)
        return int(m.group()) if m else -1

    blocks = []
    for year in sorted(by_year, key=yk, reverse=True):
        lis = []
        for e in by_year[year]:
            title = clean_tex(e.get("title", ""))
            authors = format_authors(e.get("author", ""))
            venue = clean_tex(e.get("journal") or e.get("booktitle") or e.get("publisher") or "")
            url = clean_tex(e.get("url", "")) or ("https://doi.org/" + clean_tex(e["doi"]) if e.get("doi") else "")
            bits = ["<strong>%s</strong>" % esc(title)]
            if authors:
                bits.append(esc(authors))
            if venue:
                bits.append("<em>%s</em>" % esc(venue))
            line = ". ".join(bits) + (", %s." % esc(year) if year != "Other" else ".")
            if url:
                line += ' [<a href="%s" target="_blank">link</a>]' % esc(url)
            lis.append("<li style='margin-bottom:10px;'>%s</li>" % line)
        blocks.append("<h3>%s</h3><ul>%s</ul>" % (esc(year), "".join(lis)))
    return '<div id="pub-fallback">%s</div>' % "".join(blocks)


# --------------------------------------------------------------------------- #
def head_block(pubs, news):
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Bashima Islam",
        "jobTitle": "Assistant Professor",
        "affiliation": {"@type": "CollegeOrUniversity", "name": "University of Massachusetts Amherst"},
        "url": BASE_URL,
        "sameAs": ["https://bashlab.github.io", "https://github.com/BASHLab", "https://scholar.google.com/citations?user=", "https://www.youtube.com/@BASHLab_UMass"],
        "description": "Assistant Professor at UMass Amherst leading the BASH Lab (Bridging AI and Sensing for Health): "
                       "ubiquitous AI, multimodal sensing, sensor-grounded language models, and low-power edge ML.",
    }
    ld = json.dumps({"@context": "https://schema.org", "@graph": [person]}, ensure_ascii=False, indent=2)
    desc = ("Bashima Islam \u2014 Assistant Professor at UMass Amherst, director of the BASH Lab "
            "(Bridging AI and Sensing for Health). Research in ubiquitous AI, multimodal sensing, "
            "sensor-grounded language models, and low-power edge machine learning.")
    return (
        '<meta name="description" content="%s">\n'
        '<meta property="og:title" content="Bashima Islam">\n'
        '<meta property="og:description" content="%s">\n'
        '<meta property="og:type" content="profile">\n'
        '<meta name="robots" content="index, follow">\n'
        '<meta http-equiv="Cache-Control" content="no-cache, must-revalidate">\n'
        '<meta http-equiv="Pragma" content="no-cache">\n'
        '<script type="application/ld+json">\n%s\n</script>'
    ) % (esc(desc), esc(desc), ld)


def build_llms(news, team, funding, pubs):
    L = ["# Bashima Islam", ""]
    L.append("> Assistant Professor at the University of Massachusetts Amherst and director of the BASH Lab "
             "(Bridging AI and Sensing for Health). Research in ubiquitous AI, multimodal sensing, sensor-grounded "
             "language models, and resource-constrained (edge / TinyML) machine learning for health and well-being.")
    L += ["", "Personal site: %s" % BASE_URL, "Lab: %s" % LAB, ""]
    L.append("## Recent News")
    for n in [x for x in news if x.get("category") != "internship"][:10]:
        line = "- %s: %s" % (plain(n.get("date")), plain(n.get("title")))
        if n.get("url"):
            line += " (%s)" % n["url"]
        L.append(line)
    L.append("")
    L.append("## Funding")
    if funding.get("chartData", {}).get("total"):
        L.append("Total: $%sK" % funding["chartData"]["total"])
    for g in funding.get("grants", []):
        L.append("- %s, %s, role: %s" % (plain(g.get("title")), plain(g.get("amount")), plain(g.get("role"))))
    L.append("")
    L.append("## Collaborating Institutions")
    L.append(", ".join(plain(c.get("name")) for c in team.get("collaborators", [])))
    L.append("")
    L.append("## Publications")
    for e in pubs:
        title = clean_tex(e.get("title", ""))
        authors = format_authors(e.get("author", ""))
        venue = clean_tex(e.get("journal") or e.get("booktitle") or e.get("publisher") or "")
        year = clean_tex(e.get("year", ""))
        url = clean_tex(e.get("url", "")) or ("https://doi.org/" + clean_tex(e["doi"]) if e.get("doi") else "")
        L.append("- %s. %s. %s %s%s" % (title, authors, venue, year, " " + url if url else ""))
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
def main():
    print("Fetching data from %s ..." % LAB)
    news = fetch_json(LAB + "/news.json")
    team = fetch_json(LAB + "/team.json")
    funding = fetch_json(LAB + "/funding.json")
    pubs = parse_bibtex(fetch_text(BIB_URL))
    print("news=%d, collaborators=%d, grants=%d, publications=%d"
          % (len(news), len(team.get("collaborators", [])), len(funding.get("grants", [])), len(pubs)))

    h = read_file("index.html")
    h = inject_into(h, "recent-news", "news", render_recent_news(news))
    h = inject_into(h, "funding-grants", "grants", render_grants(funding))
    h = inject_into(h, "collaborators-grid", "collaborators", render_collaborators(team))
    h = inject_before(h, '<div class="bibtex_structure">', "publications", render_publications(pubs))
    h = inject_before(h, "</head>", "head", head_block(pubs, news))
    write_file("index.html", h)

    write_file("llms.txt", build_llms(news, team, funding, pubs))
    write_file("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               '  <url><loc>%s/</loc></url>\n</urlset>\n' % BASE_URL)
    write_file("robots.txt", "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % BASE_URL)
    print("Prerender complete: index.html + llms.txt + sitemap.xml + robots.txt")


if __name__ == "__main__":
    main()
