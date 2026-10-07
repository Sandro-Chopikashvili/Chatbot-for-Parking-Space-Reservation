import hmac
import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from src.admin_agent import after_decision, apply_admin_reply  # noqa: E402

load_dotenv()

from src import db  # noqa: E402
from src.admin_agent import apply_admin_reply  # noqa: E402

app = FastAPI(title="CityPark Admin API")
api_key = APIKeyHeader(name="X-Admin-Token", auto_error=False)


def require_admin(token: str | None = Depends(api_key)):
    expected = os.getenv("ADMIN_TOKEN", "")
    if not expected or not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = ""


class ReplyIn(BaseModel):
    text: str


@app.get("/admin/reservations", dependencies=[Depends(require_admin)])
def list_reservations(status: str | None = None):
    return db.list_reservations(status)


@app.post("/admin/reservations/{rid}/decision", dependencies=[Depends(require_admin)])
def decide(rid: int, body: DecisionIn):
    if db.get_reservation(rid) is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if not db.decide_reservation(rid, body.decision, body.comment):
        raise HTTPException(status_code=409, detail="Reservation already decided")
    file_status = after_decision(rid, body.decision)
    return {**db.get_reservation(rid), "file_status": file_status}


@app.post("/admin/reply", dependencies=[Depends(require_admin)])
def reply(body: ReplyIn):
    """Free-text reply such as 'approve 5' or 'reject 5 lot is full', parsed by the admin agent."""
    return {"result": apply_admin_reply(body.text)}

@app.post("/admin/reservations/{rid}/record", dependencies=[Depends(require_admin)])
def record(rid: int):
    """Retry writing an approved reservation to the file (e.g. after the MCP server was down)."""
    if db.get_reservation(rid) is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return {"file_status": after_decision(rid, "approved")}