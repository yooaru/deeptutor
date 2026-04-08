# 📚 DeepTutor Web App

PDF-based learning platform dengan AI Tutor. Upload materi PDF dan belajar dengan bantuan AI.

## Fitur

| Fitur | Deskripsi |
|-------|-----------|
| 📄 **Upload PDF** | Upload materi → auto jadi knowledge base |
| 💬 **Chat** | Tanya tentang materi dengan AI Tutor |
| 🧮 **Deep Solve** | Solver masalah step-by-step |
| 🔍 **Deep Research** | Research dari knowledge base |
| 📝 **Quiz Generator** | Generate soal dari materi |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python app.py

# Buka browser
goto http://localhost:8001
```

## API Endpoints

| Endpoint | Method | Deskripsi |
|----------|--------|-----------|
| `/` | GET | Web UI |
| `/api/upload` | POST | Upload PDF |
| `/api/kb/list` | GET | List knowledge bases |
| `/api/chat` | POST | Chat dengan KB |
| `/api/quiz` | POST | Generate quiz |
| `/api/kb/{name}` | DELETE | Hapus KB |

## DeepTutor Integration

App menggunakan RAG sederhana dengan:
- PyMuPDF untuk extract text dari PDF
- Keyword-based retrieval
- OpenAI API untuk chat & quiz generation

Setup environment variables di Render:
```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1  # atau OpenRouter, dll
OPENAI_MODEL=gpt-4o-mini
```

## License

MIT
