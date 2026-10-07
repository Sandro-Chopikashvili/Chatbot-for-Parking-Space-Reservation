import sqlite3
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.admin_agent import after_decision, escalate

# Checkpoint file shared by the chat process and the API process
CHECKPOINT_DB = Path(__file__).resolve().parent.parent / "data" / "checkpoints.db"
_pipeline = None


# State of one reservation's journey through the pipeline
class PipelineState(TypedDict, total=False):
    reservation_id: int
    notified: bool
    decision: str
    comment: str
    file_status: str


# Node 1: Agent 2 prepares and sends the approval request
def escalate_node(state: PipelineState):
    return {"notified": escalate(state["reservation_id"])}


# Node 2: pause until the human administrator decides (the run is saved and stops here)
def await_admin(state: PipelineState):
    answer = interrupt({"reservation_id": state["reservation_id"],
                        "waiting_for": "administrator decision"})
    return {"decision": answer["decision"], "comment": answer.get("comment", "")}


# Node 3: the MCP server writes the approved reservation to the file
def record_node(state: PipelineState):
    return {"file_status": after_decision(state["reservation_id"], state["decision"])}


# Node 3 (rejected branch): nothing to record
def close_rejected(state: PipelineState):
    return {"file_status": "not_needed"}


def _route(state: PipelineState) -> str:
    return "record" if state["decision"] == "approved" else "close_rejected"


def build_pipeline(checkpointer=None):
    g = StateGraph(PipelineState)
    g.add_node("escalate", escalate_node)
    g.add_node("await_admin", await_admin)
    g.add_node("record", record_node)
    g.add_node("close_rejected", close_rejected)
    g.add_edge(START, "escalate")
    g.add_edge("escalate", "await_admin")
    g.add_conditional_edges("await_admin", _route,
                            {"record": "record", "close_rejected": "close_rejected"})
    g.add_edge("record", END)
    g.add_edge("close_rejected", END)
    return g.compile(checkpointer=checkpointer)


# Build the shared pipeline on first use, backed by the SQLite checkpoint file
def get_pipeline():
    global _pipeline
    if _pipeline is None:
        conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
        _pipeline = build_pipeline(SqliteSaver(conn))
    return _pipeline


def _config(rid: int) -> dict:
    return {"configurable": {"thread_id": f"reservation-{rid}"}}


def start_pipeline(rid: int) -> bool:
    """Run the pipeline until it pauses at the admin approval. Never raises.
    Returns True if the administrator was notified."""
    try:
        result = get_pipeline().invoke({"reservation_id": rid}, _config(rid))
        return bool(result.get("notified"))
    except Exception:
        return False


def resume_pipeline(rid: int, decision: str, comment: str = "") -> str:
    """Give the human decision to the paused run. Never raises. Returns the file status."""
    try:
        p = get_pipeline()
        # No paused run (for example a reservation created before Stage 4): use the Stage 3 path
        if not p.get_state(_config(rid)).next:
            return after_decision(rid, decision)
        result = p.invoke(Command(resume={"decision": decision, "comment": comment}), _config(rid))
        return result.get("file_status", "unavailable")
    except Exception:
        return "unavailable"