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

app = FastAPI(title="Deep Researcher Agent (jobs+background-indexing)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

indexer = Indexer()

# Background indexer wrapper
async def _background_index(paths: List[str]):
    loop = asyncio.get_running_loop()
    try:
        # run blocking indexer.index_documents in threadpool
        res = await loop.run_in_executor(None, indexer.index_documents, paths)
        print("Background indexing finished:", res)
    except Exception as e:
        print("Background indexing failed:", e)

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    saved_paths = []
    for f in files:
        file_path = UPLOAD_DIR / f.filename
        with open(file_path, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved_paths.append(str(file_path))

    # schedule background indexing (non-blocking)
    asyncio.create_task(_background_index(saved_paths))

    # immediate response (indexing will happen in background)
    return {"uploaded": saved_paths, "indexing": "started"}

# helper: shorten each context using extractive summarizer
def shorten_contexts(contexts: List[str], sentences_per_context: int = 2) -> List[str]:
    short = []
    for c in contexts:
        s = extractive_summary(c, max_sentences=sentences_per_context)
        if not s:
            s = c[:300]
        short.append(s)
    return short

# background worker: runs the LLM call in a threadpool so event loop isn't blocked
async def _worker_answer(job_id: str, question: str, top_k: int):
    try:
        set_job_running(job_id)
        # get top matching contexts
        results = indexer.query(question, top_k=top_k)
        contexts = [r[1]["text"] for r in results]
        # shorten contexts (fast)
        short_contexts = shorten_contexts(contexts, sentences_per_context=2)
        # run blocking LLM call in default threadpool
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(None, generate_answer_ollama, question, short_contexts)
        sources = [{"source": r[1]["source"], "text": r[1]["text"], "dist": float(r[0])} for r in results]
        set_job_done(job_id, {"answer": answer, "sources": sources})
    except Exception as e:
        set_job_failed(job_id, str(e))

@app.post("/query")
async def query_job(q: str = Form(...), top_k: int = Form(3)):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="q is required")
    job_id = create_job()
    asyncio.create_task(_worker_answer(job_id, q, top_k))
    return {"job_id": job_id}

@app.get("/results/{job_id}")
async def get_results(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/health")
async def health():
    return {"status": "ok"}
