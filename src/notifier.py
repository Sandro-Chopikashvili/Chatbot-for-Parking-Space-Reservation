from pathlib import Path

OUTBOX = Path(__file__).resolve().parent.parent / "outbox"


def send_to_admin(message: str, reservation_id: int) -> str:
    """Deliver an approval request: print it and keep a copy in outbox/ as an audit trail."""
    OUTBOX.mkdir(exist_ok=True)
    (OUTBOX / f"request_{reservation_id}.txt").write_text(message, encoding="utf-8")
    print(f"\n[ADMIN NOTIFICATION]\n{message}\n")
    return "console"