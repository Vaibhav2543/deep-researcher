# backend/app/indexer.py
import os
import pickle
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import numpy as np

# sentence-transformers for embeddings
from sentence_transformers import SentenceTransformer

# try faiss; if not present we'll fallback to numpy
try:
    import faiss
    FAISS_AVAILABLE = True
except Exception:
    FAISS_AVAILABLE = False

from app.utils import load_pdf_text, load_txt, simple_chunk_text

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE / "data"))
UPLOADS_DIR = BASE / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

EMB_PATH = DATA_DIR / "embeddings.npy"
META_PATH = DATA_DIR / "metadata.pkl"
FAISS_INDEX_PATH = DATA_DIR / "index.faiss"

class Indexer:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.embeddings: Optional[np.ndarray] = None
        self.metadata: List[Dict[str, Any]] = []
        self.faiss_index = None
        # Try to load existing index
        self._load_index_files()

    def _load_index_files(self):
        if META_PATH.exists():
            try:
                with META_PATH.open("rb") as f:
                    self.metadata = pickle.load(f)
            except Exception:
                self.metadata = []
        if EMB_PATH.exists():
            try:
                self.embeddings = np.load(str(EMB_PATH))
            except Exception:
                self.embeddings = None
        if FAISS_AVAILABLE and FAISS_INDEX_PATH.exists():
            try:
                self.faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))
            except Exception:
                self.faiss_index = None

    def index_documents(self, paths: List[str]) -> Dict[str, Any]:
        """
        Index a list of file paths (pdf or txt). Returns a dict with status and details.
        """
        to_index_texts = []
        sources = []
        for p in paths:
            pth = Path(p)
            if not pth.exists():
                continue
            if pth.suffix.lower() == ".pdf":
                text = load_pdf_text(str(pth))
            else:
                try:
                    text = load_txt(str(pth))
                except Exception:
                    text = ""
            if not text or not text.strip():
                # no text found for this file
                continue
            # chunk the text
            chunks = simple_chunk_text(text)
            for c in chunks:
                to_index_texts.append(c)
                sources.append({"source": pth.name, "text": c})

        if not to_index_texts:
            return {"status": "no_text_found"}

        # compute embeddings in batches
        embeddings = self.model.encode(to_index_texts, convert_to_numpy=True, show_progress_bar=True)
        # append to existing
        if self.embeddings is None:
            self.embeddings = embeddings
            self.metadata = sources
        else:
            self.embeddings = np.vstack([self.embeddings, embeddings])
            self.metadata.extend(sources)

        # save artifacts
        np.save(str(EMB_PATH), self.embeddings)
        with META_PATH.open("wb") as f:
            pickle.dump(self.metadata, f)

        # try to build faiss index if available
        if FAISS_AVAILABLE:
            try:
                dim = self.embeddings.shape[1]
                index = faiss.IndexFlatIP(dim)  # inner product for cosine if normalized
                # normalize embeddings for cosine similarity
                emb_norm = self.embeddings / (np.linalg.norm(self.embeddings, axis=1, keepdims=True) + 1e-10)
                index.add(emb_norm.astype(np.float32))
                faiss.write_index(index, str(FAISS_INDEX_PATH))
                self.faiss_index = index
                return {"status": "indexed", "n_chunks": len(self.metadata), "faiss": True}
            except Exception:
                # fail silently and fallback to numpy-only
                self.faiss_index = None

        return {"status": "indexed", "n_chunks": len(self.metadata), "faiss": False}

    def _load_metadata(self) -> List[Dict[str, Any]]:
        if not self.metadata and META_PATH.exists():
            with META_PATH.open("rb") as f:
                self.metadata = pickle.load(f)
        return self.metadata

    def _safe_cosine_search(self, query_emb: np.ndarray, top_k: int = 5) -> List[Tuple[float, int]]:
        """
        Compute cosine distances against stored embeddings in numpy.
        Returns list of (distance, index) with smaller distance = better.
        """
        if self.embeddings is None:
            raise ValueError("Embeddings not found. Please index documents first.")
        embs = self.embeddings  # shape (N, D)
        # normalize
        embs_norm = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-10)
        qn = query_emb / (np.linalg.norm(query_emb) + 1e-10)
        sims = embs_norm.dot(qn)
        dists = 1.0 - sims  # convert similarity to distance
        idxs = np.argsort(dists)[:top_k]
        return [(float(dists[i]), int(i)) for i in idxs]

    def query(self, q: str, top_k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Query the index for top_k results.
        Returns list of tuples (distance, metadata_dict)
        """
        if self.embeddings is None or not self._load_metadata():
            raise ValueError("Index not built or empty. Please upload documents first.")

        # get query embedding
        q_emb = self.model.encode([q], convert_to_numpy=True)[0]

        # Try FAISS first if available
        results = []
        try:
            if FAISS_AVAILABLE and self.faiss_index is not None:
                # we store normalized embeddings; compute normalized query
                qn = q_emb / (np.linalg.norm(q_emb) + 1e-10)
                qn32 = np.array([qn], dtype=np.float32)
                D, I = self.faiss_index.search(qn32, top_k)  # returns distances as inner-product values
                # convert inner-product similarity to distance
                for dist_val, idx in zip(D[0], I[0]):
                    # sanity-check dist_val
                    if np.isnan(dist_val) or dist_val > 1e6 or dist_val < -1e6:
                        raise ValueError("faiss returned invalid distances")
                    # inner product similarity s in [-1,1], convert to distance = 1 - s
                    s = float(dist_val)
                    d = 1.0 - s
                    results.append((d, self.metadata[int(idx)]))
                # filter out invalid indices (just in case)
                results = [(float(d), m) for d, m in results if isinstance(m, dict)]
                # dedupe by text
                seen = set()
                filtered = []
                for d, m in results:
                    t = m.get("text", "")
                    if t in seen:
                        continue
                    seen.add(t)
                    filtered.append((d, m))
                return filtered
        except Exception:
            # fallback to numpy cosine search
            pass

        # Fallback safe cosine search
        fallback = self._safe_cosine_search(q_emb, top_k=top_k)
        metadata = self._load_metadata()
        results = []
        for dist, idx in fallback:
            if idx < len(metadata):
                results.append((dist, metadata[idx]))
        # dedupe
        seen = set()
        filtered = []
        for d, m in results:
            t = m.get("text", "")
            if t in seen:
                continue
            seen.add(t)
            filtered.append((d, m))
        return filtered
