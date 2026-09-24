"""Shared client for TypeSafe's Jev via Vercel AI Gateway (evaluation model; typed questions -> typed answers).

The gateway credential is injected by the session's egress proxy, so no key is needed in code.

    from jev import ask
    ans = ask(state="...text...", questions={
        "guidance": {"type": "choice", "instructions": "What happened to full-year guidance?",
                     "criteria": {"raised": None, "maintained": None, "lowered": None, "not_given": None}},
        "one_time": {"type": "noul", "instructions": "Is an unusual one-time charge or gain mentioned?"},
        "caution":  {"type": "score", "instructions": "How cautious is the outlook language?",
                     "criteria": ["very confident", "confident", "neutral", "cautious", "very cautious"]},
    }, agent="m06")
    # ans["guidance"] -> {"choice": "raised", "probabilities": {...}, "confidence": 1.0}
    # ans["one_time"] -> {"noul": 0.99};  ans["caution"] -> {"score": 1.08 (0-based), "probabilities": {...}}

Notes
* Score criteria must be a LIST (ordered levels, returned as 0-based "score"); choice criteria a dict.
* State + longest question <= 32k tokens (~100k chars). Pre-filter text to the relevant sections.
* Responses are cached on disk (data/round5/jev_cache/<agent>/), keyed by a hash of the request, so
  re-runs cost nothing. A per-agent spending cap (USD, at $0.042 per million input tokens) is enforced.
* Lookahead: ask only about facts stated in the text ("did guidance rise?"), never about the future.
  Strip company names, tickers and dates from the state where feasible.
"""
import hashlib
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

URL = "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
MODEL = "typesafe-ai/jev"
PRICE_PER_TOKEN = 0.042e-6
ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "round5" / "jev_cache"
BUDGET_USD = {"m05": 5.0, "m06": 15.0, "m11": 5.0, "m07": 2.0}
DEFAULT_BUDGET = 2.0


class BudgetExceeded(RuntimeError):
    pass


def _ledger(agent: str) -> pathlib.Path:
    d = CACHE / agent
    d.mkdir(parents=True, exist_ok=True)
    return d / "_spend.json"


def spent(agent: str) -> dict:
    p = _ledger(agent)
    return json.loads(p.read_text()) if p.exists() else {"input_tokens": 0, "usd": 0.0, "calls": 0}


def _record(agent: str, tokens: int) -> None:
    s = spent(agent)
    s["input_tokens"] += tokens
    s["usd"] = s["input_tokens"] * PRICE_PER_TOKEN
    s["calls"] += 1
    _ledger(agent).write_text(json.dumps(s))


def ask(state, questions: dict, agent: str, retries: int = 5, timeout: float = 120.0) -> dict:
    """Evaluate `questions` against `state`; returns the answers dict (cached)."""
    body = {"model": MODEL, "state": state, "questions": questions}
    raw = json.dumps(body, sort_keys=True).encode()
    key = hashlib.sha256(raw).hexdigest()
    cdir = CACHE / agent
    cdir.mkdir(parents=True, exist_ok=True)
    cfile = cdir / f"{key[:2]}" / f"{key}.json"
    if cfile.exists():
        return json.loads(cfile.read_text())["answers"]
    cap = BUDGET_USD.get(agent, DEFAULT_BUDGET)
    if spent(agent)["usd"] >= cap:
        raise BudgetExceeded(f"{agent} reached its Jev budget of ${cap:.2f}; ask the orchestrator")
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(URL, data=raw, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:500]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay); delay *= 2; continue
            raise RuntimeError(f"Jev HTTP {e.code}: {msg}") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(delay); delay *= 2; continue
            raise
    _record(agent, int(out.get("usage", {}).get("input_tokens", 0)))
    cfile.parent.mkdir(parents=True, exist_ok=True)
    cfile.write_text(json.dumps({"answers": out["answers"], "usage": out.get("usage")}))
    return out["answers"]


if __name__ == "__main__":
    a = ask("Full-year revenue guidance was lowered to $3.9-4.0 billion.",
            {"g": {"type": "choice", "instructions": "What happened to full-year guidance?",
                   "criteria": {"raised": None, "maintained": None, "lowered": None, "not_given": None}}},
            agent="selftest")
    print(a, spent("selftest"))
