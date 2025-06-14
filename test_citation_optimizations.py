#!/usr/bin/env python3
"""
Test script for citation processing optimizations.

This script tests the improved batch processing and API optimizations
for citation extraction and metadata enhancement.
"""

import asyncio
import json
import time
from typing import Any

from loguru import logger

from thoth.analyze.citations.citations import CitationProcessor
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.utilities.schemas import Citation

# Sample citations for testing
SAMPLE_CITATIONS_TEXT = """
1. Smith, J., & Doe, A. (2023). Machine Learning Applications in Healthcare. Journal of AI Research, 15(3), 123-145. doi:10.1234/example.2023.healthcare

2. Brown, K., Wilson, M., & Davis, L. (2022). Deep Learning Methods for Natural Language Processing. Proceedings of NeurIPS, 34, 567-580. arXiv:2201.12345

3. Johnson, R. (2023). Attention Mechanisms in Transformer Models. Nature Machine Intelligence, 5(2), 89-102. doi:10.1038/s42256-023-00123-4

4. Chen, L., et al. (2022). BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. In Proceedings of NAACL-HLT, pages 4171-4186. arXiv:1810.04805

5. Williams, P., & Taylor, S. (2021). Computer Vision Applications in Autonomous Vehicles. IEEE Transactions on Pattern Analysis and Machine Intelligence, 43(7), 2456-2471. doi:10.1109/TPAMI.2021.1234567

6. Martinez, A., Rodriguez, C., & Lopez, F. (2023). Graph Neural Networks for Social Network Analysis. Proceedings of ICML, 40, 1123-1135.

7. Anderson, K. (2022). Reinforcement Learning in Robotics: A Survey. Robotics and Autonomous Systems, 98, 45-67. doi:10.1016/j.robot.2022.103456

8. Zhang, H., Li, Y., & Wang, X. (2023). Federated Learning for Privacy-Preserving Machine Learning. Communications of the ACM, 66(4), 78-89.

9. Thompson, M., & Clark, J. (2022). Quantum Computing Applications in Cryptography. Quantum Information Processing, 21(5), 167-189. arXiv:2203.09876

10. Garcia, R., Patel, N., & Kim, S. (2023). Explainable AI for Medical Diagnosis. Artificial Intelligence in Medicine, 127, 102234. doi:10.1016/j.artmed.2023.102234
"""

# Sample markdown content for document processing
SAMPLE_MARKDOWN_CONTENT = f"""
# Deep Learning for Natural Language Processing: A Comprehensive Survey

## Abstract
This paper provides a comprehensive survey of deep learning techniques applied to natural language processing tasks...

## Introduction
Natural language processing has seen remarkable advances with the introduction of deep learning methods...

## Related Work
Previous work in this area includes various approaches to text processing and understanding...

## Methodology
We propose a novel approach that combines attention mechanisms with recurrent neural networks...

## Results
Our experiments show significant improvements over baseline methods...

## Conclusion
In conclusion, our approach demonstrates the effectiveness of deep learning in NLP tasks...

## References
{SAMPLE_CITATIONS_TEXT}
"""


