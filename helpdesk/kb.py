"""Knowledge base: load the how-to articles, index them in Chroma, and search them.

Each article is split into chunks by its "## " sections, and every chunk is
prefixed with the article title so a section like "Fix" still carries its
context. Search ranks chunks, then returns whole articles (they are short),
so the agent sees the full procedure and can cite the article id.

Run with:  python -m helpdesk.kb build
           python -m helpdesk.kb search "vpn won't connect"
"""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "kb" / "articles"
DEFAULT_INDEX_DIR = ROOT / "data" / "chroma"
COLLECTION = "kb_articles"


@dataclass
class Article:
    id: str
    title: str
    category: str
    tools: list[str]
    body: str


def index_dir() -> Path:
    """Index location; override with the HELPDESK_KB_INDEX environment variable."""
    return Path(os.environ.get("HELPDESK_KB_INDEX", DEFAULT_INDEX_DIR))


def parse_article(text: str) -> Article:
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, flags=re.S)
    if match is None:
        raise ValueError("Article is missing its --- front matter block")
    fields = dict(line.split(": ", 1) for line in match.group(1).splitlines())
    tools = [] if fields["tools"] == "none" else [t.strip() for t in fields["tools"].split(",")]
    return Article(fields["id"], fields["title"], fields["category"], tools, match.group(2).strip())


def load_articles(directory: Path = ARTICLES_DIR) -> list[Article]:
    return [parse_article(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.md"))]


def chunk_article(article: Article) -> list[tuple[str, str, dict]]:
    """Split an article into (chunk id, text, metadata) by its ## sections."""
    chunks = []
    for section in re.split(r"^## ", article.body, flags=re.M):
        if not section.strip():
            continue
        heading, _, content = section.partition("\n")
        heading = heading.strip()
        chunks.append((
            f"{article.id}#{heading.lower().replace(' ', '-')}",
            f"{article.title}\n{heading}\n{content.strip()}",
            {"article_id": article.id, "title": article.title, "category": article.category, "section": heading},
        ))
    return chunks


def _client(path: Path) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


def build_index(path: Path | None = None) -> int:
    """(Re)build the Chroma index from the article files. Returns the number of chunks."""
    client = _client(Path(path or index_dir()))
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    collection = client.create_collection(COLLECTION, configuration={"hnsw": {"space": "cosine"}})
    chunks = [chunk for article in load_articles() for chunk in chunk_article(article)]
    ids, documents, metadatas = zip(*chunks)
    collection.add(ids=list(ids), documents=list(documents), metadatas=list(metadatas))
    return len(chunks)


def search_kb(query: str, k: int = 3, path: Path | None = None) -> dict:
    """Find the k articles most relevant to a ticket, best match first.

    Returns full article text so the agent can follow the procedure and cite it.
    """
    collection = _client(Path(path or index_dir())).get_collection(COLLECTION)
    hits = collection.query(query_texts=[query], n_results=min(k * 4, collection.count()))
    articles = {a.id: a for a in load_articles()}

    results = {}
    for metadata, distance in zip(hits["metadatas"][0], hits["distances"][0]):
        article_id = metadata["article_id"]
        if article_id in results:
            continue  # chunks come back best first, so the first one per article is its best score
        article = articles[article_id]
        results[article_id] = {
            "article_id": article_id,
            "title": article.title,
            "category": article.category,
            "matched_section": metadata["section"],
            "score": round(1 - distance, 3),
            "tools": article.tools,
            "content": article.body,
        }
        if len(results) == k:
            break
    return {"ok": True, "query": query, "results": list(results.values())}


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "build"
    if command == "build":
        print(f"Indexed {build_index()} chunks from {len(load_articles())} articles into {index_dir()}")
    elif command == "search":
        for hit in search_kb(" ".join(sys.argv[2:]))["results"]:
            print(f"{hit['score']:.3f}  {hit['article_id']}  {hit['title']}  ({hit['matched_section']})")
    else:
        sys.exit("Usage: python -m helpdesk.kb [build | search <query>]")
