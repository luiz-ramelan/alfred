# Alfred — Concept & Solution Documentation

> *"Be present at work. Be present at home. Alfred handles the rest."*
> *"Every Batman needs an Alfred."*

---

## 1. Brief

Alfred is a multi-agent AI butler that helps users manage family responsibilities alongside their professional life. The name is intentional — Batman's Alfred is meticulous, loyal, always one step ahead, and handles everything at home so Bruce Wayne can show up fully wherever he needs to be.

The target user is anyone who has ever rescheduled a parent's medical appointment because of a work meeting, or taken a client call during a school event. In Singapore and across Southeast and South Asia, that is most working adults. They are simultaneously a professional, a child to ageing parents, a parent to young kids, and a household coordinator — drowning in context-switching between life domains that no current tool bridges.

Alfred is not a chatbot. It is a persistent, multi-agent coordination system that holds the full picture of a household and acts on it.

---

## 2. Solution

### 2a. Approach — Translating the Problem Statement

The hackathon problem statement asks for a multi-agent AI system that manages tasks, schedules, and information across multiple tools and data sources. Alfred maps directly to this:

- **Primary agent** — Alfred Core orchestrates all intent and domain routing
- **Sub-agents** — WorkAgent, CareAgent, and HomeAgent each specialise in one life domain
- **Structured database** — Firestore stores a persistent household graph: members, priorities, work context, care context, home context
- **MCP tool integration** — Google Calendar, Tasks, Gmail, Meet, and Maps are wired as tools across agents
- **Multi-step workflows** — conflict detection, resolution proposals, confirmation, and execution span multiple agents and tools in sequence
- **API-based deployment** — Cloud Run exposes Alfred's backend as a REST API; Vertex AI Agent Builder hosts the agent runtime

The cultural insight driving the design: in Southeast and South Asian households, the boundary between work and family does not exist cleanly. Alfred is built for that reality — cross-domain conflict resolution is the core mechanic, not a feature.

### 2b. Real-World Problem & Practical Impact

Alfred solves the daily context-switching tax paid by high-functioning adults who carry both professional and caregiving responsibilities simultaneously.

Practical impact:

- A working parent no longer needs to manually check five calendars before rescheduling a family appointment
- A sandwich generation adult caring for both children and ageing parents gets a single system that holds all their context
- A household with a domestic helper gets structured task delegation without micromanagement
- Cross-domain conflicts — the most stressful kind — are surfaced proactively before they become crises

### 2c. Core Workflow

```
User sends a message (natural language)
        │
        ▼
Alfred Core classifies intent
→ work / care / home / hybrid (conflict)
        │
        ├── WorkAgent: meetings, tasks, emails, documents
        ├── CareAgent: appointments, medications, telehealth, travel time
        └── HomeAgent: helper tasks, school calendar, household admin
        │
        ▼
Agents query MCP tools (Calendar, Tasks, Gmail, Maps)
        │
        ▼
Alfred Core checks for cross-domain conflicts
→ if conflict: proposes resolution, requests confirmation
→ if no conflict: executes directly
        │
        ▼
Actions executed, logged to Firestore
User receives confirmation
```

**Example — the demo workflow:**

> User: "Dad's physio clashes with my board presentation Thursday."

1. WorkAgent pulls board presentation → Thursday 10am
2. CareAgent pulls physio → Thursday 10am, Mt Elizabeth
3. Alfred Core detects conflict, checks both calendars for alternatives
4. Alfred: "I'll move Dad's physio to Friday 9am and notify the helper. Want me to draft the clinic reschedule email too?"
5. User confirms → CareAgent updates Calendar, HomeAgent creates helper task, Gmail draft created
6. All actions logged to Firestore with timestamp and agent actor

---

## 3. Opportunities — Differentiation & USP

### What Exists Today

Notion AI, Motion, Reclaim.ai — AI scheduling within work domain only. Google Duet AI — integrates across Google Workspace but single-user, work-focused. Carely, CareZone — caregiver apps, no professional life integration. SuperHuman — email triage only.

### Where Alfred Is Different

| Dimension | Existing Tools | Alfred |
|---|---|---|
| Domain scope | Work OR family, rarely both | Work AND family as one unified system |
| Unit of use | Individual user | Household graph — multiple members, roles, dependencies |
| Core mechanic | Scheduling and reminders | Cross-domain conflict resolution |
| Cultural fit | Built for Western single-user professionals | Built for SEA/SA multigenerational households |
| Domestic layer | Not modelled | First-class: helper tasks, school coordination, care delegation |

### Unique Selling Point

Alfred is the only system where the primary design challenge is *the collision point* between a user's professional and family responsibilities — not optimising either one in isolation.

The household is the unit, not the individual. Family context is persistent. Priority logic is user-defined and culturally aware. And it works via WhatsApp and web — no new app to learn.

---

## 4. Features

**Household Setup**
Users define household members (spouse, children, parents, helpers), their roles, and their recurring needs. This context persists across all sessions and agent interactions.

