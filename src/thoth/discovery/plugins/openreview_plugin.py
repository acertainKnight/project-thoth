"""OpenReview discovery plugin for ICLR and other conferences hosted on OpenReview.

This plugin uses the openreview-py package to access papers from conferences
like ICLR, NeurIPS (some years), and other venues using the OpenReview platform.
"""

from __future__ import annotations

from datetime import datetime

from loguru import logger

from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata

from .base import BaseDiscoveryPlugin


class OpenReviewPlugin(BaseDiscoveryPlugin):
    """Discovery plugin for searching OpenReview-hosted conferences.
    
    Requires openreview-py package: pip install openreview-py
    """

    def __init__(self, config: dict | None = None) -> None:
        """Initialize the OpenReview plugin.
        
        Args:
            config: Configuration dictionary with optional keys:
                - venue: Venue ID pattern (e.g., 'ICLR.cc/2024/Conference')
                - year: Year to search
                - decision: Filter by decision ('Accept', 'Reject', None for all)
                - min_rating: Minimum average rating threshold
        """
        super().__init__(config)
        
        try:
            import openreview
            self.openreview = openreview
            # Initialize guest client (no login required for public data)
            self.client = openreview.api.OpenReviewClient(
                baseurl='https://api2.openreview.net'
            )
        except ImportError as e:
            raise ImportError(
                "openreview-py is required for OpenReview plugin. "
                "Install with: pip install openreview-py"
            ) from e

    def discover(
        self, query: ResearchQuery, max_results: int
    ) -> list[ScrapedArticleMetadata]:
        """Discover papers from OpenReview.
        
        Args:
            query: Research query with keywords and topics.
            max_results: Maximum number of papers to return.
            
        Returns:
            List of discovered papers as ScrapedArticleMetadata.
        """
        venue = self.config.get('venue', 'ICLR.cc/2024/Conference')
        decision_filter = self.config.get('decision')
        min_rating = self.config.get('min_rating')
        
        keywords = query.keywords or []
        
        self.logger.info(
            f"Searching OpenReview venue={venue}, keywords={keywords}, "
            f"max_results={max_results}"
        )
        
        results: list[ScrapedArticleMetadata] = []
        
        try:
            # Get all submissions for the venue
            submissions = self.client.get_all_notes(
                invitation=f'{venue}/-/Submission',
                details='original',
            )
            
            for note in submissions[:max_results * 2]:  # Get extra to filter
                try:
                    # Filter by keywords if provided
                    if keywords and not self._matches_keywords(note, keywords):
                        continue
                    
                    # Filter by decision if specified
                    if decision_filter and not self._matches_decision(note, decision_filter):
                        continue
                    
                    # Filter by rating if specified
                    if min_rating and not self._meets_rating_threshold(note, min_rating):
                        continue
                    
                    # Convert to ScrapedArticleMetadata
                    metadata = self._note_to_metadata(note, venue)
                    if metadata:
                        results.append(metadata)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        break
                        
                except Exception as e:
                    self.logger.warning(f"Error processing OpenReview note: {e}")
                    continue
            
            self.logger.info(f"Found {len(results)} papers from OpenReview")
            return results
            
        except Exception as e:
            self.logger.error(f"OpenReview search failed: {e}")
            return []
    
    def _matches_keywords(self, note, keywords: list[str]) -> bool:
        """Check if note matches any of the provided keywords.
        
        Args:
            note: OpenReview note object.
            keywords: List of keywords to match.
            
        Returns:
            True if note matches any keyword, False otherwise.
        """
        content = note.content
        title = content.get('title', {}).get('value', '').lower()
        abstract = content.get('abstract', {}).get('value', '').lower()
        note_keywords = content.get('keywords', {}).get('value', [])
        
        # Convert note keywords to lowercase strings
        note_keywords_lower = [k.lower() for k in note_keywords if isinstance(k, str)]
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if (keyword_lower in title or 
                keyword_lower in abstract or
                any(keyword_lower in nk for nk in note_keywords_lower)):
                return True
        
        return False
    
    def _matches_decision(self, note, decision: str) -> bool:
        """Check if note has the specified decision.
        
        Args:
            note: OpenReview note object.
            decision: Decision to filter by (e.g., 'Accept', 'Reject').
            
        Returns:
            True if note matches decision, False otherwise.
        """
        try:
            # Decision is typically in the 'decision' field
            note_decision = note.content.get('decision', {}).get('value', '')
            return decision.lower() in note_decision.lower()
        except Exception:
            return False
    
    def _meets_rating_threshold(self, note, min_rating: float) -> bool:
        """Check if note meets minimum rating threshold.
        
        Args:
            note: OpenReview note object.
            min_rating: Minimum average rating.
            
        Returns:
            True if note meets threshold, False otherwise.
        """
        try:
            # Get review ratings from details
            if hasattr(note, 'details') and note.details:
                reviews = note.details.get('replies', [])
                ratings = []
                for review in reviews:
                    if hasattr(review, 'content'):
                        rating = review.content.get('rating', {}).get('value')
                        if rating:
                            # Ratings are typically like "6: Weak Accept"
                            rating_num = int(rating.split(':')[0])
                            ratings.append(rating_num)
                
                if ratings:
                    avg_rating = sum(ratings) / len(ratings)
                    return avg_rating >= min_rating
        except Exception:
            pass
        
        return True  # Don't filter if we can't determine rating
    
    def _note_to_metadata(
        self, note, venue: str
    ) -> ScrapedArticleMetadata | None:
        """Convert OpenReview note to ScrapedArticleMetadata.
        
        Args:
            note: OpenReview note object.
            venue: Venue identifier.
            
        Returns:
            ScrapedArticleMetadata or None if conversion fails.
        """
        try:
            content = note.content
            
            # Extract basic fields
            title = content.get('title', {}).get('value', '')
            if not title:
                return None
            
            abstract = content.get('abstract', {}).get('value', '')
            authors = content.get('authors', {}).get('value', [])
            keywords_data = content.get('keywords', {}).get('value', [])
            
            # Extract keywords
            keywords = []
            if isinstance(keywords_data, list):
                keywords = [k for k in keywords_data if isinstance(k, str)]
            
            # Get URL to the paper
            paper_url = f"https://openreview.net/forum?id={note.id}"
            
            # Try to get PDF URL
            pdf_url = None
            if hasattr(note, 'content') and 'pdf' in content:
                pdf_url = content.get('pdf', {}).get('value')
            
            # Extract year from venue
            year = None
            try:
                year_str = venue.split('/')[1] if '/' in venue else None
                if year_str and year_str.isdigit():
                    year = year_str
            except Exception:
                pass
            
            # Build additional metadata
            additional_metadata = {
                'openreview_id': note.id,
                'venue': venue,
                'forum': note.forum if hasattr(note, 'forum') else note.id,
            }
            
            # Try to extract decision if available
            if 'decision' in content:
                decision = content.get('decision', {}).get('value', '')
                if decision:
                    additional_metadata['decision'] = decision
            
            # Try to extract ratings if available
            if hasattr(note, 'details') and note.details:
                reviews = note.details.get('replies', [])
                ratings = []
                for review in reviews:
                    if hasattr(review, 'content'):
                        rating = review.content.get('rating', {}).get('value')
                        if rating:
                            try:
                                rating_num = int(rating.split(':')[0])
                                ratings.append(rating_num)
                            except Exception:
                                pass
                
                if ratings:
                    additional_metadata['average_rating'] = sum(ratings) / len(ratings)
                    additional_metadata['num_reviews'] = len(ratings)
            
            return ScrapedArticleMetadata(
                title=title,
                authors=authors,
                abstract=abstract if abstract else None,
                publication_date=year,
                journal=venue.split('/')[0] if '/' in venue else venue,
                url=paper_url,
                pdf_url=pdf_url,
                keywords=keywords,
                source='openreview',
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata=additional_metadata,
            )
            
        except Exception as e:
            self.logger.error(f"Error converting OpenReview note to metadata: {e}")
            return None
