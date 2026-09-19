# 💠 AIONOS Operations Control Room — Agentic AI Factory

![Operations Control Room Dashboard](screenshots/Screenshot%202026-09-19%20113144.png)

AIONOS is a **state-of-the-art Multi-Agent Operations Control Room**. It serves as a central hub where specialized AI Agents (Finance, HR, Sales, Operations) autonomously monitor, route, and resolve incoming enterprise alerts in real-time. 

When a critical alert requires cross-department collaboration, the **Supervisor AI Orchestrator** kicks in—breaking the problem into sub-tasks, delegating them to the appropriate department agents, and aggregating their responses into a single, comprehensive resolution.

---

## 🧠 Theoretical Concept: The Agentic Factory

Traditional automation relies on hardcoded `if/else` rules. The **AIONOS Agentic Factory** relies on autonomous reasoning. 

1. **Department Specialization**: Just like a real company, AI agents are siloed into departments (e.g., HR, Finance). Each agent only has access to the tools and Standard Operating Procedures (SOPs) relevant to its domain.
2. **Supervisor Delegation**: Complex problems rarely stay within one department. The Supervisor Agent acts as the manager. It doesn't solve the problem itself; it plans a delegation tree, asking the HR Agent for employee data, and the Finance Agent for budget data, before combining the answers.
3. **Human-in-the-Loop (HITL)**: AI is powerful, but humans have the final say. High-risk actions or critical budget changes are halted by the agents and placed into an **Approvals Queue** for a human operator to review.
4. **Transparent Reasoning**: Through real-time Server-Sent Events (SSE), human operators can watch the agents "think" live—seeing exactly which tools they are calling, what policies they are fetching via RAG (Retrieval-Augmented Generation), and how they arrive at their conclusions.

---

## 📸 Platform Showcase

### 1. Operations Control Room (Dashboard)
The central nerve center offering a real-time, global view of departmental KPIs, agent statuses, and multi-agent orchestration history.
![Operations Control Room Dashboard](screenshots/Screenshot%202026-09-19%20113144.png)

### 2. Alerts Queue & LLM Hot-Swapping
Agents can seamlessly transition between LLM providers (Mistral and Groq) with built-in API quota tracking. Critical alerts can be escalated to the Orchestrator, while standard alerts are processed autonomously.
![Alerts Queue](screenshots/Screenshot%202026-09-19%20113151.png)

### 3. Human-in-the-Loop (Approvals Queue)
When an agent encounters a high-risk or cross-departmental issue, it halts and requests human intervention. Managers can explicitly review the agent's findings and authorize actions.
![Approvals Queue](screenshots/Screenshot%202026-09-19%20113203.png)

### 4. Immutable Audit Logs
For absolute enterprise compliance, every single action—whether an AI tool execution, an orchestration completion, or a human approval—is immutably recorded in the global Audit Log.
![Audit Log](screenshots/Screenshot%202026-09-19%20113216.png)

---

## 🛠 Technical Architecture

The architecture is split into a highly responsive, glassmorphic Frontend and a robust, async Python Backend.

### Frontend
* **Tech Stack**: Vanilla HTML5, CSS3, JavaScript (ES6 Modules).
* **Design System**: Custom CSS variables, Glassmorphism (acrylic blurs, subtle gradients), Light Mode optimized.
* **Streaming**: Uses the native browser `EventSource` API to consume Server-Sent Events (SSE) from the backend, rendering streaming markdown and agent reasoning tokens live.

### Backend
* **Tech Stack**: Python 3.11, FastAPI, Uvicorn.
* **AI Orchestration**: Built from scratch using modern LLM prompt engineering. Supports dynamic switching between **Groq** (for lightning-fast open-source models like LLaMA) and **Mistral**.
* **Database**: **Supabase** (PostgreSQL). Stores incoming alerts, employee databases, system logs, and tracks real-time API quota limits to prevent billing overages.
* **Authentication**: JWT-based stateless authentication.

### Database Schema (Supabase)
* `alerts`: Stores the tickets/incidents.
* `audit_logs`: Immutable ledger of every action an AI agent or human takes.
* `approvals`: Queue for Human-in-the-Loop requests.
* `api_limits`: Tracks token and request usage across LLM providers.

---

## 🚀 Getting Started (Local Development)

### Prerequisites
* Node.js (for frontend serving if desired)
* Python 3.11
* A Supabase Project
* Groq API Key & Mistral API Key

### 1. Backend Setup
\`\`\`bash
cd backend
python -m venv venv
source venv/Scripts/activate  # On Windows
pip install -r requirements.txt
\`\`\`

Create a `.env` file in the `backend` directory:
\`\`\`env
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
GROQ_API_KEY=your_groq_key
MISTRAL_API_KEY=your_mistral_key
JWT_SECRET=your_jwt_secret
JWT_ALGORITHM=HS256
\`\`\`

Run the backend:
\`\`\`bash
uvicorn main:app --reload --port 8000
\`\`\`

### 2. Frontend Setup
Because the frontend uses ES6 modules, it must be served over HTTP (not the `file://` protocol).
\`\`\`bash
cd frontend
npx serve .
\`\`\`
Go to `http://localhost:3000` in your browser.

---

## 🌍 Deployment

* **Frontend**: Deployed seamlessly on **Vercel**. Environment variable `AIONOS_API_URL` points to the Render backend.
* **Backend**: Deployed on **Render** as a Python Web Service. Uses `uvicorn main:app --host 0.0.0.0 --port $PORT` as the start command.
* **Database**: Hosted on **Supabase**.

---
*Built for the future of autonomous enterprise operations.*
