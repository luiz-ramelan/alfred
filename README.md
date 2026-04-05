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
