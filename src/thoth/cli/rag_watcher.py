"""CLI commands for the RAG watcher service."""

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from thoth.pipeline import ThothPipeline


def run_watcher_start(args, pipeline: ThothPipeline):
    """Start the RAG watcher service."""
    try:
        # Get the watcher service
        watcher = pipeline.services.get_service('rag_watcher')

        # Check if already running
        if watcher.is_running():
            logger.warning('RAG watcher is already running')
            return 1

        # Determine watch directories
        watch_dirs = []
        if hasattr(args, 'pdf_dir') and args.pdf_dir:
            watch_dirs.append(Path(args.pdf_dir))
        if hasattr(args, 'markdown_dir') and args.markdown_dir:
            watch_dirs.append(Path(args.markdown_dir))
        if hasattr(args, 'notes_dir') and args.notes_dir:
            watch_dirs.append(Path(args.notes_dir))

        if not watch_dirs:
            # Use default directories from config
            watch_dirs = None

        # Start watcher
        logger.info('Starting RAG watcher service...')
        watcher.start(watch_dirs=watch_dirs)

        logger.info('RAG watcher is now monitoring for new files')
        logger.info('Press Ctrl+C to stop')

        # Set up signal handler for graceful shutdown
        def signal_handler(sig, frame):
            logger.info('\nShutting down RAG watcher...')
            watcher.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep running until interrupted
        try:
            while watcher.is_running():
                import time

                time.sleep(1)
        except KeyboardInterrupt:
            logger.info('\nShutting down RAG watcher...')
            watcher.stop()

        return 0

    except Exception as e:
        logger.error(f'Error starting RAG watcher: {e}')
        return 1


def run_watcher_stop(args, pipeline: ThothPipeline):  # noqa: ARG001
    """Stop the RAG watcher service."""
    try:
        watcher = pipeline.services.get_service('rag_watcher')

        if not watcher.is_running():
            logger.warning('RAG watcher is not running')
            return 0

        logger.info('Stopping RAG watcher...')
        watcher.stop()
        logger.info('RAG watcher stopped')

        return 0

    except Exception as e:
        logger.error(f'Error stopping RAG watcher: {e}')
        return 1


def run_watcher_status(args, pipeline: ThothPipeline):  # noqa: ARG001
    """Show RAG watcher status."""
    try:
        watcher = pipeline.services.get_service('rag_watcher')
        status = watcher.get_status()

        logger.info('RAG Watcher Status:')
        logger.info(f"  Running: {'Yes' if status['is_running'] else 'No'}")

        if status['watched_directories']:
            logger.info('  Watching directories:')
            for directory in status['watched_directories']:
                logger.info(f'    - {directory}')

        return 0

    except Exception as e:
        logger.error(f'Error getting RAG watcher status: {e}')
        return 1


