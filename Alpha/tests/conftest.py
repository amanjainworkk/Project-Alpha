"""Project Alpha — Master Test Configuration & Shared Fixtures.

Provides contract-compliant test harnesses, isolated temporary storage,
deterministic mock LLMs, FastAPI test clients, and MCP tool execution harnesses.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional

import pytest

# Ensure Alpha root and backend are on PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

TEST_TOKEN = "test_alpha_bearer_token_secret_xyz789"


# ---------------------------------------------------------------------------
# Data Models conforming to Interface Contracts in PROJECT.md
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    tier: int
    provider: str
    model: str
    cost_per_m_in: float = 0.0
    cost_per_m_out: float = 0.0
    is_free: bool = True


@dataclass
class CAOAuditResult:
    passed: bool
    claude_score: float
    gpt_score: float
    consolidated_report: str
    p0_defects: List[str] = field(default_factory=list)
    p1_defects: List[str] = field(default_factory=list)
    escalation_required: bool = False
    round_num: int = 1


# ---------------------------------------------------------------------------
# Contract-Compliant Harness: VaultManager
# ---------------------------------------------------------------------------

class ContractVaultManager:
    """Contract-compliant VaultManager implementation for testing."""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.kv_store: Dict[str, Dict[str, Any]] = {}
        self.memories: List[Dict[str, Any]] = []
        self.projects: Dict[str, Dict[str, Any]] = {}
        self._initialize_structure()

    def _initialize_structure(self) -> None:
        (self.vault_path / "company").mkdir(parents=True, exist_ok=True)
        (self.vault_path / "agents").mkdir(parents=True, exist_ok=True)
        (self.vault_path / "projects").mkdir(parents=True, exist_ok=True)
        (self.vault_path / "knowledge").mkdir(parents=True, exist_ok=True)
        (self.vault_path / "user").mkdir(parents=True, exist_ok=True)
        (self.vault_path / "backups").mkdir(parents=True, exist_ok=True)

        # Default company identity
        self.write(
            "company/identity",
            {
                "company_name": "Alpha Corp",
                "founder": "Aman Jain",
                "vision": "Autonomous AI Executive OS",
                "core_values": ["Speed", "Autonomy", "Excellence"],
            },
        )

        # Default user profile
        self.write(
            "user/profile",
            {
                "name": "Aman Jain",
                "role": "Founder & Chairman",
                "preferred_communication": "concise",
                "escalation_policy": "critical_only",
            },
        )

    def read(self, path: str) -> Optional[Dict[str, Any]]:
        clean_path = path.strip("/").replace(".json", "")
        return self.kv_store.get(clean_path)

    def write(self, path: str, data: Dict[str, Any], agent_id: Optional[str] = None) -> bool:
        clean_path = path.strip("/").replace(".json", "")

        # Check access control if agent_id provided
        if agent_id and not self._check_write_permission(agent_id, clean_path):
            raise PermissionError(f"Agent {agent_id} does not have write access to {clean_path}")

        self.kv_store[clean_path] = data
        return True

    def delete(self, path: str) -> bool:
        clean_path = path.strip("/").replace(".json", "")
        if clean_path in self.kv_store:
            del self.kv_store[clean_path]
            return True
        return False

    def list_keys(self, prefix: str = "") -> List[str]:
        clean_prefix = prefix.strip("/")
        return [k for k in self.kv_store.keys() if k.startswith(clean_prefix)]

    def search(self, query: str, n_results: int = 5, path_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        q_lower = query.lower()
        for path, data in self.kv_store.items():
            if path_prefix and not path.startswith(path_prefix):
                continue
            dumped = json.dumps(data).lower()
            if q_lower in path.lower() or q_lower in dumped or any(word in dumped for word in q_lower.split()):
                results.append({"path": path, "data": data, "score": 0.92})
        return results[:n_results]

    def append_memory(
        self, agent_id: str, memory_type: str, content: str, importance: int, project_id: Optional[str] = None
    ) -> str:
        memory_id = f"mem_{len(self.memories) + 1:04d}"
        entry = {
            "id": memory_id,
            "agent_id": agent_id,
            "type": memory_type,
            "content": content,
            "importance": importance,
            "project_id": project_id,
            "timestamp": time.time(),
        }
        self.memories.append(entry)
        return memory_id

    def create_project(self, title: str, description: str, founder_goals: List[str]) -> str:
        project_id = f"proj_{len(self.projects) + 1:03d}"
        project_data = {
            "project_id": project_id,
            "title": title,
            "description": description,
            "founder_goals": founder_goals,
            "status": "planning",
            "created_at": time.time(),
            "deliverables": {},
            "threads": [],
        }
        self.projects[project_id] = project_data
        self.write(f"projects/{project_id}/manifest", project_data)
        return project_id

    def get_user_profile(self) -> Dict[str, Any]:
        return self.read("user/profile") or {}

    def get_agent_registry(self) -> List[Dict[str, Any]]:
        return [
            {"agent_id": "CEO", "role": "Chief Executive Officer", "status": "active"},
            {"agent_id": "CTO", "role": "Chief Technology Officer", "status": "active"},
            {"agent_id": "CMO", "role": "Chief Marketing Officer", "status": "active"},
            {"agent_id": "CPO", "role": "Chief Product Officer", "status": "active"},
            {"agent_id": "CDO", "role": "Chief Design Officer", "status": "active"},
            {"agent_id": "CFO", "role": "Chief Financial Officer", "status": "active"},
            {"agent_id": "COO", "role": "Chief Operations Officer", "status": "active"},
            {"agent_id": "CHRO", "role": "Chief Human Resources Officer", "status": "active"},
            {"agent_id": "CIO", "role": "Chief Information Officer", "status": "active"},
            {"agent_id": "CSO", "role": "Chief Strategy Officer", "status": "active"},
            {"agent_id": "CLO", "role": "Chief Legal Officer", "status": "active"},
            {"agent_id": "CAO-C", "role": "Chief Audit Officer (Claude)", "status": "active"},
            {"agent_id": "CAO-G", "role": "Chief Audit Officer (GPT)", "status": "active"},
        ]

    def _check_write_permission(self, agent_id: str, path: str) -> bool:
        if agent_id in ("CEO", "CIO"):
            return True
        if path.startswith("projects/") and agent_id in path:
            return True
        if path.startswith(f"agents/{agent_id}"):
            return True
        # Restrict unauthorized writes
        if agent_id == "CMO" and "technical-spec" in path:
            return False
        if agent_id == "CTO" and "marketing-brief" in path:
            return False
        return True


# ---------------------------------------------------------------------------
# Contract-Compliant Harness: ModelRouter
# ---------------------------------------------------------------------------

class ContractModelRouter:
    """Contract-compliant ModelRouter implementation for testing."""

    TIER_CONFIGS = {
        1: ModelConfig(tier=1, provider="ollama", model="llama3.2:1b", is_free=True),
        2: ModelConfig(tier=2, provider="ollama", model="llama3.2:3b", is_free=True),
        3: ModelConfig(tier=3, provider="groq", model="llama-3.1-70b-versatile", is_free=True),
        4: ModelConfig(tier=4, provider="gemini", model="gemini-1.5-flash", is_free=True),
        5: ModelConfig(tier=5, provider="anthropic", model="claude-3-5-sonnet", is_free=False, cost_per_m_in=3.0),
    }

    def __init__(self, simulate_groq_failure: bool = False, simulate_rate_limit: bool = False):
        self.simulate_groq_failure = simulate_groq_failure
        self.simulate_rate_limit = simulate_rate_limit
        self.call_history: List[Dict[str, Any]] = []

    def route(self, task_type: str, complexity: int, agent_role: Optional[str] = None) -> ModelConfig:
        if agent_role == "CAO-C":
            return ModelConfig(tier=5, provider="anthropic", model="claude-3-5-sonnet", is_free=False)
        if agent_role == "CAO-G":
            return ModelConfig(tier=5, provider="openai", model="gpt-4o", is_free=False)

        clamped_complexity = max(1, min(5, complexity))
        config = self.TIER_CONFIGS[clamped_complexity]

        # Handle simulated failures (fallback cascade)
        if config.provider == "groq" and self.simulate_groq_failure:
            # Fall back one tier down to Ollama
            return self.TIER_CONFIGS[2]

        return config

    def call(
        self,
        prompt: str,
        system: str = "",
        model_config: Optional[ModelConfig] = None,
        task_type: str = "general",
        complexity: int = 2,
        agent_role: Optional[str] = None,
    ) -> str:
        if not model_config:
            model_config = self.route(task_type, complexity, agent_role)

        if self.simulate_rate_limit and model_config.tier > 2:
            raise RuntimeError("429 Too Many Requests: Rate limit exceeded. Backoff required.")

        response = f"[{model_config.model}] Output for {agent_role or 'Agent'}: Verified response for task '{task_type}'."
        self.call_history.append({
            "prompt": prompt,
            "system": system,
            "model_config": model_config,
            "response": response,
            "timestamp": time.time(),
        })
        return response

    def generate(self, prompt: str, system: str, model: str) -> str:
        return f"[{model}] Response: {prompt[:30]}..."


# ---------------------------------------------------------------------------
# Contract-Compliant Harness: DualCAO
# ---------------------------------------------------------------------------

class ContractDualCAO:
    """Contract-compliant Dual CAO Audit Gate for testing."""

    def __init__(self, force_defect: bool = False, defect_type: str = "p0"):
        self.force_defect = force_defect
        self.defect_type = defect_type
        self.audit_history: List[Dict[str, Any]] = []

    def audit(self, deliverables: Dict[str, Any], project_id: str, round_num: int = 1) -> CAOAuditResult:
        if self.force_defect:
            p0 = ["Critical security vulnerability: unauthenticated endpoint exposure."] if self.defect_type == "p0" else []
            p1 = ["Missing input boundary validation on project goal."] if self.defect_type == "p1" else []
            passed = False
            claude_score = 72.0
            gpt_score = 68.0
            report = (
                f"Dual CAO Audit Round {round_num}: REJECTED.\n"
                f"- Claude Score: {claude_score}% (Threshold: 85%)\n"
                f"- GPT Score: {gpt_score}% (Threshold: 85%)\n"
                f"- Defects: {p0 + p1}"
            )
            escalation_required = (round_num >= 2)
        else:
            p0, p1 = [], []
            passed = True
            claude_score = 92.5
            gpt_score = 91.0
            report = (
                f"Dual CAO Audit Round {round_num}: PASSED.\n"
                f"- Claude Score: {claude_score}%\n"
                f"- GPT Score: {gpt_score}%\n"
                "- All 5 Addy Osmani axes satisfied (Correctness, Simplicity, Architecture, Security, Performance)."
            )
            escalation_required = False

        res = CAOAuditResult(
            passed=passed,
            claude_score=claude_score,
            gpt_score=gpt_score,
            consolidated_report=report,
            p0_defects=p0,
            p1_defects=p1,
            escalation_required=escalation_required,
            round_num=round_num,
        )
        self.audit_history.append({"project_id": project_id, "round_num": round_num, "result": res})
        return res

    def compare_audits(self, claude_report: Dict[str, Any], gpt_report: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "consensus_score": (claude_report.get("score", 90.0) + gpt_report.get("score", 90.0)) / 2,
            "agreements": ["High modularity", "Well-defined contracts"],
            "disagreements": ["Claude flagged caching latency; GPT marked acceptable."],
        }


# ---------------------------------------------------------------------------
# Contract-Compliant Harness: ArchifyEngine
# ---------------------------------------------------------------------------

class ContractArchifyEngine:
    """Contract-compliant Archify Diagram Generator for testing."""

    def generate_diagram(self, project_id: str, components: List[Dict[str, Any]]) -> str:
        html = (
            f"<!DOCTYPE html><html><head><title>Archify - {project_id}</title></head>"
            f"<body style='background:#0A0A0F; color:#E0E0E0;'>"
            f"<div id='canvas' data-project='{project_id}'>"
        )
        for c in components:
            html += f"<div class='node' id='{c.get('id', 'node')}'>{c.get('name', 'Comp')}</div>"
        html += "</div></body></html>"
        return html

    def generate_graph_data(self, project_id: str) -> Dict[str, Any]:
        return {
            "project_id": project_id,
            "nodes": [
                {"id": "node_ceo", "label": "CEO Director", "type": "agent", "status": "active"},
                {"id": "node_cto", "label": "CTO Architecture", "type": "agent", "status": "active"},
                {"id": "node_vault", "label": "Alpha Vault", "type": "storage", "status": "healthy"},
            ],
            "edges": [
                {"from": "node_ceo", "to": "node_cto", "label": "delegation", "pulsing": True},
                {"from": "node_cto", "to": "node_vault", "label": "persist_spec", "pulsing": False},
            ],
        }


# ---------------------------------------------------------------------------
# Contract-Compliant Harness: 15 MCP Tools
# ---------------------------------------------------------------------------

class ContractMCPClient:
    """Invokes and validates all 15 MCP tools according to MCP-SERVER-DESIGN.md."""

    def __init__(self, vault: ContractVaultManager, router: ContractModelRouter):
        self.vault = vault
        self.router = router
        self.active_threads: Dict[str, List[Dict[str, Any]]] = {}

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "vault_read": self._tool_vault_read,
            "vault_write": self._tool_vault_write,
            "vault_search": self._tool_vault_search,
            "vault_save_memory": self._tool_vault_save_memory,
            "agent_delegate": self._tool_agent_delegate,
            "agent_status": self._tool_agent_status,
            "agent_hire": self._tool_agent_hire,
            "project_create": self._tool_project_create,
            "project_update_status": self._tool_project_update_status,
            "project_list": self._tool_project_list,
            "thread_post": self._tool_thread_post,
            "thread_read": self._tool_thread_read,
            "model_route": self._tool_model_route,
            "user_profile_read": self._tool_user_profile_read,
            "user_escalate": self._tool_user_escalate,
        }

        handler = handlers.get(name)
        if not handler:
            raise ValueError(f"Unknown MCP Tool: {name}")

        return handler(arguments)

    def _tool_vault_read(self, args: Dict[str, Any]) -> Dict[str, Any]:
        data = self.vault.read(args["path"])
        return {"path": args["path"], "found": data is not None, "data": data}

    def _tool_vault_write(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.vault.write(args["path"], args["data"], args.get("agent_id"))
        return {"path": args["path"], "success": success}

    def _tool_vault_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        results = self.vault.search(args["query"], args.get("top_k", 5))
        return {"query": args["query"], "results": results}

    def _tool_vault_save_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        mem = args["memory"]
        mem_id = self.vault.append_memory(
            args["agent_id"], mem["type"], mem["content"], mem["importance"], mem.get("project_id")
        )
        return {"memory_id": mem_id, "saved": True}

    def _tool_agent_delegate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "delegation_id": f"del_{time.time():.0f}",
            "project_id": args["project_id"],
            "to_agents": args["to_agents"],
            "status": "dispatched",
        }

    def _tool_agent_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"agent_id": args["agent_id"], "status": "active", "current_task": "Idle or executing"}

    def _tool_agent_hire(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"role": args["role"], "hired": True, "agent_id": args["role"]}

    def _tool_project_create(self, args: Dict[str, Any]) -> Dict[str, Any]:
        proj_id = self.vault.create_project(args["name"], args["user_goal"], [args["user_goal"]])
        return {"project_id": proj_id, "status": "planning"}

    def _tool_project_update_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"project_id": args["project_id"], "new_status": args["status"], "updated": True}

    def _tool_project_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        projects = list(self.vault.projects.values())
        return {"count": len(projects), "projects": projects}

    def _tool_thread_post(self, args: Dict[str, Any]) -> Dict[str, Any]:
        pid = args["project_id"]
        if pid not in self.active_threads:
            self.active_threads[pid] = []
        msg = {
            "from": args["from_agent"],
            "to": args["to_agents"],
            "type": args["type"],
            "content": args["content"],
            "timestamp": time.time(),
        }
        self.active_threads[pid].append(msg)
        return {"posted": True, "message_count": len(self.active_threads[pid])}

    def _tool_thread_read(self, args: Dict[str, Any]) -> Dict[str, Any]:
        pid = args["project_id"]
        msgs = self.active_threads.get(pid, [])
        return {"project_id": pid, "messages": msgs}

    def _tool_model_route(self, args: Dict[str, Any]) -> Dict[str, Any]:
        config = self.router.route(args["task_type"], args["complexity"], args["agent_id"])
        return {"recommended_model": config.model, "provider": config.provider, "is_free": config.is_free}

    def _tool_user_profile_read(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self.vault.get_user_profile()

    def _tool_user_escalate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "escalated": True,
            "project_id": args["project_id"],
            "question": args["question"],
            "urgency": args["urgency"],
        }


# ---------------------------------------------------------------------------
# Contract-Compliant Test Client (FastAPI Mock/Wrapper)
# ---------------------------------------------------------------------------

class ContractAPIClient:
    """In-memory REST API test client conforming to /api/ endpoints."""

    def __init__(self, vault: ContractVaultManager, token: str = TEST_TOKEN):
        self.vault = vault
        self.token = token
        self.ws_messages: List[Dict[str, Any]] = []

    def _verify_auth(self, headers: Optional[Dict[str, str]]) -> bool:
        if not headers or "Authorization" not in headers:
            return False
        auth = headers["Authorization"]
        return auth == f"Bearer {self.token}"

    def post(self, path: str, json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if not self._verify_auth(headers):
            return {"status_code": 401, "json": {"detail": "Unauthorized"}}

        if path == "/api/goals":
            if not json_data or not json_data.get("title"):
                return {"status_code": 422, "json": {"detail": "Missing title"}}
            proj_id = self.vault.create_project(
                json_data.get("title", ""),
                json_data.get("description", ""),
                [json_data.get("title", "")],
            )
            # Push WebSocket event
            self.ws_messages.append({
                "event": "project_state_change",
                "data": {"project_id": proj_id, "status": "planning"},
                "timestamp": str(time.time()),
            })
            return {"status_code": 200, "json": {"project_id": proj_id, "status": "planning"}}

        return {"status_code": 404, "json": {"detail": "Not found"}}

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if not self._verify_auth(headers):
            return {"status_code": 401, "json": {"detail": "Unauthorized"}}

        if path == "/api/projects":
            return {"status_code": 200, "json": list(self.vault.projects.values())}

        if path.startswith("/api/projects/"):
            parts = path.strip("/").split("/")
            if len(parts) == 3:  # /api/projects/{id}
                pid = parts[2]
                proj = self.vault.projects.get(pid)
                if proj:
                    return {"status_code": 200, "json": proj}
                return {"status_code": 404, "json": {"detail": "Project not found"}}
            elif len(parts) == 4 and parts[3] == "threads":  # /api/projects/{id}/threads
                pid = parts[2]
                return {"status_code": 200, "json": {"project_id": pid, "threads": []}}

        if path == "/api/agents":
            return {"status_code": 200, "json": self.vault.get_agent_registry()}

        if path == "/api/vault/read":
            p = (params or {}).get("path", "")
            data = self.vault.read(p)
            if data is not None:
                return {"status_code": 200, "json": data}
            return {"status_code": 404, "json": {"detail": "Vault key not found"}}

        if path == "/api/vault/search":
            q = (params or {}).get("query", "")
            results = self.vault.search(q)
            return {"status_code": 200, "json": results}

        return {"status_code": 404, "json": {"detail": "Not found"}}

    def websocket_connect(self, token: str) -> bool:
        return token == self.token


# ---------------------------------------------------------------------------
# Pytest Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_vault_dir() -> Generator[Path, None, None]:
    temp_dir = Path(tempfile.mkdtemp(prefix="alpha_vault_test_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def vault_manager(temp_vault_dir: Path) -> ContractVaultManager:
    return ContractVaultManager(str(temp_vault_dir))


@pytest.fixture
def model_router() -> ContractModelRouter:
    return ContractModelRouter()


@pytest.fixture
def dual_cao() -> ContractDualCAO:
    return ContractDualCAO()


@pytest.fixture
def archify_engine() -> ContractArchifyEngine:
    return ContractArchifyEngine()


@pytest.fixture
def mcp_client(vault_manager: ContractVaultManager, model_router: ContractModelRouter) -> ContractMCPClient:
    return ContractMCPClient(vault_manager, model_router)


@pytest.fixture
def api_client(vault_manager: ContractVaultManager) -> ContractAPIClient:
    return ContractAPIClient(vault_manager)


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


# ---------------------------------------------------------------------------
# Milestone 1: Real Vault Storage Fixtures & Deterministic Embeddings
# ---------------------------------------------------------------------------

import gc
import hashlib
import math
import sqlite3

def generate_deterministic_embedding(text: str, dim: int = 768) -> list[float]:
    """Generates a deterministic 768-dimensional L2-normalized float vector."""
    if not text:
        text = "__EMPTY__"
    norm_text = text.strip().lower()
    base_hash = hashlib.sha256(norm_text.encode("utf-8")).digest()
    raw_vector: list[float] = []
    block_index = 0
    while len(raw_vector) < dim:
        block_hash = hashlib.sha256(base_hash + block_index.to_bytes(4, "big")).digest()
        for i in range(0, len(block_hash), 4):
            if len(raw_vector) >= dim:
                break
            val = int.from_bytes(block_hash[i:i+4], "big") / 0xFFFFFFFF
            raw_vector.append((val * 2.0) - 1.0)
        block_index += 1

    tokens = norm_text.split()
    for token in tokens:
        token_hash = int.from_bytes(hashlib.md5(token.encode("utf-8")).digest()[:4], "big")
        slot = token_hash % dim
        raw_vector[slot] += 2.0

    sum_sq = sum(x * x for x in raw_vector)
    norm = math.sqrt(sum_sq) if sum_sq > 0 else 1.0
    return [float(x / norm) for x in raw_vector]


@pytest.fixture
def temp_sqlite_db(tmp_path: Path) -> Generator[str, None, None]:
    db_file = tmp_path / "vault_test.db"
    db_path = str(db_file)
    yield db_path
    gc.collect()
    if db_file.exists():
        try:
            os.remove(db_file)
        except PermissionError:
            pass


@pytest.fixture
def temp_chroma_dir(tmp_path: Path) -> Generator[str, None, None]:
    chroma_dir = tmp_path / "chroma_test_db"
    chroma_dir.mkdir(parents=True, exist_ok=True)
    yield str(chroma_dir)
    gc.collect()
    if chroma_dir.exists():
        shutil.rmtree(chroma_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def mock_embeddings(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], list[float]]:
    fn = generate_deterministic_embedding
    try:
        monkeypatch.setattr("backend.vault.embeddings.embed_text", fn)
    except (ImportError, AttributeError):
        pass
    os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    return fn


@pytest.fixture
def sample_company_identity() -> dict[str, Any]:
    return {
        "company_name": "Alpha Autonomous Technologies",
        "founder": "Aman Jain",
        "founded_date": "2026-11-06T00:00:00Z",
        "vision": "Autonomous executive intelligence for every builder.",
        "mission": "Empower human founders with an AI executive C-Suite.",
        "core_values": ["Extreme Autonomy", "Verifiable Correctness", "Radical Simplicity"],
        "industry": "Artificial Intelligence Operating Systems",
        "current_stage": "Bootstrapping & R&D",
        "primary_goals": ["Ship Project Alpha M1-M12", "Master Tri-Framework Orchestration"],
        "working_style": "High-velocity asynchronous execution",
        "preferred_communication": "Concise briefs with decision matrices",
        "timezone": "Asia/Kolkata",
        "language": "en-US",
        "alpha_version": "1.0.0"
    }


@pytest.fixture
def sample_user_profile() -> dict[str, Any]:
    return {
        "name": "Aman Jain",
        "role": "Founder",
        "communication_style": "Concise and outcome-driven",
        "decision_making": "Evidence-backed with transparent trade-offs",
        "working_hours": "Flexible / Autonomous 24x7",
        "output_preferences": {
            "length": "concise",
            "format": "bullet",
            "include_reasoning": True
        },
        "auto_approve_routine": True,
        "escalation_threshold": "P0 or P1 architectural defects only",
        "current_focus_areas": ["Project Alpha OS", "Autonomous AI Agents"],
        "long_term_goals": ["Global deployment of personal executive systems"],
        "projects_completed": 0,
        "total_goals_given": 1
    }


@pytest.fixture
def sample_agent_profile() -> dict[str, Any]:
    return {
        "agent_id": "alpha-agent-cto-v1",
        "role": "CTO",
        "full_title": "Chief Technology Officer",
        "version": "1.0.0",
        "created_date": "2026-11-06T00:00:00Z",
        "jd_file": "agents/job-descriptions/CTO-Chief-Technology-Officer.md",
        "assigned_model": {
            "default": "ollama/llama3.2",
            "simple_tasks": "ollama/llama3.2",
            "complex_tasks": "claude-3-5-sonnet"
        },
        "skills": ["Architecture Design", "Python", "Flutter", "Security Auditing"],
        "communication_style": "Formal technical specifications and diagrams",
        "vault_read_access": ["company/", "projects/", "knowledge/"],
        "vault_write_access": ["projects/{id}/deliverables/", "knowledge/tech_decisions"],
        "peers": ["CEO", "CIO", "CPO", "CDO"],
        "reports_to": "CEO",
        "status": "active",
        "total_projects_completed": 0,
        "specializations": ["Distributed Systems", "Local Vector Stores"]
    }

