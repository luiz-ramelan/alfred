# 🦇 Alfred: The Wayne Household Assistant

Welcome to the team. You are now a part of the Alfred project—a specialized AI agent designed to manage both professional duties and "Special Gotham Projects" (Special Ops/Superhero tasks) for Master Bruce.

This guide will take you from a fresh computer to a fully running Alfred Agent.

---

## 🛠️ Step 1: The Utility Belt (Software Setup)

If you have nothing installed, follow these steps in order:

1. **Install Python**: [Download Python 3.12](https://www.python.org/downloads/windows/). During installation, **make sure to check the box that says "Add Python to PATH."**
2. **Install Git**: [Download Git for Windows](https://git-scm.com/download/win).
3. **Install Google Cloud (gcloud)**: [Follow these instructions](https://cloud.google.com/sdk/docs/install#windows).

---

## 🏗️ Step 2: Getting the Code (Clone & Open)

Open your terminal (PowerShell or Command Prompt) and run these commands one at a time:

1. **Clone the project**

   ```powershell
   git clone https://github.com/luiz-ramelan/alfred.git
   ```

2. **Move into the folder**

   ```powershell
   cd alfred/src/agent/alfred_agent
   ```

---

## ⚙️ Step 3: Installing Antigravity (The ADK)

Alfred runs on the **Antigravity (ADK)** framework. To install it and all other requirements:

1. **Create a virtual environment** (optional but recommended)

   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **Install the toolkit**

   ```powershell
   pip install google-adk
   pip install -r requirements.txt
   ```

---

## 🔑 Step 4: The Secret Keys (.env)

Alfred needs a few "Secret Keys" to function. In this folder, you will find a file named `.env`. If it doesn't exist, create it and paste the following:

```env
MODEL=gemini-2.5-flash
PROJECT_ID=alfred-492407
LOCATION=us-central1
MCP_URL=https://workspace-mcp-181562945855.asia-southeast2.run.app/mcp
GOOGLE_OAUTH_CLIENT_ID=your_google_oauth_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_google_oauth_client_secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8080/auth/callback
GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\your\credentials.json
```

### ⚡ How authentication works

Alfred now uses the Google OAuth browser sign-in flow in `web_login.py` to obtain and refresh user tokens automatically.
The `GOOGLE_ACCESS_TOKEN` fallback still exists for local debugging, but normal usage should go through the login flow.

---

## 🚀 Step 5: Launching Alfred

Run everything from this folder:

`C:\Users\manug\Documents\Alfred\alfred\src\agent\alfred_agent`

### Where to run what

| Task | Folder to run from | Command |
|---|---|---|
| Local ADK UI | `C:\Users\manug\Documents\Alfred\alfred\src\agent\alfred_agent` | `adk web .` |
| Local login wrapper | `C:\Users\manug\Documents\Alfred\alfred\src\agent\alfred_agent` | `python web_login.py` |
| Cloud Run ADK UI | `C:\Users\manug\Documents\Alfred\alfred\src\agent\alfred_agent` | `adk deploy cloud_run --with_ui .` |
| Cloud Run custom login wrapper | `C:\Users\manug\Documents\Alfred\alfred\src\agent\alfred_agent` | `gcloud run deploy ... --source .` |
| Cloud Run bundle for the login wrapper | `C:\Users\manug\Documents\Alfred\alfred\src\agent\alfred_agent` | keep the app self-contained in this folder |

1. **Open your terminal** in that folder.
2. **Run the built-in ADK UI**
   ```powershell
   adk web .
   ```
3. **Open your browser**: Go to the URL shown in the terminal (usually `http://localhost:8080`).

### Optional: run the custom login wrapper locally

If you want the Alfred gatekeeper and per-user OAuth flow, run:

```powershell
.\venv\Scripts\Activate.ps1
python web_login.py
```

That starts the FastAPI wrapper on `http://localhost:8080`.

### Optional: deploy the custom login wrapper to Cloud Run

From `src/agent/alfred_agent/`, deploy the wrapper with:

```powershell
& "C:\Users\manug\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" run deploy alfred-agent `
  --source . `
  --project alfred-492407 `
  --region asia-southeast2 `
  --allow-unauthenticated `
  --port 8080
```

This uses the `Procfile` entry `web: python web_login.py`.

### Optional: deploy the ADK UI to Cloud Run

If you want the screenshot-style ADK interface in Cloud Run, run this from the same folder:

```powershell
.\venv\Scripts\Activate.ps1
adk deploy cloud_run --project=alfred-492407 --region=asia-southeast2 --service_name=alfred-agent --with_ui .
```

This deploys the ADK web UI rather than the custom login wrapper.

### Note on the MCP helper

The MCP helper now lives alongside the agent code in `alfred_agent/mcp_google_client.py`, so the login wrapper deploy no longer depends on `src/mcpRunner`.

---

## 🦸‍♂️ Step 6: Hero Training (Expanding Alfred)

Want to give Alfred new powers? All the "brains" are located in **`agent.py`**.

### Change How He Speaks (Persona)

Look for any `Agent(` definition in `agent.py` and modify the `instruction` property.
*Example: If you want him to be even more sarcastic, add it to his instruction.*

### Add New Tools (Technological Upgrades)

Alfred uses **MCP (Model Context Protocol)** through ADK's `McpToolset` to talk to the world.

- Look for `workspace_toolset` in `agent.py`.
- The toolset auto-discovers Workspace actions from the MCP server.
- Google Calendar, Contacts, and Gmail CRUD are available through the same toolset, so you do not need one wrapper per operation.

### Create a New Specialist (Sub-Agents)

If we need a "Batmobile Repair Specialist" agent:

1. Define a new `Agent` in `agent.py`.
2. Add it to the `sub_agents` list in `alfred_root`.

---

## 🛡️ Final Note

*"Be present at work. Be present at home. I shall handle the rest."*
