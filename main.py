### --- main.py --- ###

import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv()

# Import your main agent function
from solver.agent import run_quiz_solver_background

app = FastAPI(
    title="LLM Analysis Quiz Agent",
    description="This API endpoint receives quiz tasks and solves them."
)

# Load required variables
MY_SECRET = os.environ.get("MY_SECRET")
MY_EMAIL = os.environ.get("MY_EMAIL")

if not MY_SECRET or not MY_EMAIL:
    print("FATAL ERROR: MY_SECRET or MY_EMAIL not found in environment.")
    # In a real app, you'd exit, but FastAPI will just fail to start
    #
    
# --- Pydantic Models ---
class QuizPayload(BaseModel):
    email: str
    secret: str
    url: str
    # We can add ... to allow other fields
    class Config:
        extra = "allow"

class APIResponse(BaseModel):
    status: str
    message: str


# --- API Endpoint ---
@app.post("/quiz-endpoint", response_model=APIResponse)
async def start_quiz(payload: QuizPayload, background_tasks: BackgroundTasks):
    """
    Receives the initial quiz task, validates it, and starts
    the solver in a background task.
    """
    
    # 1. Validate Secret
    if payload.secret != MY_SECRET:
        print(f"Invalid secret attempt: {payload.secret}")
        raise HTTPException(
            status_code=403, 
            detail="Invalid secret provided."
        )

    # 2. Validate Email
    if payload.email != MY_EMAIL:
        print(f"Invalid email attempt: {payload.email}")
        raise HTTPException(
            status_code=403, 
            detail="Invalid email provided."
        )

    # 3. Add the *actual* work as a background task
    print(f"Task accepted for {payload.email}, URL: {payload.url}")
    background_tasks.add_task(
        run_quiz_solver_background,
        payload.email,
        payload.secret,
        payload.url
    )
    
    # 4. Respond 200 OK *immediately*
    return {
        "status": "accepted",
        "message": "Quiz task accepted and is processing in the background."
    }

@app.get("/")
async def root():
    return {"message": "LLM Quiz Agent is running. POST to /quiz-endpoint to start."}