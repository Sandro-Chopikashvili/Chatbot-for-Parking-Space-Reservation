## Imports ## 
import re
from datetime import datetime, timedelta

# Regular expression for validating Georgian-style car plate numbers.
# Expected format: AB-123-CD
PLATE_RE = re.compile(r"^[A-Z]{2}-\d{3}-[A-Z]{2}$") 

# Booking fields that need to be collected from the user.
FIELDS = ["name", "surname", "car_number", "start", "end"]

# Human-readable labels used when asking the user for missing booking fields.
LABELS = {
    "name": "first name", "surname": "last name",
    "car_number": "car number plate (format AB-123-CD)",
    "start": "reservation start (date and time)", "end": "reservation end (date and time)",
}

# Date and time format used for storing and validating reservation times
FMT = "%Y-%m-%d %H:%M"

# Normalize a car plate by removing extra spaces, converting to uppercase,
# and replacing spaces with hyphens
def normalize_plate(p: str) -> str:
    return p.strip().upper().replace(" ", "-")


# Check whether the car plate is valid after normalizing its format
def valid_plate(p: str) -> bool:
    return bool(PLATE_RE.match(normalize_plate(p)))


# Date/time formats accepted when parsing reservation times.
_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]

# Convert a string into a datetime object using the supported formats.
# Return None if the value is empty or does not match any supported format.
def parse_dt(s: str) -> datetime | None:
    if not s:
        return None

    # Clean the input and remove the trailing "Z" from UTC-style timestamps.
    s = str(s).strip().replace("Z", "")

    # Try each supported date/time format until one matches.
    for fmt in _FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

# Validate Booking 
def validate(booking: dict, now: datetime | None = None) -> tuple[dict, list[str]]:
    """Return (cleaned booking, list of error messages). Invalid fields are removed."""
    now = now or datetime.now()

    # Copy the booking so the original dictionary is not modified.
    b, errors = dict(booking), []

    # Validate and normalize the car plate number.
    if b.get("car_number"):
        if valid_plate(b["car_number"]):
            b["car_number"] = normalize_plate(b["car_number"])
        else:
            errors.append("That car number doesn't look valid (expected format AB-123-CD).")
            b.pop("car_number")

    # Parse and normalize the reservation start and end times.
    for key in ("start", "end"):
        if b.get(key):
            dt = parse_dt(b[key])
            if dt is None:
                errors.append(f"I couldn't understand the {key} time.")
                b.pop(key)
            else:
                b[key] = dt.strftime(FMT)

    # Parse the cleaned start and end times for further validation
    start, end = parse_dt(b.get("start", "")), parse_dt(b.get("end", ""))

    # The reservation cannot start in the past.
    if start and start < now:
        errors.append("The start time is in the past.")
        b.pop("start")
        start = None

    # Validate the relationship between the start and end times.
    if start and end:
        if end <= start:
            errors.append("The end time must be after the start time.")
            b.pop("end")
        elif end - start > timedelta(days=30):
            # Limit the maximum reservation duration to 30 days.
            errors.append("The maximum reservation length is 30 days.")
            b.pop("end")

    # Return the cleaned booking and all validation errors.
    return b, errors

# Return the booking fields that have not been provided yet.
def missing(booking: dict) -> list[str]:
    return [f for f in FIELDS if not booking.get(f)]