**Unified Calendar View**
Alfred surfaces a cross-domain daily digest — work commitments and family commitments in one view, with conflict indicators highlighted.

**Natural Language Commands**
Users interact in plain language — including Singlish, Bahasa, and code-switching. Alfred parses intent, identifies the relevant domain, and routes to the correct agent.

**Cross-Domain Conflict Detection**
Alfred Core continuously checks for scheduling and priority conflicts across work and family domains and surfaces them proactively before they escalate.

**Conflict Resolution Proposals**
When a conflict is detected, Alfred proposes a resolution (not just an alert), explains its reasoning, and requests user confirmation before executing.

**Agent-Executed Actions**
Confirmed actions are executed directly: calendar updates, task creation, email drafts, helper reminders — no manual follow-through required.

**Audit Trail**
Every agent action is logged in Firestore with domain tag, timestamp, and which agent acted. Users can review what Alfred did and why.

**Priority Configuration**
Users define what always wins when there is no clean resolution. Grandma's chemo outranks a supplier call — Alfred needs to know that once, and remembers it.

---

## 5. Process Flow & Use Case

### Primary Use Case — Conflict Resolution

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER                                    │
│  "Dad's physio clashes with my board presentation Thursday"     │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ALFRED CORE                                   │
│  1. Classify: hybrid conflict (Work + Care)                     │
│  2. Delegate to WorkAgent + CareAgent in parallel               │
└──────────┬──────────────────────────┬───────────────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────┐        ┌──────────────────────┐
│   WORKAGENT      │        │     CAREAGENT         │
│  Query Calendar  │        │  Query Calendar       │
│  → Thu 10am      │        │  → Thu 10am physio    │
│  board meeting   │        │  Query Maps (travel)  │
└──────────┬───────┘        └────────────┬──────────┘
           │                             │
           └──────────┬──────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ALFRED CORE                                   │
│  Conflict confirmed. Check alternative slots.                   │
│  Friday 9am clear on both calendars.                            │
│  Propose: move physio to Friday 9am                             │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
                   USER CONFIRMS
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
┌──────────────────┐   ┌──────────────────────┐
│   CAREAGENT      │   │     HOMEAGENT         │
│  Update Calendar │   │  Create helper task   │
│  Draft clinic    │   │  "Accompany Dad, Fri  │
│  reschedule mail │   │  9am, Mt Elizabeth"   │
└──────────────────┘   └──────────────────────┘
           │                     │
           └──────────┬──────────┘
                      │
                      ▼
              LOG TO FIRESTORE
              Notify user: done
```

### Secondary Use Cases

- Medication reminder cascade: CareAgent creates recurring Task, HomeAgent notifies helper, alerts user if helper confirms
- School event blocking: HomeAgent reads school calendar invite, creates Calendar block, flags to WorkAgent to protect
- Supplier email triage: WorkAgent summarises Gmail thread, surfaces action items as Tasks, proposes reply draft

---

## 6. Wireframe — Screen Map

```
┌─────────────────────┐    ┌─────────────────────┐
│  HOME DASHBOARD     │    │  ALFRED CHAT         │
│                     │    │                     │
│  Good morning.      │    │  ┌─────────────────┐│
│  Here's today.      │    │  │ A  Alfred        ││
│                     │    │  │ "Dad's physio    ││
│  [WORK]             │    │  │  moved to Fri.   ││
│  ▸ Board meeting    │    │  │  Helper notified"││
│    Thu 10am         │    │  └─────────────────┘│
│  ▸ Supplier call    │    │                     │
│    Thu 3pm          │    │  ┌─────────────────┐│
│                     │    │  │ You              ││
│  [FAMILY]           │    │  │ "Also remind me  ││
│  ▸ Dad physio ⚠️    │    │  │  to call clinic" ││
│    Thu 10am CLASH   │    │  └─────────────────┘│
│  ▸ School concert   │    │                     │
│    Fri 6pm          │    │  [ Tell Alfred... ] │
│                     │    │                     │
│  [ Tell Alfred... ] │    └─────────────────────┘
└─────────────────────┘

┌─────────────────────┐    ┌─────────────────────┐
│  FAMILY             │    │  ALERTS              │
│                     │    │                     │
│  ┌─────────────┐    │    │  ⚠️ CONFLICT         │
│  │ Dad         │    │    │  Board meeting &     │
│  │ Parent      │    │    │  Dad's physio both   │
│  │ Physio Thu  │    │    │  Thursday 10am.      │
│  └─────────────┘    │    │  [Resolve] [Later]  │
│  ┌─────────────┐    │    │                     │
│  │ Mei Ling    │    │    │  ─────────────────  │
│  │ Child       │    │    │  Alfred actions log │
│  │ Concert Fri │    │    │                     │
│  └─────────────┘    │    │  ✓ Physio moved     │
│  ┌─────────────┐    │    │    Fri 9am          │
│  │ Siti        │    │    │  ✓ Helper task set  │
│  │ Helper      │    │    │  ✓ Clinic email     │
│  │ On duty     │    │    │    drafted          │
│  └─────────────┘    │    │                     │
│                     │    │                     │
│  [+ Add member]     │    │                     │
└─────────────────────┘    └─────────────────────┘

