from loguru import logger

from thoth.pipeline import ThothPipeline


def run_rag_index(args, pipeline: ThothPipeline):
    """
    Index all documents in the knowledge base.
    """
    if args.force:
        logger.warning('Force flag enabled - will reindex all documents')
    try:
        logger.info('Starting knowledge base indexing for RAG system...')
        stats = pipeline.knowledge_pipeline.index_knowledge_base()
        logger.info('Knowledge base indexing completed:')
        logger.info(f'  Total files indexed: {stats["total_files"]}')
        logger.info(f'  - Markdown files: {stats["markdown_files"]}')
        logger.info(f'  - Note files: {stats["note_files"]}')
        logger.info(f'  Total chunks created: {stats["total_chunks"]}')
        if stats['errors']:
            logger.warning(f'  Errors encountered: {len(stats["errors"])}')
            for error in stats['errors']:
                logger.warning(f'    - {error}')
        if 'vector_store' in stats:
            logger.info('Vector store info:')
            logger.info(f'  Collection: {stats["vector_store"]["collection_name"]}')
            logger.info(f'  Documents: {stats["vector_store"]["document_count"]}')
        return 0
    except Exception as e:
        logger.error(f'Error indexing knowledge base: {e}')
        return 1


def run_rag_search(args, pipeline: ThothPipeline):
    """
    Search the knowledge base.
    """
    try:
        logger.info(f'Searching knowledge base for: {args.query}')
        filter_dict = None
        if args.filter_type != 'all':
            filter_dict = {'document_type': args.filter_type}
        results = pipeline.knowledge_pipeline.search_knowledge_base(
            query=args.query,
            k=args.k,
            filter=filter_dict,
        )
        if not results:
            logger.info('No results found.')
            return 0
        logger.info(f'Found {len(results)} results:\\n')
        for i, result in enumerate(results, 1):
            logger.info(f'Result {i}:')
            logger.info(f'  Title: {result["title"]}')
            logger.info(f'  Type: {result["document_type"]}')
            logger.info(f'  Score: {result["score"]:.3f}')
            logger.info(f'  Source: {result["source"]}')
            logger.info(f'  Preview: {result["content"][:200]}...')
            logger.info('')
        return 0
    except Exception as e:
        logger.error(f'Error searching knowledge base: {e}')
        return 1


def run_rag_ask(args, pipeline: ThothPipeline):
    """
    Ask a question about the knowledge base.
    """
    try:
        logger.info(f'Asking question: {args.question}')
        response = pipeline.knowledge_pipeline.ask_knowledge_base(
            question=args.question,
            k=args.k,
        )
        logger.info('\\nQuestion:')
        logger.info(f'  {response["question"]}')
        logger.info('\\nAnswer:')
        logger.info(f'  {response["answer"]}')
        if response.get('sources'):
            logger.info('\\nSources:')
            for i, source in enumerate(response['sources'], 1):
                title = source['metadata'].get('title', 'Unknown')
                doc_type = source['metadata'].get('document_type', 'Unknown')
                logger.info(f'  {i}. {title} ({doc_type})')
        return 0
    except Exception as e:
        logger.error(f'Error asking knowledge base: {e}')
        return 1


def run_rag_stats(args, pipeline: ThothPipeline):
    """
    Show RAG system statistics.
    """
    if args.verbose:
        logger.info('Verbose mode enabled - showing detailed statistics')
    try:
        logger.info('RAG System Statistics:')
        stats = pipeline.knowledge_pipeline.get_rag_stats()
        logger.info(f'  Documents indexed: {stats.get("document_count", 0)}')
        logger.info(f'  Collection name: {stats.get("collection_name", "Unknown")}')
        logger.info(f'  Embedding model: {stats.get("embedding_model", "Unknown")}')
        logger.info(f'  QA model: {stats.get("qa_model", "Unknown")}')
        logger.info(f'  Chunk size: {stats.get("chunk_size", "Unknown")}')
        logger.info(f'  Chunk overlap: {stats.get("chunk_overlap", "Unknown")}')
        logger.info(f'  Vector DB path: {stats.get("persist_directory", "Unknown")}')
        return 0
    except Exception as e:
        logger.error(f'Error getting RAG stats: {e}')
        return 1


def run_rag_clear(args, pipeline: ThothPipeline):
    """
    Clear the RAG vector index.
    """
    try:
        if not args.confirm:
            print(
                '\\nWARNING: This will delete all indexed documents from the RAG system.'
            )
            print('You will need to re-index all documents to use RAG features again.')
            response = input('Type "clear" to confirm: ')
            if response.lower() != 'clear':
                logger.info('Clear operation cancelled.')
                return 0
        logger.warning('Clearing RAG vector index...')
        pipeline.knowledge_pipeline.clear_rag_index()
        logger.info('RAG vector index cleared successfully.')
        logger.info('Run "thoth rag index" to re-index your knowledge base.')
        return 0
    except Exception as e:
        logger.error(f'Error clearing RAG index: {e}')
        return 1


def run_rag_command(args, pipeline: ThothPipeline):
    """Handle RAG commands."""
    if not hasattr(args, 'rag_command') or not args.rag_command:
        logger.error('No RAG subcommand specified')
        return 1

    if args.rag_command == 'index':
        return run_rag_index(args, pipeline)
    elif args.rag_command == 'search':
        return run_rag_search(args, pipeline)
    elif args.rag_command == 'ask':
        return run_rag_ask(args, pipeline)
    elif args.rag_command == 'stats':
        return run_rag_stats(args, pipeline)
    elif args.rag_command == 'clear':
        return run_rag_clear(args, pipeline)
    else:
        logger.error(f'Unknown RAG command: {args.rag_command}')
        return 1


def configure_subparser(subparsers):
    """Configure the subparser for the RAG command."""
    parser = subparsers.add_parser(
        'rag', help='Manage the RAG (Retrieval-Augmented Generation) knowledge base'
    )
    rag_subparsers = parser.add_subparsers(
        dest='rag_command', help='RAG command to run'
    )

    index_parser = rag_subparsers.add_parser(
        'index', help='Index all documents in the knowledge base'
    )
    index_parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-indexing of all documents.',
    )
    index_parser.set_defaults(func=run_rag_index)

    search_parser = rag_subparsers.add_parser(
        'search', help='Search the knowledge base'
    )
    search_parser.add_argument('--query', type=str, required=True, help='Search query')
    search_parser.add_argument(
        '--k', type=int, default=4, help='Number of results to return (default: 4)'
    )
    search_parser.add_argument(
        '--filter-type',
        type=str,
        choices=['note', 'article', 'all'],
        default='all',
        help='Filter by document type',
    )
    search_parser.set_defaults(func=run_rag_search)

    ask_parser = rag_subparsers.add_parser(
        'ask', help='Ask a question about the knowledge base'
    )
    ask_parser.add_argument(
        '--question', type=str, required=True, help='Question to ask'
    )
    ask_parser.add_argument(
        '--k', type=int, default=4, help='Number of context documents (default: 4)'
    )
    ask_parser.set_defaults(func=run_rag_ask)

    stats_parser = rag_subparsers.add_parser(
        'stats', help='Show statistics about the RAG system'
    )
    stats_parser.set_defaults(func=run_rag_stats)

    clear_parser = rag_subparsers.add_parser('clear', help='Clear the RAG vector index')
    clear_parser.add_argument(
        '--confirm',
        action='store_true',
        help='Confirm clearing the index without prompting',
    )
    clear_parser.set_defaults(func=run_rag_clear)

    parser.set_defaults(func=run_rag_command)
