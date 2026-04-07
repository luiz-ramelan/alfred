import functools
import logging
import os
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from datetime import timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import google.cloud.logging
import requests
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents import SequentialAgent
from google.adk.auth.auth_credential import (
    AuthCredential,
    AuthCredentialTypes,
    OAuth2Auth,
)
from google.adk.auth.auth_schemes import OpenIdConnectWithConfig
from google.adk.auth.credential_service.base_credential_service import (
    BaseCredentialService,
)
from google.adk.tools.mcp_tool.mcp_tool import MCPTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)
from google.adk.tools.tool_context import ToolContext
from google.cloud import firestore

from mcp_google_client import MCPGoogleClient

# --- Per-Request Authentication Context ---
# This ensures that each user has their own isolated session and token.
token_context: ContextVar[str] = ContextVar("token_context", default="")
refresh_token_context: ContextVar[str] = ContextVar(
    "refresh_token_context", default=""
)
SESSION_ACCESS_TOKEN_KEY = "ALFRED_ACCESS_TOKEN"
SESSION_REFRESH_TOKEN_KEY = "ALFRED_REFRESH_TOKEN"
SESSION_TOKEN_EXPIRES_AT_KEY = "ALFRED_TOKEN_EXPIRES_AT"
SESSION_TIMEZONE_KEY = "ALFRED_TIMEZONE"
SESSION_LOCALE_KEY = "ALFRED_LOCALE"
SESSION_TOKEN_STORE: dict[str, dict[str, Any]] = {}
GENERIC_CALENDAR_QUERY_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "calendar",
    "check",
    "events",
    "event",
    "for",
    "from",
    "in",
    "is",
    "my",
    "next",
    "of",
    "on",
    "please",
    "professional",
    "schedule",
    "schedules",
    "show",
    "the",
    "this",
    "time",
    "today",
    "tomorrow",
    "upcoming",
    "week",
    "what",
    "work",
    "workevents",
    "working",
    "your",
    "with",
    "1",
    "one",
    "2",
    "2nd",
    "3",
    "3rd",
    "7",
    "7th",
    "days",
    "day",
    "week",
}


def _token_store_key(app_name: str, user_id: str) -> str:
    return f"{app_name}:{user_id}"


load_dotenv()

# --- Lazy GCP Client Initialization ---
# These MUST be lazy to prevent blocking the server startup during import.
# Cloud Run health checks fail when module-level network calls hang.
_db = None
_cloud_logging_initialized = False


def get_db():
    """Returns a Firestore client, initializing lazily on first use."""
    global _db
    if _db is None:
        try:
            _db = firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "alfred-492407"))
        except Exception as e:
            logging.warning(f"[Firestore] Could not initialize client: {e}")
    return _db


def setup_cloud_logging():
    """Configures Cloud Logging lazily on first use."""
    global _cloud_logging_initialized
    if not _cloud_logging_initialized:
        try:
            client = google.cloud.logging.Client()
            client.setup_logging()
            _cloud_logging_initialized = True
        except Exception as e:
            logging.warning(f"[Logging] Could not initialize Cloud Logging: {e}")


# Get today's date for temporal context
now = datetime.now()
today_str = now.strftime("%A, %B %d, %Y")
raw_tz = time.strftime("%z")
tz_str = f"{raw_tz[:3]}:{raw_tz[3:]}"  # Convert +0700 to +07:00

model_name = os.getenv("MODEL")
MCP_URL = os.getenv("MCP_URL", "").strip('"\'')
ACCESS_TOKEN = os.getenv("GOOGLE_ACCESS_TOKEN", "").strip('"\'')
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip('"\'')
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip('"\'')
GOOGLE_OAUTH_REDIRECT_URI = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI",
    "http://localhost:8080/auth/callback",
).strip('"\'')

WORKSPACE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
WORKSPACE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
WORKSPACE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/contacts",
]

logging.info(f"[Config] MCP_URL: {MCP_URL}")
if ACCESS_TOKEN:
    logging.info(f"[Config] Local GOOGLE_ACCESS_TOKEN found (len: {len(ACCESS_TOKEN)})")


