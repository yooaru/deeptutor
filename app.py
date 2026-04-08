#!/usr/bin/env python3
"""
PDF Tutor - Deep Learning Web Interface
Upload PDF and learn with AI tutor (using OpenAI/compatible API)
"""

import os
import json
import shutil
import base64
import io
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import pdfplumber
from PIL import Image
import openai

app = FastAPI(title="PDF Tutor", description="Learn from PDF with AI Tutor")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
KB_DIR = Path("knowledge_bases")
KB_DIR.mkdir(exist_ok=True)

# OpenAI config (can be any OpenAI-compatible API)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if OPENAI_API_KEY:
    client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
else:
    client = None

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Knowledge base storage (simple JSON-based)
def get_kb_path(kb_name: str) -> Path:
    return KB_DIR / f"{kb_name}.json"

def load_kb(kb_name: str) -> dict:
    kb_path = get_kb_path(kb_name)
    if kb_path.exists():
        with open(kb_path) as f:
            return json.load(f)
    return {"name": kb_name, "documents": [], "chunks": []}

def save_kb(kb_name: str, data: dict):
    with open(get_kb_path(kb_name), "w") as f:
        json.dump(data, f, indent=2)

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pdfplumber"""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list:
    """Simple text chunking for RAG"""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks

def get_relevant_chunks(kb_data: dict, query: str, top_k: int = 3) -> list:
    """Simple keyword-based retrieval (can be upgraded to embeddings)"""
    chunks = kb_data.get("chunks", [])
    if not chunks:
        return []
    
    # Simple scoring based on keyword overlap
    query_words = set(query.lower().split())
    scored = []
    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        score = len(query_words & chunk_words)
        scored.append((score, chunk))
    
    scored.sort(reverse=True)
    return [chunk for _, chunk in scored[:top_k]]

@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload PDF and create knowledge base"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    kb_name = file.filename.replace('.pdf', '').replace(' ', '_').lower()
    file_path = UPLOAD_DIR / f"{kb_name}.pdf"
    
    # Save file
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Extract text and create KB
    try:
        text = extract_text_from_pdf(file_path)
        chunks = chunk_text(text)
        
        kb_data = {
            "name": kb_name,
            "filename": file.filename,
            "documents": [{"path": str(file_path), "text": text[:5000]}],  # Preview only
            "chunks": chunks,
            "total_chunks": len(chunks)
        }
        save_kb(kb_name, kb_data)
        
        return JSONResponse({
            "success": True,
            "kb_name": kb_name,
            "filename": file.filename,
            "message": f"Knowledge base '{kb_name}' created with {len(chunks)} chunks",
            "preview": text[:500] + "..." if len(text) > 500 else text
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/kb/list")
async def list_knowledge_bases():
    """List all knowledge bases"""
    kbs = [f.stem for f in KB_DIR.glob("*.json")]
    return JSONResponse({"kbs": kbs})


@app.post("/api/chat")
async def chat_with_kb(
    message: str = Form(...),
    kb_name: str = Form(...),
    capability: str = Form("chat")
):
    """Chat with knowledge base using RAG"""
    kb_data = load_kb(kb_name)
    
    if not kb_data.get("chunks"):
        return JSONResponse({
            "success": False,
            "error": "Knowledge base is empty"
        })
    
    # Get relevant context
    relevant_chunks = get_relevant_chunks(kb_data, message, top_k=3)
    context = "\n\n---\n\n".join(relevant_chunks) if relevant_chunks else "No relevant context found."
    
    # Prepare system prompt based on capability
    if capability == "deep_solve":
        system_prompt = """You are a helpful tutor. Use the provided context to help solve problems step by step.
Break down complex problems into manageable steps. Show your reasoning clearly."""
    elif capability == "deep_research":
        system_prompt = """You are a research assistant. Use the provided context to give comprehensive answers.
Cite relevant sections from the context when possible."""
    else:
        system_prompt = """You are a helpful tutor. Answer questions based on the provided context.
If the context doesn't contain relevant information, say so clearly."""
    
    full_prompt = f"""Context from knowledge base:
{context}

User question: {message}

Please answer based on the context provided."""
    
    # Call LLM if available
    if client:
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
        except Exception as e:
            answer = f"Error calling LLM: {str(e)}\n\nContext retrieved:\n{context[:1000]}"
    else:
        answer = f"No LLM configured. Retrieved context:\n\n{context[:1500]}"
    
    return JSONResponse({
        "success": True,
        "response": answer,
        "context_used": len(relevant_chunks)
    })


@app.post("/api/quiz")
async def generate_quiz(
    topic: str = Form(...),
    kb_name: str = Form(...),
    num_questions: int = Form(5)
):
    """Generate quiz from knowledge base"""
    kb_data = load_kb(kb_name)
    
    if not client:
        return JSONResponse({
            "success": False,
            "quiz": "LLM not configured. Please set OPENAI_API_KEY environment variable."
        })
    
    # Get relevant context for the topic
    relevant_chunks = get_relevant_chunks(kb_data, topic, top_k=5)
    context = "\n\n---\n\n".join(relevant_chunks) if relevant_chunks else ""
    
    prompt = f"""Based on the following context, generate {num_questions} quiz questions about "{topic}".
Make the questions challenging but fair. Include multiple choice answers where appropriate.

Context:
{context}

Generate the quiz now:"""
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a quiz generator. Create clear, educational questions."},
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
            "quiz": f"Error generating quiz: {str(e)}"
        })


@app.delete("/api/kb/{kb_name}")
async def delete_kb(kb_name: str):
    """Delete knowledge base"""
    kb_path = get_kb_path(kb_name)
    pdf_path = UPLOAD_DIR / f"{kb_name}.pdf"
    
    if kb_path.exists():
        kb_path.unlink()
    if pdf_path.exists():
        pdf_path.unlink()
    
    return JSONResponse({
        "success": True,
        "message": f"Knowledge base '{kb_name}' deleted"
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
