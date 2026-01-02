"""Metrics calculation for RAG pipeline evaluation."""

from dataclasses import dataclass  # noqa: I001
from typing import List, Dict, Optional, Tuple  # noqa: F401, UP035
import numpy as np
from loguru import logger  # noqa: F401


@dataclass
class RetrievalMetrics:
    """
    Retrieval quality metrics for RAG evaluation.

    Measures how well the vector search retrieves relevant documents.
    """

    precision_at_k: Dict[int, float]  # Precision@1, @3, @5, @10  # noqa: UP006
    recall_at_k: Dict[int, float]  # Recall@1, @3, @5, @10  # noqa: UP006
    ndcg_at_k: Dict[int, float]  # NDCG@1, @3, @5, @10  # noqa: UP006
    mean_reciprocal_rank: float  # MRR
    mean_average_precision: float  # MAP
    total_queries: int
    avg_relevant_docs_per_query: float


@dataclass
class AnswerQualityMetrics:
    """
    Answer quality metrics for RAG evaluation.

    Measures accuracy and relevance of generated answers.
    """

    exact_match_score: float  # Percentage of exact matches
    token_overlap_score: float  # F1 score of token overlap
    semantic_similarity_score: float  # Cosine similarity of answer embeddings
    answer_relevance_score: float  # How relevant is answer to question?
    context_utilization_score: float  # Are retrieved docs used effectively?
    hallucination_rate: float  # Percentage of unsupported claims
    avg_answer_length: float  # Average tokens in answer
    total_queries: int


@dataclass
class PerformanceMetrics:
    """
    System performance metrics for RAG evaluation.
    """

    avg_retrieval_latency_ms: float
    avg_generation_latency_ms: float
    avg_total_latency_ms: float
    avg_tokens_per_query: float
    avg_cost_per_query: float  # Estimated cost
    total_queries: int


@dataclass
class RAGMetrics:
    """
    Comprehensive RAG evaluation metrics.
    """

    retrieval: RetrievalMetrics
    answer_quality: AnswerQualityMetrics
    performance: PerformanceMetrics
    by_difficulty: Dict[
        str, 'RAGMetrics'
    ]  # Metrics stratified by difficulty  # noqa: UP006
    by_question_type: Dict[str, 'RAGMetrics']  # Metrics by question type  # noqa: UP006


def calculate_precision_at_k(
    retrieved_doc_ids: List[str],  # noqa: UP006
    relevant_doc_ids: List[str],  # noqa: UP006
    k: int,
) -> float:
    """
    Calculate Precision@K: Fraction of top-K results that are relevant.

    Args:
        retrieved_doc_ids: Ordered list of retrieved document IDs
        relevant_doc_ids: List of ground truth relevant document IDs
        k: Number of top results to consider

    Returns:
        Precision@K score (0.0 to 1.0)
    """
    if not retrieved_doc_ids or not relevant_doc_ids:
        return 0.0

    top_k = retrieved_doc_ids[:k]
    relevant_in_top_k = sum(1 for doc_id in top_k if doc_id in relevant_doc_ids)

    return relevant_in_top_k / min(k, len(top_k))


def calculate_recall_at_k(
    retrieved_doc_ids: List[str],  # noqa: UP006
    relevant_doc_ids: List[str],  # noqa: UP006
    k: int,
) -> float:
    """
    Calculate Recall@K: Fraction of relevant docs found in top-K results.

    Args:
        retrieved_doc_ids: Ordered list of retrieved document IDs
        relevant_doc_ids: List of ground truth relevant document IDs
        k: Number of top results to consider

    Returns:
        Recall@K score (0.0 to 1.0)
    """
    if not relevant_doc_ids:
        return 0.0

    if not retrieved_doc_ids:
        return 0.0

    top_k = retrieved_doc_ids[:k]
    relevant_in_top_k = sum(1 for doc_id in top_k if doc_id in relevant_doc_ids)

    return relevant_in_top_k / len(relevant_doc_ids)


