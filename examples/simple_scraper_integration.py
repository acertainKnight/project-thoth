#!/usr/bin/env python3
"""
Simple scraper integration example.

This shows how to integrate the ScrapeFilter directly into your scraping pipeline
without needing an API server.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add the src directory to the path so we can import thoth modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from thoth.ingestion.filter import Filter as ScrapeFilter
from thoth.utilities.schemas import ScrapedArticleMetadata


def simulate_arxiv_scraper():
    """Simulate an ArXiv scraper that finds new articles."""
    # This would be your actual scraping logic
    scraped_articles = [
        {
            'title': 'Attention Is All You Need',
            'authors': ['Vaswani, A.', 'Shazeer, N.', 'Parmar, N.'],
            'abstract': 'We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.',
            'arxiv_id': '1706.03762',
            'published': '2017-06-12',
            'pdf_url': 'https://arxiv.org/pdf/1706.03762.pdf',
        },
        {
            'title': 'BERT: Pre-training of Deep Bidirectional Transformers',
            'authors': ['Devlin, J.', 'Chang, M.', 'Lee, K.'],
            'abstract': 'We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers.',
            'arxiv_id': '1810.04805',
            'published': '2018-10-11',
            'pdf_url': 'https://arxiv.org/pdf/1810.04805.pdf',
        },
        {
            'title': 'Quantum Error Correction with Surface Codes',
            'authors': ['Fowler, A.', 'Mariantoni, M.'],
            'abstract': 'We present a comprehensive analysis of quantum error correction using surface codes for fault-tolerant quantum computation.',
            'published': '2023-08-15',
            'pdf_url': 'https://example.com/quantum_paper.pdf',
        },
    ]

    return scraped_articles


def process_scraped_article(scrape_filter: ScrapeFilter, scraped_data: dict) -> dict:
    """
    Process a single scraped article through the filter.

    Args:
        scrape_filter: The initialized scrape filter.
        scraped_data: Raw scraped data from your scraper.

    Returns:
        dict: Processing result with decision and metadata.
    """
    # Convert scraped data to ScrapedArticleMetadata
    metadata = ScrapedArticleMetadata(
        title=scraped_data['title'],
        authors=scraped_data.get('authors', []),
        abstract=scraped_data.get('abstract'),
        arxiv_id=scraped_data.get('arxiv_id'),
        publication_date=scraped_data.get('published'),
        url=f'https://arxiv.org/abs/{scraped_data["arxiv_id"]}'
        if scraped_data.get('arxiv_id')
        else None,
        pdf_url=scraped_data.get('pdf_url'),
        source='arxiv',
        scrape_timestamp=datetime.now().isoformat(),
    )

    # Process through the filter
    result = scrape_filter.process_scraped_article(metadata, download_pdf=True)

    return result


def main():
    """Main scraper workflow."""
    print('🔍 Simple Scraper Integration Demo')
    print('=' * 40)

    # Initialize filter once
    print('🚀 Initializing scrape filter...')
    scrape_filter = ScrapeFilter()
    print('✅ Filter initialized')

    # Simulate scraping new articles
    print('\n📡 Scraping new articles...')
    scraped_articles = simulate_arxiv_scraper()
    print(f'Found {len(scraped_articles)} new articles')

    # Process each article
    print('\n🔍 Processing articles through filter...')
    results = []

    for i, article_data in enumerate(scraped_articles, 1):
        print(f'\n--- Article {i}: {article_data["title"][:50]}... ---')

        # Process the article
        result = process_scraped_article(scrape_filter, article_data)
        results.append(result)

        # Show result
        decision = result['decision']
        evaluation = result['evaluation']

        print(f'Decision: {decision.upper()}')
        if evaluation:
            print(f'Score: {evaluation.relevance_score:.2f}')
            print(f'Matching queries: {", ".join(evaluation.matching_queries)}')
            if result['pdf_downloaded']:
                print(f'PDF downloaded: {result["pdf_path"]}')

        if result['error_message']:
            print(f'Error: {result["error_message"]}')

    # Show summary
    print('\n📊 Summary:')
    downloaded = sum(1 for r in results if r['decision'] == 'download')
    skipped = sum(1 for r in results if r['decision'] == 'skip')

    print(f'Total articles: {len(results)}')
    print(f'Downloaded: {downloaded}')
    print(f'Skipped: {skipped}')
    print(f'Download rate: {downloaded / len(results):.1%}')

    # Show filter statistics
    stats = scrape_filter.get_statistics()
    print('\n📈 Overall filter statistics:')
    print(f'Total processed: {stats["total_articles"]}')
    print(f'Average score: {stats["average_score"]:.2f}')
    print(f'Available queries: {stats["available_queries"]}')

    # Show log location
    print(f'\n📝 Detailed logs: {scrape_filter.log_file}')

    print('\n✅ Scraping workflow completed!')


def batch_processing_example():
    """Example of batch processing multiple articles."""
    print('\n🔄 Batch Processing Example')
    print('=' * 30)

    scrape_filter = ScrapeFilter()

    # Simulate a batch of scraped articles
    batch_data = simulate_arxiv_scraper()

    print(f'Processing batch of {len(batch_data)} articles...')

    batch_results = []
    for article_data in batch_data:
        result = process_scraped_article(scrape_filter, article_data)
        batch_results.append(result)

    # Process results
    for result in batch_results:
        if result['decision'] == 'download':
            print(f'✅ Downloaded: {result["log_entry"].article_metadata.title}')
            # Here you could continue with your processing pipeline
            # e.g., send to analysis, add to database, etc.
        else:
            print(f'⏭️  Skipped: {result["log_entry"].article_metadata.title}')

    return batch_results


def continuous_scraping_example():
    """Example of continuous scraping with the filter."""
    print('\n🔄 Continuous Scraping Example')
    print('=' * 35)

    # Initialize filter once
    # scrape_filter = ScrapeFilter()

    print("""
# In your actual scraper, this would be a continuous loop:

import time
from your_scraper import get_new_articles

scrape_filter = ScrapeFilter()

while True:
    # Get new articles from your scraper
    new_articles = get_new_articles()

    for article_data in new_articles:
        # Convert to metadata format
        metadata = ScrapedArticleMetadata(
            title=article_data['title'],
            authors=article_data.get('authors', []),
            abstract=article_data.get('abstract'),
            # ... other fields from your scraper
            source='your_scraper_name',
            scrape_timestamp=datetime.now().isoformat(),
        )

        # Process through filter
        result = scrape_filter.process_scraped_article(metadata)

        if result['decision'] == 'download':
            print(f"✅ Downloaded: {metadata.title}")
            # Continue with your processing pipeline
            # e.g., analyze_pdf(result['pdf_path'])
        else:
            print(f"⏭️  Skipped: {metadata.title}")

    # Wait before next scrape
    time.sleep(300)  # 5 minutes
    """)


if __name__ == '__main__':
    main()
    batch_processing_example()
    continuous_scraping_example()