def run_watcher_backfill(args, pipeline: ThothPipeline):
    """Backfill all existing markdown files into the RAG system."""
    try:
        logger.info('Starting RAG backfill process...')
        logger.info('This will index all existing markdown files into the vector store')

        # Get services
        rag_service = pipeline.services.get_service('rag')

        # Determine directories to process
        directories = []

        # Add markdown directory (full markdown from PDFs)
        markdown_dir = pipeline.config.markdown_dir
        if markdown_dir.exists():
            directories.append(('markdown', markdown_dir, '*.md'))
        else:
            logger.warning(f'Markdown directory does not exist: {markdown_dir}')

        # Add notes directory
        notes_dir = pipeline.config.notes_dir
        if notes_dir.exists():
            directories.append(('notes', notes_dir, '*.md'))
        else:
            logger.warning(f'Notes directory does not exist: {notes_dir}')

        # Process each directory
        total_files = 0
        total_chunks = 0
        errors = []

        for dir_type, directory, pattern in directories:
            logger.info(f'\nProcessing {dir_type} directory: {directory}')

            try:
                # Get all markdown files
                files = list(directory.rglob(pattern))
                logger.info(f'Found {len(files)} {dir_type} files')

                # Index each file
                for i, file_path in enumerate(files, 1):
                    try:
                        logger.info(f'  [{i}/{len(files)}] Indexing: {file_path.name}')

                        # Check if we should skip (for testing/force options)
                        if hasattr(args, 'skip_existing') and args.skip_existing:
                            # TODO: Add check if already indexed
                            pass

                        # Index the file
                        doc_ids = rag_service.index_file(file_path)
                        total_chunks += len(doc_ids)
                        total_files += 1

                        logger.success(
                            f'    ✅ Indexed {len(doc_ids)} chunks from {file_path.name}'
                        )

                    except Exception as e:
                        error_msg = f'Failed to index {file_path}: {e}'
                        logger.error(f'    ❌ {error_msg}')
                        errors.append(error_msg)
                        continue

            except Exception as e:
                error_msg = f'Error processing {dir_type} directory: {e}'
                logger.error(error_msg)
                errors.append(error_msg)

        # Show summary
        logger.info('\n' + '=' * 60)
        logger.info('Backfill Summary:')
        logger.info(f'  Total files processed: {total_files}')
        logger.info(f'  Total chunks created: {total_chunks}')

        if errors:
            logger.warning(f'  Errors encountered: {len(errors)}')
            if hasattr(args, 'verbose') and args.verbose:
                for error in errors:
                    logger.warning(f'    - {error}')
        else:
            logger.success('  ✅ All files processed successfully!')

        # Show vector store stats
        try:
            stats = rag_service.get_statistics()
            logger.info('\nVector Store Statistics:')
            logger.info(f"  Total documents: {stats.get('document_count', 0)}")
            logger.info(f"  Collection: {stats.get('collection_name', 'Unknown')}")
            logger.info(f"  Embedding model: {stats.get('embedding_model', 'Unknown')}")
        except Exception as e:
            logger.warning(f'Could not retrieve vector store stats: {e}')

        logger.info('=' * 60)

        return 0 if not errors else 1

    except Exception as e:
        logger.error(f'Error during backfill: {e}')
        return 1


