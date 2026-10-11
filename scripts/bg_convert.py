#!/usr/bin/env python3
"""Convert APIS legislation JSON (fetched by bg_fetch.py) to LawCodex Markdown.

Usage: bg_convert.py [--raw ../../_raw/bg] [--out ..]
"""
import argparse
import datetime
import html
import json
import os
import re
import sys

from lxml import html as lhtml

SITE = "https://legislation.apis.bg"

CATEGORY = {
    544: ("konstitutsiya", "constitution"),
    545: ("kodeksi", "code"),
    546: ("zakoni", "act"),
    547: ("ratifikatsii", "act"),
    552: ("pravilnitsi", "regulation"),
}

# Bulgarian official transliteration (Transliteration Act 2009, streamlined system)
TR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sht", "ъ": "a", "ь": "y", "ю": "yu", "я": "ya",
    "ѝ": "i", "ё": "yo", "є": "e", "і": "i",
}


def translit(s):
    s = s.lower()
    s = re.sub(r"ия\b", "ia", s)
    return "".join(TR.get(c, c) for c in s)


def slugify(title, maxlen=90):
    t = re.sub(r"\((Загл\.|Загл|Изм\.|Отм\.|Обн\.|Попр\.)[^)]*\)", " ", title)
    t = translit(t)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    if len(t) > maxlen:
        t = t[:maxlen].rsplit("-", 1)[0]
    return t or "untitled"


# ---------------------------------------------------------------- HTML -> Markdown

BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "li",
         "center", "blockquote", "pre"}


def esc_inline(s):
    s = s.replace("\\", "\\\\").replace("*", "\\*").replace("`", "\\`")
    s = re.sub(r"<(?=[A-Za-z/!?])", "&lt;", s)
    return s


def esc_line_start(line):
    # avoid accidental Markdown block syntax at the start of a line
    m = re.match(r"^(\s*)(\d+)([.)])(\s|$)", line)
    if m:
        return m.group(1) + m.group(2) + "\\" + m.group(3) + line[m.end(3):]
    m = re.match(r"^(\s*)([#>+\-=|])", line)
    if m:
        return m.group(1) + "\\" + line[len(m.group(1)):]
    return line


def inline(el, img_base=SITE):
    """Render inline content of an element as Markdown text ("\n" = hard break)."""
    out = []

    def walk(e):
        tag = e.tag if isinstance(e.tag, str) else ""
        tag = tag.lower().split(":")[-1]
        if tag in ("script", "style"):
            pass
        elif tag == "br":
            out.append("\n")
        elif tag == "img":
            src = e.get("src", "").strip()
            if src:
                if not re.match(r"https?://", src):
                    src = img_base.rstrip("/") + "/" + src.lstrip("/")
                out.append(f"![{e.get('alt', '').strip()}]({src})")
        elif tag in ("b", "strong"):
            inner = inline(e).strip()
            if inner:
                out.append(" **" + inner.replace("\n", " ") + "** ")
        elif tag in ("i", "em"):
            inner = inline(e).strip()
            if inner:
                out.append(" *" + inner.replace("\n", " ") + "* ")
        elif tag in ("sub", "sup"):
            inner = inline(e).strip()
            if inner:
                out.append(f"<{tag}>{inner}</{tag}>")
        elif tag in BLOCK and tag != "table":
            out.append("\n")
            if e.text:
                out.append(esc_inline(e.text))
            for c in e:
                walk(c)
            out.append("\n")
        elif tag == "table":
            out.append("\n" + table_text(e) + "\n")
        else:
            if e.text:
                out.append(esc_inline(e.text))
            for c in e:
                walk(c)
        if e.tail:
            out.append(esc_inline(e.tail))

    if el.text:
        out.append(esc_inline(el.text))
    for c in el:
        walk(c)
    s = "".join(out).replace("\xa0", " ").replace("\xad", "")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\*\* +\*\*", " ", s)
    return s


def table_text(t):
    """Flatten a table to text lines (used for tables nested inside cells)."""
    rows = []
    for tr in t.iter("tr"):
        cells = [inline(td).strip().replace("\n", " ") for td in tr if isinstance(td.tag, str) and td.tag.lower() in ("td", "th")]
        cells = [c for c in cells if c]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def own_rows(t):
    rows = []
    for tr in t.iter("tr"):
        # skip rows of nested tables
        p = tr.getparent()
        while p is not None and p.tag.lower() != "table":
            p = p.getparent()
        if p is not t:
            continue
        cells = [td for td in tr if isinstance(td.tag, str) and td.tag.lower() in ("td", "th")]
        cells = [td for td in cells if not (td.get("width") == "0" and not inline(td).strip())]
        rows.append(cells)
    return [r for r in rows if r]