@functools.lru_cache(maxsize=128)
def get_user_email(token: str) -> str:
    """Fetches the user's email from Google to use as a unique ID."""
    if not token:
        token = token_context.get()
        if not token:
            token = os.getenv("GOOGLE_ACCESS_TOKEN", "")

    if not token:
        return "anonymous_household"

    try:
        response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json().get("email", "anonymous_household")
    except Exception as e:
        logging.warning(f"[Identity] Failed to fetch user info: {e}")
    return "anonymous_household"


def _normalize_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _should_apply_calendar_query(person: str) -> bool:
    text = " ".join(str(person or "").lower().split())
    if not text:
        return False

    tokens = [token for token in text.replace("-", " ").split() if token]
    if not tokens:
        return False

    return any(
        token not in GENERIC_CALENDAR_QUERY_WORDS and not token.isdigit()
        for token in tokens
    )


def _extract_calendar_items(payload: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            summary = str(value.get("summary") or value.get("title") or "").strip()
            start = value.get("start")
            end = value.get("end")
            description = str(value.get("description") or "").strip()
            if summary and (start is not None or end is not None):
                items.append(value)
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(payload)
    return items


def _calendar_event_label(event: dict[str, Any]) -> str:
    title = str(event.get("summary") or event.get("title") or "Untitled event").strip()
    description = str(event.get("description") or "").strip()

    start_value = event.get("start")
    end_value = event.get("end")

    def _extract_time(value: Any) -> str:
        if isinstance(value, dict):
            return str(
                value.get("dateTime")
                or value.get("date")
                or value.get("time")
                or ""
            ).strip()
        return str(value or "").strip()

    start_text = _extract_time(start_value)
    end_text = _extract_time(end_value)

    time_text = ""
    if start_text and end_text:
        time_text = f"{start_text} to {end_text}"
    elif start_text:
        time_text = start_text

    label = title
    if time_text:
        label = f"{label} ({time_text})"
    if description:
        label = f'{label} - {description}'
    return label


def _get_token_record(
    app_name: str = "",
    user_id: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    record: dict[str, Any] = {}
    if app_name and user_id:
        record = SESSION_TOKEN_STORE.get(_token_store_key(app_name, user_id), {})
    if not record and session_id:
        record = SESSION_TOKEN_STORE.get(session_id, {})
    return record


def _resolve_timezone_name(tool_context: ToolContext) -> str:
    invocation_context = getattr(tool_context, "_invocation_context", None)
    session = getattr(invocation_context, "session", None) if invocation_context else None
    if session is not None:
        session_state = getattr(session, "state", {}) or {}
        timezone_name = str(session_state.get(SESSION_TIMEZONE_KEY, "")).strip()
        if timezone_name:
            return timezone_name

    try:
        state_timezone = str(tool_context.state.get(SESSION_TIMEZONE_KEY, "")).strip()
        if state_timezone:
            return state_timezone
    except Exception:
        pass

    return os.getenv("TIMEZONE", "Asia/Bangkok")


def _resolve_access_token(tool_context: ToolContext) -> str:
    invocation_context = getattr(tool_context, "_invocation_context", None)
    session = getattr(invocation_context, "session", None) if invocation_context else None
    session_id = getattr(session, "id", "") if session is not None else ""
    app_name = getattr(invocation_context, "app_name", "") if invocation_context else ""
    user_id = getattr(invocation_context, "user_id", "") if invocation_context else ""

    record = _get_token_record(app_name, user_id, session_id)
    access_token = str(record.get(SESSION_ACCESS_TOKEN_KEY, "")).strip()
    if access_token:
        return access_token

    try:
        state_token = str(tool_context.state.get(SESSION_ACCESS_TOKEN_KEY, "")).strip()
        if state_token:
            return state_token
    except Exception:
        pass

    state_token = token_context.get().strip()
    if state_token:
        return state_token

    return ACCESS_TOKEN


def _build_oauth_credential(
    access_token: str,
    refresh_token: str = "",
    expires_at: Optional[int] = None,
) -> AuthCredential:
    return AuthCredential(
        auth_type=AuthCredentialTypes.OAUTH2,
        oauth2=OAuth2Auth(
            client_id=GOOGLE_OAUTH_CLIENT_ID or None,
            client_secret=GOOGLE_OAUTH_CLIENT_SECRET or None,
            redirect_uri=GOOGLE_OAUTH_REDIRECT_URI or None,
            access_token=access_token or None,
            refresh_token=refresh_token or None,
            expires_at=expires_at,
        ),
    )


class SessionAwareCredentialService(BaseCredentialService):
    """Credential service that resolves Google credentials from Alfred sessions."""

    async def load_credential(self, auth_config, callback_context):
        invocation_context = getattr(callback_context, "_invocation_context", None)
        app_name = getattr(invocation_context, "app_name", "") if invocation_context else ""
        user_id = getattr(invocation_context, "user_id", "") if invocation_context else ""
        session = getattr(invocation_context, "session", None) if invocation_context else None
        session_id = getattr(session, "id", "") if session is not None else ""

        record = _get_token_record(app_name, user_id, session_id)
        if not record:
            return None

        access_token = str(record.get(SESSION_ACCESS_TOKEN_KEY, "")).strip()
        if not access_token:
            return None

        refresh_token = str(record.get(SESSION_REFRESH_TOKEN_KEY, "")).strip()
        expires_at = _normalize_int(record.get(SESSION_TOKEN_EXPIRES_AT_KEY))

        logging.info(
            "[CredentialService] Loaded token for app=%s user=%s session=%s",
            app_name or "<missing>",
            user_id or "<missing>",
            session_id or "<missing>",
        )
        return _build_oauth_credential(access_token, refresh_token, expires_at)

    async def save_credential(self, auth_config, callback_context) -> None:
        invocation_context = getattr(callback_context, "_invocation_context", None)
        app_name = getattr(invocation_context, "app_name", "") if invocation_context else ""
        user_id = getattr(invocation_context, "user_id", "") if invocation_context else ""
        session = getattr(invocation_context, "session", None) if invocation_context else None
        session_id = getattr(session, "id", "") if session is not None else ""

        credential = getattr(auth_config, "exchanged_auth_credential", None)
        if not credential or not credential.oauth2:
            return

        access_token = str(credential.oauth2.access_token or "").strip()
        if not access_token:
            return

        refresh_token = str(credential.oauth2.refresh_token or "").strip()
        expires_at = _normalize_int(credential.oauth2.expires_at)
        store_session_tokens(
            app_name=app_name,
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            session_id=session_id,
            expires_at=expires_at,
        )
        logging.info(
            "[CredentialService] Saved refreshed token for app=%s user=%s session=%s",
            app_name or "<missing>",
            user_id or "<missing>",
            session_id or "<missing>",
        )


class SessionAwareMcpToolset(McpToolset):
    """McpToolset variant that uses the current session token during discovery."""

    def _resolve_headers_from_context(self, readonly_context: Any) -> Optional[dict[str, str]]:
        invocation_context = getattr(readonly_context, "_invocation_context", None)
        if invocation_context is None:
            return None

        session = getattr(invocation_context, "session", None)
        session_id = getattr(session, "id", "") if session is not None else ""
        app_name = getattr(invocation_context, "app_name", "")
        user_id = getattr(invocation_context, "user_id", "")
        record = _get_token_record(app_name, user_id, session_id)
        access_token = str(record.get(SESSION_ACCESS_TOKEN_KEY, "")).strip()
        if not access_token:
            return None
        logging.info(
            "[MCP] Resolving discovery headers for app=%s user=%s session=%s",
            app_name or "<missing>",
            user_id or "<missing>",
            session_id or "<missing>",
        )
        return {"Authorization": f"Bearer {access_token}"}

    async def get_tools(self, readonly_context=None):
        headers = self._resolve_headers_from_context(readonly_context)
        session = await self._mcp_session_manager.create_session(headers=headers)
        tools_response = await session.list_tools()
        tools = []
        for tool in tools_response.tools:
            mcp_tool = MCPTool(
                mcp_tool=tool,
                mcp_session_manager=self._mcp_session_manager,
                auth_scheme=self._auth_scheme,
                auth_credential=self._auth_credential,
            )

            if self._is_tool_selected(mcp_tool, readonly_context):
                tools.append(mcp_tool)
        return tools


def _build_workspace_toolset() -> Optional[SessionAwareMcpToolset]:
    if not MCP_URL:
        logging.warning("[Config] MCP_URL is not configured.")
        return None

    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        logging.warning(
            "[Config] Google OAuth client credentials are missing; MCP auth may fail."
        )

    auth_scheme = OpenIdConnectWithConfig(
        authorization_endpoint=WORKSPACE_AUTHORIZATION_ENDPOINT,
        token_endpoint=WORKSPACE_TOKEN_ENDPOINT,
        scopes=WORKSPACE_SCOPES,
    )
    raw_auth_credential = _build_oauth_credential("")

    return SessionAwareMcpToolset(
        connection_params=StreamableHTTPConnectionParams(url=MCP_URL),
        tool_filter=lambda tool, _: "modify_gmail_message_labels" not in tool.name,
        auth_scheme=auth_scheme,
        auth_credential=raw_auth_credential,
    )


workspace_toolset = _build_workspace_toolset()
WORKSPACE_TOOLS = [workspace_toolset] if workspace_toolset is not None else []


def store_session_tokens(
    app_name: str,
    user_id: str,
    access_token: str,
    refresh_token: str = "",
    session_id: str = "",
    expires_at: Optional[int] = None,
    timezone_name: str = "",
    locale_name: str = "",
) -> None:
    if not app_name or not user_id or not access_token:
        return

    store_key = _token_store_key(app_name, user_id)
    existing = SESSION_TOKEN_STORE.get(store_key, {})
    resolved_refresh_token = refresh_token or str(
        existing.get(SESSION_REFRESH_TOKEN_KEY, "")
    ).strip()
    resolved_expires_at = expires_at
    if resolved_expires_at is None:
        resolved_expires_at = _normalize_int(
            existing.get(SESSION_TOKEN_EXPIRES_AT_KEY)
        )

    payload: dict[str, Any] = {
        SESSION_ACCESS_TOKEN_KEY: access_token,
        SESSION_REFRESH_TOKEN_KEY: resolved_refresh_token,
    }
    if resolved_expires_at is not None:
        payload[SESSION_TOKEN_EXPIRES_AT_KEY] = resolved_expires_at
    if timezone_name:
        payload[SESSION_TIMEZONE_KEY] = timezone_name
    if locale_name:
        payload[SESSION_LOCALE_KEY] = locale_name

    SESSION_TOKEN_STORE[store_key] = payload
    if session_id:
        SESSION_TOKEN_STORE[session_id] = dict(payload)


async def calendar_activity_summary(
    tool_context: ToolContext,
    person: str = "",
    days_ahead: int = 7,
) -> dict:
    """Summarize calendar activity over the next N days."""
    setup_cloud_logging()
    if not MCP_URL:
        return {"status": "error", "message": "MCP_URL is not configured."}

    token = _resolve_access_token(tool_context)
    if not token:
        return {"status": "error", "message": "No Google access token is available."}

    timezone_name = _resolve_timezone_name(tool_context)
    try:
        tzinfo = ZoneInfo(timezone_name)
    except Exception:
        tzinfo = ZoneInfo(os.getenv("TIMEZONE", "Asia/Bangkok"))
        timezone_name = getattr(tzinfo, "key", timezone_name)

    now = datetime.now(tzinfo)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=max(days_ahead, 1))).isoformat()

    arguments: dict[str, Any] = {
        "time_min": time_min,
        "time_max": time_max,
        "detailed": True,
    }
    if _should_apply_calendar_query(person):
        arguments["query"] = person.strip()

    client = MCPGoogleClient(MCP_URL, token)
    try:
        result = await client.call_tool("get_events", arguments)
        items = _extract_calendar_items(result)
        event_lines = [_calendar_event_label(item) for item in items]
        if event_lines:
            if person.strip():
                summary_text = (
                    f"I found {len(event_lines)} calendar event(s) matching '{person.strip()}' "
                    f"in the next {days_ahead} day(s): "
                    + "; ".join(event_lines)
                )
            else:
                summary_text = (
                    f"I found {len(event_lines)} calendar event(s) in the next {days_ahead} day(s): "
                    + "; ".join(event_lines)
                )
        else:
            if person.strip():
                summary_text = (
                    f"I found no calendar events matching '{person.strip()}' in the next {days_ahead} day(s)."
                )
            else:
                summary_text = f"I found no calendar events in the next {days_ahead} day(s)."
        return {
            "status": "ok",
            "query": person.strip(),
            "timezone": timezone_name,
            "time_min": time_min,
            "time_max": time_max,
            "count": len(items),
            "summary": summary_text,
            "result": result,
        }
    except Exception as e:
        logging.exception("[MCP] Failed to summarize calendar activity")
        return {
            "status": "error",
            "message": str(e),
            "query": person,
        }
    finally:
        await client.close()


