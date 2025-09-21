from app.indexer import Indexer
from pathlib import Path
import traceback, sys

u = Path(__file__).resolve().parent / "uploads"
files = [str(p) for p in u.glob("*") if p.is_file()]
print("Files to index:", files)

try:
    idx = Indexer()
    res = idx.index_documents(files)
    print("Index result:", res)
except Exception as e:
    print("Exception during indexing:")
    traceback.print_exc(file=sys.stdout)
    raise
