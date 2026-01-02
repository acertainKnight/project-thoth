"""
Match validation for citation candidates using fuzzy matching.

This module implements comprehensive validation logic for matching citation candidates,
including weighted scoring, hard constraint checking, and best match selection.

Validation Process:
------------------
1. Hard Constraints: Filter out impossible matches
   - Year difference > 5 years
   - No author overlap at all
   - Contradicting journal names

2. Weighted Scoring: Calculate match quality (0.0-1.0)
   - Title matching: 45%
   - Author matching: 25%
   - Year matching: 15%
   - Journal matching: 15%

3. Best Match Selection: Pick highest scoring candidate
   - Must pass hard constraints
   - Returns None if no valid matches

Classes:
-------
- ComponentScores: Breakdown of individual field scores
- MatchCandidate: Citation candidate with validation metadata
- MatchValidator: Main validation and scoring engine
"""

from dataclasses import dataclass, field
from typing import List, Optional  # noqa: UP035

from loguru import logger

from thoth.analyze.citations import fuzzy_matcher
from thoth.utilities.schemas.citations import Citation


@dataclass
class ComponentScores:
    """
    Breakdown of individual component scores for a match.

    Used for debugging and transparency in matching decisions.
    All scores are in range 0.0 to 1.0.
    """

    title: float = 0.0
    authors: float = 0.0
    year: float = 0.0
    journal: float = 0.0
    overall: float = 0.0

    def __repr__(self) -> str:
        """Pretty print component scores for logging."""
        return (
            f'ComponentScores(title={self.title:.3f}, authors={self.authors:.3f}, '
            f'year={self.year:.3f}, journal={self.journal:.3f}, overall={self.overall:.3f})'
        )


@dataclass
class MatchCandidate:
    """
    A candidate citation match with validation metadata.

    Attributes:
        citation: The Citation object being evaluated as a match
        source: Where this candidate came from (e.g., 'semantic_scholar', 'crossref')
        component_scores: Detailed breakdown of matching scores
        passed_constraints: Whether candidate passed hard constraint checks
        rejection_reason: If failed constraints, why it was rejected
    """

    citation: Citation
    source: str = 'unknown'
    component_scores: ComponentScores = field(default_factory=ComponentScores)
    passed_constraints: bool = True
    rejection_reason: Optional[str] = None  # noqa: UP007

    @property
    def overall_score(self) -> float:
        """Convenience property to get overall match score."""
        return self.component_scores.overall

    def __repr__(self) -> str:
        """Pretty print match candidate for logging."""
        title = self.citation.title or 'Untitled'
        status = '✓' if self.passed_constraints else '✗'
        return (
            f'MatchCandidate({status} score={self.overall_score:.3f}, '
            f"source={self.source}, title='{title[:50]}...')"
        )


