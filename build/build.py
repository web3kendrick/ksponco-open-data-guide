"""Recompute every number shown on the site from the raw files.

    python build/build.py                      # newest folder under raw/pages is the reference date
    python build/build.py --asof 2026-11-23    # pick a reference date explicitly

Inputs (all local, nothing is fetched here)
    raw/files/<ID>/data.bin            data file downloaded from the dataset page
    raw/files/manifest.json            download date and original file name per ID
    raw/pages/<YYYY-MM-DD>/<ID>.html   dataset page saved on that day
    build/datasets.json                the 30 IDs, grouping, main date column per file
    build/period_rules.json            hand-confirmed period expressions in the descriptions

Outputs
    docs/data.json                     everything the site shows
    docs/data.js                       the same object for file:// use (window.GUIDE_DATA)
"""
import argparse
import collections
import csv
import datetime
import hashlib
import html
import io
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDER_PREFIX = "한국체육산업개발주식회사_"
DATE_RE = re.compile(r"^\s*(\d{4})[-./](\d{1,2})(?:[-./](\d{1,2}))?")
DEFAULT_MARKS = ("1990-01-01", "9999-12-31")
SERIAL_HEADERS = ("일련번호", "순번", "순서")


# ---------------------------------------------------------------- helpers
def ym_index(ym):
    return ym[0] * 12 + (ym[1] - 1)


def ym_str(ym):
    return "%04d-%02d" % (ym[0], ym[1]) if ym else None


def ym_tuple(s):
    return tuple(int(x) for x in s.split("-"))


def ym_ko(ym):
    return "%d년 %d월" % (ym[0], ym[1])


def num(s):
    return int(s.replace(",", "")) if s else None


def n_(v):
    return format(v, ",")


def strip_tags(t):
    s = re.sub(r"<script.*?</script>", " ", t, flags=re.S)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s))


# ---------------------------------------------------------------- portal page
def parse_page(path):
    t = open(path, encoding="utf-8").read()
    j = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', t, re.S).group(1))
    s = strip_tags(t)

    def g(pat):
        m = re.search(pat, s)
        return m.group(1).strip() if m else None

    props = {p["name"]: p["value"] for p in j.get("additionalProperty", [])}
    alt = j.get("alternateName") or ""
    m = re.search(r"_(\d{8})$", alt)
    return {
        "name": j["name"].replace(PROVIDER_PREFIX, ""),
        "file_title": alt.replace(PROVIDER_PREFIX, ""),
        "title_date": m.group(1) if m else None,
        "desc": (j.get("description") or "").strip(),
        "cycle": props.get("업데이트 주기"),
        "next_date": g(r"차기 등록 예정일 (\d{4}-\d{2}-\d{2})"),
        "rows": num(g(r"전체 행 ([\d,]+)")),
        "downloads": num(g(r"다운로드\(바로가기\) ([\d,]+)")),
        "created": j.get("dateCreated"),
        "modified": j.get("dateModified"),
        "dept": (j.get("creator", {}).get("contactPoint", {}) or {}).get("contactType"),
        "license": (j.get("license") or {}).get("name"),
        "ext": j.get("encodingFormat"),
        "time_range": g(r"시간범위\s(.*?)\s?제공형태") or None,
        "caveat": g(r"기타 유의사항\s(.*?)\s?표준 메타데이터") or None,
    }


# ---------------------------------------------------------------- data file
def read_table(path):
    b = open(path, "rb").read()
    if b[:2] == b"PK":
        return None, "zip", None
    for enc in ("utf-8-sig", "cp949"):
        try:
            t = b.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        t, enc = b.decode("cp949", "replace"), "cp949(일부 글자 깨짐)"
    rows = list(csv.reader(io.StringIO(t)))
    header = [h.strip() for h in rows[0]]
    data = [r for r in rows[1:] if any(c.strip() for c in r)]
    return header, enc, data


def analyse_columns(header, data, ok_min, ok_max):
    out = []
    n = len(data)
    for ci, h in enumerate(header):
        vals = [r[ci] if ci < len(r) else "" for r in data]
        filled = [v for v in vals if v.strip()]
        counter = collections.Counter(v.strip() for v in filled)
        col = {
            "name": h,
            "blank": n - len(filled),
            "blank_pct": round(100.0 * (n - len(filled)) / n, 1) if n else 0.0,
            "distinct": len(counter),
        }
        dates = []
        for v in filled:
            m = DATE_RE.match(v)
            if m and 1 <= int(m.group(2)) <= 12:
                dates.append((int(m.group(1)), int(m.group(2))))
        if filled and len(dates) >= 0.6 * len(filled):
            ok = [d for d in dates if ok_min <= d[0] <= ok_max]
            odd = collections.Counter(d for d in dates if not (ok_min <= d[0] <= ok_max))
            col["kind"] = "date"
            col["min"] = ym_str(min(ok)) if ok else None
            col["max"] = ym_str(max(ok)) if ok else None
            col["odd"] = [{"ym": ym_str(k), "rows": v} for k, v in sorted(odd.items())]
            col["odd_rows"] = sum(odd.values())
        elif filled and all(re.fullmatch(r"-?[\d,]+(\.\d+)?", v.strip()) for v in filled):
            nums = [float(v.replace(",", "")) for v in filled]
            col["kind"] = "number"
            col["min"] = ("%f" % min(nums)).rstrip("0").rstrip(".")
            col["max"] = ("%f" % max(nums)).rstrip("0").rstrip(".")
        else:
            col["kind"] = "text"
            # examples only for low-cardinality columns: free text may carry personal names
            if 0 < len(counter) <= 40:
                col["examples"] = [k if len(k) <= 80 else k[:80] + "..." for k, _ in counter.most_common(3)]
        marks = {m: sum(1 for v in filled if m in v) for m in DEFAULT_MARKS}
        col["default_marks"] = {k: v for k, v in marks.items() if v}
        out.append(col)
    return out