def html_cell(td):
    """Inline content of a cell for use inside a raw HTML table (no Markdown)."""
    s = inline(td).strip()
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\\)\*(.+?)(?<!\\)\*", r"<i>\1</i>", s)
    s = s.replace("\\*", "*").replace("\\`", "`").replace("\\\\", "\\")
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1">', s)
    return re.sub(r"\n+", "<br>", s)


def cell_md(td):
    s = inline(td).strip()
    s = re.sub(r"\n+", "<br>", s)
    return s.replace("|", "\\|")


def table_md(t):
    rows = own_rows(t)
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    nested = t.xpath(".//table")
    spans = any(td.get("colspan", "1") not in ("1", "") or td.get("rowspan", "1") not in ("1", "")
                for r in rows for td in r)
    # layout table with a single cell (or single column without spans): unwrap
    if ncols == 1 and not spans:
        blocks = []
        for r in rows:
            blocks.extend(render_blocks(r[0]))
        return "\n\n".join(blocks)
    if not spans and not nested:
        texts = [[cell_md(td) for td in r] + [""] * (ncols - len(r)) for r in rows]
        texts = [r for r in texts if any(c for c in r)]
        if not texts:
            return ""
        lines = ["| " + " | ".join(texts[0]) + " |", "|" + "---|" * ncols]
        for r in texts[1:]:
            lines.append("| " + " | ".join(r) + " |")
        return "\n".join(lines)
    # complex table: minimal HTML
    out = ["<table>"]
    for r in rows:
        out.append("<tr>")
        for td in r:
            attrs = ""
            for a in ("colspan", "rowspan"):
                v = td.get(a)
                if v and v != "1":
                    attrs += f' {a}="{v}"'
            out.append(f"<td{attrs}>{html_cell(td)}</td>")
        out.append("</tr>")
    out.append("</table>")
    return "\n".join(out)


def text_to_block(s):
    lines = [esc_line_start(l.strip()) for l in s.split("\n")]
    lines = [l for l in lines if l]
    if not lines:
        return None
    return "  \n".join(lines) if len(lines) > 1 else lines[0]


def render_blocks(el):
    """Render an element's children as a list of Markdown blocks."""
    blocks = []
    buf = []

    def flush():
        if buf:
            s = "".join(buf)
            buf.clear()
            for part in re.split(r"\n{2,}", s):
                b = text_to_block(part)
                if b:
                    blocks.append(b)

    if el.text:
        buf.append(esc_inline(el.text))
    for c in el:
        tag = c.tag.lower().split(":")[-1] if isinstance(c.tag, str) else ""
        if tag == "table":
            flush()
            t = table_md(c)
            if t.strip():
                blocks.append(t)
        elif tag in ("p", "div", "center", "blockquote", "li", "h1", "h2", "h3", "h4", "h5", "h6", "pre"):
            flush()
            if c.xpath(".//table"):
                blocks.extend(render_blocks(c))
            else:
                b = text_to_block(inline(c))
                if b:
                    blocks.append(b)
        elif tag in ("ul", "ol"):
            flush()
            blocks.extend(render_blocks(c))
        elif tag == "hr":
            flush()
        else:
            if tag:
                tmp = lhtml.Element("span")
                tmp.append(c.__copy__())
                buf.append(inline(tmp))
            else:
                buf.append(esc_inline(c.tail or ""))
                continue
        if c.tail:
            buf.append(esc_inline(c.tail))
    flush()
    return blocks


def parse(fragment):
    fragment = re.sub(r"<!\[(end)?if[^\]]*\]>", "", fragment)
    fragment = re.sub(r"</?o:p>", "", fragment)
    root = lhtml.fragment_fromstring("<div>" + fragment + "</div>")
    # drop anchors used only as targets / editorial empty links
    for a in root.xpath(".//a[@name]"):
        if not (a.text or len(a)):
            a.drop_tag()
    return root


def plain(fragment):
    root = parse(fragment)
    s = inline(root)
    return re.sub(r"\s+", " ", s.replace("\\*", "*").replace("\\\\", "\\")).strip()


