#!/usr/bin/env python3
"""Fetch consolidated Bulgarian legislation from the free APIS legislation portal.

Source: https://legislation.apis.bg (public, free consolidated texts published by
АПИС ЕООД), backed by the JSON API at https://web-api.apis.bg/api/obshtina-legislation/.

Downloads, into a cache directory (default: ../../_raw/bg relative to this script):
  index/<folderId>.json   - document lists for each top-level folder
  docs/<uniqueId>.json    - full consolidated text (DocTextJson) of each document

Re-runnable: cached documents are reused unless the list reports a newer
publication date than the cached copy (or --refresh is given).
"""
import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

API = "https://web-api.apis.bg/api/obshtina-legislation/"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"

# Top-level folders exposed by the free portal (see API "Folders").
FOLDERS = {
    544: "konstitutsiya",
    545: "kodeksi",
    546: "zakoni",
    547: "ratifikatsii",
    552: "pravilnitsi",
}

_local = threading.local()


def session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept": "application/json"})
        _local.s = s
    return s


def request(method, url, delay, **kw):
    for attempt in range(6):
        try:
            r = session().request(method, url, timeout=120, **kw)
            if r.status_code == 200:
                time.sleep(delay)
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                wait = 5 * 2 ** attempt
                print(f"  HTTP {r.status_code} {url} - retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            wait = 5 * 2 ** attempt
            print(f"  error {e} {url} - retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url}")


def fetch_folder(fid, delay):
    body = {
        "pageNumber": 1,
        "pageSize": 1000,
        "sortOrder": 1,
        "sortType": 1,
        "filters": [{"type": 29, "params": {"leadFolderId": fid, "linkedFolder": 0}}],
    }
    out = []
    while True:
        d = request("POST", API + "DocList", delay, json=body).json()
        out.extend(d.get("data") or [])
        if len(out) >= d["totalCount"] or not d.get("data"):
            break
        body["pageNumber"] += 1
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.normpath(os.path.join(here, "../../_raw/bg")))
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    os.makedirs(os.path.join(a.raw, "index"), exist_ok=True)
    os.makedirs(os.path.join(a.raw, "docs"), exist_ok=True)

    todo = []
    for fid, name in FOLDERS.items():
        docs = fetch_folder(fid, a.delay)
        print(f"folder {fid} {name}: {len(docs)} documents")
        with open(os.path.join(a.raw, "index", f"{fid}.json"), "w", encoding="utf-8") as f:
            json.dump({"folderId": fid, "name": name, "data": docs}, f, ensure_ascii=False)
        for d in docs:
            todo.append(d)

    def need(d):
        p = os.path.join(a.raw, "docs", f"{d['uniqueId']}.json")
        if a.refresh or not os.path.exists(p):
            return True
        try:
            with open(p, encoding="utf-8") as f:
                cached = json.load(f)
            return cached.get("_publDate") != d.get("publDate")
        except Exception:
            return True

    todo = [d for d in todo if need(d)]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(todo)} documents to download")

    def get(d):
        uid = d["uniqueId"]
        r = request("GET", API + f"DocTextJson/?uniqueId={uid}&dbIndex=0", a.delay)
        j = r.json()
        if not j.get("paragraphs"):
            raise RuntimeError(f"empty text for {uid}")
        j["_publDate"] = d.get("publDate")
        p = os.path.join(a.raw, "docs", f"{uid}.json")
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)
        return uid

    done = 0
    failed = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(get, d): d for d in todo}
        for fu in as_completed(futs):
            try:
                fu.result()
                done += 1
                if done % 100 == 0:
                    print(f"  {done}/{len(todo)}", flush=True)
            except Exception as e:
                failed.append(futs[fu]["uniqueId"])
                print(f"  FAILED {futs[fu]['uniqueId']}: {e}", file=sys.stderr)
    print(f"downloaded {done}, failed {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