# --- Initialize State ---
# Pre-populating to prevent 'Context variable not found' errors
initial_state = {
    "CURRENT_INTENT": "None",
    SESSION_TIMEZONE_KEY: os.getenv("TIMEZONE", "Asia/Bangkok"),
}


# --- Alfred's Specialized Tools ---

def assess_household_conflicts(tool_context: ToolContext, intent: str) -> dict:
    """Analyzes for overlaps between work (Calendar) and household (Firestore) domains."""
    setup_cloud_logging()
    logging.info(f"[Alfred Core] Analyzing intent: {intent}")

    analysis_results = []
    email = get_user_email(token_context.get())
    db = get_db()

    # 1. Read per-user household rules from Firestore
    try:
        if db is None:
            return {"status": "Error", "findings": ["Firestore unavailable."], "advice": ""}
        user_ref = db.collection("users").document(email).collection("household").document("profile")
        household = user_ref.get()
        if household.exists:
            data = household.to_dict()
            rules = data.get("rules", [])
            analysis_results.append(f"Loaded {len(rules)} family rules for {email}.")

            # Simple keyword-based conflict check
            for rule in rules:
                if rule["name"].lower() in intent.lower():
                    analysis_results.append(
                        f"ALERT: Intent matches mandatory rule '{rule['name']}' at {rule['time']}."
                    )
        else:
            analysis_results.append(
                f"No profile found for {email}. Using default butler discretion."
            )
    except Exception as e:
        logging.warning(f"[Firestore] Could not load user household: {e}")
        analysis_results.append("Error accessing Household rules.")

    return {
        "status": "Conflict analysis complete.",
        "findings": analysis_results,
        "advice": "Please cross-reference with the workspace tools to ensure no professional overlaps.",
    }