Bottom tab navigation: Home · Chat · Family · Alerts
```

---

## 7. Architecture Diagram

```
┌───────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                           │
│         React + Vite (Firebase Hosting)                       │
│         WhatsApp Business API webhook                         │
└───────────────────────────────┬───────────────────────────────┘
                                │ HTTPS
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                       API GATEWAY                             │
│                    Apigee / Cloud Endpoints                   │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                     BACKEND — Cloud Run                       │
│                    Node.js / Express API                      │
│                                                               │
│  POST /chat → routes to Vertex AI                             │
│  POST /action → executes confirmed agent actions              │
│  GET  /household → returns household context                  │
└──────────────┬─────────────────────────────┬──────────────────┘
               │                             │
               ▼                             ▼
┌──────────────────────────┐   ┌─────────────────────────────┐
│   VERTEX AI AGENT BUILDER│   │        FIRESTORE            │
│                          │   │                             │
│  ┌────────────────────┐  │   │  /households/{id}           │
│  │   ALFRED CORE      │  │   │    /members                 │
│  │   Orchestrator     │  │   │    /priorities              │
│  │   Gemini 2.0 Flash │  │   │    /workContext             │
│  └──────┬─────────────┘  │   │    /careContext             │
│         │                │   │    /homeContext             │
│    ┌────┴────┐            │   │    /events                 │
│    ▼    ▼    ▼            │   │    /agentActions            │
│  Work Care Home           │   │                             │
│  Agent Agent Agent        │   └─────────────────────────────┘
└──────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────────────────┐
│                     MCP TOOL LAYER                            │
│                                                               │
│   Google Calendar API    Google Tasks API                     │
│   Gmail API              Google Meet API                      │
│   Google Maps API                                             │
└───────────────────────────────────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────────────────┐
│                   ASYNC / EVENTS                              │
│                   Cloud Pub/Sub                               │
│   (agent-to-agent messaging, delayed task execution)          │
└───────────────────────────────────────────────────────────────┘
```

---

## 8. Tech & Google Services

| Layer | Service | Why |
|---|---|---|
| AI / Agent runtime | Vertex AI Agent Builder + Gemini 2.0 Flash | Native multi-agent orchestration, MCP support, Gemini's multilingual strength for SEA context |
| Backend API | Cloud Run | Serverless, auto-scaling, container-based — fast to deploy under hackathon conditions, scales to real usage |
| Database | Cloud Firestore | Document model fits the household graph naturally; real-time listeners enable live UI updates |
| Frontend hosting | Firebase Hosting | One-command deploy, CDN-backed, pairs natively with Firestore and Firebase Auth |
| Auth | Firebase Auth | Google Sign-In out of the box, no auth infrastructure to build |
| Async messaging | Cloud Pub/Sub | Decouples agent-to-agent communication; enables delayed and scheduled task execution without blocking the API |
| API gateway | Apigee | Rate limiting, API key management, usage monitoring — needed for real-world deployment |
| MCP tools | Google Calendar, Tasks, Gmail, Meet, Maps APIs | All natively available on Google Cloud; Alfred's core value is in how it coordinates these, not replacing them |

### Why This Stack Supports Scale

Vertex AI Agent Builder abstracts agent orchestration — adding a new sub-agent (e.g. a FinanceAgent for household budgeting) requires no infrastructure change. Cloud Run scales to zero when idle and horizontally under load — the same backend serves 10 users or 10,000. Firestore's document model scales without schema migrations. Firebase Auth supports household-level multi-user access without custom session management.

For production: AlloyDB AI replaces Firestore for relational household data with vector search for semantic memory retrieval — "what did Alfred do last time Dad missed a physio?" Alfred's agent memory becomes queryable context.

---

## 9. Snapshot — What to Include in Submission

| Item | What to Show |
|---|---|
| **Live demo** | The conflict resolution workflow end-to-end: user types one message, Alfred detects conflict, proposes resolution, user confirms, actions execute across Calendar and Tasks |
| **Architecture diagram** | Section 7 above — render as a clean visual, not a code block |
| **Agent audit log** | Firestore console showing `agentActions` collection with timestamped entries — proves multi-agent coordination actually happened |
| **UI walkthrough** | All 4 screens: Home Dashboard, Alfred Chat, Family, Alerts — show a real household with real members |
| **Code structure** | Repo showing clear separation: `/alfred-backend` (Cloud Run), `/alfred-app` (React), agent routing logic in `server.js` |
| **Cultural hook** | In the pitch: name the user (Wei Ling, Priya, Ravi — real names from the region), describe the specific moment of stress the product resolves |
| **What Alfred actually did** | Screenshot or live view of Firestore showing the action log after the demo — the receipts |

---

*Alfred — built for the Google x Hack2skill Hackathon. Multi-agent AI on Google Cloud. For everyone who wants to show up fully at work without losing their family.*