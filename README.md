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

App ini menggunakan `deeptutor` CLI untuk:
- Knowledge base management
- RAG (Retrieval Augmented Generation)
- Deep solve & quiz generation

Pastikan DeepTutor sudah terinstall:
```bash
pip install deeptutor
```

## License

MIT
