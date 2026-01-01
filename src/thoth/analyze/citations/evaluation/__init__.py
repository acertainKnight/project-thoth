"""
Citation Resolution Evaluation Framework.

This module provides comprehensive evaluation metrics for the citation
resolution system, including precision, recall, F1, and confidence calibration.

Ground Truth Strategy:
1. Round-trip testing: Use papers with known metadata, generate citations, test resolution
2. Cross-database validation: Papers that exist in multiple databases (Crossref+OpenAlex+S2)
3. Manual validation: Small gold standard dataset for edge cases
"""
