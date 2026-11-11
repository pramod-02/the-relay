from dataclasses import dataclass
from pathlib import Path
import re
from pypdf import PdfReader

@dataclass
class Passage:
    paper: str
    page: int
    text: str

def words(text: str):
    return re.findall(r"[a-z0-9]+", text.lower())

def load_passages(folder="papers", chunk_words=350, overlap=60):
    passages = []
    for pdf in sorted(Path(folder).glob("*.pdf")):
        reader = PdfReader(str(pdf))
        for page_num, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").replace("\x00", " ")
            tokens = text.split()
            if not tokens:
                continue
            step = max(1, chunk_words - overlap)
            for start in range(0, len(tokens), step):
                chunk = " ".join(tokens[start:start + chunk_words]).strip()
                if len(chunk) > 80:
                    passages.append(Passage(pdf.name, page_num, chunk))
    if not passages:
        raise RuntimeError("No passages found. Run `python download_papers.py` first.")
    return passages

def retrieve(question, passages, k=4):
    q = set(words(question))
    scored = []
    for p in passages:
        terms = words(p.text)
        if not terms:
            continue
        counts = {}
        for t in terms:
            counts[t] = counts.get(t, 0) + 1
        # Simple normalized lexical score; explain as a baseline, not semantic search.
        score = sum(1 + min(counts.get(t, 0), 3) * 0.15 for t in q if t in counts)
        score = score / max(1, len(q) ** 0.5)
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:k]]
