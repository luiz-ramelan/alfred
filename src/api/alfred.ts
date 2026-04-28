/**
 * Alfred API layer — communicates with the Alfred ADK agent on Cloud Run.
 *
 * INTEGRATION REQUIREMENTS:
 *  1. CORS: The Cloud Run backend must allow requests from this origin.
 *     Add CORS middleware to the ADK server, or configure via Cloud Run / load-balancer headers.
 *  2. VITE_GOOGLE_OAUTH_CLIENT_ID: Add your OAuth client ID to .env so the auth flow works.
 *     e.g.  VITE_GOOGLE_OAUTH_CLIENT_ID=123456789.apps.googleusercontent.com
 *     The redirect URI (window.location.origin) must be registered in GCP Console.
 */

const RAW_ALFRED_BASE_URL =
  (import.meta as unknown as { env: Record<string, string> }).env
    .VITE_ALFRED_BASE_URL || 'https://alfred-agent-gloaqqynxq-et.a.run.app';

function normalizeHttpsUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;

  try {
    const url = new URL(trimmed);
    // Don't upgrade localhost/127.0.0.1 — local backend runs plain HTTP
    const isLocal = url.hostname === 'localhost' || url.hostname === '127.0.0.1';
    if (url.protocol === 'http:' && !isLocal) {
      url.protocol = 'https:';
    }
    return url.toString().replace(/\/$/, '');
  } catch {
    return trimmed.replace(/^http:\/\//i, 'https://').replace(/\/$/, '');
  }
}

export const ALFRED_BASE_URL = normalizeHttpsUrl(RAW_ALFRED_BASE_URL);

const APP_NAME = 'alfred_agent';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ADKRunEventPart {
  text?: string;
}

interface ADKRunEvent {
  content?: {
    role?: string;
    parts?: ADKRunEventPart[];
  };
  is_final_response?: boolean;
  author?: string;
}

// ─── Session ──────────────────────────────────────────────────────────────────

/**
 * Creates a new ADK session for the given user and stores the Google access
 * token in session state so Alfred's MCP tools can authenticate.
 *
 * @returns the session ID string
 */
export async function createAlfredSession(
  userId: string,
  accessToken: string,
  timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Bangkok'
): Promise<string> {
  const res = await fetch(
    `${ALFRED_BASE_URL}/apps/${APP_NAME}/users/${encodeURIComponent(userId).replace('%40', '@')}/sessions/`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        state: {
          ALFRED_ACCESS_TOKEN: accessToken,
          ALFRED_TIMEZONE: timezone,
        },
      }),
    }
  );

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Session creation failed (${res.status}): ${body}`);
  }

  const data = (await res.json()) as { id?: string; session_id?: string };
  const id = data.id ?? data.session_id;
  if (!id) throw new Error('Session created but no ID returned');
  return id;
}

// ─── Run ──────────────────────────────────────────────────────────────────────

/**
 * Sends a natural-language message to Alfred and returns the final text reply.
 */
export async function sendToAlfred(
  userId: string,
  sessionId: string,
  message: string,
  token?: string
): Promise<string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(
    `${ALFRED_BASE_URL}/run`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        app_name: APP_NAME,
        user_id: userId,
        session_id: sessionId,
        new_message: {
          role: 'user',
          parts: [{ text: message }],
        },
      }),
    }
  );

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Alfred run failed (${res.status}): ${body}`);
  }

  const contentType = res.headers.get('content-type') ?? '';
  if (contentType.includes('text/event-stream')) {
    const text = await res.text();
    return parseSSEFinalText(text);
  }

  const data = (await res.json()) as ADKRunEvent[];
  return extractFinalText(Array.isArray(data) ? data : []);
}

// ─── Response parsing ─────────────────────────────────────────────────────────

function parseSSEFinalText(sseText: string): string {
  const lines = sseText.split('\n');
  let lastText = '';
  for (const line of lines) {
    if (!line.startsWith('data: ')) continue;
    try {
      const ev = JSON.parse(line.slice(6)) as ADKRunEvent;
      if (ev.is_final_response && ev.content?.parts) {
        for (const part of ev.content.parts) {
          if (part.text) lastText = part.text;
        }
      }
    } catch {
      // skip malformed SSE line
    }
  }
  return lastText || FALLBACK_REPLY;
}

function extractFinalText(events: ADKRunEvent[]): string {
  // Prefer explicit final-response flag
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev.is_final_response && ev.content?.parts) {
      for (const part of ev.content.parts) {
        if (part.text) return part.text;
      }
    }
  }
  // Fallback: last model text
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev.content?.role === 'model' && ev.content.parts) {
      for (const part of ev.content.parts) {
        if (part.text) return part.text;
      }
    }
  }
  return FALLBACK_REPLY;
}

const FALLBACK_REPLY = 'I am unable to respond at this moment, sir.';

// ─── Sign-out ─────────────────────────────────────────────────────────────────

/**
 * Clears all locally-stored auth tokens. Call this when the user signs out.
 */
export function signOut(): void {
  localStorage.removeItem('alfred_token');
  localStorage.removeItem('alfred_email');
  localStorage.removeItem('alfred_session');
}

// ─── Google OAuth helpers ─────────────────────────────────────────────────────

