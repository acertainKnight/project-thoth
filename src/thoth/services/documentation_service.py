"""Service for indexing Thoth's own documentation into dedicated database tables.

Documentation files from docs/ are indexed into thoth_docs and thoth_doc_chunks,
completely separate from user research data. This means:
  - Reindexing on doc changes wipes only the docs tables, never touching papers.
  - Search queries thoth_doc_chunks directly, no per-user filter shenanigans.
  - Stale doc embeddings can't leak into user searches.

Indexing is idempotent by default -- each file is hashed and only re-indexed if
the content has actually changed. Pass force=True to wipe everything and rebuild.
"""

import hashlib
import re
from pathlib import Path
from typing import Any

from loguru import logger

_DOCS_DIR = Path(__file__).parents[3] / 'docs'
_SKIP_DIRS = {'archived', 'assets'}


def _discover_docs() -> list[tuple[str, Path]]:
    """Return (title, path) pairs for all docs/*.md files."""
    if not _DOCS_DIR.exists():
        return []
    docs = []
    for p in sorted(_DOCS_DIR.iterdir()):
        if p.is_file() and p.suffix == '.md':
            docs.append((p.stem, p))
    return docs


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _chunk_markdown(content: str, max_chunk_size: int = 1500) -> list[str]:
    """Split markdown into chunks at header boundaries.

    Each chunk starts with the nearest header for context. Sections longer
    than max_chunk_size are further split at paragraph boundaries.

    Args:
        content: Raw markdown text.
        max_chunk_size: Target max characters per chunk.

    Returns:
        list[str]: Non-empty chunk strings.
    """
    parts = re.split(r'(?m)(?=^#{1,4} )', content)
    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= max_chunk_size:
            chunks.append(part)
        else:
            header_match = re.match(r'^(#{1,4} .+)$', part, re.MULTILINE)
            header_prefix = header_match.group(0) + '\n\n' if header_match else ''
            body = part[len(header_prefix) :]
            paragraphs = body.split('\n\n')
            buf = header_prefix
            for para in paragraphs:
                if len(buf) + len(para) + 2 <= max_chunk_size:
                    buf += para + '\n\n'
                else:
                    if buf.strip():
                        chunks.append(buf.strip())
                    buf = header_prefix + para + '\n\n'
            if buf.strip():
                chunks.append(buf.strip())
    return chunks


async def index_all(postgres, rag_service, *, force: bool = False) -> dict[str, str]:
    """Index all docs/ markdown files into thoth_docs / thoth_doc_chunks.

    Args:
        postgres: PostgresService instance.
        rag_service: RAGService instance (used for its embedding_manager).
        force: Wipe all existing doc entries and re-index from scratch.

    Returns:
        dict[str, str]: Mapping of doc title to 'indexed', 'skipped', or 'error'.
    """
    docs = _discover_docs()
    if not docs:
        logger.warning(f'No documentation files found in {_DOCS_DIR}')
        return {}

    if force:
        await _delete_all(postgres)

    # Pull the embedding manager out of the rag_service so we can generate
    # vectors without going through the full RAG pipeline.
    embedding_manager = rag_service.rag_manager.embedding_manager

    results: dict[str, str] = {}
    for title, path in docs:
        try:
            outcome = await _index_one(postgres, embedding_manager, title, path)
            results[title] = outcome
        except Exception as e:
            logger.error(f'Failed to index doc {title!r}: {e}')
            results[title] = 'error'

    indexed = sum(1 for v in results.values() if v == 'indexed')
    skipped = sum(1 for v in results.values() if v == 'skipped')
    errors = sum(1 for v in results.values() if v == 'error')
    logger.info(
        f'Documentation indexing complete: {indexed} indexed, {skipped} skipped, {errors} errors'
    )
    return results


async def _delete_all(postgres) -> None:
    """Wipe thoth_docs (cascades to thoth_doc_chunks via FK)."""
    try:
        async with postgres.acquire() as conn:
            result = await conn.execute('DELETE FROM thoth_docs')
            logger.info(f'Wiped thoth_docs: {result}')
    except Exception as e:
        logger.warning(f'Could not wipe thoth_docs: {e}')


