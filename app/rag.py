"""Granite Embedding 278M RAG over the NYC flood-resilience policy corpus.

Powers the `policy_corpus` pebble: retrieve the top-k policy passages
(DEP, NYCHA, Con Edison, MTA, Comptroller) for a query built from the
other evidence.

Chunks (~700 chars, page by page) are embedded offline by
scripts/build_rag_index.py into data/rag_index.npz. At runtime only the
query is embedded, in process on CPU.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("riprap.rag")

CORPUS_DIR = Path(__file__).resolve().parent.parent / "deployments" / "nyc" / "corpus"
EMBED_MODEL_NAME = "ibm-granite/granite-embedding-278m-multilingual"

CORPUS_META = {
    "dep_wastewater_2013.pdf": {
        "doc_id": "rag_dep_2013",
        "title": "NYC DEP Wastewater Resiliency Plan (2013)",
        "citation": "NYC DEP Wastewater Resiliency Plan, 2013",
    },
    "nycha_lessons.pdf": {
        "doc_id": "rag_nycha",
        "title": "Flood Resilience at NYCHA — Lessons Learned",
        "citation": "NYCHA, Flood Resilience: Lessons Learned",
    },
    "coned_22_e_0222.pdf": {
        "doc_id": "rag_coned",
        "title": "Con Edison Climate Change Resilience Plan (2023, Case 22-E-0222)",
        "citation": "Con Edison Climate Change Resilience Plan (2023, NY PSC Case 22-E-0222)",
    },
    "mta_resilience_2025.pdf": {
        "doc_id": "rag_mta",
        "title": "MTA Climate Resilience Roadmap (October 2025 update)",
        "citation": "MTA Climate Resilience Roadmap, October 2025 update",
    },
    "comptroller_rain_2024.pdf": {
        "doc_id": "rag_comptroller",
        "title": "NYC Comptroller — Is NYC Ready for Rain? (2024)",
        "citation": "NYC Comptroller, \"Is New York City Ready for Rain?\" (2024)",
    },
}


@dataclass
class Chunk:
    text: str
    file: str
    page: int
    doc_id: str
    title: str
    citation: str


def _chunks_from_pdf(path: Path, target_chars: int = 700) -> list[Chunk]:
    import pypdf
    meta = CORPUS_META.get(path.name, {
        "doc_id": f"rag_{path.stem}",
        "title": path.stem,
        "citation": path.stem,
    })
    out: list[Chunk] = []
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as e:
        log.warning("pdf load failed for %s: %s", path.name, e)
        return out
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        txt = re.sub(r"\s+", " ", txt).strip()
        if len(txt) < 80:
            continue
        # split into ~target_chars chunks at sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", txt)
        buf = ""
        for s in sentences:
            if len(buf) + len(s) + 1 <= target_chars or not buf:
                buf = (buf + " " + s).strip() if buf else s
            else:
                out.append(Chunk(text=buf, file=path.name, page=i + 1,
                                 doc_id=meta["doc_id"], title=meta["title"],
                                 citation=meta["citation"]))
                buf = s
        if buf:
            out.append(Chunk(text=buf, file=path.name, page=i + 1,
                             doc_id=meta["doc_id"], title=meta["title"],
                             citation=meta["citation"]))
    return out


INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "rag_index.npz"
_INDEX: dict | None = None
_MODEL = None
_MODEL_LOCK = threading.Lock()


def build_index(path: Path = INDEX_PATH) -> int:
    """Offline: chunk the corpus PDFs, embed every chunk, write the matrix
    and chunk metadata to one .npz. Run scripts/build_rag_index.py after
    the corpus changes. Needs the `ml` extra."""
    chunks: list[Chunk] = []
    for f in sorted(CORPUS_DIR.glob("*.pdf")):
        chunks.extend(_chunks_from_pdf(f))
    embs = _model().encode([c.text for c in chunks], batch_size=32, show_progress_bar=False,
                           convert_to_numpy=True, normalize_embeddings=True)
    meta = json.dumps([c.__dict__ for c in chunks])
    np.savez_compressed(path, embs=embs.astype("float16"), chunks=np.array(meta),
                        model=np.array(EMBED_MODEL_NAME))
    return len(chunks)


def _ensure_index() -> dict:
    """Load the prebuilt index from disk. Missing file means no policy
    retrieval (logged once), never a runtime re-embedding of the PDFs."""
    global _INDEX
    if _INDEX is None:
        if not INDEX_PATH.exists():
            log.warning("rag: %s missing; run scripts/build_rag_index.py", INDEX_PATH)
            _INDEX = {"chunks": [], "embs": None}
        else:
            z = np.load(INDEX_PATH)
            _INDEX = {"chunks": [Chunk(**c) for c in json.loads(str(z["chunks"]))],
                      "embs": z["embs"].astype("float32")}
            log.info("rag: loaded %d chunks from %s", len(_INDEX["chunks"]), INDEX_PATH.name)
    return _INDEX


def _model():
    """The query/corpus encoder, loaded once, in process, on CPU."""
    global _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            from sentence_transformers import SentenceTransformer

            _MODEL = SentenceTransformer(EMBED_MODEL_NAME, device="cpu")
    return _MODEL


def warm():
    _ensure_index()


def retrieve(query: str, k: int = 4, min_score: float = 0.30) -> list[dict]:
    """Top-k chunks by cosine similarity, at most one per document."""
    idx = _ensure_index()
    if idx["embs"] is None or not idx["chunks"]:
        return []
    qv = _model().encode([query], convert_to_numpy=True,
                         normalize_embeddings=True).astype("float32")
    sims = (idx["embs"] @ qv.T).ravel()
    out: list[dict] = []
    seen: set[str] = set()
    for i in np.argsort(-sims)[:k * 3]:
        c = idx["chunks"][i]
        if sims[i] < min_score or c.doc_id in seen:
            continue
        seen.add(c.doc_id)
        out.append({"doc_id": c.doc_id, "title": c.title, "citation": c.citation,
                    "file": c.file, "page": c.page, "text": c.text, "score": float(sims[i])})
        if len(out) >= k:
            break
    return out
