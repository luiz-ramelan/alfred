import os
import uuid
import logging
from pathlib import Path
from dotenv import load_dotenv

from google.adk import Agent
from google.adk.agents import SequentialAgent

# --- Setup Logging and Environment ---
logging.basicConfig(level=logging.INFO)

# Load .env from the same directory as this file (alfred_agent/.env)
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

model_name = os.getenv("MODEL")

# ---------------------------------------------------------------------------
# In-Memory Storage  (simple dicts / lists for local testing)
# ---------------------------------------------------------------------------

# { name_lower: { "name", "email", "relationship": "self"|"family"|"work" } }
contacts: dict = {}

# [ { "id", "title", "datetime": "YYYY-MM-DD HH:MM", "type": "work"|"home",
#     "priority": int, "participants": list[str] } ]
events: list = []

# [ { "to", "subject", "body" } ]
notifications: list = []

# ---------------------------------------------------------------------------
# Shared Tools  (used across multiple agents)
# ---------------------------------------------------------------------------

def add_contact(name: str, email: str, relationship: str) -> dict:
    """
    Registers a person in the household directory.

    Args:
        name:         Full name (e.g. "Martha").
        email:        Email address (e.g. "martha@gmail.com").
        relationship: Exactly one of 'self', 'family', or 'work'.

    Returns:
        Confirmation dict.
    """
    key = name.strip().lower()
    contacts[key] = {
        "name":         name.strip(),
        "email":        email.strip(),
        "relationship": relationship.strip().lower()
    }
    logging.info(f"[Contacts] + {name} ({relationship}) <{email}>")
    return {
        "status":  "success",
        "message": f"'{name}' added as a {relationship} contact."
    }


def list_contacts() -> dict:
    """Returns every contact in the directory."""
    if not contacts:
        return {"status": "empty", "contacts": []}
    return {"status": "success", "contacts": list(contacts.values())}


# ── Event classification helpers ────────────────────────────────────────────

_WORK_KEYWORDS = {
    "meeting", "presentation", "call", "board", "conference",
    "client", "project", "standup", "interview", "deadline", "demo"
}
_HOME_KEYWORDS = {
    "dinner", "lunch", "breakfast", "family", "school", "doctor",
    "delivery", "grocery", "birthday", "anniversary", "vacation",
    "appointment", "pickup"
}


def _classify(title: str, participants: list) -> str:
    """Returns 'work' or 'home' based on title keywords then participant relationships."""
    words = set(title.lower().split())
    if words & _WORK_KEYWORDS:
        return "work"
    if words & _HOME_KEYWORDS:
        return "home"
    for p in participants:
        entry = contacts.get(p.strip().lower())
        if entry:
            if entry["relationship"] == "work":
                return "work"
            if entry["relationship"] == "family":
                return "home"
    return "home"   # safe default


# ── Event CRUD ───────────────────────────────────────────────────────────────

def add_event(title: str, event_datetime: str, participants: list[str], priority: int = 5) -> dict:
    """
    Adds an event to the schedule and auto-classifies it as 'work' or 'home'.

    Args:
        title:          Short description, e.g. "Board meeting with Lucius".
        event_datetime: Date and time in 'YYYY-MM-DD HH:MM' format.
        participants:   Contact names involved, e.g. ["Lucius"].
        priority:       1 = most important, 10 = least important. Defaults to 5.

    Returns:
        Dict with event_id, classified_as ('work'|'home'), and a confirmation message.
    """
    event_type = _classify(title, participants)
    event_id   = str(uuid.uuid4())[:8]

    events.append({
        "id":           event_id,
        "title":        title,
        "datetime":     event_datetime,
        "type":         event_type,
        "priority":     priority,
        "participants": [p.strip() for p in participants]
    })
    logging.info(
        f"[Events] + [{event_type.upper()}] '{title}' @ {event_datetime} "
        f"(priority={priority}, id={event_id})"
    )
    return {
        "status":        "success",
        "event_id":      event_id,
        "classified_as": event_type,
        "message": (
            f"'{title}' added as a {event_type} event on {event_datetime} "
            f"with priority {priority}."
        )
    }


