import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Automatically load .env file if present
def _load_env():
    for env_path in [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
    ]:
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip("'\"")

_load_env()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import repositories, investigation
from app.database.connection import DBConnection
import os

app = FastAPI(title="Ripple AI Backend API", version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(repositories.router, prefix="/api/v1")
app.include_router(investigation.router, prefix="/api/v1")

@app.on_event("startup")
def startup_event():
    # Initialize SQLite database
    DBConnection.init_db()

@app.get("/")
def read_root():
    return {"message": "Welcome to Ripple AI Backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
