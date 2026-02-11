"""
Evaluation runner for RAG pipeline.

This module orchestrates RAG evaluation including:
- Ground truth generation
- Retrieval testing
- Answer quality evaluation
- Performance measurement
- Report generation
"""

import asyncio  # noqa: I001
from pathlib import Path
from typing import Optional, Dict, Any  # noqa: F401, UP035
import time

from loguru import logger

from thoth.config import Config
from thoth.services.postgres_service import PostgresService
from thoth.rag.rag_manager import RAGManager
from thoth.rag.evaluation.ground_truth import GroundTruthGenerator, RAGGroundTruthPair  # noqa: F401
from thoth.rag.evaluation.metrics import calculate_rag_metrics, RAGMetrics


async def run_rag_evaluation(
    num_samples: int = 100,
    output_dir: Path = Path('./rag_evaluation_results'),
    use_existing_ground_truth: Path | None = None,
    k_values: list = [1, 3, 5, 10],  # noqa: B006
) -> RAGMetrics:
    """
    Run comprehensive RAG pipeline evaluation.

    Steps:
    1. Generate or load ground truth question-answer pairs
    2. Run retrieval on test questions
    3. Generate answers using RAG system
    4. Calculate retrieval metrics (Precision@K, Recall@K, NDCG, MRR, MAP)
    5. Calculate answer quality metrics (exact match, F1, relevance)
    6. Measure performance (latency, token usage)
    7. Generate evaluation report

    Args:
        num_samples: Number of test questions to evaluate
        output_dir: Directory for evaluation results
        use_existing_ground_truth: Path to existing ground truth file
        k_values: Values of K for Precision@K, Recall@K, NDCG@K metrics

    Returns:
        RAGMetrics object with comprehensive evaluation results
    """
    logger.info(f'Starting RAG evaluation with {num_samples} samples...')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize services
    config = Config()
    postgres = PostgresService(config)
    await postgres.initialize()

    rag_manager = RAGManager(
        embedding_model=config.rag_config.embedding_model,
        llm_model=config.rag_config.qa.model,
        collection_name=config.rag_config.collection_name,
        vector_db_path=config.rag_config.vector_db_path,
    )

    try:
        # Step 1: Generate or load ground truth
        gt_generator = GroundTruthGenerator(postgres)

        if use_existing_ground_truth:
            logger.info(f'Loading ground truth from {use_existing_ground_truth}')
            ground_truth = await gt_generator.load_ground_truth(
                use_existing_ground_truth
            )
        else:
            logger.info('Generating ground truth from documents...')
            ground_truth = await gt_generator.generate_from_documents(
                num_samples=num_samples, include_synthetic=True
            )
            # Save generated ground truth
            gt_path = output_dir / 'ground_truth.json'
            await gt_generator.save_ground_truth(ground_truth, gt_path)

        logger.info(f'Evaluating {len(ground_truth)} question-answer pairs...')

        # Step 2 & 3: Run retrieval and answer generation
        retrieval_results = []
        answer_results = []
        latency_data = []

        for i, gt_pair in enumerate(ground_truth):
            if (i + 1) % 10 == 0:
                logger.info(f'Processing query {i + 1}/{len(ground_truth)}...')

            # Measure retrieval latency
            start_time = time.time()

            # Retrieve documents
            retrieved_docs = rag_manager.search(
                query=gt_pair.question, k=max(k_values), return_scores=True
            )

            retrieval_time = (time.time() - start_time) * 1000  # ms

            # Extract document IDs
            doc_ids = [doc.metadata.get('source', '') for doc, _ in retrieved_docs]

            retrieval_results.append(
                {'doc_ids': doc_ids, 'scores': [score for _, score in retrieved_docs]}
            )

            # Measure answer generation latency
            start_time = time.time()

            # Generate answer
            answer_result = rag_manager.answer_question(
                question=gt_pair.question,
                k=4,  # Use top 4 docs for answer generation
                return_sources=True,
            )

            generation_time = (time.time() - start_time) * 1000  # ms

            answer_results.append(answer_result)

            latency_data.append(
                {
                    'retrieval_ms': retrieval_time,
                    'generation_ms': generation_time,
                    'total_ms': retrieval_time + generation_time,
                }
            )

        # Step 4-6: Calculate metrics
        logger.info('Calculating metrics...')
        metrics = calculate_rag_metrics(
            ground_truth_list=ground_truth,
            retrieval_results_list=retrieval_results,
            answer_results_list=answer_results,
            latency_data=latency_data,
        )

        # Step 7: Generate report
        logger.info('Generating evaluation report...')
        await _save_rag_report(metrics, output_dir)

        logger.info(f'RAG evaluation complete! Results saved to {output_dir}')
        return metrics

    finally:
        await postgres.close()


