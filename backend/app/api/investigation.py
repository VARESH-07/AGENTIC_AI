from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agent.react_agent import RippleAgent
import os

router = APIRouter()

@router.websocket("/investigate/{repo_id}")
async def investigate(websocket: WebSocket, repo_id: str):
    await websocket.accept()
    if not os.environ.get("GEMINI_API_KEY"):
        await websocket.send_json({"type": "error", "message": "GEMINI_API_KEY environment variable is not set."})
        await websocket.close()
        return
        
    try:
        agent = RippleAgent(repo_id)
        while True:
            data = await websocket.receive_text()
            async for step in agent.investigate(data):
                await websocket.send_text(step)
    except WebSocketDisconnect:
        print(f"Client disconnected for repo {repo_id}")
    except Exception as e:
        print(f"Error during investigation: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
