import os
import json
import asyncio
from typing import AsyncGenerator
from app.tools import agent_tools
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.session import session_key_manager

OPENROUTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search the codebase for a query string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "context_lines": {"type": "integer", "description": "Number of context lines"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative file path"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_definition",
            "description": "Find definition of a symbol.",
            "parameters": {
                "type": "object",
                "properties": {"symbol_name": {"type": "string"}},
                "required": ["symbol_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_callers",
            "description": "Find callers of a symbol.",
            "parameters": {
                "type": "object",
                "properties": {"symbol_name": {"type": "string"}},
                "required": ["symbol_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_dependencies",
            "description": "Find dependencies of a symbol.",
            "parameters": {
                "type": "object",
                "properties": {"symbol_name": {"type": "string"}},
                "required": ["symbol_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_git_diff",
            "description": "Get git diff for a commit.",
            "parameters": {
                "type": "object",
                "properties": {"commit_hash": {"type": "string"}},
                "required": ["commit_hash"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_commit",
            "description": "Get info about a commit.",
            "parameters": {
                "type": "object",
                "properties": {"commit_hash": {"type": "string"}},
                "required": ["commit_hash"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_tests",
            "description": "Find tests related to a symbol.",
            "parameters": {
                "type": "object",
                "properties": {"target_symbol": {"type": "string"}},
                "required": ["target_symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run tests.",
            "parameters": {
                "type": "object",
                "properties": {"test_target": {"type": "string"}}
            }
        }
    }
]

class RippleAgent:
    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        
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

    async def _investigate_openrouter(self, prompt: str) -> AsyncGenerator[str, None]:
        import httpx
        api_key = session_key_manager.get_api_key()
        if not api_key:
            yield json.dumps({"type": "error", "message": "OpenRouter API key is not configured for this session."})
            return

        model = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        
        yield json.dumps({"type": "status", "message": f"Starting investigation with OpenRouter ({model})..."})
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        async with httpx.AsyncClient(timeout=90.0) as http_client:
            for _ in range(15):
                payload = {
                    "model": model,
                    "messages": messages,
                    "tools": OPENROUTER_TOOLS,
                    "temperature": 0.0
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://ripple.ai",
                    "X-Title": "Ripple AI Code Impact Analyzer & Investigator",
                    "Content-Type": "application/json"
                }
                
                resp = None
                for attempt in range(4):
                    try:
                        r = await http_client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
                        if r.status_code == 200:
                            resp = r.json()
                            break
                        elif r.status_code in (401, 403):
                            yield json.dumps({"type": "error", "message": "OpenRouter API key is invalid or was rejected."})
                            return
                        elif r.status_code in (429, 503, 502):
                            yield json.dumps({"type": "thought", "message": f"OpenRouter busy/rate-limited ({r.status_code}). Retrying in {(attempt+1)*3}s..."})
                            await asyncio.sleep(3 * (attempt + 1))
                        else:
                            yield json.dumps({"type": "error", "message": f"OpenRouter Error ({r.status_code}): {r.text}"})
                            return
                    except Exception as err:
                        if attempt < 3:
                            await asyncio.sleep(2 * (attempt + 1))
                        else:
                            yield json.dumps({"type": "error", "message": f"OpenRouter Network Error: {err}"})
                            return

                if not resp or not resp.get("choices"):
                    yield json.dumps({"type": "error", "message": "No response returned from OpenRouter."})
                    return

                msg = resp["choices"][0]["message"]
                messages.append(msg)

                content = msg.get("content")
                if content:
                    yield json.dumps({"type": "thought", "message": content})

                tool_calls = msg.get("tool_calls")
                if not tool_calls:
                    if content:
                        yield json.dumps({"type": "final", "message": content})
                    break

                for call in tool_calls:
                    fn = call["function"]
                    tool_name = fn["name"]
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except:
                        args = {}
                    
                    yield json.dumps({"type": "action", "message": f"Calling tool {tool_name} with args {args}"})

                    try:
                        func = self._tool_map[tool_name]
                        result = func(repo_id=self.repo_id, **args)
                    except Exception as e:
                        result = {"error": str(e)}

                    yield json.dumps({"type": "observation", "message": f"Result from {tool_name} received."})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result)
                    })

    async def _investigate_gemini(self, prompt: str) -> AsyncGenerator[str, None]:
        from google import genai
        from google.genai import types
        
        client = genai.Client()
        model = "gemini-flash-latest"
        
        tools = [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(name="search_code", description="Search code", parameters=types.Schema(type="OBJECT", properties={"query": {"type": "STRING"}, "context_lines": {"type": "INTEGER"}})),
                types.FunctionDeclaration(name="read_file", description="Read file", parameters=types.Schema(type="OBJECT", properties={"file_path": {"type": "STRING"}, "start_line": {"type": "INTEGER"}, "end_line": {"type": "INTEGER"}})),
                types.FunctionDeclaration(name="find_definition", description="Find def", parameters=types.Schema(type="OBJECT", properties={"symbol_name": {"type": "STRING"}})),
                types.FunctionDeclaration(name="find_callers", description="Find callers", parameters=types.Schema(type="OBJECT", properties={"symbol_name": {"type": "STRING"}})),
                types.FunctionDeclaration(name="find_dependencies", description="Find deps", parameters=types.Schema(type="OBJECT", properties={"symbol_name": {"type": "STRING"}})),
                types.FunctionDeclaration(name="get_git_diff", description="Get diff", parameters=types.Schema(type="OBJECT", properties={"commit_hash": {"type": "STRING"}})),
                types.FunctionDeclaration(name="get_commit", description="Get commit", parameters=types.Schema(type="OBJECT", properties={"commit_hash": {"type": "STRING"}})),
                types.FunctionDeclaration(name="find_tests", description="Find tests", parameters=types.Schema(type="OBJECT", properties={"target_symbol": {"type": "STRING"}})),
                types.FunctionDeclaration(name="run_tests", description="Run tests", parameters=types.Schema(type="OBJECT", properties={"test_target": {"type": "STRING"}}))
            ])
        ]
        
        chat = client.chats.create(model=model, config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=tools, temperature=0.0))
        yield json.dumps({"type": "status", "message": "Starting investigation with Gemini..."})
        
        current_prompt = prompt
        for _ in range(15):
            response = None
            for attempt in range(6):
                try:
                    response = chat.send_message(current_prompt)
                    break
                except Exception as err:
                    err_str = str(err)
                    if ("503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str or "EXHAUSTED" in err_str or "Quota" in err_str) and attempt < 5:
                        yield json.dumps({"type": "thought", "message": f"Gemini busy/rate limited. Retrying in {(attempt+1)*3}s..."})
                        await asyncio.sleep(3 * (attempt + 1))
                    else:
                        yield json.dumps({"type": "error", "message": f"Gemini Error: {err_str}"})
                        return

            if not response:
                break

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
                    func = self._tool_map[tool_name]
                    kwargs = dict(args)
                    result = func(repo_id=self.repo_id, **kwargs)
                except Exception as e:
                    result = {"error": str(e)}

                yield json.dumps({"type": "observation", "message": f"Result from {tool_name} received."})
                current_prompt = types.Part.from_function_response(name=tool_name, response=result)

    async def investigate(self, prompt: str) -> AsyncGenerator[str, None]:
        if session_key_manager.is_configured():
            async for step in self._investigate_openrouter(prompt):
                yield step
        elif os.environ.get("GEMINI_API_KEY"):
            async for step in self._investigate_gemini(prompt):
                yield step
        else:
            yield json.dumps({"type": "error", "message": "OpenRouter API key is not configured for this session."})