def update_household_ledger(
    tool_context: ToolContext,
    action: str,
    item: str | None = None,
) -> dict:
    """Manages the persistent Household Ledger (Shopping List, Chores, Audit Trail)."""
    setup_cloud_logging()
    email = get_user_email(token_context.get())
    logging.info(f"[Ledger] Performing: {action} on {item} for Master: {email}")
    db = get_db()

    try:
        if db is None:
            return {"status": "Ledger unavailable: Firestore not connected."}
        user_ref = db.collection("users").document(email).collection("household").document("profile")

        if "add" in action.lower() and "list" in action.lower() and item:
            user_ref.set(
                {
                    "shopping_list": firestore.ArrayUnion([item]),
                    "last_updated": datetime.now(timezone.utc),
                },
                merge=True,
            )
            return {"status": f"Added '{item}' to the Household Shopping List for {email}."}

        # Audit trail per user
        db.collection("users").document(email).collection("audit").add(
            {
                "action": action,
                "item": item,
                "agent": tool_context.agent_name if hasattr(tool_context, "agent_name") else "unknown",
                "timestamp": datetime.now(timezone.utc),
            }
        )
        return {"status": f"Action logged to {email}'s Audit Trail."}
    except Exception as e:
        logging.error(f"[Ledger Error] {e}")
        return {"status": f"Ledger error: {str(e)}"}


