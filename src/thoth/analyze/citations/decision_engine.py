"""
Citation Resolution Decision Engine

This module implements the core decision logic for determining citation resolution
outcomes based on match candidates and confidence scores. It applies threshold-based
rules to classify resolutions and provides detailed diagnostic information.

The decision engine uses a multi-tier confidence system:
    - HIGH (≥0.85): Clear, confident matches with strong evidence
    - MEDIUM (≥0.70): Good matches requiring winner validation
    - LOW (≥0.50): Weak matches requiring manual review
    - REJECT (<0.50): Poor matches that should remain unresolved

Decision Logic:
    1. Score ≥ 0.85 → RESOLVED with HIGH confidence (automatic acceptance)
    2. Score ≥ 0.70 with clear winner → RESOLVED with MEDIUM confidence
    3. Score ≥ 0.70 with ambiguity → MANUAL_REVIEW (multiple strong candidates)
    4. Score ≥ 0.50 → MANUAL_REVIEW with LOW confidence (uncertain match)
    5. Score < 0.50 → UNRESOLVED (no acceptable match found)
"""

import logging
from typing import Any, Dict, List, Optional

from .resolution_types import (
    APISource,
    CitationResolutionStatus,
    ConfidenceLevel,
    MatchCandidate,
    ResolutionMetadata,
    ResolutionResult,
)

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Decision engine for citation resolution based on confidence thresholds.

    This class implements the core decision logic that determines how citations
    should be resolved based on match candidate scores and confidence levels.
    It provides transparent, logged decision-making with clear rationale.

    Attributes:
        HIGH_CONFIDENCE (float): Threshold for automatic high-confidence resolution (0.85)
        MEDIUM_CONFIDENCE (float): Threshold for medium-confidence resolution (0.70)
        LOW_CONFIDENCE (float): Threshold for low-confidence manual review (0.50)
        REJECT_THRESHOLD (float): Threshold below which matches are rejected (0.50)
        CLEAR_WINNER_GAP (float): Score gap required to distinguish clear winner (0.15)
    """

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.70
    LOW_CONFIDENCE = 0.50
    REJECT_THRESHOLD = 0.50

    # Decision logic constants
    CLEAR_WINNER_GAP = 0.15  # Gap required between 1st and 2nd place

    def __init__(self):
        """Initialize the decision engine with logging."""
        logger.info(
            "DecisionEngine initialized with thresholds: "
            f"HIGH={self.HIGH_CONFIDENCE}, MEDIUM={self.MEDIUM_CONFIDENCE}, "
            f"LOW={self.LOW_CONFIDENCE}, REJECT={self.REJECT_THRESHOLD}"
        )

    def decide(
        self,
        input_citation: str,
        candidates: List[MatchCandidate],
        metadata: Optional[ResolutionMetadata] = None,
    ) -> ResolutionResult:
        """
        Make a resolution decision based on match candidates and scores.

        This method implements the core decision logic by:
        1. Sorting candidates by score (highest first)
        2. Applying threshold-based decision rules
        3. Checking for clear winners vs. ambiguous results
        4. Creating detailed resolution results with rationale

        Args:
            input_citation: Original citation text being resolved
            candidates: List of match candidates with scores
            metadata: Optional resolution metadata for tracking

        Returns:
            ResolutionResult with status, confidence, and decision rationale

        Decision Rules:
            - Score ≥ 0.85: RESOLVED (HIGH confidence)
            - Score ≥ 0.70 with clear winner: RESOLVED (MEDIUM confidence)
            - Score ≥ 0.70 with ambiguity: MANUAL_REVIEW
            - Score ≥ 0.50: MANUAL_REVIEW (LOW confidence)
            - Score < 0.50: UNRESOLVED
        """
        logger.info(
            f"Making decision for citation: '{input_citation[:100]}...' "
            f"with {len(candidates)} candidates"
        )

        # Initialize metadata if not provided
        if metadata is None:
            metadata = ResolutionMetadata()

        # Handle case with no candidates
        if not candidates:
            logger.warning("No candidates provided for decision-making")
            return self._create_resolution_result(
                citation=input_citation,
                status=CitationResolutionStatus.UNRESOLVED,
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                source=None,
                matched_data=None,
                candidates=[],
                metadata=metadata,
                decision_rationale="No candidates available for matching",
            )

        # Sort candidates by score (descending)
        sorted_candidates = sorted(
            candidates, key=lambda c: c.raw_score, reverse=True
        )

        best_candidate = sorted_candidates[0]
        best_score = best_candidate.raw_score

        logger.info(
            f"Best candidate score: {best_score:.3f} "
            f"(source: {best_candidate.source})"
        )

        # Log component scores for debugging
        if best_candidate.component_scores:
            component_breakdown = ", ".join(
                f"{k}={v:.3f}" for k, v in best_candidate.component_scores.items()
            )
            logger.debug(f"Component scores: {component_breakdown}")

        # Apply decision logic based on score thresholds
        if best_score >= self.HIGH_CONFIDENCE:
            # HIGH CONFIDENCE: Automatic acceptance
            return self._handle_high_confidence_match(
                citation=input_citation,
                candidate=best_candidate,
                candidates=sorted_candidates,
                metadata=metadata,
            )

        elif best_score >= self.MEDIUM_CONFIDENCE:
            # MEDIUM CONFIDENCE: Check for clear winner
            return self._handle_medium_confidence_match(
                citation=input_citation,
                best_candidate=best_candidate,
                candidates=sorted_candidates,
                metadata=metadata,
            )

        elif best_score >= self.LOW_CONFIDENCE:
            # LOW CONFIDENCE: Manual review required
            return self._handle_low_confidence_match(
                citation=input_citation,
                best_candidate=best_candidate,
                candidates=sorted_candidates,
                metadata=metadata,
            )

        else:
            # BELOW THRESHOLD: Reject match
            return self._handle_rejected_match(
                citation=input_citation,
                best_score=best_score,
                candidates=sorted_candidates,
                metadata=metadata,
            )

    def _handle_high_confidence_match(
        self,
        citation: str,
        candidate: MatchCandidate,
        candidates: List[MatchCandidate],
        metadata: ResolutionMetadata,
    ) -> ResolutionResult:
        """
        Handle high-confidence matches (score ≥ 0.85).

        These matches are automatically resolved with HIGH confidence.
        """
        logger.info(
            f"HIGH confidence match: score={candidate.raw_score:.3f}, "
            f"source={candidate.source}"
        )

        rationale = (
            f"High confidence match (score: {candidate.raw_score:.3f} ≥ "
            f"{self.HIGH_CONFIDENCE}). Match meets threshold for automatic resolution."
        )

        return self._create_resolution_result(
            citation=citation,
            status=CitationResolutionStatus.RESOLVED,
            confidence_score=candidate.raw_score,
            confidence_level=ConfidenceLevel.HIGH,
            source=candidate.source,
            matched_data=candidate.candidate_data,
            candidates=candidates,
            metadata=metadata,
            decision_rationale=rationale,
        )

    def _handle_medium_confidence_match(
        self,
        citation: str,
        best_candidate: MatchCandidate,
        candidates: List[MatchCandidate],
        metadata: ResolutionMetadata,
    ) -> ResolutionResult:
        """
        Handle medium-confidence matches (0.70 ≤ score < 0.85).

        Checks if there's a clear winner (gap ≥ 0.15 to second place).
        - Clear winner: RESOLVED with MEDIUM confidence
        - Ambiguous: MANUAL_REVIEW due to multiple strong candidates
        """
        logger.info(
            f"MEDIUM confidence match: score={best_candidate.raw_score:.3f}, "
            f"checking for clear winner..."
        )

        if self._is_clear_winner(candidates):
            # Clear winner exists
            gap = self._get_score_gap(candidates)
            logger.info(
                f"Clear winner detected with gap={gap:.3f} to second place"
            )

            rationale = (
                f"Medium confidence match (score: {best_candidate.raw_score:.3f}) "
                f"with clear winner (gap: {gap:.3f} ≥ {self.CLEAR_WINNER_GAP}). "
                f"No ambiguity detected."
            )

            return self._create_resolution_result(
                citation=citation,
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=best_candidate.raw_score,
                confidence_level=ConfidenceLevel.MEDIUM,
                source=best_candidate.source,
                matched_data=best_candidate.candidate_data,
                candidates=candidates,
                metadata=metadata,
                decision_rationale=rationale,
            )
        else:
            # Ambiguous result - multiple strong candidates
            gap = self._get_score_gap(candidates)
            logger.warning(
                f"Ambiguous result: gap={gap:.3f} < {self.CLEAR_WINNER_GAP}, "
                f"sending to manual review"
            )

            rationale = (
                f"Ambiguous result with medium confidence score "
                f"({best_candidate.raw_score:.3f}). Multiple strong candidates "
                f"detected (gap: {gap:.3f} < {self.CLEAR_WINNER_GAP}). "
                f"Manual review required to resolve ambiguity."
            )

            return self._create_resolution_result(
                citation=citation,
                status=CitationResolutionStatus.MANUAL_REVIEW,
                confidence_score=best_candidate.raw_score,
                confidence_level=ConfidenceLevel.MEDIUM,
                source=best_candidate.source,
                matched_data=best_candidate.candidate_data,
                candidates=candidates,
                metadata=metadata,
                decision_rationale=rationale,
            )

    def _handle_low_confidence_match(
        self,
        citation: str,
        best_candidate: MatchCandidate,
        candidates: List[MatchCandidate],
        metadata: ResolutionMetadata,
    ) -> ResolutionResult:
        """
        Handle low-confidence matches (0.50 ≤ score < 0.70).

        These matches require manual review due to uncertainty.
        """
        logger.warning(
            f"LOW confidence match: score={best_candidate.raw_score:.3f}, "
            f"manual review required"
        )

        rationale = (
            f"Low confidence match (score: {best_candidate.raw_score:.3f}). "
            f"Score is above rejection threshold ({self.REJECT_THRESHOLD}) but "
            f"below medium confidence threshold ({self.MEDIUM_CONFIDENCE}). "
            f"Manual review required to validate match."
        )

        return self._create_resolution_result(
            citation=citation,
            status=CitationResolutionStatus.MANUAL_REVIEW,
            confidence_score=best_candidate.raw_score,
            confidence_level=ConfidenceLevel.LOW,
            source=best_candidate.source,
            matched_data=best_candidate.candidate_data,
            candidates=candidates,
            metadata=metadata,
            decision_rationale=rationale,
        )

    def _handle_rejected_match(
        self,
        citation: str,
        best_score: float,
        candidates: List[MatchCandidate],
        metadata: ResolutionMetadata,
    ) -> ResolutionResult:
        """
        Handle rejected matches (score < 0.50).

        These matches are below the acceptable threshold and should remain unresolved.
        """
        logger.warning(
            f"Match REJECTED: best_score={best_score:.3f} < "
            f"reject_threshold={self.REJECT_THRESHOLD}"
        )

        rationale = (
            f"Match rejected due to low score ({best_score:.3f} < "
            f"{self.REJECT_THRESHOLD}). No candidates meet minimum confidence "
            f"threshold for resolution or manual review."
        )

        return self._create_resolution_result(
            citation=citation,
            status=CitationResolutionStatus.UNRESOLVED,
            confidence_score=best_score,
            confidence_level=ConfidenceLevel.LOW,
            source=None,
            matched_data=None,
            candidates=candidates,
            metadata=metadata,
            decision_rationale=rationale,
        )

    def _is_clear_winner(self, candidates: List[MatchCandidate]) -> bool:
        """
        Check if there's a clear winner among candidates.

        A clear winner exists when the score gap between the best and second-best
        candidates is at least CLEAR_WINNER_GAP (0.15).

        Args:
            candidates: List of candidates sorted by score (descending)

        Returns:
            True if there's a clear winner, False if results are ambiguous
        """
        if len(candidates) < 2:
            # Only one candidate - it's a clear winner by default
            return True

        gap = self._get_score_gap(candidates)
        is_clear = gap >= self.CLEAR_WINNER_GAP

        logger.debug(
            f"Clear winner check: gap={gap:.3f}, "
            f"threshold={self.CLEAR_WINNER_GAP}, result={is_clear}"
        )

        return is_clear

    def _get_score_gap(self, candidates: List[MatchCandidate]) -> float:
        """
        Calculate the score gap between first and second place.

        Args:
            candidates: List of candidates sorted by score (descending)

        Returns:
            Score gap between best and second-best candidates, or 1.0 if only one candidate
        """
        if len(candidates) < 2:
            return 1.0  # Maximum gap if only one candidate

        return candidates[0].raw_score - candidates[1].raw_score

    def _create_resolution_result(
        self,
        citation: str,
        status: CitationResolutionStatus,
        confidence_score: float,
        confidence_level: ConfidenceLevel,
        source: Optional[APISource],
        matched_data: Optional[Dict[str, Any]],
        candidates: List[MatchCandidate],
        metadata: ResolutionMetadata,
        decision_rationale: str,
    ) -> ResolutionResult:
        """
        Create a resolution result with complete metadata and rationale.

        Args:
            citation: Original citation text
            status: Resolution status
            confidence_score: Numerical confidence score
            confidence_level: Categorized confidence level
            source: API source of the match
            matched_data: Matched citation data
            candidates: All candidates considered
            metadata: Resolution metadata
            decision_rationale: Explanation of the decision

        Returns:
            Complete ResolutionResult object
        """
        # Add decision rationale to metadata
        metadata.additional_info = metadata.additional_info or {}
        metadata.additional_info["decision_rationale"] = decision_rationale
        metadata.additional_info["decision_engine_version"] = "1.0.0"
        metadata.additional_info["thresholds"] = {
            "high": self.HIGH_CONFIDENCE,
            "medium": self.MEDIUM_CONFIDENCE,
            "low": self.LOW_CONFIDENCE,
            "reject": self.REJECT_THRESHOLD,
        }

        result = ResolutionResult(
            citation=citation,
            status=status,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            source=source,
            matched_data=matched_data,
            candidates=candidates,
            metadata=metadata,
        )

        logger.info(
            f"Decision result: status={status}, confidence={confidence_level} "
            f"({confidence_score:.3f}), source={source}"
        )
        logger.debug(f"Decision rationale: {decision_rationale}")

        return result


# Convenience function for direct usage
def make_decision(
    citation: str,
    candidates: List[MatchCandidate],
    metadata: Optional[ResolutionMetadata] = None,
) -> ResolutionResult:
    """
    Convenience function to make a citation resolution decision.

    This is a simple wrapper around DecisionEngine.decide() for cases where
    you don't need to maintain engine state.

    Args:
        citation: Original citation text
        candidates: List of match candidates
        metadata: Optional resolution metadata

    Returns:
        ResolutionResult with decision and rationale

    Example:
        >>> candidates = [MatchCandidate(...), MatchCandidate(...)]
        >>> result = make_decision("Smith et al. (2024)", candidates)
        >>> print(result.status, result.confidence_level)
    """
    engine = DecisionEngine()
    return engine.decide(citation, candidates, metadata)