def run_watcher_backfill_db(args, pipeline: ThothPipeline):
    """Backfill RAG index from database markdown content."""
    import asyncio
    import json
    import re
    from uuid import UUID

    import asyncpg
    from langchain_core.documents import Document

    try:
        logger.info('Starting RAG database backfill process...')
        logger.info('This will index all papers with markdown_content from the database')

        # Get database URL
        db_url = getattr(pipeline.config.secrets, 'database_url', None)
        if not db_url:
            logger.error('DATABASE_URL not configured')
            return 1

        # Get RAG manager components for chunking and embedding
        rag_service = pipeline.services.get_service('rag')
        rag_manager = rag_service.rag_manager
        config = pipeline.config

        # Helper to strip images from markdown
        def strip_images(content: str) -> str:
            """Strip markdown image references from content."""
            image_pattern = r'!\[[^\]]*\]\([^)]+\)|!\[[^\]]*\]\[[^\]]*\]'
            content = re.sub(image_pattern, '', content)
            content = re.sub(r'\n{3,}', '\n\n', content)
            return content.strip()

        # Helper to check for images
        def has_images(content: str) -> bool:
            """Check if content has markdown image references."""
            image_pattern = r'!\[[^\]]*\]\([^)]+\)|!\[[^\]]*\]\[[^\]]*\]'
            return bool(re.search(image_pattern, content))

        async def do_full_backfill():
            """Run the entire backfill in a single async context."""
            # Create a single connection for the entire operation
            conn = await asyncpg.connect(db_url)
            
            try:
                # Get papers with markdown content
                if hasattr(args, 'force') and args.force:
                    query = """
                        SELECT pm.id, pm.title, pm.doi, pm.authors, pp.markdown_content
                        FROM paper_metadata pm
                        JOIN processed_papers pp ON pp.paper_id = pm.id
                        WHERE pp.markdown_content IS NOT NULL 
                          AND pp.markdown_content != ''
                        ORDER BY pm.created_at DESC
                    """
                else:
                    query = """
                        SELECT pm.id, pm.title, pm.doi, pm.authors, pp.markdown_content
                        FROM paper_metadata pm
                        JOIN processed_papers pp ON pp.paper_id = pm.id
                        LEFT JOIN document_chunks dc ON dc.paper_id = pm.id
                        WHERE pp.markdown_content IS NOT NULL 
                          AND pp.markdown_content != ''
                          AND dc.id IS NULL
                        ORDER BY pm.created_at DESC
                    """

                if hasattr(args, 'limit') and args.limit:
                    query += f' LIMIT {args.limit}'

                papers = await conn.fetch(query)
                logger.info(f'Found {len(papers)} papers to index')

                if not papers:
                    return {'papers_indexed': 0, 'total_chunks': 0, 'errors': []}

                total_papers = 0
                total_chunks = 0
                errors = []

                # Set up JSON codec for the connection
                await conn.set_type_codec(
                    'jsonb',
                    encoder=json.dumps,
                    decoder=json.loads,
                    schema='pg_catalog'
                )

                for i, row in enumerate(papers, 1):
                    paper_id = row['id']
                    title = row['title'] or 'Unknown'
                    content = row['markdown_content']

                    try:
                        logger.info(f'  [{i}/{len(papers)}] Indexing: {title[:50]}...')

                        # Strip images if configured
                        if config.rag_config.skip_files_with_images and has_images(content):
                            content = strip_images(content)
                            if len(content.strip()) < 100:
                                logger.warning(f'    Skipped: insufficient content after image removal')
                                continue

                        # Prepare metadata
                        metadata = {
                            'paper_id': str(paper_id),
                            'title': title,
                            'doi': row['doi'],
                            'authors': row['authors'],
                            'document_type': 'article',
                            'source': f"database:paper:{paper_id}",
                        }

                        # Split into chunks using RAG manager's splitter
                        chunks = rag_manager.text_splitter.split_text(content)

                        # Generate embeddings for all chunks at once
                        embeddings = rag_manager.embedding_manager.get_embedding_model().embed_documents(chunks)

                        # Insert chunks into database
                        chunk_ids = []
                        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                            chunk_metadata = {
                                **metadata,
                                'chunk_index': idx,
                                'total_chunks': len(chunks),
                            }
                            
                            # Clean metadata values
                            clean_metadata = {}
                            for k, v in chunk_metadata.items():
                                if v is None:
                                    clean_metadata[k] = None
                                elif isinstance(v, (str, int, float, bool, list, dict)):
                                    clean_metadata[k] = v
                                else:
                                    clean_metadata[k] = str(v)

                            # Convert embedding to PostgreSQL vector format
                            embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

                            result = await conn.fetchrow(
                                """
                                INSERT INTO document_chunks
                                (paper_id, content, chunk_index, chunk_type, metadata, embedding, token_count)
                                VALUES ($1, $2, $3, $4, $5::jsonb, $6::vector, $7)
                                ON CONFLICT (paper_id, chunk_index)
                                DO UPDATE SET
                                    content = EXCLUDED.content,
                                    embedding = EXCLUDED.embedding,
                                    metadata = EXCLUDED.metadata,
                                    updated_at = CURRENT_TIMESTAMP
                                RETURNING id
                                """,
                                paper_id,
                                chunk_text,
                                idx,
                                'text',
                                clean_metadata,
                                embedding_str,
                                len(chunk_text.split()),
                            )
                            chunk_ids.append(str(result['id']))

                        total_chunks += len(chunk_ids)
                        total_papers += 1
                        logger.success(f'    ✅ Indexed {len(chunk_ids)} chunks')

                    except Exception as e:
                        error_msg = f'Failed to index paper {paper_id} ({title}): {e}'
                        logger.error(f'    ❌ {error_msg}')
                        errors.append(error_msg)
                        continue

                return {
                    'papers_indexed': total_papers,
                    'total_chunks': total_chunks,
                    'errors': errors,
                }

            finally:
                await conn.close()

        # Run the entire backfill in a single async context
        logger.info('Querying database for papers with markdown content...')
        result = asyncio.run(do_full_backfill())

        total_papers = result['papers_indexed']
        total_chunks = result['total_chunks']
        errors = result['errors']

        # Show summary
        logger.info('\n' + '=' * 60)
        logger.info('Database Backfill Summary:')
        logger.info(f'  Total papers processed: {total_papers}')
        logger.info(f'  Total chunks created: {total_chunks}')

        if errors:
            logger.warning(f'  Errors encountered: {len(errors)}')
            if hasattr(args, 'verbose') and args.verbose:
                for error in errors:
                    logger.warning(f'    - {error}')
        else:
            logger.success('  ✅ All papers processed successfully!')

        # Show vector store stats
        try:
            stats = rag_service.get_statistics()
            logger.info('\nVector Store Statistics:')
            logger.info(f"  Total chunks: {stats.get('total_chunks', 0)}")
            logger.info(f"  Total papers indexed: {stats.get('total_papers', 0)}")
            logger.info(f"  Backend: {stats.get('backend', 'Unknown')}")
        except Exception as e:
            logger.warning(f'Could not retrieve vector store stats: {e}')

        logger.info('=' * 60)

        return 0 if not errors else 1

    except Exception as e:
        logger.error(f'Error during database backfill: {e}')
        import traceback
        traceback.print_exc()
        return 1


