#!/usr/bin/env python3
"""Toptien data-updater.

Haalt de wereldwijde Netflix Top 10 (Engelstalig + niet-Engelstalig) en de
Bestseller 60 (top 25) op, downloadt de afbeeldingen, verkleint ze en schrijft
data.json + img/ in de opgegeven map.

Gebruik:  python3 -I update.py <uitvoermap> [vertalingen.json]

vertalingen.json (optioneel) = {"<Engelse Netflix-titel incl. seizoen>": "<Nederlandse beschrijving>"}.
Zonder vertaling toont de app de Engelse Netflix-beschrijving.
Vereist: Python 3 + Pillow, netwerktoegang tot www.netflix.com, dnm.nflximg.net,
www.debestseller60.nl en static.unbidan.nl.
"""
import html, io, json, os, re, sys, urllib.request, datetime
from PIL import Image

UA = {"User-Agent": "Mozilla/5.0 (Toptien updater)"}
MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def get(url, tries=3):
    import http.client, time
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except http.client.IncompleteRead as e:
            if len(e.partial) > 500_000 or i == tries - 1:
                return e.partial
        except Exception:
            if i == tries - 1:
                raise
        time.sleep(2)


def dec(x):
    x = re.sub(r"\\+u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), x)
    return re.sub(r"\\+(.)", r"\1", x)


def clean(x):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))).strip()


def save_img(url, path, width):
    try:
        im = Image.open(io.BytesIO(get(url))).convert("RGB")
    except Exception as e:  # noqa
        print("  ! afbeelding mislukt:", url, e, file=sys.stderr)
        return ""
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "JPEG", quality=80, optimize=True, progressive=True)
    return path


SEASON = [
    (r"^Season (\d+)$", "Seizoen {}"),
    (r"^Part (\d+)$", "Deel {}"),
    (r"^Volume (\d+)$", "Deel {}"),
    (r"^Limited Series$", "Miniserie"),
    (r"^Book (\d+)$", "Boek {}"),
    (r"^Chapter (\d+)$", "Hoofdstuk {}"),
]


def split_title(full):
    m = re.match(r"^(.*?): (\d{4}) - .*$", full)  # "Raw: 2026 - November 9, 2026"
    if m:
        return m.group(1), m.group(2)
    if ": " in full:
        head, tail = full.rsplit(": ", 1)
        for pat, nl in SEASON:
            mm = re.match(pat, tail)
            if mm:
                return head, nl.format(*mm.groups())
    return full, ""


def netflix(kind, out, tr):
    url = "https://www.netflix.com/tudum/top10/" + ("tv" if kind == "en" else "tv-non-english")
    s = get(url).decode("utf8", "replace")
    week = re.search(r"(\d+)/(\d+)/(\d+) - (\d+)/(\d+)/(\d+)", s)
    m1, d1, y1, m2, d2, y2 = map(int, week.groups())
    label = (f"{d1}–{d2} {MONTHS[m2-1]} 20{y2}" if m1 == m2 else f"{d1} {MONTHS[m1-1]} – {d2} {MONTHS[m2-1]} 20{y2}")
    info = {}
    for m in re.finditer(r'"storyArt":\{.*?"url":"([^"]+)".*?"top10Video":\{"__typename":"Top10PulseVideo","title":"((?:[^"\\]|\\+.)*)","videoId":(\d+),"shortSynopsis":("(?:[^"\\]|\\+.)*"|null)', s, re.S):
        t = dec(m.group(2))
        info.setdefault(t, dict(story=dec(m.group(1)), vid=m.group(3), syn=dec(m.group(4)[1:-1]) if m.group(4) != "null" else ""))
    tb = s[s.find("<tbody"):s.find("</tbody>")]
    items = []
    for tr_ in re.findall(r"<tr>(.*?)</tr>", tb, re.S):
        rank = re.search(r'class="rank">(\d+)', tr_)
        if not rank:
            continue
        full = clean(re.search(r"<button>(.*?)</button>", tr_, re.S).group(1))
        wk = re.search(r'row-weeks">(\d+)', tr_)
        v = re.search(r'row-views">([\d,]+)', tr_)
        thumb = re.search(r'<img[^>]*src="([^"]+)"', tr_)
        t, season = split_title(full)
        r = int(rank.group(1))
        meta = info.get(full, {})
        img = ""
        src = meta.get("story") or (html.unescape(thumb.group(1)) if thumb else "")
        if src:
            rel = f"img/tv-{kind}-{r:02d}.jpg"
            if save_img(src, os.path.join(out, rel), 720):
                img = rel
        items.append(dict(r=r, t=t, s=season, full=full, v=round(int(v.group(1).replace(",", "")) / 1e6, 1) if v else None,
                          weeks=int(wk.group(1)) if wk else None, syn=meta.get("syn", ""), b=tr.get(full, ""),
                          vid=meta.get("vid", ""), img=img))
    return label, items