def month_series(header, data, spec, ok_min, ok_max):
    """Rows per month of the main date column. Returns (in-range Counter, out-of-range Counter)."""
    months, odd = collections.Counter(), collections.Counter()
    if not spec:
        return months, odd
    if "title_col" in spec:
        ci, rx = header.index(spec["title_col"]), re.compile(spec["title_re"])
        for r in data:
            m = rx.search(r[ci]) if ci < len(r) else None
            if not m or not 1 <= int(m.group(2)) <= 12:
                continue
            ym = (int(m.group(1)), int(m.group(2)))
            (months if ok_min <= ym[0] <= ok_max else odd)[ym] += 1
    elif "col" in spec:
        ci = header.index(spec["col"])
        for r in data:
            m = DATE_RE.match(r[ci]) if ci < len(r) else None
            if not m:
                continue
            ym = (int(m.group(1)), int(m.group(2)))
            (months if ok_min <= ym[0] <= ok_max else odd)[ym] += 1
    else:
        yi, mi = header.index(spec["year_col"]), header.index(spec["month_col"])
        for r in data:
            y, mo = re.sub(r"\D", "", r[yi]), re.sub(r"\D", "", r[mi])
            if y and mo:
                ym = (int(y), int(mo))
                (months if ok_min <= ym[0] <= ok_max else odd)[ym] += 1
    return months, odd


def content_key(row, skip):
    """Row content without the serial number, the listed columns and any date-like cell."""
    return tuple(c for j, c in enumerate(row) if j not in skip and not re.match(r"\d{4}-\d{2}", c))


def repeated_blocks(header, data, spec):
    """Longest run of consecutive months whose rows are identical apart from the
    serial number and the date cells."""
    if not spec or "col" not in spec:
        return None
    ci = header.index(spec["col"])
    by = collections.defaultdict(list)
    for r in data:
        m = DATE_RE.match(r[ci])
        if m:
            by[(int(m.group(1)), int(m.group(2)))].append(r)
    sig = {}
    for k, rows in by.items():
        key = sorted(content_key(r, (0, ci)) for r in rows)
        sig[k] = (len(rows), hashlib.md5(repr(key).encode("utf-8")).hexdigest())
    best, run = None, []
    for k in sorted(sig):
        if run and sig[k] == sig[run[-1]] and ym_index(k) == ym_index(run[-1]) + 1:
            run.append(k)
        else:
            run = [k]
        if len(run) >= 3 and sig[k][0] >= 20 and (best is None or len(run) > len(best)):
            best = list(run)
    if not best:
        return None

    def same_as_prev(k):
        prev = (k[0], k[1] - 1) if k[1] > 1 else (k[0] - 1, 12)
        if prev not in by:
            return None
        pc = collections.Counter(content_key(r, (0, ci)) for r in by[prev])
        hit = 0
        for r in by[k]:
            kk = content_key(r, (0, ci))
            if pc[kk] > 0:
                pc[kk] -= 1
                hit += 1
        return hit, len(by[k]), len(by[prev])

    base = []
    for k in sorted(by):
        s = same_as_prev(k)
        if k < best[0] and s and s[1] >= 20 and s[2] >= 20:
            base.append((k, round(100.0 * s[0] / s[1])))
    s0 = same_as_prev(best[0])
    full = [k for k in best[1:] if (lambda s: bool(s) and s[0] == s[1])(same_as_prev(k))]
    return {"start": ym_str(best[0]), "end": ym_str(best[-1]), "months": len(best), "rows_per_month": sig[best[0]][0],
            "baseline": {"start": ym_str(base[0][0]), "end": ym_str(base[-1][0]), "min_pct": min(v for _, v in base),
                         "max_pct": max(v for _, v in base)} if base else None,
            "first_pct": round(100.0 * s0[0] / s0[1]) if s0 else None,
            "full_months": len(full), "full_start": ym_str(full[0]) if full else None, "full_end": ym_str(full[-1]) if full else None}


# ---------------------------------------------------------------- description period
def parse_anchor(anchor, kind):
    """Stated (start, end, start_has_month). Year only means January for a start and December for an end."""
    toks = []
    year = None
    for m in re.finditer(r"(\d{4})\s*년도?\s*(?:(\d{1,2})\s*월)?|(\d{1,2})\s*월", anchor):
        if m.group(1):
            year = int(m.group(1))
            toks.append((year, int(m.group(2)) if m.group(2) else None))
        elif year:
            toks.append((year, int(m.group(3))))
    if not toks:
        return None, None, False
    first, last = toks[0], toks[-1]
    start_has_month = first[1] is not None
    start = (first[0], first[1] or 1)
    end = (last[0], last[1] or 12)
    if kind == "to_present":
        return start, None, start_has_month
    if kind == "asof_year":
        return None, end, False
    return start, end, start_has_month


def stated_label(anchor, kind):
    """The stated period written out the way the description gives it (year only stays year only)."""
    toks, year = [], None
    for m in re.finditer(r"(\d{4})\s*년도?\s*(?:(\d{1,2})\s*월)?|(\d{1,2})\s*월", anchor):
        if m.group(1):
            year = int(m.group(1))
            toks.append("%d년 %d월" % (year, int(m.group(2))) if m.group(2) else "%d년" % year)
        elif year:
            toks.append("%d년 %d월" % (year, int(m.group(3))))
    if kind == "to_present":
        return toks[0] + "부터 현재까지"
    if kind == "asof_year":
        return toks[-1] + " 기준"
    if kind == "single" or len(toks) == 1:
        return toks[0]
    return toks[0] + "부터 " + toks[-1] + "까지"