async def _save_rag_report(metrics: RAGMetrics, output_dir: Path) -> None:
    """Save evaluation report to file."""
    report_path = output_dir / 'evaluation_report.txt'

    with open(report_path, 'w') as f:
        f.write('=' * 80 + '\n')
        f.write('RAG PIPELINE EVALUATION REPORT\n')
        f.write('=' * 80 + '\n\n')

        # Retrieval Metrics
        f.write('RETRIEVAL METRICS\n')
        f.write('-' * 80 + '\n')
        f.write(f'Total Queries: {metrics.retrieval.total_queries}\n')
        f.write(
            f'Avg Relevant Docs per Query: {metrics.retrieval.avg_relevant_docs_per_query:.2f}\n\n'
        )

        f.write('Precision@K:\n')
        for k, score in sorted(metrics.retrieval.precision_at_k.items()):
            f.write(f'  P@{k}: {score:.4f}\n')

        f.write('\nRecall@K:\n')
        for k, score in sorted(metrics.retrieval.recall_at_k.items()):
            f.write(f'  R@{k}: {score:.4f}\n')

        f.write('\nNDCG@K:\n')
        for k, score in sorted(metrics.retrieval.ndcg_at_k.items()):
            f.write(f'  NDCG@{k}: {score:.4f}\n')

        f.write(
            f'\nMean Reciprocal Rank (MRR): {metrics.retrieval.mean_reciprocal_rank:.4f}\n'
        )
        f.write(
            f'Mean Average Precision (MAP): {metrics.retrieval.mean_average_precision:.4f}\n\n'
        )

        # Answer Quality Metrics
        f.write('ANSWER QUALITY METRICS\n')
        f.write('-' * 80 + '\n')
        f.write(f'Total Queries: {metrics.answer_quality.total_queries}\n')
        f.write(f'Exact Match Score: {metrics.answer_quality.exact_match_score:.4f}\n')
        f.write(f'Token Overlap F1: {metrics.answer_quality.token_overlap_score:.4f}\n')
        f.write(
            f'Semantic Similarity: {metrics.answer_quality.semantic_similarity_score:.4f}\n'
        )
        f.write(
            f'Answer Relevance: {metrics.answer_quality.answer_relevance_score:.4f}\n'
        )
        f.write(
            f'Context Utilization: {metrics.answer_quality.context_utilization_score:.4f}\n'
        )
        f.write(
            f'Hallucination Rate: {metrics.answer_quality.hallucination_rate:.4f}\n'
        )
        f.write(
            f'Avg Answer Length (tokens): {metrics.answer_quality.avg_answer_length:.1f}\n\n'
        )

        # Performance Metrics
        f.write('PERFORMANCE METRICS\n')
        f.write('-' * 80 + '\n')
        f.write(
            f'Avg Retrieval Latency: {metrics.performance.avg_retrieval_latency_ms:.1f} ms\n'
        )
        f.write(
            f'Avg Generation Latency: {metrics.performance.avg_generation_latency_ms:.1f} ms\n'
        )
        f.write(
            f'Avg Total Latency: {metrics.performance.avg_total_latency_ms:.1f} ms\n'
        )
        f.write(
            f'Avg Tokens per Query: {metrics.performance.avg_tokens_per_query:.1f}\n'
        )
        f.write(
            f'Estimated Avg Cost per Query: ${metrics.performance.avg_cost_per_query:.4f}\n\n'
        )

        f.write('=' * 80 + '\n')

    logger.info(f'Report saved to {report_path}')


def main():
    """CLI entry point for RAG evaluation."""
    import argparse

    parser = argparse.ArgumentParser(description='Run RAG pipeline evaluation')
    parser.add_argument(
        '--samples', type=int, default=100, help='Number of test samples to evaluate'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('./rag_evaluation_results'),
        help='Output directory for results',
    )
    parser.add_argument(
        '--ground-truth',
        type=Path,
        default=None,
        help='Path to existing ground truth file',
    )

    args = parser.parse_args()

    asyncio.run(
        run_rag_evaluation(
            num_samples=args.samples,
            output_dir=args.output,
            use_existing_ground_truth=args.ground_truth,
        )
    )


if __name__ == '__main__':
    main()
