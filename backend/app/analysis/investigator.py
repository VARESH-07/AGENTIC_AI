from typing import List, Dict, Any, Optional
from app.tools.agent_tools import _build_graph, _find_symbol_id, _get_repo_path, get_git_history, find_tests, run_tests
from app.models.schemas import ImpactChain, RiskAssessment

class CodeImpactInvestigator:
    @staticmethod
    def analyze(repo_id: str, target_symbol: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates deterministic function impact chain and risk assessment for a given symbol in a specific repository.
        """
        # Validate repo exists
        _get_repo_path(repo_id)

        graph = _build_graph(repo_id)
        
        sym_id = None
        if file_path:
            for node_id, data in graph.graph.nodes(data=True):
                if (data.get("qualified_name") == target_symbol or data.get("name") == target_symbol) and data.get("file_path") == file_path:
                    sym_id = node_id
                    break
        if not sym_id:
            sym_id = _find_symbol_id(graph, target_symbol)

        # Ensure target symbol actually exists in the selected repository
        if not sym_id and not any(data.get("name") == target_symbol or data.get("qualified_name") == target_symbol for _, data in graph.graph.nodes(data=True)):
            raise ValueError("Target not found in selected repository.")

        affected_functions = set()
        affected_files = set()
        chain = []
        
        if sym_id and sym_id in graph.graph.nodes:
            target_data = graph.graph.nodes[sym_id]
            target_file = target_data.get("file_path", "")
            target_name = target_data.get("name", target_symbol)
            
            affected_functions.add(target_name)
            if target_file:
                affected_files.add(target_file)
            chain.append(target_name)
            
            # BFS on incoming edges (who depends on/calls target)
            visited = set([sym_id])
            queue = [(sym_id, [target_name])]
            
            longest_chain = [target_name]
            
            while queue:
                curr_id, curr_path = queue.pop(0)
                if len(curr_path) > len(longest_chain):
                    longest_chain = curr_path
                    
                for src, tgt, data in graph.graph.in_edges(curr_id, data=True):
                    if data.get("type") in ["CALLS", "DEPENDS_ON", "IMPORTS", "TESTS"]:
                        if src not in visited:
                            visited.add(src)
                            node_data = graph.graph.nodes[src]
                            s_name = node_data.get("name", src)
                            s_file = node_data.get("file_path", "")
                            
                            affected_functions.add(s_name)
                            if s_file:
                                affected_files.add(s_file)
                                
                            new_path = curr_path + [s_name]
                            queue.append((src, new_path))
                            
            chain = longest_chain
        else:
            chain = [target_symbol]
            affected_functions.add(target_symbol)
            
        # Get tests
        tests_result = find_tests(repo_id, target_symbol)
        test_list = tests_result.get("results", []) if tests_result.get("success") else []
        
        # Calculate Risk Assessment
        reasons = []
        score = 0
        
        fn_count = len(affected_functions)
        file_count = len(affected_files)
        
        if fn_count > 1:
            score += min(fn_count * 15, 45)
            reasons.append(f"{fn_count} dependent functions in impact path")
            
        if file_count > 1:
            score += min(file_count * 10, 30)
            reasons.append(f"{file_count} affected files in repository")
            
        # Check for API endpoints/controllers in impact path
        api_endpoints = [fn for fn in affected_functions if "controller" in fn.lower() or "endpoint" in fn.lower() or "route" in fn.lower() or "api" in fn.lower()]
        if api_endpoints:
            score += 25
            reasons.append(f"API entrypoint affected: {', '.join(api_endpoints)}")
            
        if test_list:
            score += 15
            reasons.append(f"{len(test_list)} tests cover the affected code paths")
            
        # Check Git history for recent commit touching target
        try:
            history = get_git_history(repo_id, max_count=5)
            if history.get("success") and history.get("history"):
                score += 15
                reasons.append(f"Recent Git commit '{history['history'][0]['summary']}' modified the codebase")
        except:
            pass

        if score >= 70:
            level = "CRITICAL"
        elif score >= 45:
            level = "HIGH"
        elif score >= 25:
            level = "MEDIUM"
        else:
            level = "LOW"
            if not reasons:
                reasons.append("Single isolated function with no external caller dependencies")

        impact_chain = ImpactChain(
            target=target_symbol,
            chain=chain,
            affected_functions=sorted(list(affected_functions)),
            affected_files=sorted(list(affected_files))
        )
        
        risk = RiskAssessment(
            level=level,
            score=score,
            reasons=reasons
        )
        
        return {
            "impact": impact_chain,
            "risk": risk,
            "tests": test_list
        }

    @staticmethod
    def analyze_ripple_impact(repo_id: str, target_module: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates Ripple Impact Analysis for a MODULE/FILE node in the given repository.
        Analyzes module dependencies, dependents, affected modules, functions, tests, and impact chain.
        """
        repo_path = _get_repo_path(repo_id)

        # Get repo name from database
        from app.database.connection import DBConnection
        conn = DBConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM repositories WHERE id = ?", (repo_id,))
        row = cursor.fetchone()
        conn.close()
        repo_name = row["name"] if row else repo_id

        graph = _build_graph(repo_id)

        # Locate all nodes/symbols belonging to or representing target_module/file_path
        target_clean = target_module.replace("\\", "/")
        target_base = target_clean.split("/")[-1]

        module_nodes = []
        file_symbols = []

        for node_id, data in graph.graph.nodes(data=True):
            n_file = (data.get("file_path") or "").replace("\\", "/")
            n_name = data.get("name") or ""
            n_qname = data.get("qualified_name") or ""
            n_type = data.get("type", "")

            # Match by module/file node or by file path
            if (n_type in ["FILE", "MODULE", "PACKAGE"] and (n_name == target_module or n_name == target_base or n_file == target_clean or n_file.endswith(target_base))) \
               or (n_file == target_clean or n_file.endswith(target_base) or (file_path and n_file == file_path.replace("\\", "/"))):
                module_nodes.append((node_id, data))
                if n_type != "FILE":
                    file_symbols.append((node_id, data))

        if not module_nodes and not file_symbols:
            raise ValueError("Target not found in selected repository.")

        # Identify target module display name and target file path
        primary_file = None
        for _, data in module_nodes:
            if data.get("file_path"):
                primary_file = data.get("file_path")
                break
        
        display_module = primary_file.replace("\\", "/").split("/")[-1] if primary_file else target_base

        # Collect symbols contained within target module
        target_symbol_ids = set()
        for node_id, data in graph.graph.nodes(data=True):
            n_file = (data.get("file_path") or "").replace("\\", "/")
            if primary_file and n_file == primary_file.replace("\\", "/"):
                target_symbol_ids.add(node_id)
            elif n_file.endswith(target_base):
                target_symbol_ids.add(node_id)
            elif node_id in [m[0] for m in module_nodes]:
                target_symbol_ids.add(node_id)

        affected_modules = set([display_module])
        affected_functions = set()
        impact_chain = [display_module]

        # Populate functions inside target module
        for sym_id in target_symbol_ids:
            data = graph.graph.nodes[sym_id]
            if data.get("type") in ["FUNCTION", "METHOD", "CLASS"]:
                affected_functions.add(data.get("name", sym_id))

        # BFS on incoming edges to target module or its symbols to find dependent modules and downstream impact
        visited = set(target_symbol_ids)
        queue = []
        for sym_id in target_symbol_ids:
            queue.append((sym_id, [display_module]))

        longest_chain = [display_module]

        while queue:
            curr_id, curr_path = queue.pop(0)
            if len(curr_path) > len(longest_chain):
                longest_chain = curr_path

            for src, tgt, data in graph.graph.in_edges(curr_id, data=True):
                if data.get("type") in ["CALLS", "DEPENDS_ON", "IMPORTS", "TESTS"]:
                    if src not in visited:
                        visited.add(src)
                        src_data = graph.graph.nodes[src]
                        s_name = src_data.get("name", src)
                        s_file = (src_data.get("file_path") or "").replace("\\", "/")
                        s_mod = s_file.split("/")[-1] if s_file else s_name

                        if s_mod:
                            affected_modules.add(s_mod)
                        if src_data.get("type") in ["FUNCTION", "METHOD", "CLASS"]:
                            affected_functions.add(s_name)

                        new_path = curr_path + [s_mod or s_name]
                        queue.append((src, new_path))

        impact_chain = longest_chain

        # Discover tests for this module
        tests_res = find_tests(repo_id, target_symbol=display_module)
        affected_tests = []
        if tests_res.get("success") and tests_res.get("results"):
            for t in tests_res["results"]:
                t_name = t.get("name") or t.get("file") or str(t)
                affected_tests.append(t_name)

        # Risk Assessment calculation
        reasons = []
        score = 0

        mod_count = len(affected_modules)
        fn_count = len(affected_functions)

        if mod_count > 1:
            score += min((mod_count - 1) * 20, 40)
            reasons.append(f"{mod_count - 1} dependent module(s) rely on {display_module}")
        else:
            reasons.append(f"Isolated module with no external module dependents")

        if fn_count > 0:
            score += min(fn_count * 5, 25)
            reasons.append(f"{fn_count} function(s) affected across module scope")

        # Check for controller/api/route in affected modules
        api_mods = [m for m in affected_modules if any(k in m.lower() for k in ["api", "route", "controller", "endpoint"])]
        if api_mods:
            score += 25
            reasons.append(f"API/Controller module(s) affected: {', '.join(api_mods)}")

        if affected_tests:
            score += 10
            reasons.append(f"{len(affected_tests)} test(s) cover this module scope")

        if score >= 70:
            risk_level = "CRITICAL"
        elif score >= 45:
            risk_level = "HIGH"
        elif score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "analysis_type": "ripple",
            "repository_id": repo_id,
            "repository": repo_name,
            "target_module": display_module,
            "affected_modules": sorted(list(affected_modules)),
            "affected_functions": sorted(list(affected_functions)),
            "affected_tests": sorted(list(affected_tests)),
            "impact_chain": impact_chain,
            "risk": risk_level,
            "risk_score": score,
            "reasons": reasons,
            "reason": reasons[0] if reasons else "Single isolated module"
        }

