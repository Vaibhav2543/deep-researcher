# backend/app/utils.py
import re
from typing import List, Tuple
from pathlib import Path

# PDF loader
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except Exception:
    PYPDF2_AVAILABLE = False

# DOCX loader
try:
    import docx
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# Optional TF-IDF summarizer
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

# -------------------------
# File loaders
# -------------------------
def load_pdf_text(path: str) -> str:
    """Extract text from PDF using PyPDF2."""
    if not PYPDF2_AVAILABLE:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    try:
        text_parts = []
        with open(path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            for page in reader.pages:
                try:
                    page_text = page.extract_text()
                except Exception:
                    page_text = ""
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts).strip()
    except Exception:
        return ""

def load_docx_text(path: str) -> str:
    """Extract text from .docx using python-docx."""
    if not DOCX_AVAILABLE:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    try:
        doc = docx.Document(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n\n".join(paragraphs).strip()
    except Exception:
        return ""

def load_csv_text(path: str, max_rows: int = 50) -> str:
    """Read CSV content (headers and first max_rows) and return as plain text."""
    import csv
    p = Path(path)
    if not p.exists():
        return ""
    try:
        rows = []
        with open(path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for i, row in enumerate(reader):
                if i == 0:
                    # header
                    rows.append(" | ".join(row))
                else:
                    rows.append(" | ".join(row))
                if i >= max_rows:
                    rows.append(f"... (truncated, total rows > {max_rows})")
                    break
        return "\n".join(rows).strip()
    except Exception:
        # fallback to naive read
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except Exception:
            return ""

def load_txt(path: str) -> str:
    """Read a plain text file safely."""
    p = Path(path)
    if not p.exists():
        return ""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="latin-1") as fh:
                return fh.read()
        except Exception:
            return ""
    except Exception:
        return ""

def read_file_text(path: str) -> str:
    """Auto-detect and read file text for supported types."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return load_pdf_text(path)
    if ext == ".docx":
        return load_docx_text(path)
    if ext == ".csv":
        return load_csv_text(path)
    if ext in (".txt", ".md", ".log"):
        return load_txt(path)
    # fallback attempt
    return load_txt(path)

# -------------------------
# Chunking
# -------------------------
def simple_chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Split text into chunks up to `chunk_size` chars, using sentence boundaries when possible.
    """
    if not text:
        return []
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]
    sentences = re.split(r'(?<=[\.\?\!\n])\s+', text)
    chunks: List[str] = []
    current = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + 1 + len(s) <= chunk_size:
            current = (current + " " + s).strip() if current else s
        else:
            if current:
                chunks.append(current)
            # if single sentence > chunk_size, hard-split it
            if len(s) > chunk_size:
                start = 0
                while start < len(s):
                    part = s[start:start+chunk_size]
                    chunks.append(part)
                    start += chunk_size - overlap
                current = ""
            else:
                current = s
    if current:
        chunks.append(current)
    return chunks

# -------------------------
# Summarization helper
# -------------------------
def split_sentences(text: str) -> List[str]:
    if not text:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]

def extractive_summary(text: str, max_sentences: int = 3) -> str:
    """
    Extractive summarizer using TF-IDF sentence scoring when sklearn is available,
    otherwise fallback to the first `max_sentences` sentences.
    """
    if not text:
        return ""
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    if SKLEARN_AVAILABLE:
        try:
            vect = TfidfVectorizer(stop_words="english", ngram_range=(1,2))
            X = vect.fit_transform(sentences)
            scores = X.sum(axis=1).A1
            top_idx = list(reversed(scores.argsort()))[:max_sentences]
            top_idx_sorted = sorted(top_idx)
            selected = [sentences[i] for i in top_idx_sorted]
            return " ".join(selected)
        except Exception:
            pass
    # fallback
    return " ".join(sentences[:max_sentences])

# -------------------------
# File -> chunks utility
# -------------------------
def file_to_chunks(path: str, chunk_size: int = 1000, overlap: int = 200) -> List[Tuple[str, str]]:
    text = read_file_text(path)
    if not text:
        return []
    chunks = simple_chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    return [(path, c) for c in chunks]
