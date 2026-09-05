from google import genai
from google.genai import types
import json
from app.tools import agent_tools
from app.agent.prompts import SYSTEM_PROMPT
import os
from typing import AsyncGenerator

class RippleAgent:
    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        # Will fail if GEMINI_API_KEY is not set, which is fine
        self.client = genai.Client()
        self.model = "gemini-2.5-pro"
        
        # Define available tools
        self.tools = [
            self._wrap_tool(agent_tools.search_code, "search_code", "Search the codebase for a query string.", {"query": {"type": "STRING"}, "context_lines": {"type": "INTEGER"}}),
            self._wrap_tool(agent_tools.read_file, "read_file", "Read a file from the repository.", {"file_path": {"type": "STRING"}, "start_line": {"type": "INTEGER"}, "end_line": {"type": "INTEGER"}}),
            self._wrap_tool(agent_tools.find_definition, "find_definition", "Find the definition of a symbol.", {"symbol_name": {"type": "STRING"}}),
            self._wrap_tool(agent_tools.find_callers, "find_callers", "Find callers of a symbol.", {"symbol_name": {"type": "STRING"}}),
            self._wrap_tool(agent_tools.find_dependencies, "find_dependencies", "Find dependencies of a symbol.", {"symbol_name": {"type": "STRING"}}),
            self._wrap_tool(agent_tools.get_git_diff, "get_git_diff", "Get the git diff for a commit.", {"commit_hash": {"type": "STRING"}}),
            self._wrap_tool(agent_tools.get_commit, "get_commit", "Get info about a commit.", {"commit_hash": {"type": "STRING"}}),
            self._wrap_tool(agent_tools.find_tests, "find_tests", "Find tests related to a symbol.", {"target_symbol": {"type": "STRING"}}),
            self._wrap_tool(agent_tools.run_tests, "run_tests", "Run tests.", {"test_target": {"type": "STRING"}})
        ]
        
        # Tools map for execution
        self._tool_map = {
            "search_code": agent_tools.search_code,
            "read_file": agent_tools.read_file,
            "find_definition": agent_tools.find_definition,
            "find_callers": agent_tools.find_callers,
            "find_dependencies": agent_tools.find_dependencies,
            "get_git_diff": agent_tools.get_git_diff,
            "get_commit": agent_tools.get_commit,
            "find_tests": agent_tools.find_tests,
            "run_tests": agent_tools.run_tests
        }

    def _wrap_tool(self, func, name, description, properties):
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=name,
                    description=description,
                    parameters=types.Schema(
                        type="OBJECT",
                        properties=properties
                    )
                )
            ]
        )

    async def investigate(self, prompt: str) -> AsyncGenerator[str, None]:
        chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=self.tools,
                temperature=0.0
            )
        )
        
        yield json.dumps({"type": "status", "message": "Starting investigation..."})
        
        current_prompt = prompt
        
        for _ in range(15): # Max 15 steps
            response = chat.send_message(current_prompt)
            
            if response.text:
                yield json.dumps({"type": "thought", "message": response.text})
                
            if not response.function_calls:
                yield json.dumps({"type": "final", "message": response.text})
                break
                
            for call in response.function_calls:
                tool_name = call.name
                args = call.args
                yield json.dumps({"type": "action", "message": f"Calling tool {tool_name} with args {args}"})
                
                try:
                    # Execute tool
                    func = self._tool_map[tool_name]
                    # inject repo_id
                    kwargs = dict(args)
                    result = func(repo_id=self.repo_id, **kwargs)
                except Exception as e:
                    result = {"error": str(e)}
                    
                yield json.dumps({"type": "observation", "message": f"Result from {tool_name} received."})
                
                # Send result back
                current_prompt = types.Part.from_function_response(
                    name=tool_name,
                    response=result
                )
