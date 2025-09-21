# backend/app/indexer.py
import os
import sys
import time
import pickle
from pathlib import Path
from typing import List, Tuple, Any, Dict

from app.utils import file_to_chunks, read_file_text

# Try to import sentence_transformers and faiss; otherwise fallback to text-search
try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except Exception:
    ST_AVAILABLE = False

try:
    import faiss
    FAISS_AVAILABLE = True
except Exception:
    FAISS_AVAILABLE = False

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
METADATA_PATH = DATA_DIR / "metadata.pkl"
FAISS_INDEX_PATH = DATA_DIR / "index.faiss"

class Indexer:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        if ST_AVAILABLE:
            try:
                self.model = SentenceTransformer(self.model_name)
            except Exception:
                self.model = None

        # load index if files exist
        self.embeddings = None
        self.metadata = []
        self.index = None
        self._load_existing()

    def _load_existing(self):
        try:
            if METADATA_PATH.exists():
                with open(METADATA_PATH, "rb") as fh:
                    self.metadata = pickle.load(fh)
            if EMBEDDINGS_PATH.exists():
                import numpy as np
                self.embeddings = np.load(str(EMBEDDINGS_PATH), allow_pickle=False)
            if FAISS_INDEX_PATH.exists() and FAISS_AVAILABLE and self.embeddings is not None:
                self.index = faiss.read_index(str(FAISS_INDEX_PATH))
        except Exception:
            # don't crash on load errors
            self.metadata = []
            self.embeddings = None
            self.index = None

    def index_documents(self, paths: List[str], chunk_size: int = 1000, overlap: int = 200) -> Dict[str, Any]:
        """
        Index files. Returns dict with status and counts.
        """
        try:
            chunks: List[Tuple[str, str]] = []
            for p in paths:
                # file_to_chunks returns (source_path, chunk_text)
                chunks.extend(file_to_chunks(p, chunk_size=chunk_size, overlap=overlap))

            if not chunks:
                return {"status": "no_text_found"}

            texts = [c[1] for c in chunks]
            sources = [c[0] for c in chunks]

            # compute embeddings using sentence-transformers if available
            if self.model is not None:
                import numpy as np
                batch_size = 64
                all_embs = []
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i+batch_size]
                    emb = self.model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
                    all_embs.append(emb)
                embs = np.vstack(all_embs)
                # append to existing embeddings/metadata
                if self.embeddings is None:
                    self.embeddings = embs
                    self.metadata = [{"source": src, "text": txt} for src, txt in zip(sources, texts)]
                else:
                    self.embeddings = np.vstack([self.embeddings, embs])
                    self.metadata.extend([{"source": src, "text": txt} for src, txt in zip(sources, texts)])
                # save
                np.save(str(EMBEDDINGS_PATH), self.embeddings)
                with open(METADATA_PATH, "wb") as fh:
                    pickle.dump(self.metadata, fh)
                # build faiss index if available
                if FAISS_AVAILABLE:
                    d = self.embeddings.shape[1]
                    index = faiss.IndexFlatL2(d)
                    index.add(self.embeddings)
                    faiss.write_index(index, str(FAISS_INDEX_PATH))
                    self.index = index
                return {"status": "indexed", "n_chunks": len(self.metadata), "faiss": FAISS_AVAILABLE}
            else:
                # fallback: simple in-memory store of texts for substring search
                for src, txt in zip(sources, texts):
                    self.metadata.append({"source": src, "text": txt})
                with open(METADATA_PATH, "wb") as fh:
                    pickle.dump(self.metadata, fh)
                return {"status": "indexed_no_embeddings", "n_chunks": len(self.metadata), "faiss": False}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def query(self, q: str, top_k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Return list of (distance, metadata) pairs.
        """
        # simple checks
        if (self.metadata is None) or (len(self.metadata) == 0):
            raise ValueError("Index not built or empty. Please upload documents first.")

        # if embeddings + faiss available, use vector search
        if self.embeddings is not None and self.index is not None and ST_AVAILABLE:
            # compute query embedding
            try:
                q_emb = self.model.encode([q], convert_to_numpy=True)
                import numpy as np
                D, I = self.index.search(q_emb, top_k)
                results = []
                for dist, idx in zip(D[0], I[0]):
                    if idx < 0 or idx >= len(self.metadata):
                        continue
                    results.append((float(dist), self.metadata[idx]))
                return results
            except Exception as e:
                # fallback to text search
                pass

        # fallback substring scoring: count occurrences and pick top_k
        scores = []
        q_low = q.lower()
        for meta in self.metadata:
            text = meta.get("text", "")
            cnt = text.lower().count(q_low)
            # simple distance metric: negative count -> smaller is better
            score = -cnt
            # if none found, use heuristic on overlap of words
            if cnt == 0:
                words = set(q_low.split())
                twords = set(text.lower().split())
                inter = words.intersection(twords)
                score = -len(inter)
            scores.append((score, meta))
        # sort ascending (more negative is better)
        scores.sort(key=lambda x: x[0])
        out = []
        for s, m in scores[:top_k]:
            out.append((float(s), m))
        return out
