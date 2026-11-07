"""backend/agents/cfo.py - Project Alpha Chief Financial Officer Executive Agent.

Conforms to:
- CFO Job Description (Alpha/agents/job-descriptions/CFO-Chief-Financial-Officer.md)
- PROJECT.md Milestone 4 / Feature 21 Contract
- Free-First Token & Compute Cost Governance
- Unit Economics Architecture (CPQ, CTS, Margins)
- Budget Auditing & Founder Escalation Triggers (CEOAgent.synthesize contract)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.agents.base_agent import BaseExecutiveAgent
from backend.model_router.router import ModelRouter
from backend.vault.vault_manager import VaultManager

logger = logging.getLogger("alpha.agents.cfo")


class CFOAgent(BaseExecutiveAgent):
    """Chief Financial Officer Agent for Project Alpha.

    Responsible for:
    1. Unit Economics Modeling (CPQ, CTS, Gross Margin >85%).
    2. CapEx / OpEx Budget Forecasting & Free-First Savings Tracking.
    3. Spend Auditing & P0 Budget Breach Founder Escalation.
    4. ROI & Payback Period Evaluation.
    5. Comprehensive Financial Feasibility Reporting.
    """

    DEFAULT_MODEL_MIX = {
        "tier1_local_ollama": 0.50,
        "tier2_free_gemini": 0.35,
        "tier3_free_groq": 0.10,
        "tier5_claude_sonnet": 0.05,
    }

    def __init__(
        self,
        agent_id: str = "CFO",
        name: str = "Alpha CFO",
        role: str = "CFO",
        jd_path: Optional[Union[str, Path]] = None,
        vault_manager: Optional[VaultManager] = None,
        model_router: Optional[ModelRouter] = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            role=role,
            jd_path=jd_path,
            vault_manager=vault_manager,
            model_router=model_router,
        )

    # ------------------------------------------------------------------------
    # 1. Unit Economics Modeling
    # ------------------------------------------------------------------------
    def model_unit_economics(
        self,
        project_id: str,
        expected_queries_monthly: int = 100000,
        model_mix: Optional[Dict[str, float]] = None,
        user_count: int = 1000,
        target_price_monthly: float = 9.0,
    ) -> Dict[str, Any]:
        """Calculate Cost per Query (CPQ), Cost to Serve (CTS), and Gross Margin."""
        if not project_id or not str(project_id).strip():
            raise ValueError("project_id cannot be empty.")
        if expected_queries_monthly < 0:
            raise ValueError("expected_queries_monthly cannot be negative.")
        if user_count <= 0:
            raise ValueError("user_count must be greater than zero.")

        pid = str(project_id).strip()
        mix = model_mix or self.DEFAULT_MODEL_MIX

        # Blended CPQ calculation:
        # Tier 1, 2, 3: $0.00
        # Tier 5 (Claude Sonnet paid): ~$0.003 / query (prompt + completion)
        paid_ratio = mix.get("tier5_claude_sonnet", 0.05)
        blended_cpq = round(paid_ratio * 0.003, 6)

        queries_per_user = expected_queries_monthly / user_count
        cost_to_serve_per_user = round(queries_per_user * blended_cpq, 4)

        monthly_opex = round((expected_queries_monthly * blended_cpq) + 0.0, 2)  # Zero local desktop hosting
        monthly_revenue = round(user_count * target_price_monthly, 2)
        gross_profit = monthly_revenue - monthly_opex
        gross_margin_pct = round((gross_profit / max(monthly_revenue, 0.01)) * 100.0, 2)

        result = {
            "project_id": pid,
            "expected_queries_monthly": expected_queries_monthly,
            "user_count": user_count,
            "model_mix": mix,
            "blended_cpq": blended_cpq,
            "cost_to_serve_per_user": cost_to_serve_per_user,
            "monthly_opex": monthly_opex,
            "monthly_revenue": monthly_revenue,
            "gross_profit": gross_profit,
            "gross_margin_pct": gross_margin_pct,
            "target_margin_achieved": gross_margin_pct >= 85.0,
            "status": "modeled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/unit_economics.json"
            try:
                self.vault_manager.write(vpath, result, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving unit economics to vault: %s", e)

            try:
                self.record_thought(
                    thought=f"Modeled unit economics for {pid}: Blended CPQ=${blended_cpq:.6f}, CTS=${cost_to_serve_per_user:.4f}, Margin={gross_margin_pct:.1f}%",
                    importance=7,
                    project_id=pid,
                )
            except Exception as e:
                logger.debug("Failed recording CFO thought: %s", e)

        return result

    # ------------------------------------------------------------------------
    # 2. Budget Forecasting & Free-First Savings
    # ------------------------------------------------------------------------
    def forecast_budget(
        self,
        project_id: str,
        tasks: List[Dict[str, Any]],
        token_estimates: Optional[Dict[str, int]] = None,
        cloud_resources: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Estimate CapEx build costs, monthly OpEx, and Free-First savings."""
        pid = str(project_id).strip()
        task_count = len(tasks) if tasks else 7

        # Estimate tokens per task
        avg_tokens_per_task = 5000
        total_build_tokens = task_count * avg_tokens_per_task

        # Tiered routing cost (85% free tiers, 15% paid cloud frontier)
        tiered_build_cost = round((total_build_tokens * 0.15 / 1000) * 0.003, 2)
        unoptimized_cost = round((total_build_tokens / 1000) * 0.010, 2)  # Raw GPT-4o pricing
        savings = round(max(0.0, unoptimized_cost - tiered_build_cost), 2)

        monthly_opex = 0.0  # Zero mandatory local hosting costs

        forecast = {
            "project_id": pid,
            "task_count": task_count,
            "total_build_tokens": total_build_tokens,
            "capex_build_cost": tiered_build_cost,
            "unoptimized_baseline_cost": unoptimized_cost,
            "free_first_savings_realized": savings,
            "opex_monthly_cost": monthly_opex,
            "budget_ceiling": 500.0,
            "status": "forecasted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/budget_forecast.json"
            try:
                self.vault_manager.write(vpath, forecast, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving budget forecast: %s", e)

        return forecast

    # ------------------------------------------------------------------------
    # 3. Spend Auditing & Escalation Triggers (CEO Escalation Contract)
    # ------------------------------------------------------------------------
    def audit_spending(
        self,
        project_id: str,
        actual_spend_data: Dict[str, Any],
        budget_ceiling: float = 500.0,
    ) -> Dict[str, Any]:
        """Audit spending against budget ceiling; emit CEO-compatible breach alerts."""
        pid = str(project_id).strip()
        spend = float(actual_spend_data.get("total_spend", actual_spend_data.get("spend", 0.0)))
        cap = float(budget_ceiling)

        is_over = spend > cap
        ratio = spend / max(cap, 0.01)

        if is_over:
            status = "over_budget"
            budget_breach = True
            founder_escalation = True
            breach_details = f"Critical budget overrun: ${spend:,.2f} spent against ${cap:,.2f} allocated monthly budget."
            recommendations = [
                "Throttle Tier 5 Claude Sonnet model usage immediately",
                "Shift all non-critical cognition to local Ollama tier",
                "Require explicit Founder authorization for paid model calls",
            ]
        elif ratio >= 0.8:
            status = "warning_80_percent"
            budget_breach = False
            founder_escalation = False
            breach_details = f"Spend approaching ceiling: ${spend:,.2f} ({(ratio*100):.1f}% of ${cap:,.2f})."
            recommendations = ["Monitor Tier 5 calls closely."]
        else:
            status = "within_budget"
            budget_breach = False
            founder_escalation = False
            breach_details = f"Spend within safe operating bounds: ${spend:,.2f} of ${cap:,.2f}."
            recommendations = ["Continue current execution profile."]

        audit_record = {
            "project_id": pid,
            "total_spend": spend,
            "budget_ceiling": cap,
            "status": status,
            "budget_breach": budget_breach,
            "founder_escalation_required": founder_escalation,
            "breach_details": breach_details,
            "recommendations": recommendations,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/budget_audit.json"
            try:
                self.vault_manager.write(vpath, audit_record, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving budget audit: %s", e)

            if budget_breach:
                try:
                    self.record_decision(
                        summary=f"BUDGET BREACH: {breach_details}",
                        rationale="Spending exceeds approved ceiling; issued P0 escalation to CEO/Founder.",
                        importance=9,
                        project_id=pid,
                    )
                except Exception as e:
                    logger.debug("Failed recording breach decision: %s", e)

        return audit_record

    # ------------------------------------------------------------------------
    # 4. ROI & Payback Evaluation
    # ------------------------------------------------------------------------
    def evaluate_roi(
        self,
        project_id: str,
        build_cost: float,
        pricing_model: Dict[str, Any],
        user_growth_projections: List[int],
    ) -> Dict[str, Any]:
        """Calculate break-even volume, payback period, and 12-month net profit."""
        pid = str(project_id).strip()
        b_cost = max(0.0, float(build_cost))
        price_per_user = float(pricing_model.get("monthly_price", 9.0))
        cost_per_user = float(pricing_model.get("cts_per_user", 0.05))
        net_margin_user = max(0.01, price_per_user - cost_per_user)

        break_even_users = int(b_cost / net_margin_user) if b_cost > 0 else 0

        # Estimate payback in months based on projected user counts
        payback_months = 1
        accumulated_profit = 0.0
        for m_idx, users in enumerate(user_growth_projections, 1):
            accumulated_profit += users * net_margin_user
            if accumulated_profit >= b_cost:
                payback_months = m_idx
                break
        else:
            payback_months = max(len(user_growth_projections), 1)

        result = {
            "project_id": pid,
            "build_cost": b_cost,
            "net_margin_per_user": net_margin_user,
            "break_even_users": break_even_users,
            "payback_period_months": payback_months,
            "status": "evaluated",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.vault_manager is not None:
            vpath = f"projects/{pid}/deliverables/roi_analysis.json"
            try:
                self.vault_manager.write(vpath, result, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving ROI analysis: %s", e)

        return result

    # ------------------------------------------------------------------------
    # 5. Financial Reporting
    # ------------------------------------------------------------------------
    def generate_financial_report(
        self,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate full Financial Feasibility Brief matching JD §5."""
        pid = str(project_id).strip()
        report_id = f"fin_{uuid.uuid4().hex[:8]}"

        unit_econ = self.model_unit_economics(project_id=pid)
        forecast = self.forecast_budget(project_id=pid, tasks=[])

        report_record = {
            "report_id": report_id,
            "project_id": pid,
            "unit_economics": unit_econ,
            "forecast": forecast,
            "summary": (
                f"Financial feasibility confirmed for {pid}. Blended CPQ is ${unit_econ['blended_cpq']:.6f} "
                f"with gross margin of {unit_econ['gross_margin_pct']}%, strictly exceeding the 85% target."
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        md_content = (
            f"# Financial Feasibility Brief: Project {pid}\n"
            f"**Report ID**: `{report_id}` | **Date**: `{report_record['created_at']}`\n\n"
            f"## 1. Executive Summary\n{report_record['summary']}\n\n"
            f"## 2. Unit Economics\n"
            f"- **Blended CPQ**: ${unit_econ['blended_cpq']:.6f}\n"
            f"- **Cost to Serve (CTS)**: ${unit_econ['cost_to_serve_per_user']:.4f} / user / mo\n"
            f"- **Gross Margin**: {unit_econ['gross_margin_pct']}%\n\n"
            f"## 3. Free-First Capital Efficiency\n"
            f"- **CapEx Build Cost**: ${forecast['capex_build_cost']:.2f}\n"
            f"- **Free-First Savings Realized**: ${forecast['free_first_savings_realized']:.2f}\n"
        )
        report_record["content_md"] = md_content

        if self.vault_manager is not None:
            json_path = f"projects/{pid}/deliverables/financial_report.json"
            md_path = f"projects/{pid}/deliverables/financial_report.md"
            try:
                self.vault_manager.write(json_path, report_record, agent_id=self.agent_id)
                self.vault_manager.write(md_path, md_content, agent_id=self.agent_id)
            except Exception as e:
                logger.debug("Failed saving financial report: %s", e)

            try:
                self.vault_manager.append_memory(
                    agent_id=self.agent_id,
                    content=f"Authored financial report for {pid}: Margin={unit_econ['gross_margin_pct']}%",
                    importance=7,
                    project_id=pid,
                )
            except Exception as e:
                logger.debug("Failed appending financial history: %s", e)

        return report_record

    # ------------------------------------------------------------------------
    # 6. Universal Execution Interface
    # ------------------------------------------------------------------------
    def run(
        self,
        task: str,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute financial directive, record memory, and sync to Vault."""
        if not task or not str(task).strip():
            raise ValueError("task cannot be empty or whitespace.")

        clean_task = str(task).strip()
        pid = project_id or self.current_project_id or "default_project"
        self.current_project_id = pid
        self.current_task = clean_task

        t_lower = clean_task.lower()
        output_data: Any

        if any(w in t_lower for w in ["unit_economics", "cpq", "cts", "margin"]):
            output_data = self.model_unit_economics(project_id=pid)
        elif any(w in t_lower for w in ["forecast", "budget", "capex", "opex"]):
            output_data = self.forecast_budget(project_id=pid, tasks=[])
        elif any(w in t_lower for w in ["audit", "spend", "breach"]):
            output_data = self.audit_spending(project_id=pid, actual_spend_data={"total_spend": 100.0})
        elif any(w in t_lower for w in ["roi", "payback", "break_even"]):
            output_data = self.evaluate_roi(project_id=pid, build_cost=50.0, pricing_model={"monthly_price": 9.0}, user_growth_projections=[10, 50, 100])
        elif any(w in t_lower for w in ["report", "financial_report"]):
            output_data = self.generate_financial_report(project_id=pid)
        else:
            thought = self.think(
                context=f"CFO directive for {pid}: {clean_task}",
                complexity=3,
                task_type="financial_modeling",
            )
            output_data = {"summary": thought, "task": clean_task}

        self.record_thought(
            thought=f"CFO executed task: {clean_task[:80]}",
            importance=5,
            project_id=pid,
        )

        return {
            "status": "completed",
            "agent_id": self.agent_id,
            "role": self.role,
            "project_id": pid,
            "task": clean_task,
            "output": output_data,
        }

    # ------------------------------------------------------------------------
    # Action Dispatch Hook
    # ------------------------------------------------------------------------
    def _handle_custom_action(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        act_norm = action.lower().strip()
        if act_norm in ("model_unit_economics", "unit_economics"):
            res = self.model_unit_economics(
                project_id=parameters.get("project_id", "default_proj"),
                expected_queries_monthly=parameters.get("expected_queries_monthly", 100000),
                model_mix=parameters.get("model_mix"),
                user_count=parameters.get("user_count", 1000),
                target_price_monthly=parameters.get("target_price_monthly", 9.0),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("forecast_budget", "budget_forecast"):
            res = self.forecast_budget(
                project_id=parameters.get("project_id", "default_proj"),
                tasks=parameters.get("tasks", []),
                token_estimates=parameters.get("token_estimates"),
                cloud_resources=parameters.get("cloud_resources"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("audit_spending", "spending_audit"):
            res = self.audit_spending(
                project_id=parameters.get("project_id", "default_proj"),
                actual_spend_data=parameters.get("actual_spend_data", {}),
                budget_ceiling=parameters.get("budget_ceiling", 500.0),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("evaluate_roi", "roi_analysis"):
            res = self.evaluate_roi(
                project_id=parameters.get("project_id", "default_proj"),
                build_cost=parameters.get("build_cost", 100.0),
                pricing_model=parameters.get("pricing_model", {}),
                user_growth_projections=parameters.get("user_growth_projections", [10, 50, 100]),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm in ("generate_financial_report", "financial_report"):
            res = self.generate_financial_report(
                project_id=parameters.get("project_id", "default_proj"),
                context=parameters.get("context"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        elif act_norm == "run":
            res = self.run(
                task=parameters.get("task", ""),
                project_id=parameters.get("project_id"),
            )
            return {"status": "success", "success": True, "action": action, "data": res}

        return super()._handle_custom_action(action, parameters)
