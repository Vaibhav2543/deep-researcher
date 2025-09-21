# backend/app/llm_client.py
import os
import requests
import json
from typing import List, Any

from app.utils import extractive_summary

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SEC", "300"))

def _clean_token(s: Any) -> str:
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    cleaned = s.replace("<think>", "").replace("</think>", "").replace("\u0000", "")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()

def _extract_text_from_ollama_response(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return _clean_token(obj)
    if isinstance(obj, dict):
        if "response" in obj and obj["response"]:
            return _clean_token(obj["response"])
        for k in ("text", "content", "output", "result"):
            if k in obj and obj[k]:
                return _clean_token(obj[k])
        for k in obj:
            val = obj.get(k)
            if isinstance(val, str) and val.strip():
                return _clean_token(val)
    try:
        return _clean_token(json.dumps(obj))[:4000]
    except Exception:
        return _clean_token(str(obj))[:4000]

def generate_answer_ollama(question: str, contexts: List[str]) -> str:
    ctx = "\n\n---\n\n".join([c for c in contexts if c])
    prompt = (
        "You are a helpful assistant. Use ONLY the CONTEXT below to answer the QUESTION.\n"
        "Produce the answer as concise bullet points (each on a new line prefixed by '- ').\n"
        "If the answer is not present in the context, reply exactly: \"I don't know\".\n\n"
        f"CONTEXT:\n{ctx}\n\nQUESTION: {question}\n\n"
        "Answer in 3-6 short bullet points, prioritizing key facts and action items."
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "max_tokens": 300,
        "temperature": 0.0,
        "stream": False,
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
    except requests.RequestException as e:
        return _local_bulleted_fallback(question, contexts, note=f"ollama_error:{e}")

    if resp.status_code != 200:
        return _local_bulleted_fallback(question, contexts, note=f"ollama_status:{resp.status_code}")

    try:
        j = resp.json()
    except Exception:
        text = resp.text
        cleaned = _clean_token(text)
        if cleaned:
            return cleaned
        return _local_bulleted_fallback(question, contexts, note="ollama_nonjson")

    answer = _extract_text_from_ollama_response(j)
    if answer:
        if not answer.strip().startswith("-"):
            import re
            sents = re.split(r'(?<=[.!?])\s+', answer)
            sents = [x.strip() for x in sents if x.strip()]
            bullets = ["- " + s for s in sents[:6]]
            return "\n".join(bullets)
        return answer
    return _local_bulleted_fallback(question, contexts, note="ollama_empty")

def _local_bulleted_fallback(question: str, contexts: List[str], note: str = "") -> str:
    pieces = []
    for c in contexts[:6]:
        if not c:
            continue
        summ = extractive_summary(c, max_sentences=2)
        if summ:
            pieces.append(summ)
    if not pieces:
        return "I don't know"
    seen = set()
    bullets = []
    for p in pieces:
        s = p.strip()
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        if len(s) > 300:
            s = s[:300].rsplit(" ", 1)[0] + "..."
        bullets.append(f"- {s}")
        if len(bullets) >= 6:
            break
    return "\n".join(bullets)