// gmail.modify is a restricted scope that causes "Access blocked" for unverified apps.
// Gmail operations are handled server-side by the backend using its own OAuth token.
const GOOGLE_SCOPES = [
  'openid',
  'email',
  'profile',
  'https://www.googleapis.com/auth/calendar',
  'https://www.googleapis.com/auth/contacts',
].join(' ');

/**
 * Redirects to Google OAuth implicit flow. On return, `parseOAuthFragment()`
 * should be called to extract the access token from the URL hash.
 *
 * Requires VITE_GOOGLE_OAUTH_CLIENT_ID to be set in .env
 */
export function startGoogleOAuth(): void {
  const clientId = (import.meta as unknown as { env: Record<string, string> }).env
    .VITE_GOOGLE_OAUTH_CLIENT_ID;
  if (!clientId) {
    throw new Error(
      'VITE_GOOGLE_OAUTH_CLIENT_ID is not set. Add it to your .env file to enable Google sign-in.'
    );
  }
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: window.location.origin,
    response_type: 'token',
    scope: GOOGLE_SCOPES,
    prompt: 'select_account',
  });
  window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
}

/**
 * Parses the URL hash fragment for an OAuth access_token returned by Google.
 * Call this once on mount. Returns null if not an OAuth callback.
 */
export function parseOAuthFragment(): string | null {
  const hash = window.location.hash;
  if (!hash.includes('access_token')) return null;
  const params = new URLSearchParams(hash.slice(1)); // strip leading '#'
  return params.get('access_token');
}

/**
 * Fetches the authenticated user's email address from Google.
 */
export async function fetchUserEmail(accessToken: string): Promise<string> {
  const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`Failed to fetch user info: ${res.status}`);
  const data = (await res.json()) as { email?: string };
  return data.email ?? 'user@example.com';
}

// ─── User profile (email + display name) ─────────────────────────────────────

export async function fetchUserProfile(
  accessToken: string
): Promise<{ email: string; name: string }> {
  const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`Failed to fetch user info: ${res.status}`);
  const data = (await res.json()) as { email?: string; name?: string };
  return {
    email: data.email ?? 'user@example.com',
    name: data.name ?? '',
  };
}

// ─── Google Calendar ──────────────────────────────────────────────────────────

interface GCalEvent {
  id?: string;
  summary?: string;
  start: { dateTime?: string; date?: string };
  location?: string;
  description?: string;
}

export async function fetchCalendarEvents(accessToken: string): Promise<
  {
    id: string;
    title: string;
    day: string;
    time: string;
    context: 'work' | 'home';
    summary: string;
    location?: string;
    relatedContactIds: string[];
  }[]
> {
  const now = new Date();
  const weekLater = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  const params = new URLSearchParams({
    timeMin: now.toISOString(),
    timeMax: weekLater.toISOString(),
    singleEvents: 'true',
    orderBy: 'startTime',
    maxResults: '20',
  });
  const res = await fetch(
    `https://www.googleapis.com/calendar/v3/calendars/primary/events?${params}`,
    { headers: { Authorization: `Bearer ${accessToken}` } }
  );
  if (!res.ok) throw new Error(`Calendar fetch failed: ${res.status}`);
  const data = (await res.json()) as { items?: GCalEvent[] };
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  return (data.items ?? []).map((ev, i) => {
    const dt = ev.start.dateTime
      ? new Date(ev.start.dateTime)
      : ev.start.date
      ? new Date(ev.start.date)
      : new Date();
    return {
      id: ev.id ?? `ev-${i}`,
      title: ev.summary ?? 'Untitled Event',
      day: dayNames[dt.getDay()],
      time: ev.start.dateTime
        ? dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : 'All day',
      context: 'work' as 'work' | 'home',
      summary: ev.description ?? ev.summary ?? '',
      location: ev.location,
      relatedContactIds: [],
    };
  });
}

// ─── Google Contacts ──────────────────────────────────────────────────────────

interface GPeopleConnection {
  resourceName?: string;
  names?: { displayName?: string }[];
  emailAddresses?: { value?: string }[];
  organizations?: { title?: string; name?: string }[];
  biographies?: { value?: string }[];
}

export async function fetchGoogleContacts(accessToken: string): Promise<
  {
    id: string;
    name: string;
    role: string;
    context: 'work' | 'home';
    gmail?: string;
    note?: string;
  }[]
> {
  const params = new URLSearchParams({
    personFields: 'names,emailAddresses,organizations,biographies',
    pageSize: '50',
  });
  const res = await fetch(
    `https://people.googleapis.com/v1/people/me/connections?${params}`,
    { headers: { Authorization: `Bearer ${accessToken}` } }
  );
  if (!res.ok) throw new Error(`Contacts fetch failed: ${res.status}`);
  const data = (await res.json()) as { connections?: GPeopleConnection[] };
  return (data.connections ?? [])
    .map((p, i) => {
      const name = p.names?.[0]?.displayName ?? '';
      if (!name) return null;
      const org = p.organizations?.[0];
      return {
        id: p.resourceName ?? `contact-${i}`,
        name,
        role: org?.title ?? org?.name ?? 'Contact',
        context: 'work' as 'work' | 'home',
        gmail: p.emailAddresses?.[0]?.value,
        note: p.biographies?.[0]?.value,
      };
    })
    .filter((c): c is NonNullable<typeof c> => c !== null);
}
