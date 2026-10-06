# CityPark Parking Assistant

A two-agent chatbot for a parking facility.

- **Stage 2:** an admin agent (Agent 2) escalates each reservation to a human administrator,
  who approves or rejects it through a token-protected REST API. The user can then check the decision in the chat.

Static knowledge (location, rules, FAQ) lives in a vector database, dynamic data (prices, hours,
availability, reservations) in SQLite, and guardrails protect sensitive data. All data is fictional.

## Architecture

```mermaid
flowchart LR
    U[User] --> IG[Input guard]
    IG -->|blocked| END1[Refusal]
    IG --> CI[Classify intent]
    CI -->|info or status| INFO[Info agent]
    CI -->|booking| BK[Booking slot filling]
    CI -->|other| FB[Fallback]
    INFO --> VDB[(Milvus Lite: static docs)]
    INFO --> SQL[(SQLite: prices, hours, availability, reservations)]
    BK --> RES[(SQLite: reservations, status pending)]
    BK -->|escalate| A2[Agent 2: admin agent]
    A2 --> SQL
    A2 --> NOTIF[Notifier: console + outbox/]
    INFO --> OG[Output guard: PII redaction]
    BK --> OG
    FB --> OG
    OG --> U
```

- **Static data** (general info, location, rules, FAQ, booking process) is chunked, embedded
  with `all-MiniLM-L6-v2`, and stored in Milvus Lite.
- **Dynamic data** is read through fixed, parameterized SQL functions. The LLM never writes SQL.
- **Booking** is a slot-filling flow (name, surname, car number, start, end) with validation and a
  confirmation step. Confirmed requests are saved as `pending` and escalated to the administrator.
