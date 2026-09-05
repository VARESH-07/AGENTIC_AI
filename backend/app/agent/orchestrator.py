import os
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from app.tools import agent_tools
from app.agent.evidence import EvidenceCollector
from app.analysis.investigator import CodeImpactInvestigator
from app.models.schemas import InvestigationResponse, ImpactChain, RiskAssessment, RootCause, EvidenceItem

MAX_STEPS = 15

class RippleOrchestrator:
    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        self.evidence_collector = EvidenceCollector()
        self.trace: List[str] = []

    def _add_trace(self, step_text: str):
        step_num = len(self.trace) + 1
        formatted = f"[{step_num}] {step_text}"
        self.trace.append(formatted)
        return formatted

    def run_deterministic_investigation(self, query: str) -> InvestigationResponse:
        """
        Executes a 100% deterministic, evidence-backed investigation.
        No LLM API key required!
        """
        self.trace.clear()
        self.evidence_collector.evidence.clear()

        self._add_trace("Loading repository & parsing code graph")

        # 1. Target identification
        target_symbol = "AuthService.authenticate"
        
        symbols = agent_tools._get_symbols(self.repo_id)
        # Filter for actual function/method/class symbols (excluding module/file level symbols if possible)
        func_symbols = [s for s in symbols if s.type in ["FUNCTION", "METHOD", "CLASS"]]
        if not func_symbols:
            func_symbols = symbols

        found_target = None
        for sym in func_symbols:
            if sym.name.lower() in query.lower() or (sym.qualified_name and sym.qualified_name.lower() in query.lower()):
                found_target = sym.qualified_name or sym.name
                break
                
        if not found_target and func_symbols:
            # Fallback to main auth service or first function
            for sym in func_symbols:
                if "auth" in sym.name.lower() or "authenticate" in sym.name.lower():
                    found_target = sym.qualified_name or sym.name
                    break
            if not found_target:
                found_target = func_symbols[0].qualified_name or func_symbols[0].name

        if found_target:
            target_symbol = found_target

        self._add_trace(f"Target identified: {target_symbol}")

        # Check ephemeral memory for prior investigations on this target (supporting context)
        try:
            from app.agent.memory import memory_manager
            past_memories = memory_manager.find_by_target(target_symbol)
            if past_memories:
                prior = past_memories[0]
                self.evidence_collector.add(
                    "SEARCH",
                    f"Ephemeral Memory: Prior investigation of {target_symbol} recorded risk {prior.get('risk')} at {prior.get('timestamp')[:19]}",
                    {"prior_target": prior.get("target"), "prior_risk": prior.get("risk"), "prior_summary": prior.get("summary")}
                )
                self._add_trace(f"Memory check: Retrieved 1 prior investigation for {target_symbol}")
        except Exception as e:
            print(f"[Orchestrator] Ephemeral memory retrieval warning: {e}")

        # 2. Definition discovery
        def_res = agent_tools.find_definition(self.repo_id, target_symbol)
        if def_res.get("success") and def_res.get("result"):
            res = def_res["result"]
            self.evidence_collector.add(
                "CODE",
                f"Definition of {target_symbol} found in {res.get('file_path')}:{res.get('line_start')}",
                {"file": res.get("file_path"), "line": res.get("line_start"), "name": target_symbol}
            )
            self._add_trace(f"Definition found in {res.get('file_path')}")

        # 3. Callers & Dependency Graph
        callers_res = agent_tools.find_callers(self.repo_id, target_symbol)
        if callers_res.get("success"):
            for caller in callers_res.get("results", []):
                self.evidence_collector.add(
                    "GRAPH",
                    f"Relationship: {caller.get('symbol')} calls {target_symbol}",
                    {"source": caller.get("symbol"), "target": target_symbol, "file": caller.get("file")}
                )
            self._add_trace(f"Analyzed callers: {len(callers_res.get('results', []))} caller(s) found")

        # 4. Impact & Risk Analysis
        impact_analysis = CodeImpactInvestigator.analyze(self.repo_id, target_symbol)
        impact: ImpactChain = impact_analysis["impact"]
        risk: RiskAssessment = impact_analysis["risk"]

        self._add_trace(f"Impact calculated: {len(impact.affected_functions)} function(s) in blast radius")
        self._add_trace(f"Risk assessed: {risk.level} ({risk.score}/100)")

        # 5. Git History & Diff
        git_res = agent_tools.get_git_history(self.repo_id, max_count=5)
        latest_commit = None
        if git_res.get("success") and git_res.get("history"):
            latest_commit = git_res["history"][0]
            c_hash = latest_commit["hash"][:7]
            c_msg = latest_commit.get("message", latest_commit.get("summary", ""))
            self.evidence_collector.add(
                "GIT",
                f"Recent Commit [{c_hash}]: {c_msg}",
                {"hash": c_hash, "author": latest_commit.get("author"), "summary": c_msg}
            )
            self._add_trace(f"Git history checked: Commit [{c_hash}] '{c_msg}'")

            diff_res = agent_tools.get_git_diff(self.repo_id, latest_commit["hash"])
            if diff_res.get("success"):
                git_diff_text = diff_res.get("diff", "")

        # 6. Test Suite Run
        test_res = agent_tools.run_tests(self.repo_id)
        test_failed_count = 0
        if test_res.get("success"):
            results = test_res["results"]
            test_failed_count = results.get("failed", 0)
            status_str = "FAILED" if test_failed_count > 0 else "PASSED"
            self.evidence_collector.add(
                "TEST",
                f"Test Suite Execution: {results.get('passed')} passed, {test_failed_count} failed",
                {"passed": results.get("passed"), "failed": test_failed_count, "exit_code": results.get("exit_code")}
            )
            self._add_trace(f"Test suite executed: {status_str} ({test_failed_count} failure(s))")

        # 7. Root Cause Determination
        if test_failed_count > 0 and "Fix:" in git_res.get("history", [{}])[0].get("summary", ""):
            status = "CONFIRMED"
            confidence = "High"
            explanation = f"Recent commit '{latest_commit['summary']}' introduced a logic regression in {target_symbol}, causing tests to fail."
        elif test_failed_count > 0:
            status = "LIKELY"
            confidence = "High"
            explanation = f"Test failure detected in test suite covering {target_symbol} and its callers ({', '.join(impact.affected_functions)})."
        else:
            status = "POSSIBLE"
            confidence = "Medium"
            explanation = f"Modifying {target_symbol} will impact downstream callers ({', '.join(impact.affected_functions)}) across {len(impact.affected_files)} files."

        root_cause = RootCause(
            status=status,
            explanation=explanation,
            confidence=confidence
        )

        self._add_trace("Investigation conclusion generated")

        response = InvestigationResponse(
            query=query,
            target=target_symbol,
            impact=impact,
            root_cause=root_cause,
            risk=risk,
            evidence=self.evidence_collector.get_all(),
            affected_files=impact.affected_files,
            affected_functions=impact.affected_functions,
            trace=self.trace
        )

        # Store in ephemeral memory safely
        try:
            from app.agent.memory import memory_manager
            memory_manager.add_investigation(response, repository_id=self.repo_id)
        except Exception as e:
            print(f"[Orchestrator] Ephemeral memory save warning: {e}")

        return response


    async def investigate_stream(self, query: str) -> AsyncGenerator[str, None]:
        """
        Streams safe investigation activity trace and final result via WebSocket.
        """
        # Run deterministic pipeline step by step for real-time trace streaming
        from app.agent.react_agent import RippleAgent

        # If LLM key is configured, run LLM-guided agent
        if os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GEMINI_API_KEY"):
            llm_agent = RippleAgent(self.repo_id)
            async for step in llm_agent.investigate(query):
                yield step
            return

        # Otherwise run deterministic mode with simulated streaming
        yield json.dumps({"type": "status", "message": "Starting evidence-backed investigation (Deterministic Mode)..."})
        await asyncio.sleep(0.3)

        response = self.run_deterministic_investigation(query)

        for step in response.trace:
            yield json.dumps({"type": "action", "message": step})
            await asyncio.sleep(0.2)

        for ev in response.evidence:
            yield json.dumps({"type": "observation", "message": f"Evidence ({ev.type}): {ev.summary}"})
            await asyncio.sleep(0.1)

        final_msg = f"Target: {response.target}\nRoot Cause ({response.root_cause.status}): {response.root_cause.explanation}\nRisk: {response.risk.level} ({response.risk.score}/100)\nImpact Chain: {' -> '.join(response.impact.chain)}"

        yield json.dumps({"type": "final", "message": final_msg})