def configure_subparser(subparsers):
    """Configure the subparser for the RAG watcher commands."""
    parser = subparsers.add_parser(
        'rag-watcher', help='Manage the RAG watcher service for automatic document processing'
    )

    watcher_subparsers = parser.add_subparsers(
        dest='watcher_command', help='RAG watcher command to run'
    )

    # Start command
    start_parser = watcher_subparsers.add_parser(
        'start', help='Start the RAG watcher service'
    )
    start_parser.add_argument(
        '--pdf-dir', type=str, help='Directory to watch for PDFs (optional)'
    )
    start_parser.add_argument(
        '--markdown-dir', type=str, help='Directory to watch for markdown (optional)'
    )
    start_parser.add_argument(
        '--notes-dir', type=str, help='Directory to watch for notes (optional)'
    )
    start_parser.set_defaults(func=run_watcher_start)

    # Stop command
    stop_parser = watcher_subparsers.add_parser(
        'stop', help='Stop the RAG watcher service'
    )
    stop_parser.set_defaults(func=run_watcher_stop)

    # Status command
    status_parser = watcher_subparsers.add_parser(
        'status', help='Show RAG watcher status'
    )
    status_parser.set_defaults(func=run_watcher_status)

    # Backfill command (file-based)
    backfill_parser = watcher_subparsers.add_parser(
        'backfill',
        help='Backfill all existing markdown files into the RAG system',
    )
    backfill_parser.add_argument(
        '--verbose', action='store_true', help='Show detailed error messages'
    )
    backfill_parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip files that are already indexed (not yet implemented)',
    )
    backfill_parser.set_defaults(func=run_watcher_backfill)

    # Backfill-db command (database-based - RECOMMENDED)
    backfill_db_parser = watcher_subparsers.add_parser(
        'backfill-db',
        help='Backfill RAG index from database markdown content (recommended)',
    )
    backfill_db_parser.add_argument(
        '--verbose', action='store_true', help='Show detailed error messages'
    )
    backfill_db_parser.add_argument(
        '--force',
        action='store_true',
        help='Re-index all papers, even if already indexed',
    )
    backfill_db_parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of papers to index (useful for testing)',
    )
    backfill_db_parser.set_defaults(func=run_watcher_backfill_db)

    parser.set_defaults(func=lambda args, pipeline: run_watcher_status(args, pipeline))