def calculate_ndcg_at_k(
    retrieved_doc_ids: List[str],  # noqa: UP006
    relevant_doc_ids: List[str],  # noqa: UP006
    k: int,
    relevance_scores: Optional[Dict[str, float]] = None,  # noqa: UP006, UP007
) -> float:
    """
    Calculate NDCG@K: Normalized Discounted Cumulative Gain.

    Measures ranking quality, giving more weight to relevant docs at top positions.

    Args:
        retrieved_doc_ids: Ordered list of retrieved document IDs
        relevant_doc_ids: List of ground truth relevant document IDs
        k: Number of top results to consider
        relevance_scores: Optional dict mapping doc_id to relevance score (0-1)
                         If None, treats all relevant docs equally (binary relevance)

    Returns:
        NDCG@K score (0.0 to 1.0)
    """
    if not retrieved_doc_ids or not relevant_doc_ids:
        return 0.0

    def dcg(doc_ids: List[str], k: int) -> float:  # noqa: UP006
        """Calculate Discounted Cumulative Gain."""
        gain = 0.0
        for i, doc_id in enumerate(doc_ids[:k], start=1):
            if relevance_scores:
                rel = relevance_scores.get(doc_id, 0.0)
            else:
                rel = 1.0 if doc_id in relevant_doc_ids else 0.0

            # DCG formula: sum(rel_i / log2(i + 1))
            gain += rel / np.log2(i + 1)

        return gain

    # Calculate DCG for retrieved ranking
    dcg_score = dcg(retrieved_doc_ids, k)

    # Calculate ideal DCG (best possible ranking)
    if relevance_scores:
        # Sort by relevance score descending
        ideal_ranking = sorted(
            relevance_scores.items(), key=lambda x: x[1], reverse=True
        )
        ideal_doc_ids = [doc_id for doc_id, _ in ideal_ranking]
    else:
        # Binary relevance: all relevant docs at top
        ideal_doc_ids = list(relevant_doc_ids)

    idcg_score = dcg(ideal_doc_ids, k)

    if idcg_score == 0:
        return 0.0

    return dcg_score / idcg_score


def calculate_mrr(
    retrieved_doc_ids_list: List[List[str]],  # noqa: UP006
    relevant_doc_ids_list: List[List[str]],  # noqa: UP006
) -> float:
    """
    Calculate Mean Reciprocal Rank across multiple queries.

    MRR measures how quickly the first relevant document appears.

    Args:
        retrieved_doc_ids_list: List of retrieved doc ID lists (one per query)
        relevant_doc_ids_list: List of relevant doc ID lists (one per query)

    Returns:
        MRR score (0.0 to 1.0)
    """
    if not retrieved_doc_ids_list or not relevant_doc_ids_list:
        return 0.0

    reciprocal_ranks = []

    for retrieved, relevant in zip(retrieved_doc_ids_list, relevant_doc_ids_list):  # noqa: B905
        if not relevant:
            continue

        # Find rank of first relevant document
        rank = None
        for i, doc_id in enumerate(retrieved, start=1):
            if doc_id in relevant:
                rank = i
                break

        if rank:
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    if not reciprocal_ranks:
        return 0.0

    return np.mean(reciprocal_ranks)


def calculate_map(
    retrieved_doc_ids_list: List[List[str]],  # noqa: UP006
    relevant_doc_ids_list: List[List[str]],  # noqa: UP006
) -> float:
    """
    Calculate Mean Average Precision across multiple queries.

    MAP considers both precision and ranking position of all relevant docs.

    Args:
        retrieved_doc_ids_list: List of retrieved doc ID lists (one per query)
        relevant_doc_ids_list: List of relevant doc ID lists (one per query)

    Returns:
        MAP score (0.0 to 1.0)
    """
    if not retrieved_doc_ids_list or not relevant_doc_ids_list:
        return 0.0

    average_precisions = []

    for retrieved, relevant in zip(retrieved_doc_ids_list, relevant_doc_ids_list):  # noqa: B905
        if not relevant:
            continue

        # Calculate precision at each relevant document position
        precisions_at_relevant = []
        num_relevant_found = 0

        for i, doc_id in enumerate(retrieved, start=1):
            if doc_id in relevant:
                num_relevant_found += 1
                precision_at_i = num_relevant_found / i
                precisions_at_relevant.append(precision_at_i)

        if precisions_at_relevant:
            avg_precision = np.mean(precisions_at_relevant)
        else:
            avg_precision = 0.0

        average_precisions.append(avg_precision)

    if not average_precisions:
        return 0.0

    return np.mean(average_precisions)


