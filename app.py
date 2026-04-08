#!/usr/bin/env python3
"""
PDF Tutor - Light Version (No PDF extraction, no heavy deps)
Upload PDF metadata and chat with AI
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import openai

app = FastAPI(title="PDF Tutor Light", description="Upload PDF and chat with AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
KB_DIR = Path("knowledge_bases")
KB_DIR.mkdir(exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if OPENAI_API_KEY:
    client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
else:
    client = None

app.mount("/static", StaticFiles(directory="static"), name="static")

def get_kb_path(kb_name: str) -> Path:
    return KB_DIR / f"{kb_name}.json"

def load_kb(kb_name: str) -> dict:
    kb_path = get_kb_path(kb_name)
    if kb_path.exists():
        with open(kb_path) as f:
            return json.load(f)
    return {"name": kb_name, "filename": "", "notes": "", "created": ""}

def save_kb(kb_name: str, data: dict):
    with open(get_kb_path(kb_name), "w") as f:
        json.dump(data, f, indent=2)

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload PDF - light version, only metadata"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    kb_name = file.filename.replace('.pdf', '').replace(' ', '_').lower()[:50]
    file_path = UPLOAD_DIR / f"{kb_name}.pdf"
    
    try:
        # Save file (stream directly, no read into memory)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Get file size
        file_size = file_path.stat().st_size
        
        # Save metadata only (no PDF text extraction)
        kb_data = {
            "name": kb_name,
            "filename": file.filename,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024*1024), 2),
            "notes": "",
            "created": datetime.now().isoformat()
        }
        save_kb(kb_name, kb_data)
        
        return JSONResponse({
            "success": True,
            "kb_name": kb_name,
            "filename": file.filename,
            "size_mb": kb_data["size_mb"],
            "message": f"PDF '{file.filename}' uploaded ({kb_data['size_mb']} MB)"
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.get("/api/kb/list")
async def list_knowledge_bases():
    kbs = [f.stem for f in KB_DIR.glob("*.json")]
    return JSONResponse({"kbs": kbs})

@app.post("/api/chat")
async def chat_with_kb(
    message: str = Form(...),
    kb_name: str = Form(...),
    capability: str = Form("chat")
):
    """Chat with AI (no PDF context in light version)"""
    kb_data = load_kb(kb_name)
    
    # Build prompt based on capability
    if capability == "deep_solve":
        system_prompt = """You are a helpful tutor. Solve problems step by step.
Show your reasoning clearly. If this is a math problem, show all steps."""
    elif capability == "deep_research":
        system_prompt = """You are a research assistant. Give comprehensive answers with examples."""
    else:
        system_prompt = """You are a helpful tutor. Answer questions clearly and helpfully.
You can reference that the user has uploaded a PDF for context, but work with general knowledge."""
    
    user_context = f"User uploaded PDF: {kb_data.get('filename', 'Unknown')}. " if kb_data.get('filename') else ""
    full_prompt = f"{user_context}Question: {message}"
    
    if not client:
        return JSONResponse({
            "success": False,
            "error": "AI not configured. Set OPENAI_API_KEY."
        })
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        answer = response.choices[0].message.content
        
        return JSONResponse({
            "success": True,
            "response": answer,
            "pdf_context": kb_data.get('filename', '')
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        })

@app.post("/api/quiz")
async def generate_quiz(
    topic: str = Form(...),
    kb_name: str = Form(...),
    num_questions: int = Form(5)
):
    if not client:
        return JSONResponse({
            "success": False,
            "quiz": "AI not configured."
        })
    
    kb_data = load_kb(kb_name)
    pdf_info = f"Based on PDF: {kb_data.get('filename', 'Unknown')}. " if kb_data.get('filename') else ""
    
    prompt = f"""{pdf_info}Generate {num_questions} quiz questions about "{topic}".
Make them challenging but educational. Include answers."""
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a quiz generator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=2500
        )
        quiz = response.choices[0].message.content
        
        return JSONResponse({
            "success": True,
            "quiz": quiz
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "quiz": f"Error: {str(e)}"
        })

@app.delete("/api/kb/{kb_name}")
async def delete_kb(kb_name: str):
    kb_path = get_kb_path(kb_name)
    pdf_path = UPLOAD_DIR / f"{kb_name}.pdf"
    
    if kb_path.exists():
        kb_path.unlink()
    if pdf_path.exists():
        pdf_path.unlink()
    
    return JSONResponse({
        "success": True,
        "message": f"Deleted '{kb_name}'"
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
