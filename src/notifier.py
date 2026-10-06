from pathlib import Path

# Folder for saved approval requests: <project root>/outbox
OUTBOX = Path(__file__).resolve().parent.parent / "outbox"


# Deliver an approval request to the administrator: print it and keep a copy in outbox/
def send_to_admin(message: str, reservation_id: int) -> str:
    """Deliver an approval request: print it and keep a copy in outbox/ as an audit trail."""
    # Create outbox/ if it doesn't exist yet
    OUTBOX.mkdir(exist_ok=True)
    # Save the request as request_<id>.txt (sending again for the same id overwrites it)
    (OUTBOX / f"request_{reservation_id}.txt").write_text(message, encoding="utf-8")
    # Show the request in the console, which acts as the admin's inbox
    print(f"\n[ADMIN NOTIFICATION]\n{message}\n")
    # Name of the channel used (lets other channels like email be added later)
    return "console"