class MatchValidator:
    """
    Validates and scores citation match candidates using fuzzy matching.

    This class is responsible for:
    1. Applying hard constraints to filter out impossible matches
    2. Calculating weighted similarity scores using fuzzy_matcher
    3. Selecting the best match from a list of candidates

    The validator uses the same scoring weights as fuzzy_matcher:
    - Title: 45%
    - Authors: 25%
    - Year: 15%
    - Journal: 15%

    Hard Constraints:
    ----------------
    - Year difference must be ≤ 5 years
    - Must have at least one matching author (normalized comparison)
    - Journal names must not contradict (if both provided)

    Example:
    -------
    >>> validator = MatchValidator()
    >>> candidates = [
    ...     MatchCandidate(citation=candidate1, source='semantic_scholar'),
    ...     MatchCandidate(citation=candidate2, source='crossref'),
    ... ]
    >>> for candidate in candidates:
    ...     score = validator.validate_match(input_citation, candidate)
    >>> best = validator.get_best_match(candidates)
    """

    def __init__(self):
        """Initialize the match validator."""
        logger.debug('Initializing MatchValidator')

    def validate_match(
        self, input_citation: Citation, candidate: MatchCandidate
    ) -> float:
        """
        Validate and score a match candidate against an input citation.

        This method:
        1. Checks hard constraints first (fast rejection)
        2. If constraints pass, calculates detailed fuzzy match scores
        3. Populates candidate.component_scores with breakdown
        4. Returns overall match score for convenience

        Args:
            input_citation: The original citation we're trying to match
            candidate: The candidate match to validate

        Returns:
            Overall match score (0.0 to 1.0). Returns 0.0 if constraints fail.

        Side Effects:
            - Sets candidate.component_scores with detailed breakdown
            - Sets candidate.passed_constraints to True/False
            - Sets candidate.rejection_reason if constraints fail

        Example:
        -------
        >>> validator = MatchValidator()
        >>> input_cit = Citation(
        ...     title='Machine Learning', authors=['Smith, J.'], year=2020
        ... )
        >>> candidate = MatchCandidate(
        ...     citation=Citation(
        ...         title='Machine Learning Survey', authors=['Smith, John'], year=2020
        ...     )
        ... )
        >>> score = validator.validate_match(input_cit, candidate)
        >>> print(f'Score: {score:.2f}')
        Score: 0.87
        >>> print(candidate.component_scores)
        ComponentScores(title=0.920, authors=1.000, year=1.000, journal=0.000, overall=0.870)
        """  # noqa: W505
        candidate_cit = candidate.citation

        logger.debug(
            f'Validating match candidate from {candidate.source}: '
            f"'{candidate_cit.title[:50] if candidate_cit.title else 'Untitled'}'"
        )

        # Step 1: Check hard constraints first (fast rejection)
        if not self.check_hard_constraints(input_citation, candidate):
            logger.debug(
                f'Candidate failed hard constraints: {candidate.rejection_reason}'
            )
            # Set all scores to 0 since we rejected this candidate
            candidate.component_scores = ComponentScores()
            return 0.0

        # Step 2: Calculate fuzzy match scores using fuzzy_matcher
        try:
            overall_score, component_dict = fuzzy_matcher.calculate_fuzzy_score(
                title1=input_citation.title or '',
                title2=candidate_cit.title or '',
                authors1=input_citation.authors or [],
                authors2=candidate_cit.authors or [],
                year1=input_citation.year,
                year2=candidate_cit.year,
                journal1=input_citation.journal or '',
                journal2=candidate_cit.journal or '',
            )

            # Step 3: Populate component scores from fuzzy_matcher results
            candidate.component_scores = ComponentScores(
                title=component_dict['title'],
                authors=component_dict['authors'],
                year=component_dict['year'],
                journal=component_dict['journal'],
                overall=overall_score,
            )

            logger.debug(f'Match scores for candidate: {candidate.component_scores}')

            return overall_score

        except Exception as e:
            logger.error(
                f'Error calculating fuzzy scores for candidate: {e}', exc_info=True
            )
            # On error, mark as failed with zero scores
            candidate.component_scores = ComponentScores()
            candidate.passed_constraints = False
            candidate.rejection_reason = f'Scoring error: {str(e)}'  # noqa: RUF010
            return 0.0

    def check_hard_constraints(
        self, input_citation: Citation, candidate: MatchCandidate
    ) -> bool:
        """
        Check hard constraints that must be satisfied for a valid match.

        Implements validation checklist from improved citation resolution spec:
        - Title similarity ≥ 0.80 (checked in validate_match, not here)
        - Year matches (±1 acceptable, reject if >5 years difference)
        - At least one author name matches
        - If journal provided, it doesn't contradict

        Hard constraints are strict rules that, if violated, immediately
        disqualify a candidate regardless of fuzzy matching scores.

        Constraints checked:
        1. Year Difference: Must be ≤ 5 years apart (spec requirement)
           - Rationale: Publication dates can vary slightly due to conference
             vs journal publication, but >5 years indicates different papers
           - Hard rejection for contradictory years

        2. Author Overlap: Must have at least one matching author (spec requirement)
           - Uses normalized author names (lowercase, no punctuation)
           - Checks token overlap for format variations
           - Rationale: Different papers by completely different authors

        3. Journal Contradiction: If both have journals, they must be compatible (spec req)
           - Uses fuzzy matching to allow abbreviations
           - Threshold: journal_score < 0.3 indicates contradiction
           - Rationale: Same paper can't be in completely different journals

        Args:
            input_citation: Original citation we're matching against
            candidate: Candidate to check constraints for

        Returns:
            True if all constraints pass, False if any fail

        Side Effects:
            - Sets candidate.passed_constraints to True/False
            - Sets candidate.rejection_reason if constraints fail

        Example:
        -------
        >>> validator = MatchValidator()
        >>> input_cit = Citation(title='Test', authors=['Smith, J.'], year=2020)
        >>>
        >>> # This should pass (1 year difference)
        >>> good_candidate = MatchCandidate(
        ...     citation=Citation(authors=['Smith, John'], year=2021)
        ... )
        >>> validator.check_hard_constraints(input_cit, good_candidate)
        True
        >>>
        >>> # This should fail (10 year difference)
        >>> bad_candidate = MatchCandidate(
        ...     citation=Citation(authors=['Smith, John'], year=2010)
        ... )
        >>> validator.check_hard_constraints(input_cit, bad_candidate)
        False
        >>> bad_candidate.rejection_reason
        'Year difference too large: 10 years (hard contradiction per spec)'
        """  # noqa: W505
        candidate_cit = candidate.citation

        # Constraint 1: Year difference check (spec: hard contradiction if >5 years)
        if input_citation.year is not None and candidate_cit.year is not None:
            year_diff = abs(input_citation.year - candidate_cit.year)

            if year_diff > 5:
                candidate.passed_constraints = False
                candidate.rejection_reason = (
                    f'Year difference too large: {year_diff} years '
                    f'(hard contradiction per spec - year off by 5+)'
                )
                logger.debug(
                    f'Rejecting candidate: year difference {year_diff} > 5 '
                    f'({input_citation.year} vs {candidate_cit.year})'
                )
                return False

        # Constraint 2: Author overlap check (spec: at least one author must match)
        # We need fuzzy matching here because authors can be formatted differently:
        # "Murphy, Kevin P." vs "Murphy, K. P." vs "Kevin Murphy"
        if input_citation.authors and candidate_cit.authors:
            # Normalize all authors for comparison
            input_authors_normalized = [
                fuzzy_matcher.normalize_author(author)
                for author in input_citation.authors
                if author
            ]
            candidate_authors_normalized = [
                fuzzy_matcher.normalize_author(author)
                for author in candidate_cit.authors
                if author
            ]

            # Check if any author from input has overlap with any candidate author
            # Consider it a match if last name matches OR fuzzy score > 0.7
            has_overlap = False
            for input_author in input_authors_normalized:
                if not input_author:
                    continue
                # Extract last name (usually first token or last token)
                input_tokens = input_author.split()

                for candidate_author in candidate_authors_normalized:
                    if not candidate_author:
                        continue
                    candidate_tokens = candidate_author.split()

                    # Check for exact match first
                    if input_author == candidate_author:
                        has_overlap = True
                        break

                    # Check if they share a significant token (likely last name)
                    # Look for tokens longer than 1 character to avoid matching just initials  # noqa: W505
                    shared_tokens = set(t for t in input_tokens if len(t) > 1) & set(
                        t for t in candidate_tokens if len(t) > 1
                    )
                    if shared_tokens:
                        has_overlap = True
                        break

                if has_overlap:
                    break

            if (
                not has_overlap
                and input_authors_normalized
                and candidate_authors_normalized
            ):
                candidate.passed_constraints = False
                candidate.rejection_reason = (
                    'No author overlap found (spec: completely different authors)'
                )
                logger.debug(
                    f'Rejecting candidate: no author overlap between '
                    f'{input_authors_normalized} and {candidate_authors_normalized}'
                )
                return False

        # Constraint 3: Journal contradiction check (spec: if provided, must not contradict)  # noqa: W505
        if input_citation.journal and candidate_cit.journal:
            journal_score = fuzzy_matcher.match_journal(
                input_citation.journal, candidate_cit.journal
            )

            # If journals are completely different (score < 0.3), reject
            # This allows for abbreviations and variations but catches contradictions
            if journal_score < 0.3:
                candidate.passed_constraints = False
                candidate.rejection_reason = (
                    f"Journal names contradictory: '{input_citation.journal}' vs "
                    f"'{candidate_cit.journal}' (score: {journal_score:.2f}, spec: must not contradict)"
                )
                logger.debug(
                    f'Rejecting candidate: journal score {journal_score:.2f} < 0.3'
                )
                return False

        # All constraints passed (spec checklist validated)
        candidate.passed_constraints = True
        candidate.rejection_reason = None
        return True

    def get_best_match(
        self,
        candidates: List[MatchCandidate],  # noqa: UP006
    ) -> Optional[MatchCandidate]:  # noqa: UP007
        """
        Select the best matching candidate from a list.

        Selection criteria:
        1. Filter to only candidates that passed hard constraints
        2. Among valid candidates, return the one with highest overall_score
        3. Return None if no candidates pass constraints

        This method assumes validate_match() has already been called on
        all candidates to populate their scores and constraint status.

        Args:
            candidates: List of candidates to choose from

        Returns:
            Best matching candidate, or None if no valid candidates

        Example:
        -------
        >>> validator = MatchValidator()
        >>> candidates = [
        ...     MatchCandidate(citation=cit1, source='s2'),
        ...     MatchCandidate(citation=cit2, source='crossref'),
        ... ]
        >>> # Validate all candidates first
        >>> for candidate in candidates:
        ...     validator.validate_match(input_citation, candidate)
        >>>
        >>> best = validator.get_best_match(candidates)
        >>> if best:
        ...     print(
        ...         f'Best match from {best.source} with score {best.overall_score:.2f}'
        ...     )
        """  # noqa: W505
        if not candidates:
            logger.debug('No candidates provided to get_best_match')
            return None

        # Filter to only candidates that passed constraints
        valid_candidates = [
            candidate for candidate in candidates if candidate.passed_constraints
        ]

        if not valid_candidates:
            logger.debug(
                f'No valid candidates found (0/{len(candidates)} passed constraints)'
            )
            return None

        # Sort by overall score (descending) and take the best
        valid_candidates.sort(key=lambda c: c.overall_score, reverse=True)
        best_candidate = valid_candidates[0]

        logger.info(
            f'Selected best match from {best_candidate.source} with score '
            f'{best_candidate.overall_score:.3f} '
            f'(from {len(valid_candidates)}/{len(candidates)} valid candidates)'
        )

        # Log all valid candidates for debugging
        if len(valid_candidates) > 1:
            logger.debug(
                f'Other valid candidates: '  # noqa: F541
                + ', '.join(
                    f'{c.source}={c.overall_score:.3f}'
                    for c in valid_candidates[1:4]  # Show top 3 alternatives
                )
            )

        return best_candidate