class CitationProcessingTester:
    """Test suite for citation processing optimizations."""

    def __init__(
        self,
        test_semantic_scholar: bool = True,
        test_batch_processing: bool = True,
        batch_sizes_to_test: list[int] | None = None,
    ):
        """
        Initialize the tester.

        Args:
            test_semantic_scholar: Whether to test Semantic Scholar API optimizations
            test_batch_processing: Whether to test LLM batch processing improvements
            batch_sizes_to_test: List of batch sizes to benchmark
        """
        self.test_semantic_scholar = test_semantic_scholar
        self.test_batch_processing = test_batch_processing
        self.batch_sizes_to_test = batch_sizes_to_test or [1, 5, 10, 15, 20]

        logger.info('Citation Processing Optimization Tester initialized')

    def create_test_citations(self) -> list[Citation]:
        """Create a set of test citations with various identifier types."""
        test_citations = [
            Citation(
                title='Machine Learning Applications in Healthcare',
                authors=['Smith, J.', 'Doe, A.'],
                year=2023,
                journal='Journal of AI Research',
                doi='10.1234/example.2023.healthcare',
                volume='15',
                issue='3',
                pages='123-145',
            ),
            Citation(
                title='Deep Learning Methods for Natural Language Processing',
                authors=['Brown, K.', 'Wilson, M.', 'Davis, L.'],
                year=2022,
                venue='Proceedings of NeurIPS',
                backup_id='arxiv:2201.12345',
                volume='34',
                pages='567-580',
            ),
            Citation(
                title='Attention Mechanisms in Transformer Models',
                authors=['Johnson, R.'],
                year=2023,
                journal='Nature Machine Intelligence',
                doi='10.1038/s42256-023-00123-4',
                volume='5',
                issue='2',
                pages='89-102',
            ),
            Citation(
                title='BERT: Pre-training of Deep Bidirectional Transformers',
                authors=['Chen, L.'],
                year=2022,
                venue='Proceedings of NAACL-HLT',
                backup_id='arxiv:1810.04805',
                pages='4171-4186',
            ),
            Citation(
                title='Computer Vision Applications in Autonomous Vehicles',
                authors=['Williams, P.', 'Taylor, S.'],
                year=2021,
                journal='IEEE Transactions on Pattern Analysis and Machine Intelligence',
                doi='10.1109/TPAMI.2021.1234567',
                volume='43',
                issue='7',
                pages='2456-2471',
            ),
        ]
        return test_citations

    async def test_semantic_scholar_optimizations(self) -> dict[str, Any]:
        """Test Semantic Scholar API batch processing optimizations."""
        logger.info('🧪 Testing Semantic Scholar API optimizations...')

        results = {
            'test_name': 'Semantic Scholar Optimizations',
            'batch_processing': {},
            'individual_processing': {},
            'caching_test': {},
            'performance_comparison': {},
        }

        # Create test citations
        test_citations = self.create_test_citations()

        # Initialize Semantic Scholar API with optimizations
        api_optimized = SemanticScholarAPI(
            batch_size=500,
            enable_caching=True,
            delay_seconds=0.1,  # Faster for testing
        )

        # Test batch processing
        logger.info('Testing batch lookup functionality...')
        start_time = time.time()

        try:
            enhanced_citations_batch = api_optimized.semantic_scholar_lookup(
                test_citations.copy()
            )
            batch_time = time.time() - start_time

            results['batch_processing'] = {
                'success': True,
                'processing_time': batch_time,
                'citations_processed': len(enhanced_citations_batch),
                'citations_enhanced': sum(
                    1 for c in enhanced_citations_batch if c.doi or c.abstract
                ),
                'performance_metrics': {
                    'citations_per_second': len(enhanced_citations_batch) / batch_time
                    if batch_time > 0
                    else 0,
                    'average_time_per_citation': batch_time
                    / len(enhanced_citations_batch)
                    if enhanced_citations_batch
                    else 0,
                },
            }

            logger.info(f'✅ Batch processing completed in {batch_time:.2f}s')
            logger.info(
                f'Enhanced {results["batch_processing"]["citations_enhanced"]}/{len(enhanced_citations_batch)} citations'
            )

        except Exception as e:
            logger.error(f'❌ Batch processing failed: {e}')
            results['batch_processing'] = {'success': False, 'error': str(e)}

        # Test individual processing (for comparison)
        logger.info('Testing individual lookup for comparison...')
        api_individual = SemanticScholarAPI(
            batch_size=1, enable_caching=False, delay_seconds=0.1
        )

        start_time = time.time()
        try:
            enhanced_citations_individual = api_individual.semantic_scholar_lookup(
                test_citations.copy()
            )
            individual_time = time.time() - start_time

            results['individual_processing'] = {
                'success': True,
                'processing_time': individual_time,
                'citations_processed': len(enhanced_citations_individual),
                'citations_enhanced': sum(
                    1 for c in enhanced_citations_individual if c.doi or c.abstract
                ),
                'performance_metrics': {
                    'citations_per_second': len(enhanced_citations_individual)
                    / individual_time
                    if individual_time > 0
                    else 0,
                    'average_time_per_citation': individual_time
                    / len(enhanced_citations_individual)
                    if enhanced_citations_individual
                    else 0,
                },
            }

            logger.info(f'✅ Individual processing completed in {individual_time:.2f}s')

        except Exception as e:
            logger.error(f'❌ Individual processing failed: {e}')
            results['individual_processing'] = {'success': False, 'error': str(e)}

        # Performance comparison
        if results['batch_processing'].get('success') and results[
            'individual_processing'
        ].get('success'):
            batch_time = results['batch_processing']['processing_time']
            individual_time = results['individual_processing']['processing_time']
            speedup = individual_time / batch_time if batch_time > 0 else 0

            results['performance_comparison'] = {
                'speedup_factor': speedup,
                'time_saved_seconds': individual_time - batch_time,
                'efficiency_improvement_percent': (
                    (individual_time - batch_time) / individual_time * 100
                )
                if individual_time > 0
                else 0,
            }

            logger.info(
                f'🚀 Performance improvement: {speedup:.1f}x faster with batch processing'
            )
            logger.info(f'⏱️  Time saved: {individual_time - batch_time:.2f} seconds')

        # Test caching
        logger.info('Testing caching functionality...')
        start_time = time.time()
        try:
            # Second lookup should be faster due to caching
            api_optimized.semantic_scholar_lookup(test_citations.copy())
            cached_time = time.time() - start_time

            results['caching_test'] = {
                'success': True,
                'cached_processing_time': cached_time,
                'cache_speedup': batch_time / cached_time if cached_time > 0 else 0,
            }

            logger.info(f'✅ Cached lookup completed in {cached_time:.2f}s')
            logger.info(
                f'🎯 Cache speedup: {results["caching_test"]["cache_speedup"]:.1f}x'
            )

        except Exception as e:
            logger.error(f'❌ Caching test failed: {e}')
            results['caching_test'] = {'success': False, 'error': str(e)}

        api_optimized.close()
        api_individual.close()

        return results

    async def test_llm_batch_processing(self) -> dict[str, Any]:
        """Test LLM batch processing improvements."""
        logger.info('🧪 Testing LLM batch processing optimizations...')

        results = {
            'test_name': 'LLM Batch Processing',
            'batch_size_tests': {},
            'prompt_improvements': {},
            'fallback_mechanisms': {},
        }

        # Test different batch sizes
        for batch_size in self.batch_sizes_to_test:
            logger.info(f'Testing batch size: {batch_size}')

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

                results['batch_size_tests'][batch_size] = {
                    'success': True,
                    'processing_time': processing_time,
                    'citations_extracted': len(citations),
                    'document_citation': sum(
                        1 for c in citations if c.is_document_citation
                    ),
                    'reference_citations': sum(
                        1 for c in citations if not c.is_document_citation
                    ),
                    'performance_metrics': {
                        'citations_per_second': len(citations) / processing_time
                        if processing_time > 0
                        else 0,
                        'average_time_per_citation': processing_time / len(citations)
                        if citations
                        else 0,
                    },
                }

                logger.info(
                    f'✅ Batch size {batch_size}: {len(citations)} citations in {processing_time:.2f}s'
                )

            except Exception as e:
                logger.error(f'❌ Batch size {batch_size} failed: {e}')
                results['batch_size_tests'][batch_size] = {
                    'success': False,
                    'error': str(e),
                }

        # Analyze optimal batch size
        successful_tests = {
            k: v for k, v in results['batch_size_tests'].items() if v.get('success')
        }
        if successful_tests:
            optimal_batch_size = min(
                successful_tests.keys(),
                key=lambda x: successful_tests[x]['processing_time'],
            )

            results['optimal_batch_size'] = {
                'size': optimal_batch_size,
                'processing_time': successful_tests[optimal_batch_size][
                    'processing_time'
                ],
                'citations_extracted': successful_tests[optimal_batch_size][
                    'citations_extracted'
                ],
            }

            logger.info(f'🎯 Optimal batch size: {optimal_batch_size}')

        return results

    async def run_comprehensive_test(self) -> dict[str, Any]:
        """Run all tests and generate comprehensive results."""
        logger.info(
            '🚀 Starting comprehensive citation processing optimization tests...'
        )

        all_results = {
            'test_session': {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'configuration': {
                    'test_semantic_scholar': self.test_semantic_scholar,
                    'test_batch_processing': self.test_batch_processing,
                    'batch_sizes_tested': self.batch_sizes_to_test,
                },
            },
            'test_results': {},
        }

        # Test Semantic Scholar optimizations
        if self.test_semantic_scholar:
            try:
                semantic_results = await self.test_semantic_scholar_optimizations()
                all_results['test_results']['semantic_scholar'] = semantic_results
            except Exception as e:
                logger.error(f'Semantic Scholar tests failed: {e}')
                all_results['test_results']['semantic_scholar'] = {'error': str(e)}

        # Test LLM batch processing
        if self.test_batch_processing:
            try:
                batch_results = await self.test_llm_batch_processing()
                all_results['test_results']['llm_batch_processing'] = batch_results
            except Exception as e:
                logger.error(f'LLM batch processing tests failed: {e}')
                all_results['test_results']['llm_batch_processing'] = {'error': str(e)}

        # Generate summary
        all_results['summary'] = self._generate_test_summary(
            all_results['test_results']
        )

        logger.info('✅ All tests completed!')
        return all_results

    def _generate_test_summary(self, test_results: dict[str, Any]) -> dict[str, Any]:
        """Generate a summary of all test results."""
        summary = {
            'overall_success': True,
            'performance_improvements': {},
            'recommendations': [],
        }

        # Analyze Semantic Scholar results
        if 'semantic_scholar' in test_results:
            ss_results = test_results['semantic_scholar']
            if ss_results.get('performance_comparison', {}).get('speedup_factor'):
                speedup = ss_results['performance_comparison']['speedup_factor']
                summary['performance_improvements']['semantic_scholar_speedup'] = (
                    f'{speedup:.1f}x'
                )

                if speedup > 5:
                    summary['recommendations'].append(
                        'Semantic Scholar batch processing is highly effective'
                    )
                elif speedup > 2:
                    summary['recommendations'].append(
                        'Semantic Scholar batch processing shows good improvements'
                    )
                else:
                    summary['recommendations'].append(
                        'Consider API key for better Semantic Scholar performance'
                    )

        # Analyze LLM batch processing results
        if 'llm_batch_processing' in test_results:
            llm_results = test_results['llm_batch_processing']
            if 'optimal_batch_size' in llm_results:
                optimal_size = llm_results['optimal_batch_size']['size']
                summary['performance_improvements']['optimal_batch_size'] = optimal_size

                if optimal_size > 1:
                    summary['recommendations'].append(
                        f'Use batch size {optimal_size} for optimal performance'
                    )
                else:
                    summary['recommendations'].append(
                        'Single citation processing may be more reliable for your setup'
                    )

        return summary

    def save_results(
        self, results: dict[str, Any], filename: str = 'citation_test_results.json'
    ):
        """Save test results to a JSON file."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f'📄 Results saved to {filename}')

    def print_results_summary(self, results: dict[str, Any]):
        """Print a formatted summary of test results."""
        print('\n' + '=' * 80)
        print('🎯 CITATION PROCESSING OPTIMIZATION TEST RESULTS')
        print('=' * 80)

        # Test configuration
        config = results.get('test_session', {}).get('configuration', {})
        print('\n📋 Test Configuration:')
        print(
            f'   • Semantic Scholar Tests: {config.get("test_semantic_scholar", "N/A")}'
        )
        print(
            f'   • Batch Processing Tests: {config.get("test_batch_processing", "N/A")}'
        )
        print(f'   • Batch Sizes Tested: {config.get("batch_sizes_tested", "N/A")}')

        # Performance improvements
        summary = results.get('summary', {})
        improvements = summary.get('performance_improvements', {})

        if improvements:
            print('\n🚀 Performance Improvements:')
            for key, value in improvements.items():
                print(f'   • {key.replace("_", " ").title()}: {value}')

        # Recommendations
        recommendations = summary.get('recommendations', [])
        if recommendations:
            print('\n💡 Recommendations:')
            for i, rec in enumerate(recommendations, 1):
                print(f'   {i}. {rec}')

        # Detailed results
        test_results = results.get('test_results', {})

        if 'semantic_scholar' in test_results:
            ss_results = test_results['semantic_scholar']
            print('\n📊 Semantic Scholar Results:')

            if ss_results.get('batch_processing', {}).get('success'):
                bp = ss_results['batch_processing']
                print(
                    f'   • Batch Processing: ✅ {bp["citations_enhanced"]}/{bp["citations_processed"]} citations enhanced'
                )
                print(f'   • Processing Time: {bp["processing_time"]:.2f}s')
                print(
                    f'   • Rate: {bp["performance_metrics"]["citations_per_second"]:.1f} citations/sec'
                )

            if 'performance_comparison' in ss_results:
                pc = ss_results['performance_comparison']
                print(
                    f'   • Speedup: {pc["speedup_factor"]:.1f}x faster than individual processing'
                )
                print(
                    f'   • Efficiency Gain: {pc["efficiency_improvement_percent"]:.1f}%'
                )

        if 'llm_batch_processing' in test_results:
            llm_results = test_results['llm_batch_processing']
            print('\n🤖 LLM Batch Processing Results:')

            if 'optimal_batch_size' in llm_results:
                obs = llm_results['optimal_batch_size']
                print(f'   • Optimal Batch Size: {obs["size"]}')
                print(f'   • Processing Time: {obs["processing_time"]:.2f}s')
                print(f'   • Citations Extracted: {obs["citations_extracted"]}')

            # Show batch size comparison
            batch_tests = llm_results.get('batch_size_tests', {})
            successful_tests = {
                k: v for k, v in batch_tests.items() if v.get('success')
            }

            if len(successful_tests) > 1:
                print('\n   📈 Batch Size Performance:')
                for size, data in sorted(successful_tests.items()):
                    print(
                        f'      Size {size}: {data["processing_time"]:.2f}s, {data["citations_extracted"]} citations'
                    )

        print('\n' + '=' * 80)


async def main():
    """Main test execution function."""
    logger.info('Starting citation processing optimization tests...')

    # Configure test parameters
    tester = CitationProcessingTester(
        test_semantic_scholar=True,
        test_batch_processing=True,
        batch_sizes_to_test=[1, 5, 10, 15],  # Reduced for faster testing
    )

    try:
        # Run all tests
        results = await tester.run_comprehensive_test()

        # Print summary
        tester.print_results_summary(results)

        # Save detailed results
        tester.save_results(results)

        logger.info('🎉 Testing completed successfully!')

    except Exception as e:
        logger.error(f'❌ Testing failed: {e}')
        raise


if __name__ == '__main__':
    asyncio.run(main())