# --- Agent Definitions ---

# 1. The Work Agent (Professional Obligations)
# Has full Google Workspace access (Calendar, Contacts, Gmail, etc.) via MCP.
work_agent = Agent(
    name="work_agent",
    model=model_name,
    description="Manages meetings, emails, contacts, and professional documents.",
    instruction=f"""
    You are Alfred's professional attache. Your focus is Master Wayne's professional life.
    TODAY'S DATE is {today_str}. TIMEZONE is {tz_str}.
    Prefer the timezone in session state under `{SESSION_TIMEZONE_KEY}` when present.

    - Use the Google Workspace MCP tools for Calendar, Contacts, and Email CRUD.
    - For calendar summaries, use `calendar_activity_summary` instead of inventing date math or code.
    - Example: for "Robin next 1 week", call `calendar_activity_summary(person="Robin", days_ahead=7)`.
    - Example: for "What are the work events in the next 1 week?", call `calendar_activity_summary(days_ahead=7)`.
    - Never write Python, import modules, or invent helper code in your response.
    - When needed, inspect the available Workspace tools first and then call the correct tool by name.
    - Strictly only return events that are professional (meetings, syncs, deadlines).
    - SPECIAL PROJECTS: Mentions of Gotham, Batman, or high-stakes 'midnight' meetings are to be treated as top-secret high-priority work.
    - MIDNIGHT LOGIC: If the Master asks for 'midnight' and it is currently late in the day (after 6 PM), assume he means the midnight that starts TOMORROW.
    - MANUALLY CALCULATE the date range for any relative terms.
    - IGNORE: Birthdays, Zumba, and simple family errands.
    """,
    tools=[calendar_activity_summary, *WORKSPACE_TOOLS],
    output_key="work_context",
)