def sentence_with(desc, anchor):
    for part in re.split(r"(?<=[.])\s+", desc):
        if anchor in part:
            return part.strip()
    return anchor if anchor in desc else None


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    cfg = json.load(open(os.path.join(ROOT, "build", "datasets.json"), encoding="utf-8"))
    rules = json.load(open(os.path.join(ROOT, "build", "period_rules.json"), encoding="utf-8"))
    manifest = json.load(open(os.path.join(ROOT, "raw", "files", "manifest.json"), encoding="utf-8"))
    ok_min, ok_max = rules["ok_year_min"], rules["ok_year_max"]
    days = sorted(d for d in os.listdir(os.path.join(ROOT, "raw", "pages")) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d))
    asof = args.asof or days[-1]
    prev_day = ([d for d in days if d < asof] or [None])[-1]
    asof_date = datetime.date.fromisoformat(asof)
    group_of = {i: g["name"] for g in cfg["groups"] for i in g["ids"]}
    ids = [i for g in cfg["groups"] for i in g["ids"]]
    period_rule = {r["id"]: r for r in rules["period"]}
    shared_rule = {r["id"]: r for r in rules["shared_description"]}

    datasets = []
    tables = {}
    for i in ids:
        meta = parse_page(os.path.join(ROOT, "raw", "pages", asof, i + ".html"))
        d = {"id": i, "group": group_of[i], **meta}
        d["url"] = cfg["portal_url"].format(id=i)
        fm = manifest.get(i, {})
        d["file"] = {"downloaded": fm.get("downloaded_kst"), "filename": fm.get("filename"), "bytes": fm.get("bytes")}
        d["notes"] = []
        path = os.path.join(ROOT, "raw", "files", i, "data.bin")
        header, enc, data = read_table(path)
        d["encoding"] = enc
        spec = cfg["main_date"].get(i)
        d["actual"] = None
        if header is None:
            z = zipfile.ZipFile(path)
            names = [n.filename for n in z.infolist() if not n.filename.endswith("/")]
            exts = collections.Counter(os.path.splitext(n)[1].lower().lstrip(".") or "(없음)" for n in names)
            d["zip"] = {"entries": len(names), "by_ext": dict(exts)}
            d["n_rows"] = None
        else:
            tables[i] = (header, data)
            d["n_rows"] = len(data)
            d["n_cols"] = len(header)
            d["rows_match"] = (meta["rows"] == len(data)) if meta["rows"] is not None else None
            d["columns"] = analyse_columns(header, data, ok_min, ok_max)
            full = collections.Counter(tuple(r) for r in data)
            d["dup_rows"] = sum(v - 1 for v in full.values() if v > 1)
            if header[0] in SERIAL_HEADERS:
                rest = collections.Counter(tuple(r[1:]) for r in data)
                d["dup_rows_ignoring_serial"] = sum(v - 1 for v in rest.values() if v > 1)
            months, odd = month_series(header, data, spec, ok_min, ok_max)
            if months:
                keys = sorted(months)
                if "title_col" in spec:
                    col_name = spec["title_col"]
                    basis = "'%s' 칸의 연월" % col_name
                else:
                    col_name = spec.get("col") or (spec["year_col"] + ", " + spec["month_col"])
                    basis = "'%s' 칸" % col_name
                d["actual"] = {
                    "column": col_name,
                    "basis": basis,
                    "one_per_month": all(v == 1 for v in months.values()) and len(keys) == ym_index(keys[-1]) - ym_index(keys[0]) + 1,
                    "start": ym_str(keys[0]),
                    "end": ym_str(keys[-1]),
                    "excluded_rows": sum(odd.values()),
                    "excluded": [{"ym": ym_str(k), "rows": v} for k, v in sorted(odd.items())],
                    "unread_rows": len(data) - sum(months.values()) - sum(odd.values()),
                }
                d["monthly"] = [[ym_str(k), months[k]] for k in keys]
                d["repeat"] = repeated_blocks(header, data, spec)
                if spec.get("reg_col"):
                    ri, ti, rx = header.index(spec["reg_col"]), header.index(spec["title_col"]), re.compile(spec["title_re"])
                    pairs = []
                    for r in data:
                        m, rm = rx.search(r[ti]), DATE_RE.match(r[ri])
                        if m and rm:
                            pairs.append(((int(m.group(1)), int(m.group(2))), (int(rm.group(1)), int(rm.group(2))), r[ri].strip()))
                    reg_start = min(p[1] for p in pairs)
                    bulk_day, bulk_rows = collections.Counter(p[2] for p in pairs).most_common(1)[0]
                    bulk = sorted(p[0] for p in pairs if p[2] == bulk_day)
                    d["title_month"] = {"reg_col": spec["reg_col"], "reg_start": ym_str(reg_start),
                                        "reg_end": ym_str(max(p[1] for p in pairs)),
                                        "before_reg_start": sum(1 for p in pairs if p[0] < reg_start),
                                        "bulk_day": bulk_day, "bulk_rows": bulk_rows,
                                        "bulk_start": ym_str(bulk[0]), "bulk_end": ym_str(bulk[-1])}
        datasets.append(d)
    by_id = {d["id"]: d for d in datasets}

    # ---- description period vs actual period
    for d in datasets:
        i = d["id"]
        d["period"] = None
        if i in shared_rule:
            r = shared_rule[i]
            other = by_id[r["same_as"]]
            sent = sentence_with(d["desc"], r["anchor"])
            d["status"] = "other_desc" if (sent and d["desc"] == other["desc"]) else "changed"
            d["period"] = {"sentence": sent, "same_as": other["id"], "same_as_name": other["name"],
                           "whole_description_identical": d["desc"] == other["desc"]}
            continue
        if i not in period_rule:
            d["status"] = "no_period"
            continue
        r = period_rule[i]
        sent = sentence_with(d["desc"], r["anchor"])
        if not sent or not d.get("actual"):
            d["status"] = "changed"
            d["period"] = {"sentence": None, "anchor": r["anchor"]}
            continue
        start, end, start_has_month = parse_anchor(r["anchor"], r["kind"])
        a_start, a_end = ym_tuple(d["actual"]["start"]), ym_tuple(d["actual"]["end"])
        gap = ym_index(a_end) - ym_index(end) if end else None
        if start is None:
            start_differs = False
        elif start_has_month:
            start_differs = start != a_start
        else:
            start_differs = start[0] != a_start[0]
        d["period"] = {
            "sentence": sent, "anchor": r["anchor"], "kind": r["kind"], "noun": r["noun"],
            "stated_start": ym_str(start) if start else None,
            "stated_start_year_only": bool(start) and not start_has_month,
            "stated_end": ym_str(end) if end else None,
            "stated_end_open": r["kind"] == "to_present",
            "stated_label": stated_label(r["anchor"], r["kind"]),
            "gap_months": gap,
            "start_differs": start_differs,
        }
        d["status"] = "newer" if (gap is not None and gap > 0) else "match"

    # ---- notes (every number below is counted from the file)
    def note(d, level, title, body, use=None):
        n = {"level": level, "title": title, "body": body}
        if use:
            n["use"] = use
        d["notes"].append(n)

    def idx(i, name):
        return tables[i][0].index(name)

    # 9999 marker placement in the pool and Ilsan files
    for i, start_col, end_col in (("15101610", "시작일자", "종료일자"), ("15114776", "시작일", "종료일")):
        h, data = tables[i]
        si, ei = idx(i, start_col), idx(i, end_col)
        in_start = sum(1 for r in data if r[si].strip().endswith("~9999-12-31"))
        in_end = sum(1 for r in data if r[ei].startswith("9999"))
        range_cells = sum(1 for r in data if "~" in r[si])
        end_is_start = sum(1 for r in data if r[ei].strip() == r[si].split("~")[0].strip())
        says = "종료일이 9999-12-31" in by_id[i]["desc"]
        mi = idx(i, cfg["main_date"][i]["col"])
        dist = collections.Counter(r[mi][:7] for r in data if r[si].strip().endswith("~9999-12-31")).most_common(4)
        by_id[i]["marker"] = {"start_col": start_col, "end_col": end_col, "in_start": in_start, "in_end": in_end,
                              "range_cells": range_cells, "end_is_start": end_is_start, "desc_says_end_9999": says,
                              "by_month": [[k, v] for k, v in dist]}
        body = ("'%s' 칸 %s행 중 %s행에 시작일과 종료일이 함께 적혀 있고, '%s' 칸 값이 그 시작일과 같은 행은 %s행임. "
                "'%s' 칸이 9999-12-31인 행은 %s행이고, '%s' 칸이 9999-12-31로 끝나는 행은 %s행임."
                % (start_col, n_(len(data)), n_(range_cells), end_col, n_(end_is_start), end_col, n_(in_end), start_col, n_(in_start)))
        if says:
            body += " 포털 설명은 종료일이 9999-12-31인 강좌를 운영 중인 강좌로 안내함."
        note(by_id[i], "caution", "9999-12-31 표시는 '%s' 칸에 있고 '%s' 칸에는 없음" % (start_col, end_col), body,
             "계속 운영 중인 강좌를 고를 때는 '%s' 칸이 9999-12-31로 끝나는 행을 고를 것" % start_col)

    # 9999 end dates spread over old months (Olympic Sports Center, Bundang)
    for i, month_col, end_col in (("15110953", "수강월", "수강종료일"), ("15118652", "수강월", "기간종료일")):
        h, data = tables[i]
        mi, ei = idx(i, month_col), idx(i, end_col)
        open_rows = [r for r in data if r[ei].startswith("9999")]
        dist = collections.Counter(r[mi][:7] for r in open_rows)
        latest = max(k for k in dist if ok_min <= int(k[:4]) <= ok_max)
        by_id[i]["marker"] = {"end_col": end_col, "in_end": len(open_rows),
                              "by_month": [[k, v] for k, v in dist.most_common(6)], "latest_month": latest,
                              "latest_rows": dist[latest]}
        if len(open_rows) - dist[latest]:
            top = ", ".join("%s %s행" % (k, n_(v)) for k, v in dist.most_common(4))
            note(by_id[i], "caution", "종료일 9999-12-31 행에 지난 %s이 섞여 있음" % month_col,
                 "'%s' 칸이 9999-12-31인 %s행의 %s 분포는 많은 순으로 %s임. 가장 최근 달(%s)의 행은 %s행임."
                 % (end_col, n_(len(open_rows)), month_col, top, latest, n_(dist[latest])),
                 "현재 강좌를 고를 때는 '%s' 9999-12-31 조건에 %s 조건을 함께 둘 것" % (end_col, month_col))

    # Olympic Sports Center: 1990-01 rows and tennis rows without an indoor or outdoor label
    h, data = tables["15110953"]
    mi, ei = idx("15110953", "수강월"), idx("15110953", "수강종료일")
    si, ni = idx("15110953", "종목"), idx("15110953", "강좌명")
    r1990 = [r for r in data if r[mi].startswith("1990-01")]
    if r1990:
        subjects = collections.Counter(r[si].strip() for r in r1990)
        by_id["15110953"]["rows_1990"] = {"rows": len(r1990), "subjects": subjects.most_common(6)}
        note(by_id["15110953"], "caution", "수강월이 1990-01인 행 %d개" % len(r1990),
             "수강월 1990-01 행 %d개는 종목 %d종에 걸쳐 있고 많은 순으로 %s임. 기간 계산에서는 제외함."
             % (len(r1990), len(subjects), ", ".join("%s %d행" % kv for kv in subjects.most_common(4))),
             "기간이나 월별 집계를 낼 때 수강월이 %d년보다 앞선 행을 뺄 것" % ok_min)
    tennis = [r for r in data if r[si].strip() == "테니스" and r[ei].startswith("9999")]
    unlabeled = [r for r in tennis if "실내" not in r[ni] and "실외" not in r[ni]]
    if tennis:
        by_id["15110953"]["tennis"] = {"open_rows": len(tennis), "unlabeled": len(unlabeled)}
        note(by_id["15110953"], "caution", "테니스 강좌명 %s행에 실내와 실외 표시가 없음" % n_(len(unlabeled)),
             "종목이 테니스이고 수강종료일이 9999-12-31인 %s행 중 %s행은 강좌명에 '실내'도 '실외'도 없음."
             % (n_(len(tennis)), n_(len(unlabeled))),
             "실내와 실외를 나눠 셀 때 표시 없는 행을 따로 둘 것")

    # '(토)' in weekday columns
    for i, day_col in (("15101610", "요일"), ("15110953", "수강요일")):
        h, data = tables[i]
        di = idx(i, day_col)
        paren = sum(1 for r in data if "(토)" in r[di])
        plain = sum(1 for r in data if re.search(r"(?<!\()토(?!\))", r[di]))
        by_id[i]["paren_sat"] = {"col": day_col, "paren": paren, "plain": plain}
        if paren:
            body = "'%s' 칸에 '(토)'가 든 행은 %s행, 괄호 없는 '토'가 든 행은 %s행임." % (day_col, n_(paren), n_(plain))
            if i == "15101610":
                hq = cfg["host_quotes"]["pool_fee"]
                body += " %s에는 '%s'로 적혀 있음(한국체육산업개발 누리집, %s 확인)." % (hq["page"], hq["quote"], hq["checked"])
                use = "주당 수업 횟수를 셀 때 '(토)'를 수업일과 구분해 셀 것"
            else:
                body += " 괄호의 뜻은 담당 부서 확인이 필요함."
                use = "'(토)'의 뜻을 확인하기 전에는 '(토)'가 든 행을 따로 두고 셀 것"
            note(by_id[i], "caution", "'%s' 칸의 괄호 친 '(토)' %s행" % (day_col, n_(paren)), body, use)

    # Bundang: out-of-range month and whether the same course has the in-range row
    h, data = tables["15118652"]
    mi, ci = idx("15118652", "수강월"), idx("15118652", "강좌번호")
    for r in data:
        m = DATE_RE.match(r[mi])
        if m and not (ok_min <= int(m.group(1)) <= ok_max):
            fixed = "2" + r[mi][1:]
            twin = [x for x in data if x[ci] == r[ci] and x[mi] == fixed]
            ni = idx("15118652", "강좌명")
            same = [x for x in twin if content_key(x, (0, 2, mi, ni)) == content_key(r, (0, 2, mi, ni))]
            cmp_ = None
            if len(twin) == 1:
                x = twin[0]
                cols = [j for j in range(len(h)) if j not in (0, mi)]
                cmp_ = {"same": [h[j] for j in cols if x[j] == r[j]],
                        "differ": [h[j] if j == ni else "%s(%s과 %s)" % (h[j], r[j], x[j]) for j in cols if x[j] != r[j]]}
            by_id["15118652"].setdefault("odd_month_rows", []).append(
                {"month": r[mi], "twin_month": fixed, "twin_rows": len(twin), "twin_same_content": len(same), "compare": cmp_})
            note(by_id["15118652"], "caution", "수강월 %s 행 1개" % r[mi],
                 "수강월이 %s인 행이 1개 있음. 같은 강좌번호의 수강월 %s 행은 %d개이고, 그중 강좌명을 뺀 종목, 시간, 정원, 요일, 대상, 수강료가 같은 행은 %d개임. 기간 계산에서는 제외함."
                 % (r[mi], fixed, len(twin), len(same)),
                 "수강월이 %d년 뒤인 행을 뺄 것" % ok_max)

    # Sports item list: default period value
    h, data = tables["15144839"]
    pi = idx("15144839", "시작 종료일")
    default_rows = sum(1 for r in data if r[pi].startswith("1990-01-01") and "9999-12-31" in r[pi])
    by_id["15144839"]["default_period"] = {"rows": default_rows, "of": len(data)}
    note(by_id["15144839"], "caution", "'시작 종료일' 칸 %d행이 1990-01-01부터 9999-12-31까지로 적혀 있음" % default_rows,
         "%d행 중 %d행의 '시작 종료일'이 1990-01-01부터 9999-12-31까지임. 기간을 따로 정하지 않은 종목의 기본값으로 보임." % (len(data), default_rows),
         "이 칸으로 운영 기간을 계산하지 말 것")

    # generic notes
    for d in datasets:
        i = d["id"]
        if d.get("repeat"):
            rp = d["repeat"]
            body = "일련번호와 날짜 칸을 뺀 나머지 내용이 %d개월 연속으로 같음(월 %s행)." % (rp["months"], n_(rp["rows_per_month"]))
            if rp.get("baseline"):
                b = rp["baseline"]
                body += " 앞 달과 같은 행의 비율은 %s부터 %s까지 %d%%에서 %d%%였고" % (b["start"], b["end"], b["min_pct"], b["max_pct"])
                if rp.get("first_pct") is not None and rp["first_pct"] < 100:
                    body += ", %s는 %d%%" % (rp["start"], rp["first_pct"])
                if rp.get("full_months"):
                    body += ", %s부터 %s까지 %d개월은 100%%임." % (rp["full_start"], rp["full_end"], rp["full_months"])
                else:
                    body += "."
            body += " 같은 내용이 달마다 복제된 것으로 보이며 원인은 담당 부서 확인이 필요함."
            note(d, "caution", "%s부터 %s까지 %d개월 동안 같은 %s행이 반복됨" % (rp["start"], rp["end"], rp["months"], n_(rp["rows_per_month"])),
                 body, "이 구간을 월별 추이나 신규 강좌 집계에 쓰지 말 것")
        if d.get("title_month"):
            tm, a = d["title_month"], d["actual"]
            note(d, "info", "자료의 월은 제목에 있고 '%s' 칸과 다름" % tm["reg_col"],
                 "제목의 연월 기준으로 %s부터 %s까지이고, '%s' 칸은 %s부터 %s까지임. '%s' 칸의 첫 달보다 앞선 달의 목록이 %s건이고, 그중 제목 연월 %s부터 %s까지 %s건은 %s 하루에 등록됨."
                 % (a["start"], a["end"], tm["reg_col"], tm["reg_start"], tm["reg_end"], tm["reg_col"], n_(tm["before_reg_start"]),
                    tm["bulk_start"], tm["bulk_end"], n_(tm["bulk_rows"]), tm["bulk_day"]))
        if d.get("actual") and d["actual"]["excluded_rows"] and i not in ("15118652", "15110953"):
            note(d, "caution", "'%s' 칸에 %d년 이전 또는 %d년 뒤 날짜 %d행" % (d["actual"]["column"], ok_min, ok_max, d["actual"]["excluded_rows"]),
                 "%s. 기간 계산에서는 제외함." % ", ".join("%s %d행" % (e["ym"], e["rows"]) for e in d["actual"]["excluded"][:5]))
        for c in d.get("columns", []):
            if c.get("kind") == "date" and c["odd_rows"] and (not d.get("actual") or c["name"] != d["actual"]["column"]):
                if d.get("actual") and c["odd"] == d["actual"]["excluded"]:
                    continue  # same rows as the main date column, already reported
                if i == "15144839":
                    continue  # reported above as the default period value
                if all(e["ym"].startswith("9999") for e in c["odd"]):
                    note(d, "info", "'%s' 칸 %s행이 9999-12로 적혀 있음" % (c["name"], n_(c["odd_rows"])),
                         "종료일을 정하지 않았다는 표시로 쓰임.")
                else:
                    note(d, "info", "'%s' 칸에 %d년 이전 또는 %d년 뒤 날짜 %s행" % (c["name"], ok_min, ok_max, n_(c["odd_rows"])),
                         ", ".join("%s %d행" % (e["ym"], e["rows"]) for e in c["odd"][:6]) + ".")
        if d.get("dup_rows"):
            body = "%s행 중 앞선 행과 모든 칸이 같은 행이 %s개임." % (n_(d["n_rows"]), n_(d["dup_rows"]))
            if tables[i][0][0] not in SERIAL_HEADERS:
                body += " 행을 구분하는 번호 칸이 없는 파일이어서 서로 다른 건이 같은 값으로 적힌 것일 수 있음."
            note(d, "caution", "모든 칸이 같은 행 %s개" % n_(d["dup_rows"]), body,
                 "건수를 셀 때 중복 제거 여부를 먼저 정할 것")
        elif d.get("dup_rows_ignoring_serial"):
            note(d, "caution", "첫 칸만 다르고 나머지가 같은 행 %s개" % n_(d["dup_rows_ignoring_serial"]),
                 "첫 칸('%s')을 뺀 나머지 칸이 모두 같은 행을 셈." % tables[i][0][0], "건수를 셀 때 같은 내용의 행인지 확인할 것")
        if d["next_date"]:
            nd = datetime.date.fromisoformat(d["next_date"])
            d["next_in_days"] = (nd - asof_date).days
            if nd < asof_date:
                d["overdue_days"] = (asof_date - nd).days
                body = "기준일 %s은 포털 차기 등록 예정일에서 %d일 뒤임. 업데이트 주기는 '%s'임." % (asof, d["overdue_days"], d["cycle"])
                if d["modified"] and d["modified"] >= d["next_date"]:
                    body += " 포털 수정일은 %s로 예정일 뒤에 수정된 기록이 있어, 포털의 예정일 칸이 갱신되지 않았을 가능성도 있음." % d["modified"]
                note(d, "caution", "포털 차기 등록 예정일 %s, 파일 안 최신 월 %s" % (d["next_date"], d["actual"]["end"] if d.get("actual") else "없음"),
                     body, "파일 안 최신 월을 확인한 뒤 쓸 것")
        if d.get("rows_match") is False:
            note(d, "caution", "파일 행 수(%s)와 포털 '전체 행'(%s)이 다름" % (n_(d["n_rows"]), n_(d["rows"])),
                 "파일을 내려받은 날짜는 %s임." % d["file"].get("downloaded"))
        if d.get("zip"):
            m = re.search(r"([\d,]+)\s*건", d["desc"])
            img = sum(v for k, v in d["zip"]["by_ext"].items() if k in ("jpg", "jpeg", "png"))
            d["zip"]["images"] = img
            if m:
                d["zip"]["desc_count"] = num(m.group(1))
                if num(m.group(1)) != img:
                    note(d, "caution", "설명의 %s건과 압축 파일 안 사진 %d장이 다름" % (m.group(1), img),
                         "압축 파일 안 파일은 %d개이고 그중 사진은 %d장임." % (d["zip"]["entries"], img))
        if d.get("time_range") and d.get("actual"):
            m = re.search(r"(\d{4})년\s*(\d{1,2})월", d["time_range"])
            if m and ym_str((int(m.group(1)), int(m.group(2)))) != d["actual"]["end"]:
                note(d, "info", "파일 안 최신 월(%s)이 포털 '시간범위' 칸 값('%s')과 다름" % (d["actual"]["end"], d["time_range"]),
                     "포털 '시간범위' 칸에 적힌 값을 그대로 옮김.")
        if d["title_date"] and d["file"].get("filename"):
            fm = re.search(r"(20\d{6})", d["file"]["filename"])
            if fm and fm.group(1) != d["title_date"]:
                note(d, "info", "파일데이터명 끝의 날짜 %s, 파일 이름의 날짜 %s" % (d["title_date"], fm.group(1)),
                     "내려받은 파일 이름은 '%s'임. 두 날짜 모두 파일 안 최신 월과 다를 수 있음." % d["file"]["filename"])
        d["caution_count"] = sum(1 for n in d["notes"] if n["level"] == "caution")

    # ---- headline numbers
    stated = [d for d in datasets if d["id"] in period_rule]
    newer = [d for d in datasets if d["status"] == "newer"]
    other = [d for d in datasets if d["status"] == "other_desc"]
    total_dl = sum(d["downloads"] or 0 for d in datasets)
    csvs = [d for d in datasets if d.get("n_rows") is not None]
    mods = sorted(d["modified"] for d in datasets)
    head = {
        "datasets": len(datasets),
        "period_stated": len(stated),
        "newer": len(newer),
        "match": sum(1 for d in datasets if d["status"] == "match"),
        "changed": sum(1 for d in datasets if d["status"] == "changed"),
        "other_desc": len(other),
        "no_period": sum(1 for d in datasets if d["status"] == "no_period"),
        "gap_min": min(d["period"]["gap_months"] for d in newer) if newer else None,
        "gap_max": max(d["period"]["gap_months"] for d in newer) if newer else None,
        "downloads_total": total_dl,
        "downloads_newer": sum(d["downloads"] for d in newer),
        "downloads_newer_pct": round(100.0 * sum(d["downloads"] for d in newer) / total_dl, 1),
        "downloads_newer_or_other": sum(d["downloads"] for d in newer + other),
        "downloads_newer_or_other_pct": round(100.0 * sum(d["downloads"] for d in newer + other) / total_dl, 1),
        "csv_files": len(csvs),
        "csv_rows_match": sum(1 for d in csvs if d.get("rows_match")),
        "rows_total": sum(d["n_rows"] for d in csvs),
        "overdue": sum(1 for d in datasets if d.get("overdue_days")),
        "caution_total": sum(d["caution_count"] for d in datasets),
        "datasets_with_caution": sum(1 for d in datasets if d["caution_count"]),
        "modified_min": mods[0],
        "modified_max": mods[-1],
        "modified_months": dict(collections.Counter(m[:7] for m in mods)),
        "depts": dict(collections.Counter(d["dept"] for d in datasets)),
        "licenses": dict(collections.Counter(d["license"] for d in datasets)),
        "encodings": dict(collections.Counter(d["encoding"] for d in datasets)),
    }

    # ---- suggestions for the data team
    sugg = []
    for d in newer:
        p, a = d["period"], d["actual"]
        s, e = ym_tuple(a["start"]), ym_tuple(a["end"])
        if p["noun"] == "강좌":
            new = "%s부터 %s까지의 강좌를 확인하실 수 있습니다." % (ym_ko(s), ym_ko(e))
        elif a.get("one_per_month"):
            new = "%s부터 %s까지 월별 %s %s건(달마다 1건)을 제공하고 있습니다." % (ym_ko(s), ym_ko(e), p["noun"], n_(d["n_rows"]))
        else:
            new = "%s부터 %s까지의 %s 자료를 제공하고 있습니다." % (ym_ko(s), ym_ko(e), p["noun"])
        ev = "%s 기준 실제 자료 기간은 %s부터 %s까지이고 행 수는 %s행임." % (a["basis"], a["start"], a["end"], n_(d["n_rows"]))
        if a.get("one_per_month"):
            ev += " 달마다 1행씩 빠진 달 없이 들어 있음."
        ev += " 설명상 끝 시점 %s보다 %d개월 뒤까지 들어 있음." % (p["stated_end"], p["gap_months"])
        solid = [m for m in d["monthly"] if m[1] >= 10]
        if d["monthly"][-1][1] < 10 and solid:
            sg = ym_index(ym_tuple(solid[-1][0])) - ym_index(ym_tuple(p["stated_end"]))
            ev += " 가장 늦은 달(%s)의 행은 %d행이고, 10행 이상인 가장 늦은 달(%s, %s행)" % (a["end"], d["monthly"][-1][1], solid[-1][0], n_(solid[-1][1]))
            ev += ("로 보아도 설명상 끝보다 %d개월 뒤임." % sg) if sg > 0 else "은 설명상 끝보다 늦지 않음."
        if p["start_differs"]:
            st = p["stated_start"][:4] + "년" if p["stated_start_year_only"] else p["stated_start"]
            if s < ym_tuple(p["stated_start"]):
                ev += " 설명상 시작 %s보다 이른 %s 자료부터 들어 있음." % (st, a["start"])
            else:
                ev += " 설명상 시작 %s보다 늦은 %s부터 들어 있음." % (st, a["start"])
        if d.get("title_month"):
            tm = d["title_month"]
            ev += " 제목 연월 %s부터 %s까지 %s건은 '%s' 칸이 %s 하루임." % (tm["bulk_start"], tm["bulk_end"], n_(tm["bulk_rows"]), tm["reg_col"], tm["bulk_day"])
        if a["excluded_rows"]:
            ev += " %d년 이전 또는 %d년 뒤 날짜 %d행은 계산에서 제외함." % (ok_min, ok_max, a["excluded_rows"])
        sugg.append({"id": d["id"], "name": d["name"], "downloads": d["downloads"], "type": "설명 문장 갱신",
                     "current": p["sentence"], "proposed": new, "evidence": ev})
    for d in other:
        h, data = tables[d["id"]]
        a = d["actual"]
        new = "%s입니다. %s 기준 %s부터 %s까지의 %s건을 제공하며, %s 항목으로 구성되어 있습니다." % (
            d["name"], a["column"], ym_ko(ym_tuple(a["start"])), ym_ko(ym_tuple(a["end"])), n_(d["n_rows"]), ", ".join(h))
        sugg.append({"id": d["id"], "name": d["name"], "downloads": d["downloads"], "type": "설명 전체 교체",
                     "current": d["desc"], "proposed": new,
                     "evidence": "지금 설명은 '%s' 데이터의 설명과 글자까지 같음. 파일에는 %s행이 있고 항목은 %s임."
                                 % (d["period"]["same_as_name"], n_(d["n_rows"]), ", ".join(h))})
    for i in ("15101610", "15114776"):
        d = by_id[i]
        mk = d["marker"]
        if mk["desc_says_end_9999"] and mk["in_end"] == 0:
            n = d["n_rows"]
            ev = ("'%s' 칸 %s행 중 %s행이 '시작일~종료일' 형태이고, '%s' 칸 값이 그 시작일과 같은 행은 %s행임. "
                  "그래서 기간의 끝이 9999-12-31인 %s행은 '%s' 칸에서만 보이고 '%s' 칸이 9999-12-31인 행은 %d행임. "
                  "설명의 '종료일이 9999-12-31'은 기간의 끝으로 보면 맞으나, 이용자가 '%s' 칸으로 거르면 0행이 나옴."
                  % (mk["start_col"], n_(n), n_(mk["range_cells"]), mk["end_col"], n_(mk["end_is_start"]),
                     n_(mk["in_start"]), mk["start_col"], mk["end_col"], mk["in_end"], mk["end_col"]))
            sugg.append({"id": i, "name": d["name"], "downloads": d["downloads"], "type": "칸 배치 확인",
                         "current": sentence_with(d["desc"], "종료일이 9999-12-31"),
                         "proposed": "'%s' 칸과 '%s' 칸의 이름과 값 배치 확인 요청" % (mk["start_col"], mk["end_col"]),
                         "evidence": ev})
    d = by_id["15160326"]
    if d["zip"].get("desc_count") and d["zip"]["desc_count"] != d["zip"]["images"]:
        sugg.append({"id": d["id"], "name": d["name"], "downloads": d["downloads"], "type": "건수 확인",
                     "current": sentence_with(d["desc"], "건의 데이터를 제공하고 있으며"),
                     "proposed": "압축 파일 기준 사진 %d장을 제공하고 있습니다." % d["zip"]["images"],
                     "evidence": "설명은 %d건, 압축 파일 안 사진은 %d장임. 어느 쪽이 맞는지는 담당 부서 확인이 필요함."
                                 % (d["zip"]["desc_count"], d["zip"]["images"])})
    d = by_id["15118652"]
    for o in d.get("odd_month_rows", []):
        sugg.append({"id": d["id"], "name": d["name"], "downloads": d["downloads"], "type": "행 확인",
                     "current": "수강월 %s 행 1개" % o["month"],
                     "proposed": "수강월 %s 행과 겹치는 행인지 확인 요청" % o["twin_month"],
                     "evidence": ("같은 강좌번호의 수강월 %s 행 1개와 비교하면 %s 칸이 같고, %s 칸이 다름."
                                  % (o["twin_month"], ", ".join(o["compare"]["same"]), ", ".join(o["compare"]["differ"])))
                                 if o.get("compare") else
                                 "같은 강좌번호의 수강월 %s 행은 %d개임." % (o["twin_month"], o["twin_rows"])})
    sugg.sort(key=lambda x: -x["downloads"])

    schedule = sorted(
        [{"id": d["id"], "name": d["name"], "cycle": d["cycle"], "next_date": d["next_date"], "days": d["next_in_days"],
          "actual_end": d["actual"]["end"] if d.get("actual") else None}
         for d in datasets if d.get("next_in_days") is not None and d["next_in_days"] <= 60],
        key=lambda x: x["next_date"])

    # ---- change since the previous page snapshot
    changes = None
    if prev_day:
        items, dl_prev = [], 0
        for d in datasets:
            pm = parse_page(os.path.join(ROOT, "raw", "pages", prev_day, d["id"] + ".html"))
            dl_prev += pm["downloads"] or 0
            d["downloads_prev"] = pm["downloads"]
            for key, label in (("desc", "설명"), ("file_title", "파일데이터명"), ("rows", "전체 행"), ("modified", "수정일"),
                               ("next_date", "차기 등록 예정일"), ("cycle", "업데이트 주기")):
                if pm[key] != d[key]:
                    items.append({"id": d["id"], "name": d["name"], "field": label, "before": pm[key], "after": d[key]})
        changes = {"prev": prev_day, "items": items, "downloads_prev_total": dl_prev,
                   "downloads_added": total_dl - dl_prev,
                   "downloads_newer_prev": sum(d["downloads_prev"] or 0 for d in newer)}

    # ---- sentences with a year that are not period statements (for the method page)
    not_period = []
    reasons = collections.defaultdict(list)
    for r in rules["not_period"]:
        reasons[r["id"]].append(r)
    for d in datasets:
        anchors = [period_rule[d["id"]]["anchor"]] if d["id"] in period_rule else []
        anchors += [shared_rule[d["id"]]["anchor"]] if d["id"] in shared_rule else []
        for part in re.split(r"(?<=[.])\s+", d["desc"]):
            listed = any(r["anchor"] in part for r in reasons[d["id"]])
            if (not re.search(r"\d{4}\s*년", part) and not listed) or any(a in part for a in anchors):
                continue
            why = next((r["reason"] for r in reasons[d["id"]] if r["anchor"] in part), None)
            not_period.append({"id": d["id"], "name": d["name"], "sentence": part.strip()[:160], "reason": why or "분류 전"})

    cases = [by_id[i] for i in ("15101610", "15114776")
             if by_id[i]["marker"]["desc_says_end_9999"] and by_id[i]["marker"]["in_end"] == 0]
    lead_case = None
    if cases:
        c = max(cases, key=lambda x: x["downloads"])
        mk = c["marker"]
        lead_case = {"id": c["id"], "name": c["name"], "start_col": mk["start_col"], "end_col": mk["end_col"],
                     "in_end": mk["in_end"], "in_start": mk["in_start"], "n_rows": c["n_rows"]}
    out = {
        "asof": asof,
        "next_check": cfg.get("next_check"),
        "lead_case": lead_case,
        "prev": prev_day,
        "files_downloaded": sorted({m.get("downloaded_kst") for m in manifest.values() if m.get("downloaded_kst")}),
        "rule": {"ok_year_min": ok_min, "ok_year_max": ok_max},
        "source": {"portal": "공공데이터포털", "portal_url": "https://www.data.go.kr", "provider": cfg["provider"],
                   "pool_fee": cfg["host_quotes"]["pool_fee"]},
        "groups": [g["name"] for g in cfg["groups"]],
        "headline": head,
        "datasets": datasets,
        "suggestions": sugg,
        "schedule": schedule,
        "changes": changes,
        "not_period": not_period,
    }
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    text = json.dumps(out, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "docs", "data.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    with open(os.path.join(ROOT, "docs", "data.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("window.GUIDE_DATA = " + text + ";\n")

    # ---- console report
    print("reference date %s (previous snapshot %s), files downloaded %s" % (asof, prev_day, ", ".join(out["files_downloaded"])))
    print("\n[1] description period vs actual period")
    print("%-9s %-22s %-8s %-8s %-8s %-8s %4s %6s %s" % ("id", "name", "stated_s", "stated_e", "actual_s", "actual_e", "gap", "dl", "status"))
    for d in sorted(stated + other, key=lambda x: -(x["period"].get("gap_months") or -1)):
        p, a = d["period"], d["actual"] or {}
        print("%-9s %-22s %-8s %-8s %-8s %-8s %4s %6s %s%s" % (
            d["id"], d["name"][:20], p.get("stated_start"), p.get("stated_end") or ("open" if p.get("stated_end_open") else None),
            a.get("start"), a.get("end"), p.get("gap_months"), d["downloads"], d["status"],
            " (start differs)" if p.get("start_differs") else ""))
    print("\n[2] headline")
    for k, v in head.items():
        print("  %-30s %s" % (k, v))
    if changes:
        print("  %-30s %s" % ("downloads_total_prev", changes["downloads_prev_total"]))
        print("  %-30s %s" % ("downloads_newer_prev", changes["downloads_newer_prev"]))
        print("  %-30s %s" % ("page_fields_changed", len(changes["items"])))
    print("\n[3] notes")
    for d in datasets:
        for n in d["notes"]:
            print("  %s %s [%s] %s | %s" % (d["id"], d["name"][:14], n["level"], n["title"], n["body"][:140]))
    print("\n[4] suggestions %d, schedule %d, unclassified year sentences %d" % (
        len(sugg), len(schedule), sum(1 for x in not_period if x["reason"] == "분류 전")))
    print("wrote docs/data.json (%d bytes)" % len(text.encode("utf-8")))


if __name__ == "__main__":
    main()
