# backend/app/main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import os
import asyncio
from typing import List

from app.indexer import Indexer
from app.llm_client import generate_answer_ollama
from app.job_manager import create_job, set_job_running, set_job_done, set_job_failed, get_job
from app.utils import extractive_summary

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Deep Researcher Agent (clear-index-on-upload)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# single shared indexer instance
indexer = Indexer()

# -----------------------
# Background indexing
# -----------------------
async def _background_index(paths: List[str]):
    """
    Run indexer.index_documents in a threadpool so we don't block the event loop.
    """
    loop = asyncio.get_running_loop()
    try:
        res = await loop.run_in_executor(None, indexer.index_documents, paths)
        # log result - uvicorn console will show this
        print("Background indexing finished:", res)
    except Exception as e:
        print("Background indexing failed:", e)

# -----------------------
# Upload endpoint (clears index first)
# -----------------------
@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Save uploaded files, clear existing index, then start background indexing of the uploaded files.
    This ensures queries will only consider the newly uploaded documents.
    """
    saved_paths = []
    for f in files:
        # sanitize filename
        filename = os.path.basename(f.filename)
        file_path = UPLOAD_DIR / filename
        with open(file_path, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved_paths.append(str(file_path))

    # Clear existing index (in-memory) and on-disk references in the indexer object.
    try:
        indexer.metadata = []
        indexer.embeddings = None
        indexer.index = None
        # remove saved index files on disk if present
        data_dir = BASE_DIR / "data"
        try:
            for fname in ("embeddings.npy", "metadata.pkl", "index.faiss"):
                p = data_dir / fname
                if p.exists():
                    try:
                        p.unlink()
                        print(f"Removed old index file: {p}")
                    except Exception as e:
                        print(f"Failed to remove {p}: {e}")
        except Exception:
            pass
    except Exception as e:
        print("Error while clearing index in-memory:", e)

    # start background indexing for the uploaded files (non-blocking response)
    asyncio.create_task(_background_index(saved_paths))

    return {"uploaded": saved_paths, "indexing": "started", "note": "Cleared previous index; indexing new uploads in background."}

# -----------------------
# Shorten contexts helper
# -----------------------
def shorten_contexts(contexts: List[str], sentences_per_context: int = 2) -> List[str]:
    short = []
    for c in contexts:
        s = extractive_summary(c, max_sentences=sentences_per_context)
        if not s:
            s = c[:300]
        short.append(s)
    return short

# -----------------------
# Background worker for queries
# -----------------------
async def _worker_answer(job_id: str, question: str, top_k: int):
    try:
        set_job_running(job_id)
        # fetch top-k matching chunks from indexer
        results = indexer.query(question, top_k=top_k)
        contexts = [r[1]["text"] for r in results]
        # shorten contexts to keep LLM prompt small
        short_contexts = shorten_contexts(contexts, sentences_per_context=2)
        # run blocking LLM call in executor
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(None, generate_answer_ollama, question, short_contexts)
        sources = [{"source": r[1]["source"], "text": r[1]["text"], "dist": float(r[0])} for r in results]
        set_job_done(job_id, {"answer": answer, "sources": sources})
    except Exception as e:
        set_job_failed(job_id, str(e))

# -----------------------
# Query endpoint (returns job_id)
# -----------------------
@app.post("/query")
async def query_job(q: str = Form(...), top_k: int = Form(3)):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="q is required")

    # Ensure index is not empty
    if not getattr(indexer, "metadata", None) or len(indexer.metadata) == 0:
        raise HTTPException(status_code=400, detail="Index not built or empty. Please upload documents first.")

    job_id = create_job()
    asyncio.create_task(_worker_answer(job_id, q, top_k))
    return {"job_id": job_id}

# -----------------------
# Polling result endpoint
# -----------------------
@app.get("/results/{job_id}")
async def get_results(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

# -----------------------
# List indexed files (for frontend to confirm)
# -----------------------
@app.get("/indexed-files")
async def indexed_files():
    """
    Return a list of distinct source filenames present in the current in-memory metadata.
    Useful for the frontend to confirm which files are indexed.
    """
    sources = []
    try:
        for m in getattr(indexer, "metadata", []) or []:
            src = m.get("source")
            if src and src not in sources:
                sources.append(src)
    except Exception:
        pass
    return {"indexed": sources}

# -----------------------
# Health
# -----------------------
@app.get("/health")
async def health():
    return {"status": "ok"}
