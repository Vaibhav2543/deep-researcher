# Deep Researcher Agent

**Deep Researcher Agent** — a hackathon project that lets you upload documents (PDF, DOCX, CSV, TXT) and ask semantic questions.  
Backend: FastAPI (semantic index + Ollama / local fallback).  
Frontend: React + Vite + Tailwind + Framer Motion.

---

## Features
- Upload documents (PDF, DOCX, CSV, TXT) for indexing.
- Background indexing (upload returns immediately).
- Semantic search using embeddings + FAISS (or file-based fallback).
- Background job processing for long LLM calls (prevents frontend timeouts).
- Answers returned as concise **bullet points** with source references.
- Frontend UI with drag & drop upload and a nice modern design.

---

## Repo layout
deep-researcher/
├─ backend/
│ ├─ app/
│ │ ├─ main.py
│ │ ├─ indexer.py
│ │ ├─ llm_client.py
│ │ ├─ utils.py
│ │ ├─ job_manager.py
│ │ └─ ...
│ ├─ venv/ (local, ignored)
│ ├─ requirements.txt
│ └─ reindex.py
├─ frontend/
│ ├─ src/
│ ├─ package.json
│ └─ ...
├─ .gitignore
└─ README.md

## Quick Local Setup (Windows PowerShell)

### 1) Backend (Python)

powershell
cd backend
# create venv if not already
python -m venv venv
.\venv\Scripts\Activate.ps1

# install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# if you don't have requirements.txt, install manually:
# pip install fastapi uvicorn python-multipart python-dotenv sentence-transformers faiss-cpu PyPDF2 python-docx scikit-learn requests

# set env (temporary in this shell)
$env:OLLAMA_URL="http://127.0.0.1:11434/api/generate"
$env:OLLAMA_MODEL="deepseek-r1:7b"
$env:OLLAMA_TIMEOUT_SEC="600"

# start backend (development)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

2) Frontend (Node)
Open a separate terminal:

cd frontend
npm install
npm run dev
# open http://localhost:5173

3) Environment variables (examples)
Create backend/.env (DO NOT COMMIT .env):

OLLAMA_URL=http://127.0.0.1:11434/api/generate
OLLAMA_MODEL=deepseek-r1:7b
OLLAMA_TIMEOUT_SEC=600


Create frontend/.env:
VITE_API_URL=http://127.0.0.1:8000
Note: Vite reads VITE_* variables


How to use (basic):

Upload a file via Frontend UI (drag & drop or choose). Upload returns immediately and indexing runs in background.
Wait a few seconds for indexing (watch backend logs).
Ask a question in the Query panel → UI will create a job and poll GET /results/{job_id} until a reply is ready.
Answer will appear as bullet points with sources.


API (important endpoints):
POST /upload — multipart form, field name files; response: {"uploaded": [...], "indexing": "started"}
POST /query — form-encoded q (question), top_k optional; returns {"job_id": "..."}.
GET /results/{job_id} — returns { status: "pending|running|done|failed", result/error }
GET /health — simple health check
Example query curl:
curl -X POST "http://127.0.0.1:8000/query" -d "q=Summarize the uploaded CV in bullet points."
# then:
curl "http://127.0.0.1:8000/results/<job_id>"


Deployment overview:

Frontend: deploy to Vercel (static build from frontend/).
Backend: deploy to Render or Railway (recommended) because your backend needs a persistent server (long-running tasks, background jobs, and possibly Ollama or remote LLM). Vercel serverless functions are not suitable for long-running LLM calls.
See DEPLOYMENT.md or the Deploy section in this README for full steps.


Tips & notes
Do not commit backend/data, backend/uploads, or any model binaries.
If using large models with Ollama, do not host the model files in GitHub — use local model downloads or a dedicated server.
For better performance, precompute chunk summaries during indexing (recommended).
For production, use a persistent job queue (Redis + Celery/RQ).