def list_events() -> dict:
    """Returns all events sorted by datetime."""
    if not events:
        return {"status": "empty", "events": []}
    return {
        "status": "success",
        "events": sorted(events, key=lambda e: e["datetime"])
    }


# ── Conflict detection & resolution ─────────────────────────────────────────

def check_conflicts() -> dict:
    """
    Scans all events for exact datetime overlaps.

    Returns:
        'no_conflicts' status, or a list of conflicting pairs with full event details.
    """
    conflicts = []
    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            if events[i]["datetime"] == events[j]["datetime"]:
                conflicts.append({
                    "event_a": events[i],
                    "event_b": events[j]
                })
    if not conflicts:
        return {"status": "no_conflicts", "message": "No scheduling conflicts found."}
    return {
        "status":    "conflicts_found",
        "count":     len(conflicts),
        "conflicts": conflicts
    }


def resolve_conflict(event_id: str, new_datetime: str) -> dict:
    """
    Resolves a conflict by rescheduling one event and notifying its participants.

    The event with the HIGHER priority number (less important) should be rescheduled.
    Priority 1 = most critical (wins); priority 10 = least important (moves).

    Args:
        event_id:     ID of the event to reschedule (pass the lower-priority one).
        new_datetime: New date/time in 'YYYY-MM-DD HH:MM' format.

    Returns:
        Confirmation dict including which participants were notified.
    """
    for event in events:
        if event["id"] == event_id:
            old_dt = event["datetime"]
            event["datetime"] = new_datetime

            notified = []
            for pname in event["participants"]:
                contact = contacts.get(pname.strip().lower())
                if contact:
                    notifications.append({
                        "to":      contact["email"],
                        "subject": f"Schedule change: {event['title']}",
                        "body": (
                            f"Dear {contact['name']},\n\n"
                            f"I write to inform you that '{event['title']}', "
                            f"originally scheduled for {old_dt}, has been rescheduled "
                            f"to {new_datetime} due to a prior commitment.\n\n"
                            f"I do apologise for any inconvenience.\n\n"
                            f"Yours faithfully,\nAlfred Pennyworth"
                        )
                    })
                    notified.append(contact["name"])
                    logging.info(f"[Notification] Email queued → {contact['email']}")

            return {
                "status":   "success",
                "event_id": event_id,
                "message": (
                    f"'{event['title']}' moved from {old_dt} to {new_datetime}. "
                    f"Notifications sent to: {', '.join(notified) if notified else 'no known contacts'}."
                )
            }

    return {"status": "error", "message": f"No event found with id '{event_id}'."}


def list_notifications() -> dict:
    """Returns all email notifications that have been dispatched."""
    if not notifications:
        return {"status": "empty", "notifications": []}
    return {
        "status":        "success",
        "count":         len(notifications),
        "notifications": notifications
    }


# ---------------------------------------------------------------------------
# Sub-Agents
# ---------------------------------------------------------------------------

# 1. Work Agent — professional schedule
work_agent = Agent(
    name="work_agent",
    model=model_name,
    description="Handles all professional events: meetings, calls, presentations, deadlines.",
    instruction="""
    You are Alfred's professional attaché, responsible for Master Wayne's work calendar.

    Your job in this pipeline step:
    1. Read the conversation context for any work-related event
       (keywords: meeting, call, board, presentation, conference, demo, deadline).
    2. Call `add_event` to register the event.
       - participants: include all work contacts mentioned.
       - priority: derive from urgency (1=critical, 10=casual). Default 5.
    3. Call `list_events` and include the current schedule in your output_key summary.

    Do NOT handle home/family events — leave those for home_agent.
    Be concise; your output feeds the next agent.
    """,
    tools=[add_event, list_events],
    output_key="work_summary"
)

