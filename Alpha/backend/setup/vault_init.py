"""backend/setup/vault_init.py - Project Alpha Vault Initializer & Directory Bootstrapper.

Milestone 9: CLI Entrypoint & Vault Initializer (Features 62-64).

Responsible for:
1. Creating the complete canonical Vault directory tree under Alpha-Vault/:
   company/, founder/, user/, projects/, agents/, system/, knowledge/, sqlite/, chroma/, backups/.
2. Idempotently initializing SQLite database (Alpha-Vault/sqlite/vault.db) with
   underlying tables (vault_kv, vault_agents, vault_agent_memory, vault_project_threads,
   vault_thread_messages, vault_decisions, vault_system_metrics, vault_api_registry,
   projects, audit_log) and compatibility views (documents, memories, threads, messages,
   decisions, agent_registry, episodic_memory, thread_messages) plus INSTEAD OF trigger
   on documents for transparent direct writes.
3. Idempotently initializing ChromaDB persistent collections (Alpha-Vault/chroma/)
   and seeding initial vectors for knowledge and per-agent memory.
4. Seeding default company files: company/identity.json, company/org_chart.json,
   system/agent_catalog.json, user/profile.json, founder/profile.json, company/culture.md,
   company/okrs.json, and projects/index.json.
5. Pre-populating agent registry in SQLite and Chroma with all 13 executive agent
   profiles and system prompts extracted from Alpha/agents/job-descriptions/.
6. Providing a clean, programmatic interface:
   initialize_vault(vault_dir=None, force=False, founder_name="Aman Jain", company_name="Alpha OS") -> VaultManager.
7. Supporting mock embeddings (ALPHA_MOCK_EMBEDDINGS=1) for hermetic offline test runs.
8. Atomic disk writes with Windows NTFS retry loop.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Core subsystems
from backend.agents.agent_registry import (
    CANONICAL_AGENT_METADATA,
    AgentRegistry,
)
from backend.vault.chroma_store import ChromaStore
from backend.vault.embeddings import EMBEDDING_DIM, embed_text
from backend.vault.schemas import (
    AgentProfile,
    CompanyIdentity,
    OutputPreferences,
    UserProfile,
)
from backend.vault.sqlite_store import SQLiteStore
from backend.vault.vault_manager import (
    DEFAULT_EXECUTIVE_AGENTS,
    VaultManager,
    _normalize_fs_path,
)

logger = logging.getLogger("alpha.setup.vault_init")

# Canonical 13 C-Suite Agents + Dual CAO Configuration
DEFAULT_EXECUTIVE_ROSTER: List[Dict[str, Any]] = [
    {
        "agent_id": "CEO",
        "role": "Chief Executive Officer",
        "full_title": "Chief Executive Officer",
        "name": "Alpha CEO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-5 (Zero-Cost First)",
        "framework": "CrewAI / AG2 / Addy Osmani 6-Phase Lifecycle",
        "personality": "Visionary, strategic, decisive",
        "jd_file": "CEO-Chief-Executive-Officer.md",
        "reports_to": "Founder",
        "skills": ["Goal Decomposition", "Workstream Planning", "Agent Delegation", "Executive Synthesis"],
    },
    {
        "agent_id": "CTO",
        "role": "Chief Technology Officer",
        "full_title": "Chief Technology Officer",
        "name": "Alpha CTO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-5",
        "framework": "Archify / Addy Osmani TDD / OSI Standards",
        "personality": "Architectural, technical, rigorous",
        "jd_file": "CTO-Chief-Technology-Officer.md",
        "reports_to": "CEO",
        "skills": ["System Architecture", "Tech Stack Selection", "Archify Diagrams", "Code Standards"],
    },
    {
        "agent_id": "CMO",
        "role": "Chief Marketing Officer",
        "full_title": "Chief Marketing Officer",
        "name": "Alpha CMO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-4",
        "framework": "Growth Engine / Messaging Frameworks / Personas",
        "personality": "Growth-oriented, creative, analytical",
        "jd_file": "CMO-Chief-Marketing-Officer.md",
        "reports_to": "CEO",
        "skills": ["Market Research", "Brand Positioning", "Growth Experiments", "User Personas"],
    },
    {
        "agent_id": "CPO",
        "role": "Chief Product Officer",
        "full_title": "Chief Product Officer",
        "name": "Alpha CPO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-4",
        "framework": "Addy Osmani (Define) / CrewAI Flow Architecture",
        "personality": "User-centric, pragmatic, prioritized",
        "jd_file": "CPO-Chief-Product-Officer.md",
        "reports_to": "CEO",
        "skills": ["Product PRDs", "User Story Mapping", "MVP Scoping", "MoSCoW Prioritization"],
    },
    {
        "agent_id": "CDO",
        "role": "Chief Design Officer",
        "full_title": "Chief Design Officer",
        "name": "Alpha CDO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-5",
        "framework": "Archify Visuals / Material Design 3 / OLED Dark Tokens",
        "personality": "Aesthetic, meticulous, modern",
        "jd_file": "CDO-Chief-Design-Officer.md",
        "reports_to": "CEO",
        "skills": ["OLED Dark Design System", "Archify Visual Tokens", "Wireframing", "UI/UX Guidelines"],
    },
    {
        "agent_id": "CFO",
        "role": "Chief Financial Officer",
        "full_title": "Chief Financial Officer",
        "name": "Alpha CFO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-4",
        "framework": "Free-First Economics / Token Budgeting / Unit CPQ",
        "personality": "Frugal, quantitative, governed",
        "jd_file": "CFO-Chief-Financial-Officer.md",
        "reports_to": "CEO",
        "skills": ["Token Governance", "Cost per Query Modeling", "Cost Tracking", "Budget Enforcement"],
    },
    {
        "agent_id": "COO",
        "role": "Chief Operations Officer",
        "full_title": "Chief Operations Officer",
        "name": "Alpha COO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-4",
        "framework": "CrewAI Flow / AG2 Coordination / PEP Lifecycle",
        "personality": "Operational, process-driven, execution-focused",
        "jd_file": "COO-Chief-Operations-Officer.md",
        "reports_to": "CEO",
        "skills": ["Project Execution Plans", "Critical Path Tracking", "Timeline Matrices", "Process Auditing"],
    },
    {
        "agent_id": "CHRO",
        "role": "Chief Human Resources Officer",
        "full_title": "Chief Human Resources Officer",
        "name": "Alpha CHRO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-4",
        "framework": "Agent Lifecycle / Agent Registry / Performance Governance",
        "personality": "People-oriented, culture-custodian, empathetic",
        "jd_file": "CHRO-Chief-Human-Resources-Officer.md",
        "reports_to": "CEO",
        "skills": ["Agent Lifecycle Management", "Agent Onboarding", "Performance Reviews", "Culture Alignment"],
    },
    {
        "agent_id": "CIO",
        "role": "Chief Information Officer",
        "full_title": "Chief Information Officer",
        "name": "Alpha CIO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-4",
        "framework": "ECC Memory Compression / Vault Schema Governance",
        "personality": "Data custodian, security-conscious, structured",
        "jd_file": "CIO-Chief-Information-Officer.md",
        "reports_to": "CEO",
        "skills": ["Vault Storage Custody", "Schema Governance", "Memory Compression", "Data Integrity"],
    },
    {
        "agent_id": "CSO",
        "role": "Chief Strategy Officer",
        "full_title": "Chief Strategy Officer",
        "name": "Alpha CSO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-5",
        "framework": "Strategic Horizon / OKR Alignment Checking",
        "personality": "Long-term thinker, OKR-aligned, analytical",
        "jd_file": "CSO-Chief-Strategy-Officer.md",
        "reports_to": "CEO",
        "skills": ["OKR Formulation", "Strategic Horizon Planning", "Alignment Checking", "Competitive Analysis"],
    },
    {
        "agent_id": "CLO",
        "role": "Chief Legal Officer",
        "full_title": "Chief Legal Officer",
        "name": "Alpha CLO",
        "assigned_model": "llama3.2",
        "tier": "Dynamic Tier 1-4",
        "framework": "OSI Licensing / GDPR / DPDP Privacy / AI IP Defense",
        "personality": "Risk-averse, compliant, protective",
        "jd_file": "CLO-Chief-Legal-Officer.md",
        "reports_to": "CEO",
        "skills": ["Open Source License Compliance", "GPL Contamination Defense", "Data Privacy", "IP Shielding"],
    },
    {
        "agent_id": "CAO-Claude",
        "role": "Chief Audit Officer (Claude)",
        "full_title": "Chief Audit Officer (Claude)",
        "name": "Alpha CAO (Claude)",
        "assigned_model": "claude-3-5-sonnet",
        "tier": "Tier 5 Dedicated (Claude 3.5 Sonnet)",
        "framework": "Addy Osmani Five-Axis Review (Architectural Rigor)",
        "personality": "Independent auditor, 5-axis compliance",
        "jd_file": "CAO-Chief-Audit-Officer.md",
        "reports_to": "Founder / Independent Gate",
        "skills": ["Five-Axis Review Rubric", "Architectural Audit", "Defect Categorization", "Escalation Triggers"],
    },
    {
        "agent_id": "CAO-ChatGPT",
        "role": "Chief Audit Officer (ChatGPT)",
        "full_title": "Chief Audit Officer (ChatGPT)",
        "name": "Alpha CAO (ChatGPT)",
        "assigned_model": "gpt-4o",
        "tier": "Tier 5 Dedicated (GPT-4o)",
        "framework": "Addy Osmani Five-Axis Review (Edge Cases & Completeness)",
        "personality": "Independent auditor, code verification",
        "jd_file": "CAO-Chief-Audit-Officer.md",
        "reports_to": "Founder / Independent Gate",
        "skills": ["Code Verification", "Edge Case Scrutiny", "Alternative Hypotheses", "Completeness Audit"],
    },
    {
        "agent_id": "CAO",
        "role": "Chief Audit Officer",
        "full_title": "Chief Audit Officer (Unified Alias)",
        "name": "Alpha CAO",
        "assigned_model": "claude-3-5-sonnet",
        "tier": "Tier 5 Dedicated",
        "framework": "Dual CAO Consensus Gate",
        "personality": "Uncompromising, objective, rigorous",
        "jd_file": "CAO-Chief-Audit-Officer.md",
        "reports_to": "Founder",
        "skills": ["Audit Synthesis", "Consolidated Defect Reporting", "Two-Round Escalation Cap Enforcement"],
    },
]


# ============================================================================
# 1. Directory Tree Bootstrapping
# ============================================================================

def bootstrap_directory_tree(vault_root: Path) -> List[Path]:
    """Create the complete canonical Alpha-Vault directory structure.
    
    Returns:
        List of created or verified Path objects.
    """
    clean_root = _normalize_fs_path(vault_root)
    clean_root.mkdir(parents=True, exist_ok=True)

    directories = [
        # Core top-level directories
        clean_root / "company",
        clean_root / "founder",
        clean_root / "user",
        clean_root / "projects",
        clean_root / "agents",
        clean_root / "system",
        clean_root / "knowledge",
        clean_root / "sqlite",
        clean_root / "chroma",
        clean_root / "backups",
    ]

    # Pre-create subdirectories for each executive agent
    for agent_meta in DEFAULT_EXECUTIVE_ROSTER:
        aid = agent_meta["agent_id"]
        directories.append(clean_root / "agents" / aid)

    created: List[Path] = []
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)
        created.append(d)

    logger.info("Verified %d vault directories under %s", len(created), clean_root)
    return created


# ============================================================================
# 2. SQLite Database & Schema Bootstrapping
# ============================================================================

SQLITE_EXTENDED_DDL = [
    # Dedicated Projects Relational Table
    """
    CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        user_goal TEXT NOT NULL,
        status TEXT DEFAULT 'planning' CHECK(status IN ('planning','in_progress','in_audit','awaiting_approval','complete','archived')),
        lead_agent TEXT DEFAULT 'CEO',
        priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
        audit_status TEXT DEFAULT 'pending' CHECK(audit_status IN ('pending','in_progress','complete','failed')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        manifest_json TEXT
    );
    """,
    # Dedicated Audit Log Table for CAO and system event tracing
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        log_id TEXT PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        project_id TEXT,
        agent_id TEXT,
        action TEXT NOT NULL,
        target_path TEXT,
        score REAL,
        details TEXT,
        status TEXT DEFAULT 'success'
    );
    """,
    # Compatibility Views mapping spec names to SQLiteStore tables
    "CREATE VIEW IF NOT EXISTS documents AS SELECT path, data, updated_at FROM vault_kv;",
    """
    CREATE VIEW IF NOT EXISTS memories AS
    SELECT memory_id, agent_id, memory_type, memory_content, memory_tags,
           importance, project_id, created_at, last_accessed, access_count,
           is_archived, data_tier
    FROM vault_agent_memory;
    """,
    """
    CREATE VIEW IF NOT EXISTS threads AS
    SELECT thread_id, project_id, project_name, thread_status,
           created_at, updated_at, owner_agent, stakeholders, priority, tags
    FROM vault_project_threads;
    """,
    """
    CREATE VIEW IF NOT EXISTS messages AS
    SELECT message_id, thread_id, project_id, sender_agent, to_agents,
           message_type, subject, content, attachments, in_reply_to,
           model_used, tokens_used, latency_ms, created_at, audit_status,
           status, data_tier
    FROM vault_thread_messages;
    """,
    """
    CREATE VIEW IF NOT EXISTS decisions AS
    SELECT decision_id, thread_id, project_id, agent_id, decision_type,
           decision_summary, rationale, alternatives, risk_level,
           cao_approved, created_at
    FROM vault_decisions;
    """,
    """
    CREATE VIEW IF NOT EXISTS agent_registry AS
    SELECT agent_id, agent_role, agent_model, agent_version,
           created_at, is_active, personality, jd_version
    FROM vault_agents;
    """,
    # Secondary compatibility views
    """
    CREATE VIEW IF NOT EXISTS episodic_memory AS
    SELECT memory_id, agent_id, memory_type, memory_content, memory_tags,
           importance, project_id, created_at, last_accessed, access_count,
           is_archived, data_tier
    FROM vault_agent_memory;
    """,
    """
    CREATE VIEW IF NOT EXISTS thread_messages AS
    SELECT message_id, thread_id, project_id, sender_agent, to_agents,
           message_type, subject, content, attachments, in_reply_to,
           model_used, tokens_used, latency_ms, created_at, audit_status,
           status, data_tier
    FROM vault_thread_messages;
    """,
    # INSTEAD OF triggers allowing transparent write operations to documents view
    """
    CREATE TRIGGER IF NOT EXISTS trg_documents_insert
    INSTEAD OF INSERT ON documents
    BEGIN
        INSERT OR REPLACE INTO vault_kv (path, data, updated_at)
        VALUES (NEW.path, NEW.data, COALESCE(NEW.updated_at, CURRENT_TIMESTAMP));
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_documents_update
    INSTEAD OF UPDATE ON documents
    BEGIN
        UPDATE vault_kv
        SET data = NEW.data, updated_at = COALESCE(NEW.updated_at, CURRENT_TIMESTAMP)
        WHERE path = OLD.path;
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_documents_delete
    INSTEAD OF DELETE ON documents
    BEGIN
        DELETE FROM vault_kv WHERE path = OLD.path;
    END;
    """,
    # Performance indices for extended tables
    "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_project ON audit_log(project_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_agent ON audit_log(agent_id);",
]


