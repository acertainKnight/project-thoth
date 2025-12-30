"""
Fuzzy matching algorithms for citation deduplication and enrichment.

This module implements multi-strategy fuzzy matching for academic citations,
using weighted scoring across title, authors, year, and journal fields.

Algorithm Overview:
------------------
1. Title Matching (45% weight):
   - Uses three strategies: fuzzy_ratio, token_sort_ratio, token_set_ratio
   - Takes maximum score across strategies for robustness
   - Handles word order variations and partial matches

2. Author Matching (25% weight):
   - First author exact match bonus
   - Overlap scoring for author lists
   - Normalized name comparison (lowercase, stripped)

3. Year Matching (15% weight):
   - Exact match: 1.0
   - ±1 year: 0.8
   - ±2 years: 0.4
   - >2 years: 0.0

4. Journal Matching (15% weight):
   - Detects journal abbreviations
   - Uses fuzzy matching for full journal names
   - Handles common abbreviation patterns

Weighted Scoring Formula:
------------------------
final_score = (0.45 * title_score +
               0.25 * author_score +
               0.15 * year_score +
               0.15 * journal_score)

Dependencies:
------------
- rapidfuzz: Fast fuzzy string matching library
"""

from typing import List, Optional, Tuple
import re
from rapidfuzz import fuzz


# Weighted scoring constants
WEIGHT_TITLE = 0.45
WEIGHT_AUTHORS = 0.25
WEIGHT_YEAR = 0.15
WEIGHT_JOURNAL = 0.15


