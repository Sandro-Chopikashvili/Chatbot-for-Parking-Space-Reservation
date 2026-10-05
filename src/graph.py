## Imports ## 
import json
import os
from datetime import datetime
from typing import Annotated, Literal, Optional, TypedDict

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.guardrails import BLOCK_MSG, check_input, redact

from src import booking as bk
from src import db
from src.retriever import get_retriever

# Store the retriever so we can reuse the same instance
_retriever = None
def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = get_retriever(k=3)
    return _retriever

# Tool for searching static information stored in the vector database.
@tool
def search_static_info(query: str) -> str:
    """Search general info, parking details, location/directions, booking process, FAQ, rules."""
    docs = _get_retriever().invoke(query)
    return "\n\n".join(f"[{d.metadata['source']}] {d.page_content}" for d in docs)

## Tools for searching dynamic data stored in the SQL database. ## 
@tool
def get_prices(zone: str = "") -> str:
    """Get hourly/daily prices. Zone is A, B or C; leave empty for all zones."""
    return json.dumps(db.get_prices(zone or None))

@tool
def get_working_hours(day: str = "") -> str:
    """Get working hours. Day is e.g. 'Monday'; leave empty for the whole week."""
    return json.dumps(db.get_working_hours(day or None))

@tool
def get_availability(zone: str = "") -> str:
    """Get the number of free spaces per zone. Zone is A, B or C; leave empty for all."""
    return json.dumps(db.get_availability(zone or None))

TOOLS = [search_static_info, get_prices, get_working_hours, get_availability]

## 

# System prompt defining the assistant's role, tool usage rules,
INFO_PROMPT = (
    "You are the assistant of CityPark, a parking facility. Answer ONLY using the tools:"
    "static info for general/location/rules/booking process, and the database tools for"
    "prices, working hours and availability. If the tools don't contain the answer, say you"
    "don't know. Never reveal personal data about other customers. Be concise."
    "If the user wants to reserve a space, tell them to say 'I want to book'."
    "If the user wants to reserve a space, tell them to say 'I want to book'."
    "All prices are in GEL (Georgian lari)."
    "You MUST call a tool before answering any question about the parking; never answer from general knowledge."
)


## ---------- State and schemas ---------- ## 