async def _index_one(postgres, embedding_manager, title: str, path: Path) -> str:
    """Index a single doc file if its content has changed since last index.

    Args:
        postgres: PostgresService instance.
        embedding_manager: EmbeddingManager for generating chunk vectors.
        title: Doc title (filename stem).
        path: Absolute path to the markdown file.

    Returns:
        'indexed' if written, 'skipped' if content unchanged.
    """
    content = path.read_text(encoding='utf-8')
    new_hash = _content_hash(content)

    async with postgres.acquire() as conn:
        existing = await conn.fetchrow(
            'SELECT id, content_hash FROM thoth_docs WHERE title = $1',
            title,
        )

        if existing and existing['content_hash'] == new_hash:
            return 'skipped'

        # Delete stale entry (cascades to chunks) before re-inserting.
        if existing:
            await conn.execute('DELETE FROM thoth_docs WHERE id = $1', existing['id'])

        row = await conn.fetchrow(
            """
            INSERT INTO thoth_docs (title, file_path, content_hash, markdown_content)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            title,
            str(path.relative_to(path.parents[3])),
            new_hash,
            content,
        )
        doc_id = row['id']

    chunks = _chunk_markdown(content)
    if not chunks:
        logger.debug(f'No chunks generated for {title!r}')
        return 'indexed'

    vectors = embedding_manager.embed_documents(chunks)

    async with postgres.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO thoth_doc_chunks (doc_id, chunk_index, content, embedding)
            VALUES ($1, $2, $3, $4::vector)
            ON CONFLICT (doc_id, chunk_index) DO UPDATE
                SET content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding
            """,
            [
                (doc_id, idx, chunk, f'[{",".join(str(v) for v in vec)}]')
                for idx, (chunk, vec) in enumerate(zip(chunks, vectors))  # noqa: B905
            ],
        )

    logger.debug(f'Indexed doc {title!r}: {len(chunks)} chunks')
    return 'indexed'


async def search(
    postgres, embedding_manager, query: str, k: int = 5
) -> list[dict[str, Any]]:
    """Semantic search over indexed documentation.

    Queries thoth_doc_chunks directly using pgvector cosine similarity.

    Args:
        postgres: PostgresService instance.
        embedding_manager: EmbeddingManager to embed the query.
        query: Natural language search query.
        k: Number of results to return.

    Returns:
        list of dicts with 'title', 'content', 'score' keys.
    """
    query_vec = embedding_manager.embed_query(query)
    vec_str = f'[{",".join(str(v) for v in query_vec)}]'

    async with postgres.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                d.title,
                c.content,
                1 - (c.embedding <=> $1::vector) AS score
            FROM thoth_doc_chunks c
            JOIN thoth_docs d ON d.id = c.doc_id
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2
            """,
            vec_str,
            k,
        )

    return [
        {'title': row['title'], 'content': row['content'], 'score': float(row['score'])}
        for row in rows
    ]


async def get_doc_content(postgres, title: str) -> str | None:
    """Fetch the full markdown content of a doc by title stem.

    Falls back to reading from disk if not found in DB.

    Args:
        postgres: PostgresService instance.
        title: Doc title (filename stem, e.g. 'rag-system').

    Returns:
        Markdown content string, or None if not found.
    """
    try:
        async with postgres.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT markdown_content
                FROM thoth_docs
                WHERE lower(title) = lower($1)
                   OR lower(title) LIKE lower($1) || '%'
                ORDER BY length(title)
                LIMIT 1
                """,
                title,
            )
            if row and row['markdown_content']:
                return row['markdown_content']
    except Exception as e:
        logger.warning(f'DB lookup for doc {title!r} failed: {e}')

    # Disk fallback for when DB isn't available yet
    path = _DOCS_DIR / f'{title}.md'
    if path.exists():
        return path.read_text(encoding='utf-8')

    matches = list(_DOCS_DIR.glob(f'{title}*.md'))
    if len(matches) == 1:
        return matches[0].read_text(encoding='utf-8')

    return None


def list_available() -> list[dict[str, str]]:
    """Return metadata for all discoverable doc files from disk."""
    return [{'title': title, 'path': str(path)} for title, path in _discover_docs()]