def heading_parts(fragment):
    root = parse(fragment)
    s = inline(root)
    parts = [re.sub(r"\s+", " ", p).strip() for p in s.split("\n")]
    return [p for p in parts if p]


KINDS = ["part", "dyal", "glava", "razdel", "podrazdel", "sub"]


def heading_kind(text):
    t = text.strip().lower()
    if t.startswith(("част", "книга")) or re.fullmatch(r"(обща|особена|специална)\s+част", t):
        return "part"
    if t.startswith("дял"):
        return "dyal"
    if t.startswith("глава"):
        return "glava"
    if t.startswith("подраздел"):
        return "podrazdel"
    if t.startswith("раздел"):
        return "razdel"
    return "top"


CAPTION_RE = re.compile(r'<span class="par-caption">(.*?)</span>(\s*\.(?!\.))?', re.S)


def is_heading(p):
    return p["type"] in (1, 2, 3, 4) or re.match(r"\s*<h\d", p["text"]) is not None


def split_caption(fragment):
    m = CAPTION_RE.search(fragment)
    if not m:
        return None, fragment
    cap = plain(m.group(1)) + (".") if m.group(2) else plain(m.group(1))
    rest = fragment[: m.start()] + fragment[m.end():]
    return cap, rest


def convert_doc(meta, folder_id, paragraphs, retrieved):
    cat, typ = CATEGORY[folder_id]
    title = re.sub(r"\s+", " ", meta["caption"]).strip()

    # structure detection
    present = set()
    for p in paragraphs:
        if is_heading(p):
            parts = heading_parts(p["text"])
            if parts:
                k = heading_kind(parts[0])
                if k != "top":
                    present.add(k)
        elif p["type"] == 9:
            present.add("sub")
    order = [k for k in KINDS if k in present]
    level_of = {k: 2 + i for i, k in enumerate(order)}
    art_level = 2 + len(order)
    art_bold = art_level > 6

    def hl(n):
        return "#" * min(6, n)

    body = []
    history = None
    pending_title = None
    for p in paragraphs:
        t, ft, txt = p["type"], p["fieldType"], p["text"]
        if t == 0 and ft == 1:
            continue  # caption = H1
        if t == 0 and ft == 2:
            history = plain(txt)
            body.append(esc_line_start(history))
            continue
        if is_heading(p):
            parts = heading_parts(txt)
            if not parts:
                continue
            k = heading_kind(parts[0])
            lvl = 2 if k == "top" else level_of[k]
            text = parts[0] + (" — " + " ".join(parts[1:]) if len(parts) > 1 else "")
            body.append(f"{hl(lvl)} {text}")
            continue
        if t == 9:
            text = " ".join(heading_parts(txt))
            if text:
                body.append(f"{hl(level_of['sub'])} {text}")
            continue
        if t == 25:
            text = " ".join(heading_parts(txt))
            if text:
                pending_title = text
            continue
        if t == 50:
            root = parse(txt)
            blocks = render_blocks(root)
            if not blocks:
                continue
            first = blocks[0].replace("  \n", " ")
            if re.fullmatch(r"[А-ЯЁ„“\"\s,.\-–]{6,}", first):
                # heading of the transitional provisions of an amending act:
                # caption up to (and including) the "(ДВ, бр. ...)" line
                head = []
                rest = list(blocks)
                while rest and len(head) < 4:
                    b = rest.pop(0)
                    head.append(b.replace("  \n", " "))
                    if re.match(r"^\(ДВ", b):
                        break
                body.append("## " + " ".join(head))
                body.extend(b for b in rest if not re.fullmatch(r"[.…\s]+", b))
            else:
                m = re.match(r"^(§\s*\d+[а-я]?\.)\s*(.*)$", blocks[0], re.S)
                if m:
                    body.append(f"**{m.group(1)}**" if art_bold else f"{hl(art_level)} {m.group(1)}")
                    blocks = ([m.group(2)] if m.group(2).strip() else []) + blocks[1:]
                body.extend(b for b in blocks if not re.fullmatch(r"[.…\s]+", b))
            continue
        # article / paragraph / annex text (type 11 and others)
        cap, rest = split_caption(txt)
        if cap and ft == 10 and re.match(r"(?i)^(приложение|таблица|образец|списък)", cap):
            # annex: caption + following text lines form the heading block
            root = parse(rest)
            blocks = render_blocks(root)
            body.append(f"## {cap}")
            body.extend(blocks)
            continue
        if cap and re.match(r"^(Чл\.|§|Член|Параграф|Т\.|Точка|Правило|Раздел|Приложение)", cap):
            if art_bold:
                head = f"**{cap}**"
            else:
                head = f"{hl(art_level)} {cap}"
            body.append(head)
            if pending_title:
                body.append(f"*{pending_title}*")
                pending_title = None
            body.extend(render_blocks(parse(rest)))
            continue
        blocks = render_blocks(parse(txt))
        m = re.match(r"^((?:Чл\.|§)\s*\d+[а-я]?\.)\s*(.*)$", blocks[0], re.S) if blocks else None
        if m and ft != 10:
            body.append(f"**{m.group(1)}**" if art_bold else f"{hl(art_level)} {m.group(1)}")
            if pending_title:
                body.append(f"*{pending_title}*")
                pending_title = None
            blocks = ([m.group(2)] if m.group(2).strip() else []) + blocks[1:]
        elif pending_title:
            body.append(f"*{pending_title}*")
            pending_title = None
        body.extend(blocks)

    # front matter
    def d(x):
        return x[:10] if x else None

    ident = None
    if history:
        m = re.search(r"ДВ,?\s*бр\.\s*(\d+)\s*от\s*(\d{1,2}\.\d{1,2}\.\d{4})", history)
        if m:
            ident = f"ДВ, бр. {m.group(1)} от {m.group(2)} г."
    fm = {
        "title": title,
        "identifier": ident or f"APIS {meta['uniqueId']}",
        "type": typ,
        "jurisdiction": "bg",
        "language": "bg",
        "date": d(meta.get("actDate")),
        "last_amended": d(meta.get("publDate")),
        "version_in_force_from": d(meta.get("startDate")),
        "status": "in_force" if meta.get("isActual") == 1 and not meta.get("endDate") else "unknown",
        "source": f"{SITE}/doc/{meta['uniqueId']}/0/",
        "apis_id": meta["uniqueId"],
        "retrieved": retrieved,
    }
    lines = ["---"]
    for k, v in fm.items():
        if v is None:
            continue
        if isinstance(v, int):
            lines.append(f"{k}: {v}")
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)) or k in ("jurisdiction", "language", "type", "status"):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: " + json.dumps(v, ensure_ascii=False))
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    md = "\n".join(lines) + "\n" + "\n\n".join(b for b in body if b.strip()) + "\n"
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.normpath(os.path.join(here, "../../_raw/bg")))
    ap.add_argument("--out", default=os.path.normpath(os.path.join(here, "..")))
    ap.add_argument("--retrieved", default=None)
    ap.add_argument("--only", type=int, nargs="*")
    a = ap.parse_args()

    stats = {}
    used = {}
    missing = []
    for fid, (cat, typ) in CATEGORY.items():
        ip = os.path.join(a.raw, "index", f"{fid}.json")
        if not os.path.exists(ip):
            continue
        with open(ip, encoding="utf-8") as f:
            docs = json.load(f)["data"]
        docs.sort(key=lambda x: x["uniqueId"])
        for meta in docs:
            uid = meta["uniqueId"]
            if a.only and uid not in a.only:
                continue
            dp = os.path.join(a.raw, "docs", f"{uid}.json")
            if not os.path.exists(dp):
                missing.append(uid)
                continue
            with open(dp, encoding="utf-8") as f:
                j = json.load(f)
            retrieved = a.retrieved or datetime.date.fromtimestamp(os.path.getmtime(dp)).isoformat()
            slug = slugify(meta["caption"])
            year = (meta.get("actDate") or "0000")[:4]
            if cat in ("zakoni", "ratifikatsii", "pravilnitsi"):
                rel = f"{cat}/{year}/{slug}"
            else:
                rel = f"{cat}/{slug}"
            if rel in used:
                rel = f"{rel}-{uid}"
            used[rel] = uid
            try:
                md = convert_doc(meta, fid, j["paragraphs"], retrieved)
            except Exception as e:
                print(f"ERROR converting {uid}: {e}", file=sys.stderr)
                raise
            path = os.path.join(a.out, rel + ".md")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(md)
            stats[cat] = stats.get(cat, 0) + 1
    print(stats, "missing:", len(missing))


if __name__ == "__main__":
    main()