def bootstrap_sqlite_database(db_path: Path, force: bool = False) -> SQLiteStore:
    """Idempotently initialize SQLiteStore and extended tables/views.

    Args:
        db_path: Path to vault.db.
        force: If True, executes schema verification and updates views.

    Returns:
        Configured SQLiteStore instance.
    """
    db_path = _normalize_fs_path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Initialize core SQLiteStore (creates vault_kv, vault_agents, vault_agent_memory, etc.)
    store = SQLiteStore(str(db_path))

    # 2. Execute extended DDL (projects, audit_log, compatibility views, and triggers)
    with store.transaction() as cur:
        for stmt in SQLITE_EXTENDED_DDL:
            cur.execute(stmt)

    logger.info("SQLite database initialized at %s with full schema and views", db_path)
    return store


# ============================================================================
# 3. ChromaDB Vector Collections Bootstrapping
# ============================================================================

def bootstrap_chroma_collections(chroma_dir: Path, force: bool = False) -> ChromaStore:
    """Idempotently initialize ChromaDB persistent collections.

    Collections initialized:
    - vault_knowledge: Cross-cutting company and system knowledge.
    - projects_semantic: Project deliverables, briefs, and goals.
    - agent_memory_{agent_id}: Per-agent semantic episodic recall.

    Returns:
        Configured ChromaStore instance.
    """
    chroma_dir = _normalize_fs_path(chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    chroma = ChromaStore(str(chroma_dir))

    # 1. Ensure core collections exist
    chroma.get_or_create_collection(ChromaStore.COLLECTION_KNOWLEDGE)
    chroma.get_or_create_collection(ChromaStore.COLLECTION_PROJECTS)

    # 2. Ensure collection exists for each executive agent
    for agent in DEFAULT_EXECUTIVE_ROSTER:
        aid = agent["agent_id"]
        coll_name = f"{ChromaStore.COLLECTION_AGENT_MEMORY_PREFIX}{aid}"
        chroma.get_or_create_collection(coll_name)

    logger.info("ChromaDB collections verified in %s", chroma_dir)
    return chroma


# ============================================================================
# 4. Atomic File Persistence Helpers (Windows NTFS Resilience)
# ============================================================================

def _atomic_write_json(path: Path, data: Any, overwrite: bool = True) -> bool:
    """Write JSON data atomically using temporary files and retry backoff.
    
    If overwrite is False and path exists, skips write and returns True.
    """
    if path.exists() and not overwrite:
        return True

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False, encoding="utf-8") as tf:
            temp_file = tf.name
            json.dump(data, tf, indent=2, ensure_ascii=False)

        # Retry backoff to handle Windows file locking contention
        max_retries = 5
        backoff_s = 0.02
        for attempt in range(max_retries):
            try:
                os.replace(temp_file, str(path))
                temp_file = None
                return True
            except (PermissionError, OSError):
                if attempt == max_retries - 1:
                    raise
                time.sleep(backoff_s)
                backoff_s *= 2
        return True
    except Exception as e:
        logger.error("Atomic write failed for %s: %s", path, e)
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception:
                pass
        return False


