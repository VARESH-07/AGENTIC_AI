from typing import List, Dict, Any, Optional
from app.tools.agent_tools import _build_graph, _find_symbol_id, _get_repo_path, get_git_history, find_tests, run_tests
from app.models.schemas import ImpactChain, RiskAssessment

class CodeImpactInvestigator:
    @staticmethod
    def analyze(repo_id: str, target_symbol: str) -> Dict[str, Any]:
        """
        Calculates deterministic impact chain and risk assessment for a given symbol.
        """
        graph = _build_graph(repo_id)
        sym_id = _find_symbol_id(graph, target_symbol)
        
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
