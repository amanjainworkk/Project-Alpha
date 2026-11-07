# Alpha's Vault — Architecture & Schema Reference

> **Custodian:** CIO (Chief Information Officer)
> **Last Updated:** 2026-11-06
> **Status:** Canonical Design Document

---

## 1. What Is Alpha's Vault?

Alpha's Vault is the **living institutional memory** of Project Alpha. It is the single source of truth for:

- Every decision ever made by any agent
- Every project ever run — briefs, threads, deliverables, audits
- Every piece of knowledge agents have accumulated
- The user's preferences, goals, and feedback history
- Each agent's identity, skills, and learned behaviors

The Vault makes Alpha **immortal** — it cannot forget. The longer Alpha runs, the smarter every agent becomes, because they draw on a richer and more specific history of your company.

---

## 2. Vault Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Vector Store** | ChromaDB (local) | Semantic search across all content |
| **Structured Store** | SQLite | Metadata, relationships, quick lookups |
| **Embedding Model** | nomic-embed-text via Ollama | Converts text to vectors (free, local) |
| **Vault Manager** | Python service | Unified read/write/search API |
| **Backup** | Auto-snapshot JSON | Disaster recovery, portability |

**Why local-first?** The Vault runs entirely on your desktop. No cloud, no subscriptions, no data leaving your machine. Perfect for the open-source self-hosting model.

---

## 3. Vault Directory Structure

```
Alpha-Vault/
│
├── company/
│   ├── identity.json              # Who you are as a company
│   ├── okrs.json                  # Strategic objectives
│   ├── culture.md                 # Values, working principles
│   └── history.json               # Company milestones
│
├── agents/
│   ├── registry.json              # Master list of all active agents
│   ├── CEO/
│   │   ├── profile.json
│   │   ├── episodic_memory.jsonl   # Append-only decision log
│   │   ├── semantic_memory/        # ChromaDB collection for this agent
│   │   └── performance_log.jsonl
│   ├── CTO/
│   │   └── ... (same structure)
│   └── ... (all 13 agents)
│
├── projects/
│   ├── index.json                 # All projects: id, name, status, dates
│   ├── {project_id}/
│   │   ├── manifest.json          # Project metadata
│   │   ├── goal.md                # Original user goal (verbatim)
│   │   ├── ceo_brief.md           # CEO's initial delegation brief
│   │   ├── threads/
│   │   │   ├── main.jsonl         # Primary inter-agent thread
│   │   │   └── {topic}.jsonl      # Sub-threads per topic
│   │   ├── deliverables/
│   │   │   ├── technical_spec.md
│   │   │   ├── marketing_brief.md
│   │   │   ├── product_prd.md
│   │   │   ├── design_guide.md
│   │   │   ├── financial_report.md
│   │   │   ├── execution_plan.md
│   │   │   ├── legal_review.md
│   │   │   └── strategic_alignment.md
│   │   ├── audit/
│   │   │   ├── claude_audit.md
│   │   │   ├── gpt_audit.md
│   │   │   └── resolution.md      # How CEO addressed audit findings
│   │   └── final_output.md        # What was delivered to user
│
├── knowledge/
│   ├── tech_decisions.jsonl        # CTO's accumulated tech choices
│   ├── brand_guidelines.json       # CMO's brand identity document
│   ├── design_system.json          # CDO's design tokens and components
│   ├── financial_history.jsonl     # CFO's cost/budget records
│   ├── legal_registry.json         # CLO's compliance and license log
│   ├── market_intelligence.jsonl   # CMO's competitive research log
│   └── user_feedback.jsonl         # Feedback on every output
│
├── user/
│   ├── profile.json               # User preferences and working style
│   ├── interaction_log.jsonl      # Every user ↔ CEO conversation
│   ├── approval_log.jsonl         # What user approved/rejected
│   └── goals_history.jsonl        # All goals ever given
│
└── backups/
    └── {timestamp}/               # Full vault snapshots
```

---