def bestseller(out, n=25):
    s = get("https://www.debestseller60.nl/").decode("utf8", "replace")
    wk = re.search(r'board__week">\s*Week\s*(\d+)\s*-\s*(\d{4})', s)
    label = f"Week {wk.group(1)} · {wk.group(2)}" if wk else ""
    items = []
    for p in s.split('<div class="card__row">')[1:]:
        pos = re.search(r'card__position(?: card__position--(\w+))?[^"]*">\s*(\d+)', p)
        if not pos:
            continue
        g = lambda pat: (lambda m: clean(m.group(1)) if m else "")(re.search(pat, p, re.S))
        tags = [clean(t) for t in re.findall(r'card__tags__tag[^"]*">(.*?)</div>', p, re.S)]
        new = "Nieuw" in tags
        rest = [t for t in tags if t != "Nieuw"]
        price = next((t for t in rest if t.startswith("€")), "")
        isbn = next((t.replace("ISBN ", "") for t in rest if t.startswith("ISBN")), "")
        date = next((t for t in rest if re.match(r"\d\d-\d\d-\d{4}$", t)), "")
        pub = next((t for t in rest if t not in (price, "ISBN " + isbn, date)), "")
        r = int(pos.group(2))
        src = g(r'card__cover__img[^>]*src="([^"]+)"')
        img = ""
        if src:
            rel = f"img/book-{r:02d}.jpg"
            if save_img(src, os.path.join(out, rel), 440):
                img = rel
        if not img and isbn:  # reserve: Open Library op ISBN
            rel = f"img/book-{r:02d}.jpg"
            if save_img(f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false", os.path.join(out, rel), 440):
                img = rel
        items.append(dict(r=r, move=pos.group(1) or "", t=g(r'card__title[^>]*>(.*?)</div>'),
                          a=g(r'card__author">(.*?)</div>'), b=g(r'card__summary">(.*?)</div>'),
                          pub=pub, price=price, isbn=isbn, date=date, new=new, img=img))
        if len(items) >= n:
            break
    return label, items


def main():
    out = sys.argv[1]
    tr = json.load(open(sys.argv[2], encoding="utf8")) if len(sys.argv) > 2 else {}
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    en_w, en = netflix("en", out, tr)
    int_w, intl = netflix("int", out, tr)
    bk_w, books = bestseller(out)
    data = dict(updated=datetime.date.today().isoformat(),
                series=dict(week=en_w, en=en, int=intl),
                books=dict(week=bk_w, items=books))
    with open(os.path.join(out, "data.json"), "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"Netflix {en_w}: {len(en)} + {len(intl)} titels; Bestseller 60 {bk_w}: {len(books)} boeken")
    missing = [x["full"] for x in en + intl if not x["b"]]
    if missing:
        print("Nog geen Nederlandse beschrijving voor:", *missing, sep="\n  ")


if __name__ == "__main__":
    main()
