#!/usr/bin/env python3
"""
Focused test script for LLM batch processing optimizations.
"""

import time

from loguru import logger

from thoth.analyze.citations.citations import CitationProcessor

# Sample markdown content for testing
SAMPLE_MARKDOWN_CONTENT = """
# Machine Learning in Healthcare: A Review

## Abstract
This paper reviews recent advances in machine learning applications for healthcare...

## Introduction
Healthcare applications of machine learning have grown rapidly...

## References

1. Smith, J., & Doe, A. (2023). Machine Learning Applications in Healthcare. Journal of AI Research, 15(3), 123-145. doi:10.1234/example.2023.healthcare

2. Brown, K., Wilson, M., & Davis, L. (2022). Deep Learning Methods for Natural Language Processing. Proceedings of NeurIPS, 34, 567-580. arXiv:2201.12345

3. Johnson, R. (2023). Attention Mechanisms in Transformer Models. Nature Machine Intelligence, 5(2), 89-102. doi:10.1038/s42256-023-00123-4

4. Chen, L., et al. (2022). BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. In Proceedings of NAACL-HLT, pages 4171-4186. arXiv:1810.04805

5. Williams, P., & Taylor, S. (2021). Computer Vision Applications in Autonomous Vehicles. IEEE Transactions on Pattern Analysis and Machine Intelligence, 43(7), 2456-2471. doi:10.1109/TPAMI.2021.1234567

6. Martinez, A., Rodriguez, C., & Lopez, F. (2023). Graph Neural Networks for Social Network Analysis. Proceedings of ICML, 40, 1123-1135.

7. Anderson, K. (2022). Reinforcement Learning in Robotics: A Survey. Robotics and Autonomous Systems, 98, 45-67. doi:10.1016/j.robot.2022.103456

8. Zhang, H., Li, Y., & Wang, X. (2023). Federated Learning for Privacy-Preserving Machine Learning. Communications of the ACM, 66(4), 78-89.
"""


def test_batch_size(batch_size: int) -> dict:
    """Test a specific batch size and return performance metrics."""
    logger.info(f'🧪 Testing batch size: {batch_size}')

    try:
        # Create citation processor with specific batch size
        processor = CitationProcessor(
            model='openai/gpt-4o-mini',  # Use faster model for testing
            citation_batch_size=batch_size,
            use_semanticscholar=False,  # Disable for isolated testing
            use_opencitations=False,
            use_scholarly=False,
            use_arxiv=False,
        )

        start_time = time.time()
        citations = processor.process_document(SAMPLE_MARKDOWN_CONTENT)
        processing_time = time.time() - start_time

        result = {
            'success': True,
            'batch_size': batch_size,
            'processing_time': processing_time,
            'citations_extracted': len(citations),
            'document_citation': sum(1 for c in citations if c.is_document_citation),
            'reference_citations': sum(
                1 for c in citations if not c.is_document_citation
            ),
            'citations_per_second': len(citations) / processing_time
            if processing_time > 0
            else 0,
            'avg_time_per_citation': processing_time / len(citations)
            if citations
            else 0,
        }

        logger.info(
            f'✅ Batch size {batch_size}: {len(citations)} citations in {processing_time:.2f}s'
        )
        logger.info(f'   📊 Rate: {result["citations_per_second"]:.1f} citations/sec')

        return result

    except Exception as e:
        logger.error(f'❌ Batch size {batch_size} failed: {e}')
        return {'success': False, 'batch_size': batch_size, 'error': str(e)}


def main():
    """Main test function."""
    logger.info('🚀 Testing LLM Batch Processing Optimizations')
    logger.info('=' * 60)

    batch_sizes = [1, 5, 10, 15, 20]
    results = []

    for batch_size in batch_sizes:
        result = test_batch_size(batch_size)
        results.append(result)

        # Add a small delay between tests
        time.sleep(1)

    # Analysis and summary
    logger.info('\n📈 BATCH PROCESSING PERFORMANCE ANALYSIS')
    logger.info('=' * 60)

    successful_results = [r for r in results if r.get('success')]

    if successful_results:
        print(
            f'\n{"Batch Size":<12} {"Time (s)":<10} {"Citations":<10} {"Rate (c/s)":<12} {"Status"}'
        )
        print('-' * 60)

        for result in results:
            if result.get('success'):
                print(
                    f'{result["batch_size"]:<12} {result["processing_time"]:<10.2f} '
                    f'{result["citations_extracted"]:<10} {result["citations_per_second"]:<12.1f} ✅'
                )
            else:
                print(
                    f'{result["batch_size"]:<12} {"N/A":<10} {"N/A":<10} {"N/A":<12} ❌'
                )

        # Find optimal batch size (fastest processing)
        optimal = min(successful_results, key=lambda x: x['processing_time'])
        speedup_baseline = max(successful_results, key=lambda x: x['processing_time'])

        speedup = speedup_baseline['processing_time'] / optimal['processing_time']

        print('\n🎯 OPTIMIZATION RESULTS:')
        print(f'   • Optimal Batch Size: {optimal["batch_size"]}')
        print(f'   • Best Processing Time: {optimal["processing_time"]:.2f}s')
        print(f'   • Citations Extracted: {optimal["citations_extracted"]}')
        print(f'   • Performance Improvement: {speedup:.1f}x faster than worst case')
        print(f'   • Optimal Rate: {optimal["citations_per_second"]:.1f} citations/sec')

        # Check if batch processing is beneficial
        batch_size_1_result = next(
            (r for r in successful_results if r['batch_size'] == 1), None
        )
        if batch_size_1_result and optimal['batch_size'] > 1:
            batch_speedup = (
                batch_size_1_result['processing_time'] / optimal['processing_time']
            )
            print(
                f'   • Batch Processing Speedup: {batch_speedup:.1f}x faster than individual processing'
            )

        print('\n💡 RECOMMENDATIONS:')
        if optimal['batch_size'] > 1:
            print(
                f'   ✅ Use batch size {optimal["batch_size"]} for optimal performance'
            )
            print(f'   ✅ Batch processing is {speedup:.1f}x more efficient')
        else:
            print('   ⚠️  Individual processing (batch size 1) performed best')
            print('   ⚠️  Consider checking prompt templates and model reliability')

    else:
        print('❌ All batch processing tests failed!')
        print('Check your configuration and prompt templates.')

    logger.info('\n🎉 LLM batch processing tests completed!')


if __name__ == '__main__':
    main()
