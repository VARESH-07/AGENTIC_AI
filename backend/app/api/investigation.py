from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import os
from app.models.schemas import InvestigationRequest, InvestigationResponse
from app.agent.orchestrator import RippleOrchestrator
from app.database.connection import DBConnection

router = APIRouter()

@router.post("/investigate", response_model=InvestigationResponse)
def post_investigate(req: InvestigationRequest):
    from app.main import _load_env
    _load_env()

    repo_id = req.repository_id or req.repository

    if not repo_id:
        # Fetch default/first registered repository if none provided
        conn = DBConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM repositories LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            repo_id = row["id"]
        else:
            raise HTTPException(status_code=400, detail="No repository registered. Please register a repository first.")

    orchestrator = RippleOrchestrator(repo_id)
    return orchestrator.run_deterministic_investigation(req.query)

@router.websocket("/investigate/{repo_id}")
async def investigate(websocket: WebSocket, repo_id: str):
    await websocket.accept()
    from app.main import _load_env
    _load_env()

    orchestrator = RippleOrchestrator(repo_id)

    try:
        while True:
            data = await websocket.receive_text()
            async for step in orchestrator.investigate_stream(data):
                await websocket.send_text(step)
    except WebSocketDisconnect:
        print(f"Client disconnected for repo {repo_id}")
    except Exception as e:
        print(f"Error during investigation: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass

