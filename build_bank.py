# -*- coding: utf-8 -*-
"""Merge question JSON files into data/bank.js for the app.

Usage: python build_bank.py <source_dir>
<source_dir> holds exam_*.json, original_*.json, notes.json, numbers.json.
"""
import json, glob, os, re, sys
from collections import Counter, defaultdict

TOPICS = [
    "חוק המתווכים ותקנותיו", "חוק החוזים - חלק כללי", "חוק החוזים - תרופות", "חוזים אחידים",
    "הגנת הצרכן", "חוק המקרקעין - זכויות, עסקאות ורישום", "שיתוף במקרקעין ובתים משותפים",
    'חיזוק בתים משותפים (תמ"א 38)', "חוק המכר (דירות) והבטחת השקעות", "תכנון ובנייה",
    "מיסוי מקרקעין", "ירושה", "הגנת הדייר", "מקרקעי ישראל", "הוצאה לפועל", "עונשין",
    "רישוי עסקים", "שמאי מקרקעין", "כללי/אחר",
]
BIDI = re.compile("[‎‏‪-‮⁦-⁩﻿]")
PREFIX = re.compile(r"^\s*[אבגד]\s*[\.\)]\s*")


def clean(s):
    return BIDI.sub("", s).strip() if isinstance(s, str) else s


def norm(s):
    return re.sub(r"[^א-ת0-9a-zA-Z]", "", s or "")


def load(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("SKIP (bad json)", path, e)
        return None


def main(src):
    here = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(src, "exam_*.json"))) + sorted(glob.glob(os.path.join(src, "original_*.json")))
    problems, items = [], []
    for p in files:
        data = load(p)
        if not isinstance(data, list):
            continue
        for q in data:
            q = {k: clean(v) if isinstance(v, str) else v for k, v in q.items()}
            opts = [PREFIX.sub("", clean(o or "")) for o in q.get("options", [])]
            ww = q.get("why_wrong") or [None] * 4
            ans = q.get("answer")
            if len(opts) != 4 or not isinstance(ans, int) or not 0 <= ans <= 3 or not q.get("q"):
                problems.append(f"{os.path.basename(p)} {q.get('id')}: bad shape")
                continue
            ww = [clean(w) if w else None for w in (list(ww) + [None] * 4)[:4]]
            ww[ans] = None
            topic = q.get("topic") if q.get("topic") in TOPICS else "כללי/אחר"
            if q.get("topic") not in TOPICS:
                problems.append(f"{q.get('id')}: unknown topic {q.get('topic')}")
            items.append({
                "id": q["id"], "src": q.get("source", ""), "date": q.get("date", ""), "num": q.get("num"),
                "topic": topic, "q": q["q"], "o": opts, "a": ans,
                "ex": q.get("explain", ""), "ww": ww, "law": q.get("law", ""), "tip": q.get("tip", ""),
                "ks": q.get("keySource", ""), "old": bool(q.get("outdated")), "oldNote": q.get("outdated_note", ""),
                "orig": q.get("keySource") == "original",
            })

    # Dedupe repeated exam questions: keep newest, record every sitting it appeared in.
    items.sort(key=lambda x: x["date"] or "0000", reverse=True)
    seen, out = {}, []
    for it in items:
        key = norm(it["q"])[:140] + "|" + norm(it["o"][it["a"]])[:60]
        if not it["orig"] and key in seen:
            seen[key]["seen"].append(it["date"])
            it["dupOf"] = seen[key]["id"]
        else:
            it["seen"] = [it["date"]] if it["date"] else []
            if not it["orig"]:
                seen[key] = it
            out.append(it)
    # Exams keep full 25-question lists (including duplicates) so a past sitting can be replayed exactly.
    exams = defaultdict(list)
    for it in items:
        if it["orig"]:
            continue
        exams[(it["date"], it["src"])].append((it["num"] or 0, it.get("dupOf") or it["id"]))
    exam_list = [{"date": d, "src": s, "ids": [i for _, i in sorted(v)]} for (d, s), v in exams.items()]
    exam_list.sort(key=lambda e: e["date"], reverse=True)

    # Topic weights: frequency in official exams, recent sittings (2022+) weighted x2.
    w = Counter()
    for it in items:
        if it["orig"] or not it["date"]:
            continue
        w[it["topic"]] += 2 if it["date"] >= "2022" else 1
    tot = sum(w.values()) or 1
    weights = {t: round(w[t] / tot, 4) for t in TOPICS}

    notes = load(os.path.join(src, "notes.json")) or []
    numbers = load(os.path.join(src, "numbers.json")) or []
    bank = {"built": __import__("datetime").date.today().isoformat(), "topics": TOPICS, "weights": weights,
            "questions": out, "exams": exam_list, "notes": notes, "numbers": numbers}
    os.makedirs(os.path.join(here, "data"), exist_ok=True)
    with open(os.path.join(here, "data", "bank.js"), "w", encoding="utf-8") as f:
        f.write("window.QB=" + json.dumps(bank, ensure_ascii=False) + ";\n")
    print(f"files={len(files)} raw={len(items)} unique={len(out)} exams={len(exam_list)} "
          f"orig={sum(1 for i in out if i['orig'])} outdated={sum(1 for i in out if i['old'])} "
          f"notes={len(notes)} numbers={len(numbers)}")
    print("weights:", {k: v for k, v in sorted(weights.items(), key=lambda kv: -kv[1])})
    for p in problems[:40]:
        print("WARN", p)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