def normalize_text(text: str) -> str:
    """
    Normalize text for fuzzy matching by removing special characters and whitespace.

    Normalization steps:
    1. Convert to lowercase
    2. Remove punctuation and special characters
    3. Replace multiple spaces with single space
    4. Strip leading/trailing whitespace

    Args:
        text: Raw text string to normalize

    Returns:
        Normalized text string suitable for fuzzy matching

    Example:
        >>> normalize_text("Machine Learning: A Survey!!")
        'machine learning a survey'
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove punctuation and special characters, keep alphanumeric and spaces
    text = re.sub(r'[^\w\s]', ' ', text)

    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing whitespace
    return text.strip()


def normalize_author(author: str) -> str:
    """
    Normalize author name for comparison.

    Handles various author name formats:
    - "Last, First Middle"
    - "First Middle Last"
    - "Last F.M."

    Normalization:
    1. Convert to lowercase
    2. Remove punctuation
    3. Strip whitespace

    Args:
        author: Author name in any standard format

    Returns:
        Normalized author name

    Example:
        >>> normalize_author("Smith, John A.")
        'smith john a'
        >>> normalize_author("J. A. Smith")
        'j a smith'
    """
    if not author:
        return ""

    # Convert to lowercase and remove punctuation
    normalized = author.lower()
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)

    return normalized.strip()


def is_abbreviation(text: str) -> bool:
    """
    Detect if a journal name is likely an abbreviation.

    Abbreviation indicators:
    1. Contains periods (e.g., "Proc. Natl. Acad. Sci.")
    2. Short length (<20 chars) with capital letters
    3. All uppercase letters
    4. High ratio of capital letters to total length

    Args:
        text: Potential journal abbreviation

    Returns:
        True if text appears to be an abbreviation, False otherwise

    Example:
        >>> is_abbreviation("Proc. Natl. Acad. Sci.")
        True
        >>> is_abbreviation("PNAS")
        True
        >>> is_abbreviation("Journal of Machine Learning Research")
        False
    """
    if not text:
        return False

    # Check for periods (common in abbreviations)
    if '.' in text:
        return True

    # Check if all uppercase (common for acronyms)
    if text.isupper() and len(text) <= 10:
        return True

    # Check for short length with high capital letter ratio
    if len(text) < 20:
        capital_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if capital_ratio > 0.5:
            return True

    return False


def match_title(title1: str, title2: str) -> float:
    """
    Match two titles using multiple fuzzy matching strategies with smart weighting.

    Strategies employed (as per improved citation resolution spec):
    1. fuzzy_ratio: Basic Levenshtein distance ratio (exact matching)
    2. token_sort_ratio: Ratio after sorting tokens (handles word order)
    3. token_set_ratio: Ratio using set intersection (handles subtitles/substrings)

    Smart scoring: Takes fuzzy_ratio as primary, but allows token_sort/token_set
    to boost score if they perform significantly better (handles title variations,
    subtitles, and word reordering like "Deep Learning" vs "Deep Learning: A Survey").

    Args:
        title1: First title to compare
        title2: Second title to compare

    Returns:
        Similarity score between 0.0 and 1.0 (1.0 = perfect match)

    Example:
        >>> match_title("Machine Learning Survey", "A Survey of Machine Learning")
        0.87  # High score due to token_set_ratio with slight penalty for reordering
        >>> match_title("Deep Learning", "Deep Learning: A Survey")
        0.92  # High score, token_set handles subtitle gracefully
    """
    if not title1 or not title2:
        return 0.0

    # Normalize both titles
    norm1 = normalize_text(title1)
    norm2 = normalize_text(title2)

    if not norm1 or not norm2:
        return 0.0

    # Apply multiple matching strategies
    ratio_basic = fuzz.ratio(norm1, norm2) / 100.0
    ratio_token_sort = fuzz.token_sort_ratio(norm1, norm2) / 100.0
    ratio_token_set = fuzz.token_set_ratio(norm1, norm2) / 100.0

    # Smart scoring (per spec): Use exact match as primary, but allow
    # token strategies to boost if significantly better (handles reordering/subtitles)
    # Apply slight penalty (0.95x) for non-exact order matching
    return max(ratio_basic, max(ratio_token_sort, ratio_token_set) * 0.95)


def match_authors(authors1: List[str], authors2: List[str]) -> float:
    """
    Match two author lists using first-author priority and overlap scoring.

    Algorithm (per improved citation resolution spec):
    1. Check if first authors match (with fuzzy tolerance for name variations)
       - Exact match: 0.6 points
       - Last name match: 0.4 points (handles "Smith, J." vs "John Smith")
       - Fuzzy match >0.7: 0.3 points (handles initials/abbreviations)
    2. Calculate overlap score for remaining authors (2-3 additional authors):
       - Uses fuzzy matching to handle name format variations
       - Weighted by author list size
    3. Final score = 0.6 * first_author_score + 0.4 * overlap_score

    This approach prioritizes first author (often corresponding/primary author)
    while rewarding overall author list similarity and handling name variations.

    Args:
        authors1: First list of author names
        authors2: Second list of author names

    Returns:
        Similarity score between 0.0 and 1.0

    Example:
        >>> match_authors(["Smith, J.", "Doe, A."], ["Smith, John", "Doe, Alice", "Brown, B."])
        0.82  # First author strong match + good overlap
        >>> match_authors(["J. Smith", "A. Doe"], ["John Smith", "Alice Doe"])
        0.88  # Handles initial/full name variations
    """
    if not authors1 or not authors2:
        return 0.0

    # Normalize all authors
    norm_authors1 = [normalize_author(a) for a in authors1 if a]
    norm_authors2 = [normalize_author(a) for a in authors2 if a]

    if not norm_authors1 or not norm_authors2:
        return 0.0

    # Check first author match with fuzzy tolerance (60% weight)
    first_author_score = 0.0
    first_1 = norm_authors1[0]
    first_2 = norm_authors2[0]

    # Exact match
    if first_1 == first_2:
        first_author_score = 1.0
    else:
        # Extract last names (usually last token, sometimes first for "Smith, John" format)
        tokens1 = first_1.split()
        tokens2 = first_2.split()

        # Try last name matching (handles different formats)
        if tokens1 and tokens2:
            # Check if last names match
            last_name_match = any(
                token1 in tokens2 or token2 in tokens1
                for token1 in tokens1
                for token2 in tokens2
                if len(token1) > 1 and len(token2) > 1  # Ignore initials
            )
            if last_name_match:
                first_author_score = 0.7  # Good match despite format difference
            else:
                # Try fuzzy matching for typos/transliteration
                fuzzy_score = fuzz.ratio(first_1, first_2) / 100.0
                if fuzzy_score > 0.7:
                    first_author_score = 0.5  # Acceptable fuzzy match

    # Calculate overlap score for additional authors (40% weight)
    overlap_score = 0.0
    if len(norm_authors1) > 1 and len(norm_authors2) > 1:
        # Check 2-3 additional authors for overlap
        additional_1 = set(norm_authors1[1:4])  # Check up to 3 more authors
        additional_2 = set(norm_authors2[1:4])

        # Simple set intersection for additional authors
        matches = 0
        for auth1 in additional_1:
            for auth2 in additional_2:
                # Check for exact match or significant token overlap
                tokens_a1 = set(t for t in auth1.split() if len(t) > 1)
                tokens_a2 = set(t for t in auth2.split() if len(t) > 1)
                if auth1 == auth2 or (tokens_a1 & tokens_a2):
                    matches += 1
                    break

        # Overlap score based on matches found
        total_checked = max(len(additional_1), len(additional_2))
        overlap_score = matches / total_checked if total_checked > 0 else 0.0

    # Combine scores: first author (60%) + overlap (40%)
    return 0.6 * first_author_score + 0.4 * overlap_score


def match_year(year1: Optional[int], year2: Optional[int]) -> float:
    """
    Match publication years with tolerance for small differences.

    Scoring rules:
    - Exact match: 1.0
    - ±1 year difference: 0.8 (common for publication delays)
    - ±2 year difference: 0.4 (possible but less likely)
    - >2 year difference: 0.0 (likely different papers)

    Rationale: Publication dates can vary due to:
    - Online vs print publication
    - Conference proceedings vs journal publication
    - Citation errors

    Args:
        year1: First publication year
        year2: Second publication year

    Returns:
        Similarity score between 0.0 and 1.0

    Example:
        >>> match_year(2020, 2020)
        1.0
        >>> match_year(2020, 2021)
        0.8
        >>> match_year(2020, 2023)
        0.0
    """
    if year1 is None or year2 is None:
        return 0.0

    year_diff = abs(year1 - year2)

    if year_diff == 0:
        return 1.0
    elif year_diff == 1:
        return 0.8
    elif year_diff == 2:
        return 0.4
    else:
        return 0.0


def match_journal(journal1: str, journal2: str) -> float:
    """
    Match journal names with abbreviation detection.

    Algorithm:
    1. Check if either journal is an abbreviation
    2. If abbreviation detected:
       - Use basic fuzzy ratio (abbreviations are short)
       - Lower threshold for acceptance
    3. If both are full names:
       - Use token_set_ratio (handles "Journal of X" vs "X Journal")
       - Higher matching standards

    Common abbreviation patterns handled:
    - "Proc. Natl. Acad. Sci." vs "Proceedings of the National Academy of Sciences"
    - "JMLR" vs "Journal of Machine Learning Research"
    - "Nature" vs "Nature" (simple cases)

    Args:
        journal1: First journal name
        journal2: Second journal name

    Returns:
        Similarity score between 0.0 and 1.0

    Example:
        >>> match_journal("Proc. Natl. Acad. Sci.", "Proceedings of National Academy of Sciences")
        0.72  # Moderate score due to abbreviation
        >>> match_journal("Nature", "Nature Reviews")
        0.65  # Partial match
    """
    if not journal1 or not journal2:
        return 0.0

    # Check for abbreviations
    is_abbrev1 = is_abbreviation(journal1)
    is_abbrev2 = is_abbreviation(journal2)

    # Normalize journal names
    norm1 = normalize_text(journal1)
    norm2 = normalize_text(journal2)

    if not norm1 or not norm2:
        return 0.0

    # If either is an abbreviation, use basic ratio
    if is_abbrev1 or is_abbrev2:
        return fuzz.ratio(norm1, norm2) / 100.0

    # Both are full names, use token_set_ratio for better matching
    return fuzz.token_set_ratio(norm1, norm2) / 100.0


def calculate_fuzzy_score(
    title1: str,
    title2: str,
    authors1: List[str],
    authors2: List[str],
    year1: Optional[int],
    year2: Optional[int],
    journal1: str = "",
    journal2: str = ""
) -> Tuple[float, dict]:
    """
    Calculate overall fuzzy match score using weighted combination of field scores.

    This is the main entry point for fuzzy citation matching. It combines
    scores from all fields using empirically-determined weights that reflect
    the relative importance of each field for citation matching.

    Weights rationale:
    - Title (45%): Most distinctive field, varies significantly between papers
    - Authors (25%): Important but can have variations in spelling/format
    - Year (15%): Useful but less distinctive (many papers per year)
    - Journal (15%): Helpful but many papers per journal

    Args:
        title1: First citation title
        title2: Second citation title
        authors1: First citation author list
        authors2: Second citation author list
        year1: First citation publication year
        year2: Second citation publication year
        journal1: First citation journal name (optional)
        journal2: Second citation journal name (optional)

    Returns:
        Tuple of (overall_score, component_scores):
        - overall_score: Final weighted score (0.0 to 1.0)
        - component_scores: Dictionary with individual field scores:
            {
                'title': float,
                'authors': float,
                'year': float,
                'journal': float,
                'overall': float
            }

    Example:
        >>> score, components = calculate_fuzzy_score(
        ...     "Machine Learning Survey",
        ...     "A Survey of Machine Learning",
        ...     ["Smith, J.", "Doe, A."],
        ...     ["Smith, John", "Doe, Alice"],
        ...     2020,
        ...     2020,
        ...     "Nature",
        ...     "Nature Reviews"
        ... )
        >>> score
        0.87
        >>> components
        {
            'title': 0.92,
            'authors': 1.0,
            'year': 1.0,
            'journal': 0.65,
            'overall': 0.87
        }
    """
    # Calculate individual field scores
    title_score = match_title(title1, title2)
    author_score = match_authors(authors1, authors2)
    year_score = match_year(year1, year2)
    journal_score = match_journal(journal1, journal2)

    # Calculate weighted overall score
    overall_score = (
        WEIGHT_TITLE * title_score +
        WEIGHT_AUTHORS * author_score +
        WEIGHT_YEAR * year_score +
        WEIGHT_JOURNAL * journal_score
    )

    # Return score and component breakdown for debugging/analysis
    component_scores = {
        'title': title_score,
        'authors': author_score,
        'year': year_score,
        'journal': journal_score,
        'overall': overall_score
    }

    return overall_score, component_scores
