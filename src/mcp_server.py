import hmac
import os
import re
import threading
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

load_dotenv()

from src import db  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# Fixed output path from config; callers can never choose where the server writes
OUTPUT_FILE = Path(os.getenv("APPROVED_FILE", ROOT / "output" / "approved_reservations.txt"))
_write_lock = threading.Lock()

mcp = FastMCP("CityPark Reservations", stateless_http=True, json_response=True)


def _clean(value) -> str:
    """Remove characters that could break the 'a | b | c | d' line format."""
    return re.sub(r"[|\r\n]+", " ", str(value)).strip()


def write_approved(rid: int) -> str:
    """Append an approved reservation to the file. Returns a status string."""
    if not db.claim_for_recording(rid):
        r = db.get_reservation(rid)
        if r is None:
            return "not_found"
        if r["status"] != "approved":
            return "not_approved"
        return "already_recorded"
    r = db.get_reservation(rid)
    line = " | ".join([
        _clean(f"{r['name']} {r['surname']}"),
        _clean(r["car_number"]),
        f"{_clean(r['start_time'])} to {_clean(r['end_time'])}",
        _clean(r["decided_at"]),
    ])
    try:
        with _write_lock:
            OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with OUTPUT_FILE.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        db.release_claim(rid)  # allow a retry
        raise
    return "recorded"


@mcp.tool()
def record_approved_reservation(reservation_id: int) -> str:
    """Write an approved reservation to the approvals file as:
    Name | Car Number | Reservation Period | Approval Time.
    Returns: recorded, already_recorded, not_approved or not_found."""
    return write_approved(reservation_id)


class TokenMiddleware(BaseHTTPMiddleware):
    """Reject every request that lacks the correct bearer token."""

    async def dispatch(self, request, call_next):
        expected = os.getenv("MCP_TOKEN", "")
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
            return JSONResponse({"detail": "Invalid or missing token"}, status_code=401)
        return await call_next(request)


app = mcp.streamable_http_app()
app.add_middleware(TokenMiddleware)