- **Guardrails:** regex input filter, private chunks excluded at retrieval, fixed tools only,
  and Presidio PII redaction on every output (the user's own booking data is allowed).

### How the two agents communicate

Agent 1 calls `escalate(reservation_id)` after saving a reservation. Agent 2 is a LangChain agent with
four tools: `get_reservation_details`, `check_conflicts`, `check_availability` and
`send_admin_notification`. It writes a short request with a recommendation (approve, reject or review).
The two agents share the SQLite `reservations` table.

If the LLM fails three times, `escalate()` sends a deterministic template message instead, so the
administrator is always notified. `escalate()` never raises, so a failure in Agent 2 cannot break the chat.

### Administrator channel

The administrator receives the request in the console and in `outbox/request_<id>.txt` (kept as an
audit trail). The reply goes through the REST API.

| Endpoint | Purpose |
|---|---|
| `GET /admin/reservations?status=pending` | List reservations, optionally filtered by status |
| `POST /admin/reservations/{id}/decision` | Structured decision: `{"decision": "approved" or "rejected", "comment": "..."}` |
| `POST /admin/reply` | Free-text reply such as `approve 5` or `reject 5 lot is full`, parsed by the admin agent |

All endpoints require the `X-Admin-Token` header. Interactive docs are at `http://localhost:8000/docs`
(click **Authorize** and paste the token).

Example:

```bash
curl -X POST http://localhost:8000/admin/reservations/1/decision \
  -H "X-Admin-Token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "comment": "Welcome!"}'
```

Reply parsing uses a regex first (fast, works offline) and falls back to an LLM with structured output
for free text.

### Checking the result as a user

Ask the chat: "What is the status of reservation 1?" The bot asks for the reservation number and the
car number used when booking, then reports `pending`, `approved` or `rejected` and any administrator comment.

### Security notes

- **The LLM never decides.** Agent 2 can only write and send the request. Decisions come only from the
  administrator through the authenticated API. This matters because reservation fields are user-controlled text.
- **Token-protected API.** A missing or wrong token returns `401` (compared in constant time).
- **One-time decisions.** Only a `pending` reservation can be decided, and a second decision returns `409`.
- **Status needs both the reservation id and the car number**, so users can't read other people's reservations.
- **Admin commands typed into the chat are refused.** A message like `approve 5` in the user chat gets a
  clear "only the administrator can decide" reply.

## Setup

Requires Python 3.11.

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

Create `.env`:

```
GROQ_API_KEY=your_key
MODEL=groq:openai/gpt-oss-120b
ADMIN_TOKEN=put-a-long-random-string-here
```

Any provider supported by LangChain's `init_chat_model` works; install its package and change `MODEL`.
Use a long random value for `ADMIN_TOKEN`, for example the output of
`python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Usage

Prepare the data once:

```bash
python data/seed.py          # create SQLite tables and sample data (rebuilds the database)
python -m src.ingest         # embed static docs into Milvus Lite
```

Run the demo in two terminals, each with the virtual environment active:

| Terminal | Command | What it is |
|---|---|---|
| 1 | `python -m src.main` | The user chat (Agent 1) |
| 2 | `uvicorn src.api:app --port 8000` | The administrator REST API |

Demo steps:

1. In the chat, make a booking and confirm. The `[ADMIN NOTIFICATION]` message appears in the console and
   `outbox/request_<id>.txt` holds a copy.
2. Open `http://localhost:8000/docs`, authorize with `ADMIN_TOKEN`, and list pending reservations.
3. Approve or reject the reservation with `POST /admin/reservations/{id}/decision`.
4. In the chat, ask for the status of the reservation and give your car number.

Other commands:

```bash
python -m eval.run_eval      # run the evaluation (add --skip-e2e to skip LLM calls)
pytest -q                    # run tests
```

Example questions: "What are the prices in Zone C?", "Is there EV charging?",
"Are there free spaces?", "I want to book a space.", "What is the status of reservation 1?"

## Project structure

```
data/static/         markdown docs for the vector DB (private_notes.md is fake sensitive data)
data/seed.py         creates and fills the SQLite database
src/ingest.py        chunk, embed, store in Milvus
src/retriever.py     retriever with a public-only filter
src/db.py            parameterized SQL queries, reservation decisions, conflict checks
src/booking.py       booking validation (plate, dates)
src/guardrails.py    input filter and PII redaction
src/graph.py         LangGraph flow (Agent 1)
src/admin_agent.py   admin agent (Agent 2): escalation, notification, reply parsing
src/notifier.py      delivers approval requests to the console and outbox/
src/api.py           token-protected FastAPI app for the administrator
src/main.py          CLI chat loop
eval/                golden set and evaluation script
tests/               pytest suite
EVALUATION.md        evaluation report
```

## Tests

`pytest -q` runs the whole suite offline, with no LLM calls. Stage 2 adds tests for each new module:

- `tests/test_db_admin.py`: one-time decisions, status lookup needs a matching plate, conflicts count only approved reservations
- `tests/test_notifier.py`: outbox file and console output, directory creation and overwrite
- `tests/test_admin_agent.py`: reply parsing, database update from a reply, fallback template when the agent fails
- `tests/test_api.py`: `401` without a token, list and decide, `409` on a second decision and `404` on an unknown id

## Evaluation summary

Chunk size 300 with k=3 gives Recall@3 0.84, Precision@3 0.58 and MRR 0.83 on a 30-question
golden set. Retrieval takes about 15 ms; end-to-end latency (dominated by the LLM) has a median of
about 2-5 s. The input filter blocks 10/10 direct attacks and 2/10 paraphrased ones, but no secret
leaked end to end in any of the 10 paraphrased attacks. Details and limitations are in
[EVALUATION.md](EVALUATION.md).

## Limitations

- The user learns the outcome only by asking, because the CLI chat has no push channel. A WebSocket or a
  background poll could be a next step.
- Admin delivery is console and file only. An email or Slack notifier could replace the body of
  `send_to_admin` in `src/notifier.py` without touching the agent.
- SQLite is shared by two processes, which is fine at this scale. A server database would be the production choice.
- `MemorySaver` and the in-memory set of sent requests do not survive restarts.
- Reservations are not tied to a specific zone.

## Notes

- Milvus Lite is used, so no server is needed.
- `private_notes.md` contains invented data used only to demonstrate the guardrails.
- Do not commit `.env`, `outbox/` or any `*.db` file.