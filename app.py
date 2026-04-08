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
try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

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

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text using pypdf (lightweight)"""
    if not PDF_AVAILABLE:
        return "[PDF text extraction not available]"
    try:
        reader = PdfReader(str(pdf_path))
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n".join(text_parts)
    except Exception as e:
        return f"[Error extracting PDF: {str(e)}]"

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

def chunk_text(text: str, chunk_size: int = 1000) -> list:
    """Simple text chunking"""
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i+chunk_size])
    return chunks

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload PDF with text extraction"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    kb_name = file.filename.replace('.pdf', '').replace(' ', '_').lower()[:50]
    file_path = UPLOAD_DIR / f"{kb_name}.pdf"
    
    try:
        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        file_size = file_path.stat().st_size
        
        # Extract text (limit to avoid OOM on huge PDFs)
        text = ""
        if file_size < 10 * 1024 * 1024:  # Only process PDFs < 10MB
            text = extract_text_from_pdf(file_path)
            # Limit text size
            if len(text) > 50000:  # Max 50k chars
                text = text[:50000] + "\n\n[Text truncated due to size limit]"
        
        chunks = chunk_text(text) if text else []
        
        kb_data = {
            "name": kb_name,
            "filename": file.filename,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024*1024), 2),
            "text": text[:5000] if text else "",  # Preview only
            "chunks": chunks,
            "total_chunks": len(chunks),
            "created": datetime.now().isoformat()
        }
        save_kb(kb_name, kb_data)
        
        return JSONResponse({
            "success": True,
            "kb_name": kb_name,
            "filename": file.filename,
            "size_mb": kb_data["size_mb"],
            "chunks": len(chunks),
            "message": f"PDF '{file.filename}' uploaded ({kb_data['size_mb']} MB, {len(chunks)} chunks)"
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

def get_relevant_chunks(kb_data: dict, query: str, top_k: int = 3) -> list:
    """Simple keyword-based retrieval"""
    chunks = kb_data.get("chunks", [])
    if not chunks:
        return []
    query_words = set(query.lower().split())
    scored = []
    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        score = len(query_words & chunk_words)
        scored.append((score, chunk))
    scored.sort(reverse=True)
    return [chunk for _, chunk in scored[:top_k]]

@app.post("/api/chat")
async def chat_with_kb(
    message: str = Form(...),
    kb_name: str = Form(...),
    capability: str = Form("chat")
):
    """Chat with AI using PDF context"""
    kb_data = load_kb(kb_name)
    
    # Get relevant context from PDF
    relevant_chunks = get_relevant_chunks(kb_data, message, top_k=3)
    context = "\n\n---\n\n".join(relevant_chunks) if relevant_chunks else "No PDF context available."
    
    if capability == "deep_solve":
        system_prompt = """You are a helpful tutor. Use the provided PDF context to solve problems step by step.
Break down complex problems clearly."""
    elif capability == "deep_research":
        system_prompt = """You are a research assistant. Use the provided PDF context for comprehensive answers."""
    else:
        system_prompt = """You are a helpful tutor. Answer based on the provided PDF context.
If context is insufficient, say so clearly."""
    
    full_prompt = f"""PDF Context:
{context}

User Question: {message}

Answer based on the context above:"""
    
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
            "context_used": len(relevant_chunks)
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