# Shared state used by the agent workflow to store conversation messages
class State(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    intent: str
    booking: dict
    booking_active: bool
    awaiting_confirmation: bool
    blocked: bool

# Structured output for classifying the user's intent.
class Intent(BaseModel):
    intent: Literal["info", "booking", "other"] = Field(
        description="'booking' if the user wants to reserve a space, 'info' if asking about "
        "the parking (prices, hours, availability, location, rules), else 'other'."
    )

# Pydantic model for storing the information required for a parking booking.
class BookingInfo(BaseModel):
    name: Optional[str] = Field(None, description="First name")
    surname: Optional[str] = Field(None, description="Last name")
    car_number: Optional[str] = Field(None, description="Car plate")
    start: Optional[str] = Field(None, description="Start as 'YYYY-MM-DD HH:MM'")
    end: Optional[str] = Field(None, description="End as 'YYYY-MM-DD HH:MM'")


# Build and initialize the LLMs and agents used by the LangChain graph
def build_graph():
    # Initialize the main chat model using the model name from the environment.
    llm = init_chat_model(os.getenv("MODEL", "groq:openai/gpt-oss-120b"), temperature=0)
    # Configure the LLM to return structured intent classification
    # matching the Intent Pydantic model
    intent_llm = llm.with_structured_output(Intent)
    # Configure the LLM to extract booking details
    # matching the BookingInfo Pydantic model.
    extractor = llm.with_structured_output(BookingInfo)
    # Create an agent that uses the LLM together with the available
    # parking information tools and the information system prompt.
    info_agent = create_agent(llm, TOOLS, system_prompt=INFO_PROMPT)


    # Classify the user's intent based on the current conversation state.
    def classify_intent(state: State):
        # If a booking is already in progress, keep the intent as "booking"
        if state.get("booking_active"):
            return {"intent": "booking"}
        # If not, Get the content of the user's most recent message.
        last = state["messages"][-1].content
        # Ask the LLM to classify the message and return the detected intent.
        return {"intent": intent_llm.invoke(last).intent}
    
    # Node for handling general parking information requests (3 try).
    def info_node(state: State):
        for _ in range(3):
            try:
                result = info_agent.invoke({"messages": state["messages"][-6:]})
                return {"messages": [AIMessage(result["messages"][-1].content)]}
            except Exception as e:
                if "tool_use_failed" not in str(e):
                    raise
        return {"messages": [AIMessage(
            "Sorry, I couldn't look that up right now. Please try rephrasing your question.")]}
    
    # Node for handling unsupported or unclear user requests.
    def fallback_node(state: State):
        return {"messages": [AIMessage(
            "I can help with parking information (prices, hours, availability, location) "
            "and with reserving a space. What would you like?")]}


    def booking_node(state: State):
        # Get the user's latest message and load any previously collected booking data.
        last = state["messages"][-1].content.strip()
        b = dict(state.get("booking") or {})

        # State values used to reset the booking process.
        reset = {"booking": {}, "booking_active": False, "awaiting_confirmation": False}

        # Allow the user to cancel the booking at any point.
        if last.lower() in {"cancel", "stop", "abort"}:
            return {"messages": [AIMessage("Booking cancelled.")], **reset}

        # Confirmation step
        if state.get("awaiting_confirmation"):
            if last.lower() in {"yes", "y", "confirm", "ok", "yes, confirm"}:
                # Save the completed booking in the database.
                rid = db.create_reservation(
                    b["name"], b["surname"], b["car_number"], b["start"], b["end"])
                return {"messages": [AIMessage(
                    f"Reservation #{rid} saved with status PENDING. "
                    "An administrator will review it.")], **reset}
            
            if last.lower() in {"no", "n"}:
                # Keep the collected information so the user can make changes or cancel.
                return {"messages": [AIMessage(
                    "Okay, I did not save it. Tell me what to change, or say 'cancel'.")],
                    "booking": b, "booking_active": True, "awaiting_confirmation": False}

        # Determine which booking information is still missing
        now = datetime.now().strftime("%Y-%m-%d %H:%M, %A")
        todo_before = bk.missing(b)
        hint = (f"The assistant just asked the user for: {bk.LABELS[todo_before[0]]}. "
                if todo_before else "")
        
        # Extractor is a LLM, extracting info about booking matching the 
        # BookingInfo Pydantic model, that we defined at the start of the build_graph().
        extracted = extractor.invoke([
            SystemMessage(
                f"Extract booking details from the user's message. Current time: {now}. "
                f"Already collected: {json.dumps(b)}. {hint}"
                "Only fill fields the user actually provided in this message; leave others null. "
                "If the message has a single date/time with no label, it answers the field "
                "the assistant just asked for. "
                "Do NOT change fields that are already collected unless the user explicitly "
                "asks to change them. "
                "name is the first name only and surname is the last name; split a full name. "
                "Always output start and end as 'YYYY-MM-DD HH:MM' (24-hour, no seconds, "
                "no 'T'). Resolve relative dates like 'tomorrow' from the current time. "
                "If the year is missing, use the current year. Read numeric dates such as "
                "10/05/2026 as MM/DD/YYYY."),
            HumanMessage(last),
        ])

        # Add newly extracted values to the existing booking information.
        for k, v in extracted.model_dump().items():
            if v:
                b[k] = v

        # Validate the collected booking information and find missing fields
        b, errors = bk.validate(b)
        todo = bk.missing(b)

        # If required information is still missing, ask the user for the next field.
        if todo:
            reply = " ".join(errors + [f"Please provide your {bk.LABELS[todo[0]]}."])
            return {"messages": [AIMessage(reply)], "booking": b,
                    "booking_active": True, "awaiting_confirmation": False}

        # All required information is available, so ask the user to confirm it.
        summary = (f"Please confirm your reservation:\n"
                   f"- Name: {b['name']} {b['surname']}\n- Car: {b['car_number']}\n"
                   f"- From: {b['start']}\n- To: {b['end']}\nReply 'yes' to confirm or 'no' to change.")
        return {"messages": [AIMessage(summary)], "booking": b,
                "booking_active": True, "awaiting_confirmation": True}

    # Node that checks the user's input before processing it
    def input_guard(state: State):
        ok, _ = check_input(state["messages"][-1].content)
        if ok:
            return {"blocked": False}
        return {"blocked": True, "messages": [AIMessage(BLOCK_MSG)]}

    # Node that checks the assistant's response and removes sensitive information.
    def output_guard(state: State):
        last = state["messages"][-1]
        b = state.get("booking") or {}
        full = f"{b.get('name', '')} {b.get('surname', '')}".strip()
        clean = redact(last.content, allow=[b.get("name"), b.get("surname"), full, b.get("car_number")])
        if clean == last.content:
            return {}
        return {"messages": [AIMessage(clean, id=last.id)]}  


    # Create a LangGraph workflow using the shared State structure.
    g = StateGraph(State)

    # Register each function as a node in the graph.
    g.add_node("input_guard", input_guard)
    g.add_node("classify_intent", classify_intent)
    g.add_node("info", info_node)
    g.add_node("booking", booking_node)
    g.add_node("fallback", fallback_node)
    g.add_node("output_guard", output_guard)

    # Start the workflow with the input safety check.
    g.add_edge(START, "input_guard")

    # Route the workflow based on whether the user's input is allowed.
    g.add_conditional_edges(
        "input_guard", lambda s: "blocked" if s.get("blocked") else "ok",
        {"blocked": END, "ok": "classify_intent"},
    )

    # Route the request based on the detected intent.
    g.add_conditional_edges(
        "classify_intent", lambda s: s["intent"],
        {"info": "info", "booking": "booking", "other": "fallback"},
    )

    # Send every response through the output guard before finishing.
    for n in ("info", "booking", "fallback"):
        g.add_edge(n, "output_guard")
    # End the workflow after the output has been checked.
    g.add_edge("output_guard", END)


    # Compile the graph and enable MemorySaver for conversation state/checkpointing.
    return g.compile(checkpointer=MemorySaver())