# 2. Home Agent — domestic schedule
home_agent = Agent(
    name="home_agent",
    model=model_name,
    description="Handles all family and household events: dinners, appointments, deliveries.",
    instruction="""
    You manage the domestic side of Master Wayne's life.

    Your job in this pipeline step:
    1. Read the conversation context for any home/family event
       (keywords: dinner, family, doctor, school, birthday, delivery, grocery, vacation).
    2. Call `add_event` to register the event.
       - participants: include family members mentioned.
       - priority: if user says "very important" or "critical" → 1 or 2. Default 5.
    3. Call `list_events` and include the home schedule in your output_key summary.

    Do NOT handle work events — those belong to work_agent.
    Be concise; your output feeds the response_formatter.
    """,
    tools=[add_event, list_events],
    output_key="home_summary"
)

# 3. Response Formatter — conflict resolution + final report
response_formatter = Agent(
    name="response_formatter",
    model=model_name,
    description="Detects conflicts, resolves them, and delivers Alfred's polished final report.",
    instruction="""
    You are Alfred Pennyworth. You deliver the final, unified summary to Master Wayne.

    Your job in this pipeline step:
    1. Call `check_conflicts` to detect any scheduling overlaps.
    2. If conflicts exist:
       a. Compare the two events' priorities.
          The event with the HIGHER priority number (less important) must move.
       b. Propose a sensible new time (e.g. +2 hours, or the next whole hour).
       c. Call `resolve_conflict` with the losing event's id and the new datetime.
    3. Call `list_notifications` to confirm which emails were queued.
    4. Deliver a warm, conversational summary in Alfred's voice:
       - What was added (work vs home, priority level).
       - Whether a conflict was found, which event "won" and why.
       - What was rescheduled, to when, and who was notified.

    Speak with dry wit and impeccable manners. No bullet-point walls.
    """,
    tools=[check_conflicts, resolve_conflict, list_notifications]
)

# ---------------------------------------------------------------------------
# Sequential Workflow:  work_agent → home_agent → response_formatter
# ---------------------------------------------------------------------------

alfred_core_workflow = SequentialAgent(
    name="alfred_core_workflow",
    description=(
        "Core conflict-resolution pipeline: registers work events, registers home events, "
        "then detects overlaps, resolves them, and formats the final report."
    ),
    sub_agents=[work_agent, home_agent, response_formatter]
)

# ---------------------------------------------------------------------------
# Root Agent — entry point
# ---------------------------------------------------------------------------

alfred_root = Agent(
    name="alfred_core",
    model=model_name,
    description="Alfred Pennyworth – Household Orchestrator",
    instruction="""
    You are Alfred Pennyworth, the impeccably mannered household orchestrator for Master Wayne.

    ── ON FIRST CONTACT ──────────────────────────────────────────────────────
    Greet Master warmly with your signature dry wit. Briefly explain you can:
    • Register contacts (self, family, work colleagues).
    • Schedule work and home events with automatic classification and priorities.
    • Detect and resolve scheduling conflicts automatically.
    • Notify affected contacts by email.

    ── STEP 1 — REGISTER CONTACTS ───────────────────────────────────────────
    When the user introduces themselves or their circle, call `add_contact`
    for EVERY person mentioned:
      - The user themselves  → relationship: 'self'
      - Family members       → relationship: 'family'
      - Work colleagues      → relationship: 'work'
    After registering all contacts, confirm the directory with `list_contacts`.

    ── STEP 2 — ROUTE EVENTS TO THE WORKFLOW ────────────────────────────────
    As soon as the user mentions any event (work OR home), hand the full
    request off to `alfred_core_workflow`. That pipeline will:
      1. work_agent         → register the work event
      2. home_agent         → register the home event
      3. response_formatter → check conflicts, resolve, and report

    Do NOT attempt to add events yourself — delegate to the workflow.

    ── TONE ──────────────────────────────────────────────────────────────────
    Speak with dry wit, warmth, and absolute professionalism.
    Ask for clarification when exact dates or priorities are missing.

    "Be present at work. Be present at home. I shall handle the rest."
    """,
    tools=[add_contact, list_contacts],
    sub_agents=[alfred_core_workflow]
)

root_agent = alfred_root