## 4. Core JSON Schemas

### 4.1 Company Identity (`company/identity.json`)
```json
{
  "company_name": "string",
  "founder": "string",
  "founded_date": "ISO8601",
  "vision": "string",
  "mission": "string",
  "core_values": ["string"],
  "industry": "string",
  "current_stage": "string",
  "primary_goals": ["string"],
  "working_style": "string",
  "preferred_communication": "string",
  "timezone": "string",
  "language": "string",
  "alpha_version": "string"
}
```

### 4.2 Agent Profile (`agents/{ROLE}/profile.json`)
```json
{
  "agent_id": "string",
  "role": "string",
  "full_title": "string",
  "version": "string",
  "created_date": "ISO8601",
  "jd_file": "path/to/jd.md",
  "assigned_model": {
    "default": "string",
    "simple_tasks": "string",
    "complex_tasks": "string"
  },
  "skills": ["string"],
  "communication_style": "string",
  "vault_read_access": ["string"],
  "vault_write_access": ["string"],
  "peers": ["agent_id"],
  "reports_to": "agent_id",
  "status": "active | inactive | on_task",
  "total_projects_completed": "integer",
  "specializations": ["string"]
}
```

### 4.3 Project Manifest (`projects/{id}/manifest.json`)
```json
{
  "project_id": "string",
  "name": "string",
  "user_goal": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "status": "planning | in_progress | in_audit | awaiting_approval | complete | archived",
  "assigned_agents": ["agent_id"],
  "lead_agent": "CEO",
  "priority": "low | medium | high | critical",
  "deadline": "ISO8601 | null",
  "deliverables_expected": ["string"],
  "deliverables_completed": ["string"],
  "audit_status": "pending | in_progress | complete | failed",
  "user_approved": "boolean | null",
  "parent_project": "project_id | null",
  "tags": ["string"]
}
```

### 4.4 Agent Episodic Memory Entry (`agents/{ROLE}/episodic_memory.jsonl`)
```json
{
  "memory_id": "string",
  "timestamp": "ISO8601",
  "project_id": "string",
  "type": "decision | observation | feedback | lesson",
  "content": "string",
  "context": "string",
  "importance": 1-5,
  "referenced_agents": ["agent_id"],
  "tags": ["string"]
}
```

### 4.5 Inter-Agent Thread Message (`projects/{id}/threads/main.jsonl`)
```json
{
  "message_id": "string",
  "thread_id": "string",
  "timestamp": "ISO8601",
  "from_agent": "agent_id",
  "to_agents": ["agent_id | 'all'"],
  "type": "DELEGATION | DELIVERABLE | QUESTION | RESPONSE | REVIEW_REQUEST | SYNTHESIS | AUDIT_REQUEST | AUDIT_REPORT | USER_ESCALATION",
  "subject": "string",
  "content": "string",
  "attachments": ["file_path"],
  "in_reply_to": "message_id | null",
  "model_used": "string",
  "tokens_used": "integer",
  "status": "sent | read | actioned | resolved"
}
```

### 4.6 User Profile (`user/profile.json`)
```json
{
  "name": "string",
  "role": "Founder",
  "communication_style": "string",
  "decision_making": "string",
  "working_hours": "string",
  "output_preferences": {
    "length": "concise | detailed | both",
    "format": "bullet | prose | mixed",
    "include_reasoning": "boolean"
  },
  "auto_approve_routine": "boolean",
  "escalation_threshold": "string",
  "current_focus_areas": ["string"],
  "long_term_goals": ["string"],
  "projects_completed": "integer",
  "total_goals_given": "integer"
}
```

---

## 5. Vault Manager API

The Vault Manager is a Python service that all agents use to interact with the Vault. No agent writes to the filesystem directly — they always go through the Vault Manager.

