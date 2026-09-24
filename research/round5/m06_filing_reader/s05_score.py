"""Score each press release: FinBERT (ProsusAI/finbert, original 2020-12-24 weights, trained on pre-2015
text) over the first K narrative sentences, and Loughran-McDonald dictionary tone.
Usage: s05_score.py TEXTS.jsonl.gz OUT.parquet"""
import os, sys, re, json, gzip, time
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ["HF_HOME"] = "/home/user/alpha/data/round5/m06_filing_reader/hf"
os.environ["HF_HUB_OFFLINE"] = "1"
import numpy as np, pandas as pd, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import pysentiment2 as ps
from common import DATA

torch.set_num_threads(1)
REV = "4556d13015211d73dccd3fdd39d39232506f3e43"  # pytorch_model.bin sha256 e15a7b57.. committed 2020-12-24
tok = AutoTokenizer.from_pretrained("ProsusAI/finbert", revision=REV)
mdl = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert", revision=REV, use_safetensors=False).eval()
lm = ps.LM()
K = 24
BOIL = re.compile(r"forward-looking|conference call|webcast|non-gaap|safe harbor|www\.|http|investor relations|"
                  r"dial-in|replay|press release|reconciliation|table|incorporated by reference|exhibit|"
                  r"securities exchange act|pursuant to|signature|form 8-k", re.I)


def sentences(text):
    out = []
    for line in (c for l in text.split("\n") for c in l.split("|")):
        line = line.strip(" \u2022\u25cf\u25aa\u00b7\u2013-*")
        words = line.split()
        if len(words) < 8:
            continue
        letters = sum(ch.isalpha() for ch in line)
        if letters / max(len(line), 1) < 0.5:
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", line):
            s = s.strip()
            if len(s.split()) >= 6 and not BOIL.search(s):
                out.append(s)
    return out


@torch.no_grad()
def finbert(sents):
    enc = tok(sents, return_tensors="pt", padding=True, truncation=True, max_length=96)
    p = torch.softmax(mdl(**enc).logits, -1).numpy()  # pos, neg, neu
    return p


if __name__ != "__main__":
    raise SystemExit  # importable only for sentences()/finbert() in tests
# Usage: s05_score.py TEXTS.jsonl.gz OUTPREFIX  -> DATA/OUTPREFIX_partNNN.parquet (resumable; 500 docs per part)
import glob
inp, pref = DATA / sys.argv[1], sys.argv[2]
parts = sorted(glob.glob(str(DATA / f"{pref}_part*.parquet")))
done = set()
for q in parts:
    done |= set(pd.read_parquet(q, columns=["acc"]).acc)
k = len(parts)
rows = []; t0 = time.time(); n = 0


def flush():
    global rows, k
    if rows:
        pd.DataFrame(rows).to_parquet(DATA / f"{pref}_part{k:03d}.parquet"); k += 1; rows = []


try:
    f = gzip.open(inp, "rt")
    for line in f:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            break
        if d["acc"] in done:
            continue
        S = sentences(d["text"])[:K]
        r = {"acc": d["acc"], "dtype": d["dtype"], "nchar": d["nchar"], "nsent": len(S)}
        if S:
            p = finbert(S)
            net = p[:, 0] - p[:, 1]
            r.update(fb_mean=net.mean(), fb_head=net[:3].mean(), fb_pos=p[:, 0].mean(), fb_neg=p[:, 1].mean(),
                     fb_frac_neg=(p[:, 1] > 0.5).mean())
        # LM on first ~4000 words of narrative text (tables excluded)
        narr = " ".join(c for l in d["text"].split("\n") for c in l.split("|") if len(c.split()) >= 5)
        w = " ".join(narr.split()[:4000])
        sc = lm.get_score(lm.tokenize(w)) if w else {"Positive": 0, "Negative": 0}
        nw = max(len(w.split()), 1)
        r.update(lm_pos=sc["Positive"] / nw, lm_neg=sc["Negative"] / nw,
                 lm_tone=(sc["Positive"] - sc["Negative"]) / max(sc["Positive"] + sc["Negative"], 1))
        rows.append(r); n += 1
        if len(rows) >= 500:
            flush(); print(n, round(time.time() - t0), flush=True)
except (EOFError, OSError):
    pass  # file still being appended / truncated tail: resume next run
flush()
print("done", n, round(time.time() - t0))
