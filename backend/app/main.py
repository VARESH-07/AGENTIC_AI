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
