"""
Analysis Pipeline Evaluation Framework.

This module provides comprehensive evaluation metrics for the LLM-based analysis
pipeline, including extraction accuracy, content quality, and strategy efficiency.

Evaluation Strategy:
1. **Extraction Accuracy**: Measure completeness and correctness of structured extraction
   - Field completeness: Percentage of fields populated
   - Field accuracy: Correctness of extracted values vs. ground truth
   - Schema adherence: Does output conform to AnalysisResponse?

2. **Content Quality**: Measure quality of generated summaries and analysis
   - Summary coherence: Logical flow and readability
   - Key points relevance: Do key points capture main ideas?
   - Methodology extraction: Completeness of methods description
   - Tag appropriateness: Are tags relevant and consistent?

3. **Strategy Efficiency**: Evaluate adaptive processing strategy selection
   - Strategy selection accuracy: Was optimal strategy chosen?
   - Processing time by strategy: Direct vs Map-Reduce vs Refine
   - Quality-speed tradeoff: Does faster processing sacrifice quality?

Ground Truth Generation:
- Use papers with known metadata (DOI, title, authors from database)
- Manual annotation of gold-standard paper analyses
- Cross-validation: Multiple annotators for quality assessment
- Synthetic papers: Control content complexity and length
"""  # noqa: W505

from thoth.analyze.evaluation.ground_truth import (
    AnalysisGroundTruthGenerator,
    AnalysisGroundTruthPair,
)  # noqa: I001
from thoth.analyze.evaluation.metrics import (
    AnalysisMetrics,
    ExtractionMetrics,
    ContentQualityMetrics,
    calculate_analysis_metrics,
)
from thoth.analyze.evaluation.runner import run_analysis_evaluation

__all__ = [  # noqa: RUF022
    'AnalysisGroundTruthGenerator',
    'AnalysisGroundTruthPair',
    'AnalysisMetrics',
    'ExtractionMetrics',
    'ContentQualityMetrics',
    'calculate_analysis_metrics',
    'run_analysis_evaluation',
]
