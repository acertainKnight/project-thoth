# RAG and Analysis Pipeline Evaluation Frameworks

## Overview

This document describes the comprehensive evaluation frameworks for the **RAG (Retrieval-Augmented Generation)** pipeline and the **Analysis** pipeline in Project Thoth.

## Table of Contents

1. [RAG Pipeline Evaluation](#rag-pipeline-evaluation)
2. [Analysis Pipeline Evaluation](#analysis-pipeline-evaluation)
3. [Usage Examples](#usage-examples)
4. [Interpreting Results](#interpreting-results)
5. [Best Practices](#best-practices)

---

## RAG Pipeline Evaluation

### Purpose

Evaluate the quality and performance of the document retrieval and question-answering system.

### Metrics

#### 1. Retrieval Quality Metrics

**Precision@K**: Fraction of top-K retrieved documents that are relevant
- **P@1**: Precision at rank 1 (most important)
- **P@3, P@5, P@10**: Precision at various cutoffs
- **Interpretation**: Higher is better (0.0 to 1.0)

**Recall@K**: Fraction of all relevant documents found in top-K results
- **R@1, R@3, R@5, R@10**: Recall at various cutoffs
- **Interpretation**: Higher is better (0.0 to 1.0)
- **Note**: Recall requires knowing all relevant documents

**NDCG@K** (Normalized Discounted Cumulative Gain): Ranking quality metric
- Rewards relevant documents at top positions
- **Interpretation**: Higher is better (0.0 to 1.0)
- **Use case**: When document relevance varies (not just binary relevant/irrelevant)

**MRR** (Mean Reciprocal Rank): How quickly the first relevant document appears
- MRR = Average(1/rank_of_first_relevant_doc)
- **Interpretation**: Higher is better (0.0 to 1.0)
- **Use case**: When users only need the first relevant result

**MAP** (Mean Average Precision): Combines precision and ranking
- Considers precision at each relevant document position
- **Interpretation**: Higher is better (0.0 to 1.0)
- **Use case**: Comprehensive retrieval quality assessment

#### 2. Answer Quality Metrics

**Exact Match Score**: Percentage of answers that exactly match ground truth
- Strict metric, useful for factual questions
- **Interpretation**: Higher is better (0.0 to 1.0)

**Token Overlap F1**: F1 score based on word overlap with ground truth
- More lenient than exact match
- **Interpretation**: Higher is better (0.0 to 1.0)

**Semantic Similarity**: Cosine similarity of answer embeddings
- Measures semantic equivalence even with different wording
- **Interpretation**: Higher is better (0.0 to 1.0)

**Answer Relevance**: Does the answer address the question?
- Measures how well the answer responds to the query
- **Interpretation**: Higher is better (0.0 to 1.0)

**Context Utilization**: Are retrieved documents used effectively?
- Measures if answer uses information from retrieved docs
- **Interpretation**: Higher is better (0.0 to 1.0)

**Hallucination Rate**: Percentage of unsupported claims in answers
- Percentage of answer content not grounded in retrieved documents
- **Interpretation**: Lower is better (0.0 to 1.0)

#### 3. Performance Metrics

- **Avg Retrieval Latency**: Time to retrieve documents (milliseconds)
- **Avg Generation Latency**: Time to generate answer (milliseconds)
- **Avg Total Latency**: End-to-end time per query (milliseconds)
- **Avg Tokens per Query**: Average tokens in generated answers
- **Estimated Cost per Query**: Estimated API cost per question

### Ground Truth Generation Strategy

#### Approach 1: Database Round-Trip Testing
1. Query papers from database with known metadata
2. Generate questions about paper attributes (title, authors, year)
3. Test if RAG system can retrieve and answer correctly
4. **Advantage**: Automated, scalable

#### Approach 2: Topic-Based Questions
1. Group papers by topic keywords
2. Generate analytical questions requiring multiple documents
3. Test cross-document retrieval and synthesis
4. **Advantage**: Tests complex retrieval scenarios

#### Approach 3: Temporal Analysis
1. Group papers by publication year ranges
2. Generate questions about research evolution
3. Test temporal understanding and synthesis
4. **Advantage**: Tests high-level reasoning

### Difficulty Levels

- **Easy (30%)**: Single-document factual questions
  - Example: "Who are the authors of paper X?"
  - Expected: High precision, exact answers

- **Medium (50%)**: Multi-document analytical questions
  - Example: "What are the main approaches to X?"
  - Expected: Good retrieval, synthesized answers

- **Hard (20%)**: Cross-document synthesis questions
  - Example: "How has research focus evolved from 2015-2020?"
  - Expected: Complex retrieval, high-level synthesis

### Usage

```python
from thoth.rag.evaluation.runner import run_rag_evaluation

# Run evaluation
metrics = await run_rag_evaluation(
    num_samples=100,  # Number of test questions
    output_dir=Path("./rag_evaluation_results")
)

# Or use CLI
# python -m thoth.rag.evaluation.runner --samples 100 --output ./results
```

### Output Files

- `ground_truth.json`: Generated test questions with answers
- `evaluation_report.txt`: Human-readable metrics report
- `summary.json`: Machine-readable metrics
- `precision_recall_curve.png`: Visualization
- `latency_distribution.png`: Performance visualization

---

## Analysis Pipeline Evaluation

### Purpose

Evaluate the quality and efficiency of the LLM-based paper analysis and metadata extraction system.

### Metrics

#### 1. Extraction Accuracy Metrics

**Field Completeness**: Percentage of fields successfully populated
- **Interpretation**: Higher is better (0.0 to 1.0)
- **Use case**: Measures how thorough the extraction is

**Required Fields Completeness**: Percentage of required fields populated
- Fields: title, authors, abstract
- **Interpretation**: Should be close to 1.0 for valid papers

**Optional Fields Completeness**: Percentage of optional fields populated
- Fields: methodology, results, discussion, etc.
- **Interpretation**: Indicates extraction depth

**Field-wise Accuracy**: Correctness per field
- Compares extracted values to ground truth
- **Methods**:
  - String fields: Token overlap F1
  - Integer fields: Exact match
  - List fields: Overlap coefficient

#### 2. Content Quality Metrics

**Summary Coherence**: Logical flow and readability
- Measures sentence structure, length appropriateness, transitions
- **Interpretation**: Higher is better (0.0 to 1.0)

**Summary Completeness**: Coverage of main points
- Does summary capture key aspects of the paper?
- **Interpretation**: Higher is better (0.0 to 1.0)

**Key Points Relevance**: Relevance of extracted key points
- Token overlap between key points and paper content
- **Interpretation**: Higher is better (0.0 to 1.0)

**Key Points Coverage**: Do key points cover the paper?
- Measures breadth of key points across paper sections
- **Interpretation**: Higher is better (0.0 to 1.0)

**Methodology Extraction Quality**: Quality of methods description
- Completeness and accuracy of methodology extraction
- **Interpretation**: Higher is better (0.0 to 1.0)

**Tag Appropriateness**: Relevance and consistency of assigned tags
- Are tags relevant and would others assign the same tags?
- **Interpretation**: Higher is better (0.0 to 1.0)

#### 3. Strategy Efficiency Metrics

**Strategy Selection Accuracy**: Was the optimal strategy chosen?
- Compares actual strategy to expected strategy
- **Interpretation**: Higher is better (0.0 to 1.0)

**Avg Processing Time by Strategy**:
- **Direct**: < 5 seconds for short papers
- **Map-Reduce**: 10-30 seconds for medium papers
- **Refine**: 30-60 seconds for long papers

**Quality by Strategy**: Does strategy affect quality?
- Measures if different strategies produce different quality
- **Expected**: Similar quality across strategies

**Strategy Usage Distribution**:
- Direct: ~30% (short papers)
- Map-Reduce: ~50% (medium papers)
- Refine: ~20% (long papers)

### Ground Truth Generation Strategy

#### Approach: Database Metadata as Ground Truth

1. Query papers with complete metadata from database
2. Use known fields (title, authors, year, DOI, abstract) as ground truth
3. Generate test content of varying lengths:
   - **Low complexity**: Abstract only (~100-500 chars)
   - **Medium complexity**: Abstract + simulated sections (~500-2000 chars)
   - **High complexity**: Full paper structure (~2000+ chars)
4. Test if analysis pipeline correctly extracts known fields
5. **Advantage**: Automated, verifiable ground truth

### Complexity Levels

- **Low (30%)**: Short papers, direct strategy
  - Content: Abstract only
  - Expected strategy: Direct
  - Expected time: < 5 seconds

- **Medium (50%)**: Medium papers, map-reduce strategy
  - Content: Abstract + 2-3 sections
  - Expected strategy: Map-Reduce
  - Expected time: 10-30 seconds

- **High (20%)**: Long papers, refine strategy
  - Content: Full paper structure
  - Expected strategy: Refine
  - Expected time: 30-60 seconds

### Usage

```python
from thoth.analyze.evaluation.runner import run_analysis_evaluation

# Run evaluation
metrics = await run_analysis_evaluation(
    num_samples=50,  # Number of test papers
    output_dir=Path("./analysis_evaluation_results")
)

# Or use CLI
# python -m thoth.analyze.evaluation.runner --samples 50 --output ./results
```

### Output Files

- `ground_truth.json`: Generated test papers with ground truth
- `evaluation_report.txt`: Human-readable metrics report
- `summary.json`: Machine-readable metrics
- `completeness_heatmap.png`: Field completeness visualization
- `strategy_comparison.png`: Strategy performance visualization

---

## Usage Examples

### Example 1: Quick RAG Evaluation (10 samples)

```bash
python -m thoth.rag.evaluation.runner \
    --samples 10 \
    --output ./quick_rag_eval
```

### Example 2: Full RAG Evaluation (100 samples)

```bash
python -m thoth.rag.evaluation.runner \
    --samples 100 \
    --output ./full_rag_eval
```

### Example 3: RAG Evaluation with Existing Ground Truth

```bash
python -m thoth.rag.evaluation.runner \
    --samples 100 \
    --output ./rag_eval_retest \
    --ground-truth ./previous_eval/ground_truth.json
```

### Example 4: Quick Analysis Evaluation (5 samples)

```bash
python -m thoth.analyze.evaluation.runner \
    --samples 5 \
    --output ./quick_analysis_eval
```

### Example 5: Full Analysis Evaluation (50 samples)

```bash
python -m thoth.analyze.evaluation.runner \
    --samples 50 \
    --output ./full_analysis_eval
```

### Example 6: Programmatic Evaluation

```python
import asyncio
from pathlib import Path
from thoth.rag.evaluation.runner import run_rag_evaluation
from thoth.analyze.evaluation.runner import run_analysis_evaluation

async def evaluate_both_pipelines():
    # RAG evaluation
    rag_metrics = await run_rag_evaluation(
        num_samples=100,
        output_dir=Path("./rag_results")
    )

    # Analysis evaluation
    analysis_metrics = await run_analysis_evaluation(
        num_samples=50,
        output_dir=Path("./analysis_results")
    )

    # Compare results
    print(f"RAG Precision@5: {rag_metrics.retrieval.precision_at_k[5]:.3f}")
    print(f"Analysis Field Completeness: {analysis_metrics.extraction.field_completeness:.3f}")

asyncio.run(evaluate_both_pipelines())
```

---

## Interpreting Results

### RAG Pipeline

#### Excellent Performance
- **Precision@5** > 0.8: Most top results are relevant
- **Recall@5** > 0.7: Finding most relevant documents
- **NDCG@5** > 0.8: Good ranking quality
- **MRR** > 0.7: First relevant result appears quickly
- **Token Overlap F1** > 0.6: Answers match ground truth well
- **Hallucination Rate** < 0.1: Few unsupported claims

#### Good Performance
- **Precision@5**: 0.6-0.8
- **Recall@5**: 0.5-0.7
- **NDCG@5**: 0.6-0.8
- **MRR**: 0.5-0.7
- **Token Overlap F1**: 0.4-0.6
- **Hallucination Rate**: 0.1-0.2

#### Needs Improvement
- **Precision@5** < 0.6: Many irrelevant results
- **Recall@5** < 0.5: Missing relevant documents
- **NDCG@5** < 0.6: Poor ranking quality
- **MRR** < 0.5: First relevant result appears late
- **Token Overlap F1** < 0.4: Answers don't match well
- **Hallucination Rate** > 0.2: Many unsupported claims

### Analysis Pipeline

#### Excellent Performance
- **Field Completeness** > 0.9: Almost all fields populated
- **Required Fields Completeness** = 1.0: All required fields present
- **Summary Coherence** > 0.8: High-quality summaries
- **Key Points Relevance** > 0.7: Key points are relevant
- **Strategy Selection Accuracy** > 0.9: Correct strategy chosen

#### Good Performance
- **Field Completeness**: 0.7-0.9
- **Required Fields Completeness**: 0.9-1.0
- **Summary Coherence**: 0.6-0.8
- **Key Points Relevance**: 0.5-0.7
- **Strategy Selection Accuracy**: 0.7-0.9

#### Needs Improvement
- **Field Completeness** < 0.7: Many missing fields
- **Required Fields Completeness** < 0.9: Missing critical fields
- **Summary Coherence** < 0.6: Low-quality summaries
- **Key Points Relevance** < 0.5: Irrelevant key points
- **Strategy Selection Accuracy** < 0.7: Wrong strategy often chosen

---

## Best Practices

### For RAG Evaluation

1. **Start Small**: Test with 10-20 samples first
2. **Verify Ground Truth**: Manually check a sample of generated questions
3. **Balance Difficulty**: Use recommended 30/50/20 distribution
4. **Monitor Latency**: Track if retrieval/generation slows over time
5. **Test Edge Cases**: Include questions with no relevant docs
6. **Iterate**: Re-evaluate after system changes

### For Analysis Evaluation

1. **Start with Known Papers**: Use papers with complete metadata
2. **Vary Content Length**: Test all three complexity levels
3. **Check Strategy Selection**: Verify strategies match content length
4. **Review Failures**: Manually inspect failed extractions
5. **Monitor Quality**: Track if quality degrades with longer papers
6. **Test Model Changes**: Re-evaluate after LLM model updates

### General Best Practices

1. **Version Control**: Save ground truth files for reproducibility
2. **Baseline Metrics**: Establish baseline before improvements
3. **A/B Testing**: Compare metrics before/after changes
4. **Continuous Evaluation**: Run evaluations regularly (weekly/monthly)
5. **Document Findings**: Keep notes on what works and what doesn't
6. **Share Results**: Communicate metrics with team

### Troubleshooting

#### Low RAG Retrieval Metrics
- Check if documents are properly indexed
- Verify embedding model quality
- Adjust chunk size/overlap
- Review vector store configuration

#### Low RAG Answer Quality
- Check if retrieval is finding relevant docs
- Review LLM prompt templates
- Adjust context window size
- Test different LLM models

#### Low Analysis Extraction Accuracy
- Check if ground truth papers have complete metadata
- Review extraction prompt templates
- Adjust LLM temperature and sampling
- Test with higher-quality LLM models

#### Wrong Strategy Selection
- Review token count thresholds
- Check content preprocessing
- Verify strategy selection logic
- Adjust threshold multipliers

---

## Future Enhancements

### RAG Pipeline
- [ ] Add query categorization (factual, analytical, etc.)
- [ ] Implement cross-lingual evaluation
- [ ] Add user satisfaction metrics
- [ ] Implement A/B testing framework

### Analysis Pipeline
- [ ] Add human evaluation interface
- [ ] Implement inter-annotator agreement metrics
- [ ] Add domain-specific quality metrics
- [ ] Create gold-standard test set

### Both Pipelines
- [ ] Automated regression detection
- [ ] Continuous integration of evaluations
- [ ] Real-time monitoring dashboards
- [ ] Cost optimization analysis

---

## References

- **Information Retrieval Metrics**: Manning et al., "Introduction to Information Retrieval" (2008)
- **RAG Evaluation**: Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (2020)
- **LLM Evaluation**: Liang et al., "Holistic Evaluation of Language Models" (2023)
- **NDCG**: Järvelin & Kekäläinen, "Cumulated Gain-Based Evaluation of IR Techniques" (2002)
