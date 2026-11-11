#!/usr/bin/env python3
"""Read resume.pdf and refresh the resume-driven parts of resume.json.

Usage: python scripts/build_resume.py resume.pdf resume.json

Updated from the PDF:  work, education, skills, publications, certifications, awards,
                       and the GitHub / LinkedIn / Email link URLs.
Left untouched:        tagline, about, info, photo, projects (you write these by hand).
If the PDF can't be parsed (no work experience found), the script exits with an error
and leaves resume.json as it was, so a bad parse never reaches your live site.
"""
import json, os, re, sys
import pypdfium2 as pdfium          # text extraction (handles "fi"/"ffi" ligatures correctly)
from pypdf import PdfReader         # hyperlink targets

MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
DATE_RANGE = re.compile(rf"^{MONTH}\s+\d{{4}}\s*[–—-]\s*(?:{MONTH}\s+\d{{4}}|Present|Current)$", re.I)
HEADINGS = {
    "education": "education",
    "technical skills": "skills", "skills": "skills",
    "work experience": "work", "experience": "work",
    "publications": "publications", "research publications": "publications",
    "certifications & awards": "certs", "certifications": "certs", "awards": "certs",
}

def read_lines(pdf_path):
    doc = pdfium.PdfDocument(pdf_path)
    text = "\n".join(p.get_textpage().get_text_range() for p in doc)
    text = text.replace("\ufffe", "-").replace("\u00ad", "-")   # soft hyphens at line wraps
    lines = []
    for raw in text.splitlines():
        parts = [p.strip() for p in re.split(r"\t[\t ]*", raw) if p.strip()]
        if parts:
            lines.append(parts)
    return lines

def join_wrapped(prev, nxt):
    return prev + nxt if prev.endswith(("-", "/")) else prev + " " + nxt

def split_items(s):
    items, depth, cur = [], 0, ""
    for ch in s:
        depth += ch == "("; depth -= ch == ")"
        if ch == "," and depth == 0:
            items.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip(): items.append(cur.strip())
    return items

def sections(lines):
    out, cur = {}, None
    for parts in lines:
        key = HEADINGS.get(" ".join(parts).lower())
        if len(parts) == 1 and key:
            cur = key; out.setdefault(cur, []); continue
        if cur: out[cur].append(parts)
    return out

def bullets(block):
    """Group wrapped lines into bullets. Returns list of strings."""
    res = []
    for parts in block:
        t = " ".join(parts)
        if t.startswith("•"):
            res.append(t.lstrip("• ").strip())
        elif res:
            res[-1] = join_wrapped(res[-1], t)
    return res

def parse_education(block):
    if not block: return []
    first, second = block[0], block[1] if len(block) > 1 else [""]
    school = first[0]
    dates = first[1] if len(first) > 1 else ""
    extra = second[1] if len(second) > 1 else ""
    return [{"dates": dates, "title": second[0], "school": school + (" · " + extra if extra else "")}]

def parse_skills(block):
    groups = []
    for b in bullets(block):
        if ":" in b:
            g, items = b.split(":", 1)
            groups.append({"group": g.strip(), "items": split_items(items)})
    return groups

def parse_work(block):
    jobs, i = [], 0
    while i < len(block):
        parts = block[i]
        if len(parts) == 2 and DATE_RANGE.match(parts[1]) and not parts[0].startswith("•"):
            company, dates = parts
            title_line = block[i + 1] if i + 1 < len(block) else [""]
            title = title_line[0]
            location = title_line[1] if len(title_line) > 1 and not title_line[1].startswith("•") else ""
            body, i = [], i + 2
            stuck = [p for p in title_line[1:] if p.startswith("•")]   # bullet on the same line
            if stuck: body.append(stuck)
            while i < len(block) and not (len(block[i]) == 2 and DATE_RANGE.match(block[i][1])):
                body.append(block[i]); i += 1
            jobs.append({"dates": dates, "title": title,
                         "company": company + (", " + location if location else ""),
                         "bullets": bullets(body)})
        else:
            i += 1
    return jobs

def parse_publications(block):
    pubs = []
    for parts in block:
        t = " ".join(parts)
        if t.startswith("•"):
            title = parts[0].lstrip("• ").strip()
            venue = parts[1] if len(parts) > 1 else ""
            m = re.search(r"\s+(Published (?:in|at|by) .+)$", title)
            if m and not venue:
                title, venue = title[:m.start()].strip(), m.group(1)
            pubs.append({"citation": title, "venue": venue, "description": "", "url": ""})
        elif pubs and re.match(r"^o\s", t):
            pubs[-1]["description"] = t[1:].strip()
        elif pubs and pubs[-1]["description"]:
            pubs[-1]["description"] = join_wrapped(pubs[-1]["description"], t)
        elif pubs:                                   # wrapped title
            pubs[-1]["citation"] = join_wrapped(pubs[-1]["citation"], parts[0])
    return pubs

def parse_certs(block):
    certs, awards = [], []
    for b in bullets(block):
        (awards if re.search(r"award", b, re.I) else certs).append(b)
    return [{"name": c, "url": ""} for c in certs], awards

def read_links(pdf_path):
    """Return [(y, url)] for every hyperlink, top of page first."""
    found = []
    for page in PdfReader(pdf_path).pages:
        for a in page.get("/Annots") or []:
            a = a.get_object()
            act = a.get("/A")
            if act and "/URI" in act:
                found.append((float(a["/Rect"][1]), str(act["/URI"])))
    return sorted(found, key=lambda x: -x[0])

def main(pdf, out):
    lines = read_lines(pdf)
    sec = sections(lines)
    data = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else {}

    work = parse_work(sec.get("work", []))
    if not work:
        sys.exit("ERROR: found no work experience in the PDF; leaving resume.json unchanged.")
    certs, awards = parse_certs(sec.get("certs", []))
    pubs = parse_publications(sec.get("publications", []))

    # Attach hyperlinks. Header links (email, LinkedIn, GitHub) are identified by domain;
    # all other links are matched by order to publications first, then certifications.
    header, others = {}, []
    for _, url in read_links(pdf):
        if url.startswith("mailto:"): header["Email"] = url
        elif "linkedin.com" in url: header["LinkedIn"] = url.replace("http://", "https://")
        elif "github.com/" in url and url.count("/") <= 3: header["GitHub"] = url
        else: others.append(url)
    if len(others) == len(pubs) + len(certs):
        for item, url in zip(pubs + certs, others): item["url"] = url
    else:
        print(f"WARNING: {len(others)} links found for {len(pubs)} publications + {len(certs)} "
              "certifications; not attaching links. Check that each item is hyperlinked.")
    for l in data.get("links", []):
        if l.get("label") in header: l["url"] = header[l["label"]]

    data.update({"skills": parse_skills(sec.get("skills", [])), "work": work,
                 "publications": pubs, "certifications": certs, "awards": awards,
                 "education": parse_education(sec.get("education", []))})
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2); f.write("\n")
    print(f"OK: {len(work)} roles, {len(pubs)} publications, {len(certs)} certifications, "
          f"{len(data['skills'])} skill groups -> {out}")

if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])