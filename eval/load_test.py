import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()

QUESTIONS = ["What are the prices in Zone C?", "What are the working hours on Sunday?",
             "Are there free spaces?"]


def _report(name, lat, errors, wall):
    ls = sorted(lat)
    p = lambda q: ls[min(len(ls) - 1, int(q * len(ls)))] * 1000 if ls else 0
    print(f"{name}: ok={len(ls)} errors={errors} throughput={len(ls) / wall:.1f}/s "
          f"p50={p(.5):.0f}ms p95={p(.95):.0f}ms max={(ls[-1] * 1000 if ls else 0):.0f}ms")


def _run(fn, jobs, workers):
    lat, errors = [], 0

    def one(job):
        t = time.perf_counter()
        try:
            fn(job)
            return time.perf_counter() - t
        except Exception as e:
            print(f"  error: {type(e).__name__}: {e}")
            return None

    t0 = time.perf_counter()
    with ThreadPoolExecutor(workers) as ex:
        for r in ex.map(one, jobs):
            if r is None:
                errors += 1
            else:
                lat.append(r)
    return lat, errors, time.perf_counter() - t0


def _make_reservations(n, approve=False):
    from src import db
    ids = []
    for i in range(n):
        day = f"2031-01-{(i % 28) + 1:02d}"
        rid = db.create_reservation("Load", f"User{i}", f"LT-{i:03d}-XX", f"{day} 10:00", f"{day} 12:00")
        if approve:
            db.decide_reservation(rid, "approved", "load test")
        ids.append(rid)
    return ids


def load_chat(users):
    """Interactive chat: each simulated user asks 3 questions in their own conversation."""
    from langchain_core.messages import HumanMessage
    from src.graph import build_graph
    graph = build_graph()
    lat, errs = [], []

    def user(uid):
        for q in QUESTIONS:
            t = time.perf_counter()
            try:
                graph.invoke({"messages": [HumanMessage(q)]},
                             {"configurable": {"thread_id": f"load-{uid}"}})
                lat.append(time.perf_counter() - t)
            except Exception as e:
                print(f"  error: {type(e).__name__}")
                errs.append(1)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(users) as ex:
        list(ex.map(user, range(users)))
    _report(f"chat ({users} users)", lat, len(errs), time.perf_counter() - t0)


def load_admin(n, workers):
    """Administrator confirmation through the running API (includes the MCP write)."""
    import httpx
    from src.mcp_server import OUTPUT_FILE
    ids = _make_reservations(n)
    client = httpx.Client(base_url=os.getenv("ADMIN_URL", "http://127.0.0.1:8000"),
                          headers={"X-Admin-Token": os.environ["ADMIN_TOKEN"]}, timeout=60)

    def approve(rid):
        r = client.post(f"/admin/reservations/{rid}/decision",
                        json={"decision": "approved", "comment": "load"})
        r.raise_for_status()
        if r.json().get("file_status") != "recorded":
            raise RuntimeError(f"file_status={r.json().get('file_status')}")

    _report(f"admin approval ({n} requests, {workers} workers)", *_run(approve, ids, workers))
    lines = [l for l in OUTPUT_FILE.read_text(encoding="utf-8").splitlines() if l.startswith("Load ")]
    print(f"  file check: {len(lines)} load-test lines for {n} approvals")


def load_mcp(n, workers):
    """MCP server recording, called directly, plus a duplicate (idempotency) check."""
    from src import mcp_client
    ids = _make_reservations(n, approve=True)

    def record(rid):
        status = mcp_client.record_approved(rid)
        if status != "recorded":
            raise RuntimeError(status)

    _report(f"mcp recording ({n} calls, {workers} workers)", *_run(record, ids, workers))
    repeat = {mcp_client.record_approved(rid) for rid in ids[:5]}
    print(f"  repeat calls return: {repeat} (expected {{'already_recorded'}})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("target", choices=["chat", "admin", "mcp"])
    ap.add_argument("--users", type=int, default=3)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    {"chat": lambda: load_chat(a.users),
     "admin": lambda: load_admin(a.n, a.workers),
     "mcp": lambda: load_mcp(a.n, a.workers)}[a.target]()