```python
class VaultManager:
    
    # READ OPERATIONS
    def read(self, path: str) -> dict
    def search(self, query: str, collection: str, top_k: int = 5) -> list[dict]
    def get_project(self, project_id: str) -> dict
    def get_agent_memory(self, agent_id: str, top_k: int = 10) -> list[dict]
    def get_user_profile(self) -> dict
    def get_company_identity(self) -> dict
    
    # WRITE OPERATIONS
    def write(self, path: str, data: dict) -> bool
    def append_memory(self, agent_id: str, memory: dict) -> bool
    def create_project(self, manifest: dict) -> str  # returns project_id
    def update_project_status(self, project_id: str, status: str) -> bool
    def post_thread_message(self, project_id: str, message: dict) -> bool
    def save_deliverable(self, project_id: str, role: str, content: str) -> bool
    def save_audit(self, project_id: str, cao_instance: str, report: str) -> bool
    def save_final_output(self, project_id: str, output: str) -> bool
    
    # SEARCH OPERATIONS
    def semantic_search(self, query: str, scope: str = "all") -> list[dict]
    def find_similar_projects(self, goal: str) -> list[dict]
    def get_tech_decisions(self, topic: str) -> list[dict]
    
    # ADMIN OPERATIONS  
    def backup(self) -> str  # returns backup path
    def register_agent(self, profile: dict) -> bool
    def get_agent_registry(self) -> list[dict]
```

---

## 6. Vault Initialization (First Run)

On first run, Alpha's Vault is bootstrapped by CHRO and CIO working together:

```
1. CIO creates the directory structure
2. CIO initializes ChromaDB collections for each agent + project space
3. CHRO prompts user (via CEO) for:
   - Company name and vision
   - User's name and role
   - Primary goals and industry
   - Working style preferences
4. CIO writes company/identity.json
5. CIO writes user/profile.json
6. CHRO registers all 13 agents in agents/registry.json
7. Each agent writes their own profile.json
8. Vault is LIVE
```

---

## 7. Memory Strategy Per Agent

Each agent has two types of memory, both stored in the Vault:

### Episodic Memory (What happened)
- Stored as JSONL append-only log
- Each entry = one experience from one project
- Agents write new entries after every project
- Read at task start to contextualize current work
- Example CTO entry: "For Project X, chose Next.js over Remix because team familiarity was higher and SSG was sufficient."

### Semantic Memory (What it knows)
- Stored as ChromaDB vector embeddings
- All past deliverables, decisions, and research are embedded
- Agents run similarity search before starting any new task
- Example CTO query: "Find all past decisions about database selection"
- Returns top-5 most relevant past decisions with full context

---

## 8. Context Window Management

Since agents have limited context windows, the Vault uses a smart retrieval strategy:

```
Before every agent task:
1. Retrieve user's profile (always included)
2. Retrieve company identity (always included)
3. Run semantic search for top-5 most relevant past memories
4. Retrieve current project manifest and thread
5. Retrieve agent's own profile and top-10 recent episodic memories
6. Pack into context: [System Prompt (JD)] + [Vault Context] + [Current Task]
```

This ensures agents always have:
- Their complete identity (from JD)
- Relevant historical context (from Vault search)
- Current project state (from project thread)

---

## 9. Vault Backup & Portability

```
Backup Schedule: After every project completion + every 24 hours
Backup Format: Compressed JSON snapshot of entire vault
Backup Location: Alpha-Vault/backups/{YYYY-MM-DD_HH-MM}/
Retention: Last 30 backups kept

Restore Command: alpha vault restore --backup {backup_path}
Export Command:  alpha vault export --format json
Import Command:  alpha vault import --file {export_file}
```

This ensures users can:
- Move Alpha to a new machine
- Share their Vault config (without sensitive data) with the community
- Roll back if something goes wrong

---

## 10. Vault Security

- **Local only:** Vault never connects to external servers
- **No PII transmission:** User data stays on device
- **API key isolation:** Keys stored in `.env`, never in Vault
- **Agent access control:** Enforced by VaultManager, agents cannot bypass
- **Audit trail:** Every write is logged with timestamp and agent ID
