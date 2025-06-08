from pathlib import Path

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.utilities.config import get_config


def run_reprocess_note(args):
    """
    Regenerate the note for an existing article.
    """
    logger.info(f'Attempting to reprocess note for article_id: {args.article_id}')
    config = get_config()
    pipeline = ThothPipeline(
        ocr_api_key=config.api_keys.mistral_key,
        llm_api_key=config.api_keys.openrouter_key,
        templates_dir=Path(config.templates_dir),
        prompts_dir=Path(config.prompts_dir),
        output_dir=Path(config.output_dir),
        notes_dir=Path(config.notes_dir),
        api_base_url=config.api_server_config.base_url,
    )
    article_id = args.article_id
    regen_data = pipeline.citation_tracker.get_article_data_for_regeneration(article_id)

    if not regen_data:
        logger.error(
            f"Could not retrieve data for article_id '{article_id}'. "
            'Ensure the article exists in the graph and has all necessary data (PDF path, Markdown path, analysis).'
        )
        return 1

    try:
        logger.info(f'Regenerating note for {article_id}...')
        note_path, new_pdf_path, new_markdown_path = pipeline.services.note.create_note(
            pdf_path=regen_data['pdf_path'],
            markdown_path=regen_data['markdown_path'],
            analysis=regen_data['analysis'],
            citations=regen_data['citations'],
        )
        logger.info(f'Successfully regenerated note for {article_id} at: {note_path}')
        logger.info(f'Associated PDF path: {new_pdf_path}')
        logger.info(f'Associated Markdown path: {new_markdown_path}')
        pipeline.citation_tracker.update_article_file_paths(
            article_id=article_id,
            new_pdf_path=new_pdf_path,
            new_markdown_path=new_markdown_path,
        )
        logger.info(f'Updated file paths in tracker for {article_id} if changed.')
        return 0
    except Exception as e:
        logger.error(
            f"Error during note reprocessing for article_id '{article_id}': {e}"
        )
        return 1


def run_regenerate_all_notes(args):
    """
    Regenerate all notes for all articles in the citation graph.
    """
    if args.force:
        logger.warning('Force flag enabled - will overwrite existing notes')
    logger.info('Attempting to regenerate all notes for all articles.')
    config = get_config()
    try:
        pipeline = ThothPipeline(
            ocr_api_key=config.api_keys.mistral_key,
            llm_api_key=config.api_keys.openrouter_key,
            templates_dir=Path(config.templates_dir),
            prompts_dir=Path(config.prompts_dir),
            output_dir=Path(config.output_dir),
            notes_dir=Path(config.notes_dir),
            api_base_url=config.api_server_config.base_url,
        )
        successfully_regenerated_files = pipeline.regenerate_all_notes()
        logger.info(
            f'Regeneration process completed. {len(successfully_regenerated_files)} notes reported as successfully regenerated.'
        )
        # Note: PDFTracker update logic moved to PDFMonitor to avoid duplication
        return 0
    except Exception as e:
        logger.error(f'Error during overall regeneration of all notes: {e}')
        return 1


def run_consolidate_tags(args):
    """
    Consolidate existing tags and suggest additional relevant tags for all articles.
    """
    if args.force:
        logger.warning('Force flag enabled - will overwrite existing tags')
    logger.info('Attempting to consolidate tags and retag all articles.')
    config = get_config()
    try:
        pipeline = ThothPipeline(
            ocr_api_key=config.api_keys.mistral_key,
            llm_api_key=config.api_keys.openrouter_key,
            templates_dir=Path(config.templates_dir),
            prompts_dir=Path(config.prompts_dir),
            output_dir=Path(config.output_dir),
            notes_dir=Path(config.notes_dir),
            api_base_url=config.api_server_config.base_url,
        )
        stats = pipeline.consolidate_and_retag_all_articles()
        logger.info('Tag consolidation and re-tagging process completed successfully.')
        logger.info('Summary statistics:')
        logger.info(f'  - Articles processed: {stats["articles_processed"]}')
        logger.info(f'  - Articles updated: {stats["articles_updated"]}')
        logger.info(f'  - Tags consolidated: {stats["tags_consolidated"]}')
        logger.info(f'  - Tags added: {stats["tags_added"]}')
        logger.info(f'  - Original tag count: {stats["original_tag_count"]}')
        logger.info(f'  - Final tag count: {stats["final_tag_count"]}')
        logger.info(f'  - Total vocabulary size: {stats["total_vocabulary_size"]}')
        return 0
    except Exception as e:
        logger.error(f'Error during tag consolidation and re-tagging: {e}')
        return 1


def configure_subparser(subparsers):
    """Configure the subparser for note-related commands."""
    reprocess_parser = subparsers.add_parser(
        'reprocess-note',
        help='Regenerate the note for an existing article in the graph',
    )
    reprocess_parser.add_argument(
        '--article-id',
        type=str,
        required=True,
        help='The unique ID of the article (e.g., DOI) whose note needs to be reprocessed.',
    )
    reprocess_parser.set_defaults(func=run_reprocess_note)

    regenerate_all_parser = subparsers.add_parser(
        'regenerate-all-notes',
        help='Regenerate all markdown notes for all articles in the graph.',
    )
    regenerate_all_parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration even if notes already exist.',
    )
    regenerate_all_parser.set_defaults(func=run_regenerate_all_notes)

    consolidate_tags_parser = subparsers.add_parser(
        'consolidate-tags',
        help='Consolidate existing tags and suggest additional relevant tags for all articles in the graph.',
    )
    consolidate_tags_parser.add_argument(
        '--force',
        action='store_true',
        help='Force consolidation and re-tagging even if recently performed.',
    )
    consolidate_tags_parser.set_defaults(func=run_consolidate_tags)
