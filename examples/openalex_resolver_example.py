"""
Example usage of OpenAlexResolver for citation matching.

This script demonstrates how to use the OpenAlex resolver to match
citations and retrieve metadata.
"""

import asyncio

from thoth.analyze.citations.openalex_resolver import OpenAlexResolver
from thoth.utilities.schemas import Citation


async def main():
    """Demonstrate OpenAlex resolver usage."""

    # Initialize resolver
    # Note: Providing an email gets you into the "polite pool" with 10x higher rate limits
    resolver = OpenAlexResolver(
        email='your-email@example.com',  # Optional but recommended
        requests_per_second=10.0,         # Rate limit
        max_retries=3,                    # Retry attempts
        timeout=30,                       # Request timeout
    )

    # Example 1: Single citation resolution
    print('=' * 80)
    print('Example 1: Single Citation Resolution')
    print('=' * 80)

    citation = Citation(
        title='Attention Is All You Need',
        authors=['Vaswani', 'Shazeer', 'Parmar'],
        year=2017,
    )

    candidates = await resolver.resolve_citation(citation)

    print(f'\nFound {len(candidates)} match candidates:')
    for i, candidate in enumerate(candidates, 1):
        print(f'\n{i}. {candidate.title}')
        print(f'   OpenAlex ID: {candidate.openalex_id}')
        print(f'   DOI: {candidate.doi}')
        print(f'   Authors: {", ".join(candidate.authors[:3]) if candidate.authors else "N/A"}...')
        print(f'   Year: {candidate.year}')
        print(f'   Citations: {candidate.citation_count}')
        print(f'   Confidence: {candidate.confidence_score:.2f}')

        if candidate.is_open_access:
            print(f'   ✓ Open Access: {candidate.pdf_url}')

    # Example 2: Batch resolution
    print('\n' + '=' * 80)
    print('Example 2: Batch Resolution')
    print('=' * 80)

    citations = [
        Citation(
            title='BERT: Pre-training of Deep Bidirectional Transformers',
            year=2019,
        ),
        Citation(
            title='Deep Residual Learning for Image Recognition',
            authors=['He', 'Zhang', 'Ren', 'Sun'],
            year=2016,
        ),
        Citation(
            title='ImageNet Classification with Deep Convolutional Neural Networks',
            year=2012,
        ),
    ]

    results = await resolver.batch_resolve(citations)

    print(f'\nBatch resolved {len(citations)} citations:')
    for citation, candidates in results.items():
        print(f'\n• {citation.title[:60]}...')
        if candidates:
            best = candidates[0]
            print(f'  ✓ Matched: {best.title[:60]}...')
            print(f'    DOI: {best.doi}')
            print(f'    Confidence: {best.confidence_score:.2f}')
        else:
            print('  ✗ No matches found')

    # Example 3: Convert match to Citation
    print('\n' + '=' * 80)
    print('Example 3: Convert Match to Citation')
    print('=' * 80)

    if candidates:
        best_match = candidates[0]
        enriched_citation = best_match.to_citation()

        print(f'\nOriginal citation:')
        print(f'  Title: {citation.title}')
        print(f'  Authors: {citation.authors}')
        print(f'  Year: {citation.year}')

        print(f'\nEnriched citation:')
        print(f'  Title: {enriched_citation.title}')
        print(f'  Authors: {enriched_citation.authors}')
        print(f'  Year: {enriched_citation.year}')
        print(f'  DOI: {enriched_citation.doi}')
        print(f'  Venue: {enriched_citation.venue}')
        print(f'  Citations: {enriched_citation.citation_count}')
        print(f'  Backup ID: {enriched_citation.backup_id}')
        if enriched_citation.abstract:
            print(f'  Abstract: {enriched_citation.abstract[:150]}...')

    # Display statistics
    print('\n' + '=' * 80)
    print('Resolver Statistics')
    print('=' * 80)
    stats = resolver.get_statistics()
    for key, value in stats.items():
        print(f'  {key}: {value}')


if __name__ == '__main__':
    asyncio.run(main())