def calculate_token_overlap_f1(prediction: str, reference: str) -> float:
    """
    Calculate F1 score based on token overlap between prediction and reference.

    Args:
        prediction: Generated answer
        reference: Ground truth answer

    Returns:
        F1 score (0.0 to 1.0)
    """
    # Tokenize (simple whitespace split + lowercase)
    pred_tokens = set(prediction.lower().split())
    ref_tokens = set(reference.lower().split())

    if not pred_tokens or not ref_tokens:
        return 0.0

    # Calculate overlap
    overlap = pred_tokens & ref_tokens

    if not overlap:
        return 0.0

    precision = len(overlap) / len(pred_tokens)
    recall = len(overlap) / len(ref_tokens)

    if precision + recall == 0:
        return 0.0

    f1 = 2 * (precision * recall) / (precision + recall)
    return f1


def calculate_exact_match(
    prediction: str, reference: str, normalize: bool = True
) -> bool:
    """
    Check if prediction exactly matches reference.

    Args:
        prediction: Generated answer
        reference: Ground truth answer
        normalize: Whether to normalize (lowercase, strip) before comparing

    Returns:
        True if exact match, False otherwise
    """
    if normalize:
        pred = prediction.lower().strip()
        ref = reference.lower().strip()
    else:
        pred = prediction
        ref = reference

    return pred == ref


def calculate_rag_metrics(
    ground_truth_list,
    retrieval_results_list,  # noqa: ARG001
    answer_results_list,  # noqa: ARG001
    latency_data: Optional[List[Dict[str, float]]] = None,  # noqa: ARG001, UP006, UP007
) -> RAGMetrics:
    """
    Calculate comprehensive RAG metrics from evaluation results.

    Args:
        ground_truth_list: List of RAGGroundTruthPair objects
        retrieval_results_list: List of retrieval results (doc IDs and scores)
        answer_results_list: List of generated answers
        latency_data: Optional latency measurements per query

    Returns:
        RAGMetrics object with all metrics
    """
    # TODO: Implement full metrics calculation
    # This is a placeholder structure

    retrieval_metrics = RetrievalMetrics(
        precision_at_k={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        recall_at_k={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        ndcg_at_k={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        mean_reciprocal_rank=0.0,
        mean_average_precision=0.0,
        total_queries=len(ground_truth_list),
        avg_relevant_docs_per_query=0.0,
    )

    answer_quality_metrics = AnswerQualityMetrics(
        exact_match_score=0.0,
        token_overlap_score=0.0,
        semantic_similarity_score=0.0,
        answer_relevance_score=0.0,
        context_utilization_score=0.0,
        hallucination_rate=0.0,
        avg_answer_length=0.0,
        total_queries=len(ground_truth_list),
    )

    performance_metrics = PerformanceMetrics(
        avg_retrieval_latency_ms=0.0,
        avg_generation_latency_ms=0.0,
        avg_total_latency_ms=0.0,
        avg_tokens_per_query=0.0,
        avg_cost_per_query=0.0,
        total_queries=len(ground_truth_list),
    )

    return RAGMetrics(
        retrieval=retrieval_metrics,
        answer_quality=answer_quality_metrics,
        performance=performance_metrics,
        by_difficulty={},
        by_question_type={},
    )