# 2. The Home Agent (Domestic Coordination)
home_agent = Agent(
    name="home_agent",
    model=model_name,
    description="Coordinates for family events, home maintenance, and deliveries.",
    instruction="""
    You manage the family domain and home coordination.
    - Track grocery lists, errands, and family appointments.
    - When a household or family need is mentioned, use the workspace tools for Calendar, Contacts, and Email as needed.
    - If the current task is purely professional (work meetings, emails), simply observe and provide context if asked.
    - Maintain the Alfred persona: helpful, efficient, and deeply loyal to the household's well-being.
    """,
    tools=[update_household_ledger, *WORKSPACE_TOOLS],
    output_key="home_context",
)


output_formatter = Agent(
    name="output_formatter",
    model=model_name,
    description="Final response formatter for Alfred's voice.",
    instruction=f"""
    You are Alfred Pennyworth (Batman's butler).
    TODAY'S DATE: {today_str}

    Your task is to take the specialist result and provide a single, unified summary for the Master.

    - Be dry, witty, and impeccable.
    - If a conflict between work and home was detected, explain which event took precedence and why.
    - If there was no conflict, simply provide a polished summary of the requested information.
    - Mention any actions taken, such as emails sent or entries made.
    - Preserve important names, dates, times, and counts exactly.
    - Do not add new facts.
    - Do not mention internal tools, callbacks, or agents.
    - Maintain the persona. No bullet-point walls.
    """,
)


work_flow = SequentialAgent(
    name="work_flow",
    description="Runs the work specialist and then the output formatter.",
    sub_agents=[work_agent, output_formatter],
)

home_output_formatter = output_formatter.clone(update={"name": "home_output_formatter"})

home_flow = SequentialAgent(
    name="home_flow",
    description="Runs the home specialist and then the output formatter.",
    sub_agents=[home_agent, home_output_formatter],
)


# --- The Orchestration Layer ---

alfred_root = Agent(
    name="alfred_core",
    model=model_name,
    description="Alfred Pennyworth - Household Orchestrator",
    instruction=f"""
    You are Alfred Pennyworth, butler to the Wayne family.
    TODAY'S DATE: {today_str} | TIMEZONE: {tz_str}
    Prefer the timezone in session state under `{SESSION_TIMEZONE_KEY}` when present.

    Your primary duty is to ensure Master can fulfill his professional duties,
    including all Google Workspace work, while not neglecting his family responsibilities.

    ROUTING RULES:
    1. If the request is primarily professional, delegate only to work_agent.
    2. If the request is primarily household/domestic, delegate only to home_agent.
    3. If the request genuinely spans both domains, delegate to the specialist that owns the dominant part first, then only involve the other if necessary.
    4. Do not invoke both specialists for a single-domain request.
    5. Do not answer the user directly; delegate to the correct workflow and let the formatter deliver the final reply.

    "Be present at work. Be present at home. I shall handle the rest."
    """,
    tools=[assess_household_conflicts],
    sub_agents=[work_flow, home_flow],
)

root_agent = alfred_root
