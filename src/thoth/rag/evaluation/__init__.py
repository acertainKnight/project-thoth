"""
RAG Pipeline Evaluation Framework.

This module provides comprehensive evaluation metrics for the Retrieval-Augmented
Generation (RAG) system, including retrieval quality, answer quality, and system
performance metrics.

Evaluation Strategy:
1. **Retrieval Quality**: Measure how well the vector search retrieves relevant documents
   - Use information retrieval metrics: Precision@K, Recall@K, NDCG, MRR
   - Ground truth: Questions with known relevant document IDs

2. **Answer Quality**: Measure accuracy and relevance of generated answers
   - Factual accuracy: Compare answers to ground truth answers
   - Answer relevance: Does answer address the question?
   - Context utilization: Are retrieved documents used effectively?
   - Hallucination detection: Does LLM generate unsupported claims?

3. **System Performance**: Measure efficiency and resource usage
   - Retrieval latency
   - End-to-end latency
   - Token usage per question
   - Cost per query

Ground Truth Generation:
- Use existing indexed documents to create question-document pairs
- Generate synthetic questions from document content
- Manual curation of complex evaluation cases
- Round-trip testing: Can system retrieve documents it indexed?
"""  # noqa: W505

from thoth.rag.evaluation.ground_truth import GroundTruthGenerator, RAGGroundTruthPair  # noqa: I001
from thoth.rag.evaluation.metrics import (
    RAGMetrics,
    RetrievalMetrics,
    AnswerQualityMetrics,
    calculate_rag_metrics,
)
from thoth.rag.evaluation.runner import run_rag_evaluation

__all__ = [  # noqa: RUF022
    'GroundTruthGenerator',
    'RAGGroundTruthPair',
    'RAGMetrics',
    'RetrievalMetrics',
    'AnswerQualityMetrics',
    'calculate_rag_metrics',
    'run_rag_evaluation',
]
