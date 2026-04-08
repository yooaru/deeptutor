#!/usr/bin/env python3
"""
PDF Tutor - DeepTutor Web Interface
Upload PDF and learn with AI tutor
"""

import os
import subprocess
import json
import shutil
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="PDF Tutor", description="Learn from PDF with DeepTutor")

# CORS untuk development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")


def run_deeptutor(cmd: list) -> tuple:
    """Run deeptutor CLI command and return (stdout, stderr, returncode)"""
    try:
        result = subprocess.run(
            ["deeptutor"] + cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd="/home/ubuntu/.openclaw/workspace"
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    except Exception as e:
        return "", str(e), 1


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload PDF and create knowledge base"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    # Save file
    kb_name = file.filename.replace('.pdf', '').replace(' ', '_').lower()
    file_path = UPLOAD_DIR / f"{kb_name}.pdf"
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Create knowledge base with DeepTutor
    stdout, stderr, rc = run_deeptutor([
        "kb", "create", kb_name,
        "--doc", str(file_path)
    ])
    
    if rc != 0 and "already exists" not in stderr:
        # Try to add if already exists
        stdout2, stderr2, rc2 = run_deeptutor([
            "kb", "add", kb_name,
            "--doc", str(file_path)
        ])
        if rc2 != 0:
            return JSONResponse({
                "success": False,
                "error": stderr or stderr2,
                "kb_name": kb_name
            })
    
    return JSONResponse({
        "success": True,
        "kb_name": kb_name,
        "filename": file.filename,
        "message": f"Knowledge base '{kb_name}' created"
    })


@app.get("/api/kb/list")
async def list_knowledge_bases():
    """List all knowledge bases"""
    stdout, stderr, rc = run_deeptutor(["kb", "list"])
    
    if rc != 0:
        return JSONResponse({"kbs": [], "error": stderr})
    
    # Parse output
    kbs = []
    for line in stdout.strip().split('\n'):
        if line and not line.startswith('-'):
            kbs.append(line.strip())
    
    return JSONResponse({"kbs": kbs})


@app.post("/api/chat")
async def chat_with_kb(
    message: str = Form(...),
    kb_name: str = Form(...),
    capability: str = Form("chat")
):
    """Chat with knowledge base"""
    # Use deeptutor run with the knowledge base
    stdout, stderr, rc = run_deeptutor([
        "run", capability, message,
        "--kb", kb_name,
        "--tool", "rag",
        "--format", "json"
    ])
    
    if rc != 0:
        return JSONResponse({
            "success": False,
            "error": stderr or stdout
        })
    
    # Try to parse JSON response
    try:
        response_data = json.loads(stdout)
        return JSONResponse({
            "success": True,
            "response": response_data.get("response", stdout),
            "raw": stdout
        })
    except json.JSONDecodeError:
        return JSONResponse({
            "success": True,
            "response": stdout,
            "raw": stdout
        })


@app.post("/api/solve")
async def deep_solve(
    problem: str = Form(...),
    kb_name: str = Form(None),
    image: UploadFile = File(None)
):
    """Deep solve a problem (text or image)"""
    cmd = ["run", "deep_solve", problem, "--tool", "reason"]
    
    if kb_name:
        cmd.extend(["--kb", kb_name, "--tool", "rag"])
    
    stdout, stderr, rc = run_deeptutor(cmd)
    
    return JSONResponse({
        "success": rc == 0,
        "solution": stdout if rc == 0 else stderr
    })


@app.post("/api/quiz")
async def generate_quiz(
    topic: str = Form(...),
    kb_name: str = Form(...),
    num_questions: int = Form(5)
):
    """Generate quiz from knowledge base"""
    stdout, stderr, rc = run_deeptutor([
        "run", "deep_question", topic,
        "--kb", kb_name,
        "--config", f"num_questions={num_questions}",
        "--tool", "rag"
    ])
    
    return JSONResponse({
        "success": rc == 0,
        "quiz": stdout if rc == 0 else stderr
    })


@app.delete("/api/kb/{kb_name}")
async def delete_kb(kb_name: str):
    """Delete knowledge base"""
    stdout, stderr, rc = run_deeptutor(["kb", "delete", kb_name, "--force"])
    
    return JSONResponse({
        "success": rc == 0,
        "message": stdout if rc == 0 else stderr
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