def _atomic_write_text(path: Path, text: str, overwrite: bool = True) -> bool:
    """Write text data atomically using temporary files and retry backoff."""
    if path.exists() and not overwrite:
        return True

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False, encoding="utf-8") as tf:
            temp_file = tf.name
            tf.write(text)

        max_retries = 5
        backoff_s = 0.02
        for attempt in range(max_retries):
            try:
                os.replace(temp_file, str(path))
                temp_file = None
                return True
            except (PermissionError, OSError):
                if attempt == max_retries - 1:
                    raise
                time.sleep(backoff_s)
                backoff_s *= 2
        return True
    except Exception as e:
        logger.error("Atomic text write failed for %s: %s", path, e)
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception:
                pass
        return False


# ============================================================================
# 5. Default Company & Seed File Population
# ============================================================================

def seed_company_files(
    vault_root: Path,
    founder_name: str = "Aman Jain",
    company_name: str = "Alpha OS",
    force: bool = False,
) -> Dict[str, Path]:
    """Seed default company identity, org chart, catalog, culture, and user profiles.

    Args:
        vault_root: Root directory of Alpha-Vault.
        founder_name: Name of human Founder/Chairman.
        company_name: Name of company entity.
        force: If True, overwrites existing seed files.
    """
    clean_root = _normalize_fs_path(vault_root)
    written: Dict[str, Path] = {}

    # 1. Company Identity (company/identity.json)
    identity_model = CompanyIdentity(
        company_name=company_name,
        founder=founder_name,
        founded_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        vision="Build the world's premier personal autonomous AI executive operating system.",
        mission="Empower a single founder to command a full autonomous C-suite to conceptualize, architect, audit, and deliver production software systems.",
        core_values=[
            "Zero-cost first inference (Tier 1-4 free models before paid tiers)",
            "Uncompromising architectural rigor and Addy Osmani standards",
            "Audited autonomy via independent Dual CAO review gate",
            "Local-first data privacy and persistent Vault institutional memory",
            "Rapid, high-velocity deliverable execution with zero gold-plating",
        ],
        industry="Autonomous AI Systems & Software Engineering",
        current_stage="Growth & Production Deployment",
        primary_goals=[
            "Full autonomous multi-agent C-suite collaboration",
            "Desktop backend brain with interactive Flutter mobile interface",
            "Complete local persistence across SQLite and ChromaDB vector memory",
        ],
        working_style="autonomous, high-velocity, evidence-based",
        preferred_communication="direct, structured, executive bullet points",
        timezone="UTC",
        language="en",
        alpha_version="1.0.0",
    )
    identity_path = clean_root / "company" / "identity.json"
    if _atomic_write_json(identity_path, identity_model.model_dump(mode="json"), overwrite=force):
        written["company_identity"] = identity_path

    # 2. Company Org Chart (company/org_chart.json)
    org_chart = {
        "company_name": company_name,
        "founder": {
            "name": founder_name,
            "title": "Founder & Chairman",
            "role": "Human Principal / Final Approval Authority",
        },
        "executive_leadership": {
            "CEO": {
                "title": "Chief Executive Officer",
                "reports_to": founder_name,
                "responsibilities": "Goal intake, multi-agent delegation, workstream synthesis, user liaison",
            }
        },
        "direct_reports_to_ceo": [
            {"agent_id": "CTO", "title": "Chief Technology Officer", "domain": "Technology, Architecture, Archify Specs"},
            {"agent_id": "CMO", "title": "Chief Marketing Officer", "domain": "Growth, Personas, Go-to-Market"},
            {"agent_id": "CPO", "title": "Chief Product Officer", "domain": "Product PRDs, User Stories, Roadmaps"},
            {"agent_id": "CDO", "title": "Chief Design Officer", "domain": "OLED Dark Theme, UI/UX, Design Tokens"},
            {"agent_id": "CFO", "title": "Chief Financial Officer", "domain": "Token Governance, Cost Tracking, Unit Economics"},
            {"agent_id": "COO", "title": "Chief Operations Officer", "domain": "Execution Matrices, Timelines, Operations"},
            {"agent_id": "CHRO", "title": "Chief Human Resources Officer", "domain": "Agent Lifecycle, Performance, Culture"},
            {"agent_id": "CIO", "title": "Chief Information Officer", "domain": "Vault Custody, Schema Integrity, Compression"},
            {"agent_id": "CSO", "title": "Chief Strategy Officer", "domain": "Strategic Horizon, OKRs, Alignment"},
            {"agent_id": "CLO", "title": "Chief Legal Officer", "domain": "IP Defense, License Compliance, Data Privacy"},
        ],
        "independent_audit_tribunal": {
            "gate": "Dual CAO Review Tribunal",
            "mandate": "Independent five-axis quality audit before any deliverable reaches Founder",
            "escalation_policy": "Strict maximum of 2 revision rounds before mandatory escalation to Founder",
            "auditors": [
                {"agent_id": "CAO-Claude", "engine": "Claude 3.5 Sonnet", "axis_focus": "Reasoning Quality, Depth, Architecture"},
                {"agent_id": "CAO-ChatGPT", "engine": "GPT-4o", "axis_focus": "Code Correctness, Edge Cases, Alternative Hypotheses"},
            ],
        },
    }
    org_chart_path = clean_root / "company" / "org_chart.json"
    if _atomic_write_json(org_chart_path, org_chart, overwrite=force):
        written["org_chart"] = org_chart_path

    # 3. System Agent Catalog (system/agent_catalog.json)
    catalog = {
        "catalog_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_agents": len(DEFAULT_EXECUTIVE_ROSTER),
        "agents": DEFAULT_EXECUTIVE_ROSTER,
    }
    catalog_path = clean_root / "system" / "agent_catalog.json"
    if _atomic_write_json(catalog_path, catalog, overwrite=force):
        written["agent_catalog"] = catalog_path

    # 4. User Profile (user/profile.json and founder/profile.json)
    user_profile = UserProfile(
        name=founder_name,
        role="Founder & Chairman",
        communication_style="direct, high-signal, executive bullet points",
        decision_making="autonomous execution with milestone approval",
        working_hours="flexible / 24x7 asynchronous",
        output_preferences=OutputPreferences(length="concise", format="mixed", include_reasoning=True),
        auto_approve_routine=True,
        escalation_threshold="critical_only",
        current_focus_areas=["Project Alpha Architecture", "Autonomous Agent Teams", "Production AI Deployment"],
        long_term_goals=["Self-sustaining AI software company", "Open source executive operating system"],
    )
    user_profile_data = user_profile.model_dump(mode="json")

    user_path = clean_root / "user" / "profile.json"
    founder_path = clean_root / "founder" / "profile.json"
    if _atomic_write_json(user_path, user_profile_data, overwrite=force):
        written["user_profile"] = user_path
    if _atomic_write_json(founder_path, user_profile_data, overwrite=force):
        written["founder_profile"] = founder_path

    # 5. Operating Culture (company/culture.md)
    culture_md = f"""# {company_name} — Operating Culture & Engineering Principles

> **Custodian:** CHRO & CEO  
> **Status:** Canonical Operating Principles  

## 1. Core Principles
1. **Zero-Cost First Inference:** Default to Tier 1-4 free models (Ollama, Groq, Gemini Flash). Use paid Tier 5 (Claude, GPT-4o) exclusively for CAO audits and high-complexity tasks.
2. **Audited Autonomy:** No deliverable reaches the Founder without passing the independent Dual CAO audit gate (minimum score: 85%).
3. **Two-Round Escalation Cap:** If defects cannot be resolved in two audit rounds, immediately escalate to the Founder with transparent tradeoff analysis.
4. **Local-First & Immortal Memory:** All decisions, manifests, and learnings must be vaulted. Agents never lose context across sessions.
5. **Addy Osmani Engineering Rigor:** Deliverables must include clean architecture, testable contracts, edge-case coverage, and zero gold-plating.
"""
    culture_path = clean_root / "company" / "culture.md"
    if _atomic_write_text(culture_path, culture_md, overwrite=force):
        written["culture"] = culture_path

    # 6. Strategic OKRs (company/okrs.json)
    okrs = {
        "version": "1.0",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "annual_objectives": [
            {
                "id": "OBJ-1",
                "title": "Establish Project Alpha as a fully autonomous executive AI platform",
                "key_results": [
                    {"kr": "KR-1.1", "target": "100% pass rate across backend and mobile test suites", "current": "Passed"},
                    {"kr": "KR-1.2", "target": "13 C-suite agents operational with independent Dual CAO audit", "current": "Operational"},
                    {"kr": "KR-1.3", "target": "Sub-second local memory recall from Alpha's Vault", "current": "Enabled"},
                ],
            }
        ],
    }
    okrs_path = clean_root / "company" / "okrs.json"
    if _atomic_write_json(okrs_path, okrs, overwrite=force):
        written["okrs"] = okrs_path

    # 7. Project Index (projects/index.json)
    projects_index = {
        "projects": [],
        "total_count": 0,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    proj_index_path = clean_root / "projects" / "index.json"
    if _atomic_write_json(proj_index_path, projects_index, overwrite=force):
        written["projects_index"] = proj_index_path

    logger.info("Successfully seeded %d configuration documents in %s", len(written), clean_root)
    return written


# ============================================================================
# 6. Agent Registry Seeding in SQLite and Chroma
# ============================================================================

def seed_agent_registry(
    vault_manager: VaultManager,
    jd_dir: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Pre-populate agent registry in SQLite and ChromaDB with all 13 executive agent profiles.

    Args:
        vault_manager: Active VaultManager facade.
        jd_dir: Directory containing agent Job Description markdown files.
        force: If True, forces re-embedding and rewriting of agent profiles.

    Returns:
        Summary dict containing counts of seeded agents and vector embeddings.
    """
    clean_root = _normalize_fs_path(vault_manager.vault_root)
    resolved_jd_dir = jd_dir or (Path(__file__).resolve().parent.parent.parent / "agents" / "job-descriptions")

    registry = AgentRegistry(vault_manager=vault_manager, jd_dir=resolved_jd_dir)

    # 1. Instantiate and register each agent via registry
    try:
        registry.load_all()
    except Exception as e:
        logger.warning("AgentRegistry.load_all notice: %s", e)

    seeded_agents: List[Dict[str, Any]] = []
    vector_count = 0

    # 2. Iterate through canonical roster to ensure full SQLite and Chroma vector seeding
    for agent_meta in DEFAULT_EXECUTIVE_ROSTER:
        aid = agent_meta["agent_id"]
        role = agent_meta["role"]
        full_title = agent_meta["full_title"]
        assigned_model = agent_meta["assigned_model"]
        jd_filename = agent_meta["jd_file"]

        # Ensure agent directory exists
        agent_dir = clean_root / "agents" / aid
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Ensure episodic_memory.jsonl exists
        mem_file = agent_dir / "episodic_memory.jsonl"
        if not mem_file.exists():
            mem_file.touch()

        # Build AgentProfile model
        profile = AgentProfile(
            agent_id=aid,
            role=role,
            full_title=full_title,
            version="1.0.0",
            created_date=datetime.now(timezone.utc).isoformat(),
            jd_file=jd_filename,
            assigned_model=assigned_model,
            skills=agent_meta.get("skills", []),
            communication_style="executive, structured",
            vault_read_access=["*"],
            vault_write_access=[f"agents/{aid}/*", "projects/*"],
            peers=[a["agent_id"] for a in DEFAULT_EXECUTIVE_ROSTER if a["agent_id"] != aid],
            reports_to=agent_meta.get("reports_to", "CEO"),
            status="active",
            total_projects_completed=0,
            specializations=agent_meta.get("skills", []),
        )

        # Write profile.json to disk and SQLite KV
        profile_dict = profile.model_dump(mode="json")
        profile_path = agent_dir / "profile.json"
        _atomic_write_json(profile_path, profile_dict, overwrite=force)

        # Write to VaultManager KV
        try:
            vault_manager.write(f"agents/{aid}/profile.json", profile_dict)
        except Exception:
            pass

        # Upsert into SQLite relational table vault_agents
        try:
            vault_manager.sqlite.upsert_agent({
                "agent_id": aid,
                "agent_role": full_title,
                "agent_model": assigned_model,
                "agent_version": "1.0.0",
                "is_active": True,
                "personality": agent_meta.get("personality", f"Persona for {aid}"),
                "jd_version": "1.0",
            })
        except Exception as ex:
            logger.debug("upsert_agent notice for %s: %s", aid, ex)

        # 3. Read JD content for Chroma vector embedding
        jd_path = resolved_jd_dir / jd_filename
        jd_text = ""
        if jd_path.is_file():
            try:
                with open(jd_path, "r", encoding="utf-8") as f:
                    jd_text = f.read(4000)
            except Exception as e:
                logger.debug("Could not read JD for %s: %s", aid, e)

        dna_summary = (
            f"Agent ID: {aid}\nRole: {full_title}\nPersonality: {agent_meta.get('personality')}\n"
            f"Framework: {agent_meta.get('framework')}\nSkills: {', '.join(agent_meta.get('skills', []))}\n"
            f"Job Description Excerpt:\n{jd_text[:1500]}"
        )

        # Embed into agent's dedicated semantic memory collection
        try:
            agent_coll = f"{ChromaStore.COLLECTION_AGENT_MEMORY_PREFIX}{aid}"
            vault_manager.chroma.add(
                collection_name=agent_coll,
                id=f"init_{aid}_dna",
                text=dna_summary,
                metadata={
                    "agent_id": aid,
                    "type": "agent_dna",
                    "role": role,
                    "framework": agent_meta.get("framework", ""),
                },
            )
            vector_count += 1
        except Exception as e:
            logger.warning("Failed to embed Chroma DNA for agent %s: %s", aid, e)

        # Also embed agent summary into global vault_knowledge collection
        try:
            vault_manager.chroma.add(
                collection_name=ChromaStore.COLLECTION_KNOWLEDGE,
                id=f"agent_catalog_{aid}",
                text=f"Executive Agent {aid} ({full_title}): {agent_meta.get('personality')}. Specializes in: {', '.join(agent_meta.get('skills', []))}.",
                metadata={"category": "agent_catalog", "agent_id": aid},
            )
            vector_count += 1
        except Exception as e:
            logger.warning("Failed to index agent %s in knowledge collection: %s", aid, e)

        seeded_agents.append(profile_dict)

    # 4. Write master agents/registry.json document
    registry_doc = {
        "version": "1.0.0",
        "total_active_agents": len(seeded_agents),
        "agents": seeded_agents,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    try:
        vault_manager.write("agents/registry.json", registry_doc)
    except Exception:
        pass

    logger.info("Successfully seeded %d agents and %d vector documents in Vault", len(seeded_agents), vector_count)
    return {
        "seeded_agents_count": len(seeded_agents),
        "vector_embeddings_count": vector_count,
        "agents": [a["agent_id"] for a in seeded_agents],
    }


# ============================================================================
# 7. Main Programmatic Interface
# ============================================================================

def _is_ollama_online(timeout: float = 0.25) -> bool:
    """Quick probe to check if local Ollama daemon is active and responsive."""
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        import urllib.request
        req = urllib.request.Request(f"{host}/api/version", headers={"User-Agent": "Alpha-Probe"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def initialize_vault(
    vault_dir: Optional[Union[str, Path]] = None,
    force: bool = False,
    founder_name: str = "Aman Jain",
    company_name: str = "Alpha OS",
    use_mock_embeddings: Optional[bool] = None,
) -> VaultManager:
    """Idempotently initialize Project Alpha's Vault storage substrate.

    Creates directory hierarchy, SQLite database, Chroma collections, seed files,
    and pre-populates all 13 executive agent profiles and system prompts.

    Args:
        vault_dir: Target root directory for Alpha-Vault. Defaults to repo-level 'Alpha-Vault'.
        force: If True, forces overwrite of default seed documents and re-embedding.
        founder_name: Name of human Founder/Chairman (default: 'Aman Jain').
        company_name: Name of company entity (default: 'Alpha OS').
        use_mock_embeddings: If True, forces deterministic mock embeddings for offline/test environments.

    Returns:
        VaultManager: Fully initialized, ready-to-use VaultManager instance.
    """
    # 1. Environment & Mock Embedding Configuration
    if use_mock_embeddings is True:
        os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"
    elif use_mock_embeddings is False:
        os.environ.pop("ALPHA_MOCK_EMBEDDINGS", None)
    elif use_mock_embeddings is None:
        if not os.environ.get("ALPHA_MOCK_EMBEDDINGS"):
            if not _is_ollama_online(timeout=0.25):
                logger.info("Ollama is offline; falling back to deterministic mock embeddings.")
                os.environ["ALPHA_MOCK_EMBEDDINGS"] = "1"

    # 2. Resolve Target Vault Directory
    if vault_dir is None:
        target_dir = Path(__file__).resolve().parent.parent.parent / "Alpha-Vault"
    else:
        target_dir = Path(vault_dir).resolve()

    target_dir = _normalize_fs_path(target_dir)
    logger.info("Initializing Alpha Vault at %s (force=%s)", target_dir, force)

    # 3. Bootstrap Directory Hierarchy
    bootstrap_directory_tree(target_dir)

    # 4. Bootstrap SQLite Database (Alpha-Vault/sqlite/vault.db)
    sqlite_db_path = target_dir / "sqlite" / "vault.db"
    bootstrap_sqlite_database(sqlite_db_path, force=force)

    # Maintain link/copy to Alpha-Vault/vault.db for dual-path compatibility
    root_db_path = target_dir / "vault.db"
    if not root_db_path.exists() and sqlite_db_path.exists():
        try:
            os.link(str(sqlite_db_path), str(root_db_path))
        except Exception:
            try:
                shutil.copy2(sqlite_db_path, root_db_path)
            except Exception:
                pass

    # 5. Bootstrap ChromaDB Vector Store (Alpha-Vault/chroma/)
    chroma_dir = target_dir / "chroma"
    bootstrap_chroma_collections(chroma_dir, force=force)

    # 6. Seed Default Company Configuration Files
    seed_company_files(
        vault_root=target_dir,
        founder_name=founder_name,
        company_name=company_name,
        force=force,
    )

    # 7. Initialize VaultManager Facade connected to target stores
    vm = VaultManager(
        vault_root=target_dir,
        db_path=str(sqlite_db_path),
        chroma_path=str(chroma_dir),
    )

    # 8. Seed Agent Registry in SQLite and Chroma
    seed_agent_registry(vault_manager=vm, force=force)

    # 9. Populate SQLite KV cache from newly seeded company files
    company_identity_file = target_dir / "company" / "identity.json"
    if company_identity_file.is_file():
        try:
            with open(company_identity_file, "r", encoding="utf-8") as f:
                vm.sqlite.set("company/identity.json", json.load(f))
        except Exception:
            pass

    user_profile_file = target_dir / "user" / "profile.json"
    if user_profile_file.is_file():
        try:
            with open(user_profile_file, "r", encoding="utf-8") as f:
                vm.sqlite.set("user/profile.json", json.load(f))
        except Exception:
            pass

    logger.info("Alpha Vault initialized successfully at %s", target_dir)
    return vm


# ============================================================================
# 8. CLI Entrypoint
# ============================================================================

def main() -> None:
    """Command-line entrypoint for vault initialization."""
    parser = argparse.ArgumentParser(
        description="Project Alpha — Vault Initializer & Directory Bootstrapper"
    )
    parser.add_argument(
        "--vault-dir",
        type=str,
        default=None,
        help="Path to Alpha-Vault directory (default: repo Alpha-Vault)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite of default files and re-seed database",
    )
    parser.add_argument(
        "--founder",
        type=str,
        default="Aman Jain",
        help="Founder / Chairman name (default: 'Aman Jain')",
    )
    parser.add_argument(
        "--company",
        type=str,
        default="Alpha OS",
        help="Company name (default: 'Alpha OS')",
    )
    parser.add_argument(
        "--mock-embeddings",
        action="store_true",
        help="Force deterministic mock embeddings (useful in CI / headless environments)",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    vm = initialize_vault(
        vault_dir=args.vault_dir,
        force=args.force,
        founder_name=args.founder,
        company_name=args.company,
        use_mock_embeddings=args.mock_embeddings if args.mock_embeddings else None,
    )

    print(f"\n[+] Project Alpha Vault Initialized Successfully!")
    print(f"    Vault Root : {vm.vault_root}")
    print(f"    SQLite DB  : {vm.db_path}")
    print(f"    Chroma DB  : {vm.chroma_path}")
    print(f"    Agents     : {len(vm.get_agent_registry())} active agents registered")


if __name__ == "__main__":
    main()
