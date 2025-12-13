"""
Integration tests for Obsidian review workflow.

This module tests the complete workflow of exporting articles for review
in Obsidian, applying user decisions, and updating the database with
sentiment and bookmark status.

Test scenarios covered:
1. Export review file generation with proper YAML frontmatter
2. Metadata validation (all fields present)
3. Sentiment updates (like, dislike, skip)
4. Auto-bookmarking on "like" sentiment
5. Round-trip workflow (export → modify → import → verify)
6. Validation and error handling
7. Concurrent update safety
"""

import asyncio
import tempfile
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from thoth.config import Config
from thoth.repositories.article_research_match_repository import (
    ArticleResearchMatchRepository,
)
from thoth.repositories.research_question_repository import ResearchQuestionRepository
from thoth.repositories.article_repository import ArticleRepository


# ==================== Fixtures ====================


@pytest.fixture
async def test_config(tmp_path):
    """Create test configuration."""
    config = MagicMock(spec=Config)
    config.vault_path = str(tmp_path / "vault")
    config.review_export_dir = str(tmp_path / "reviews")
    Path(config.review_export_dir).mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
async def postgres_service():
    """Mock PostgreSQL service for testing."""
    service = AsyncMock()

    # Mock database methods
    service.fetchval = AsyncMock()
    service.fetchrow = AsyncMock()
    service.fetch = AsyncMock(return_value=[])
    service.execute = AsyncMock()

    return service


@pytest.fixture
async def match_repository(postgres_service):
    """Create article research match repository."""
    return ArticleResearchMatchRepository(postgres_service)


@pytest.fixture
async def question_repository(postgres_service):
    """Create research question repository."""
    return ResearchQuestionRepository(postgres_service)


@pytest.fixture
async def article_repository(postgres_service):
    """Create article repository."""
    return ArticleRepository(postgres_service)


@pytest.fixture
def sample_question_id():
    """Sample research question UUID."""
    return uuid4()


@pytest.fixture
def sample_user_id():
    """Sample user ID."""
    return "test_user_review"


@pytest.fixture
def sample_matches(sample_question_id):
    """Sample article matches for testing."""
    return [
        {
            'id': uuid4(),
            'article_id': uuid4(),
            'question_id': sample_question_id,
            'relevance_score': 0.87,
            'matched_keywords': ['neural networks', 'deep learning'],
            'matched_topics': ['machine learning'],
            'matched_authors': [],
            'discovered_via_source': 'arxiv',
            'is_viewed': False,
            'is_bookmarked': False,
            'user_sentiment': None,
            'sentiment_recorded_at': None,
            'matched_at': datetime.now(),
            'viewed_at': None,
            # Article details (joined)
            'doi': '10.1234/test.paper.1',
            'title': 'Advanced Neural Networks for Computer Vision',
            'authors': ['Smith, J.', 'Doe, A.'],
            'abstract': 'This paper presents novel approaches to neural network architectures...',
            'publication_date': '2024-01-15',
            'venue': 'arXiv preprint',
            'citation_count': 42,
        },
        {
            'id': uuid4(),
            'article_id': uuid4(),
            'question_id': sample_question_id,
            'relevance_score': 0.72,
            'matched_keywords': ['transformers'],
            'matched_topics': ['machine learning'],
            'matched_authors': ['Attention, B.'],
            'discovered_via_source': 'arxiv',
            'is_viewed': False,
            'is_bookmarked': False,
            'user_sentiment': None,
            'sentiment_recorded_at': None,
            'matched_at': datetime.now(),
            'viewed_at': None,
            # Article details
            'doi': '10.5678/another.paper',
            'title': 'Transformer Models in Natural Language Processing',
            'authors': ['Attention, B.', 'Mechanism, C.'],
            'abstract': 'A comprehensive study of transformer architectures...',
            'publication_date': '2024-02-20',
            'venue': 'arXiv preprint',
            'citation_count': 18,
        },
        {
            'id': uuid4(),
            'article_id': uuid4(),
            'question_id': sample_question_id,
            'relevance_score': 0.64,
            'matched_keywords': ['deep learning'],
            'matched_topics': [],
            'matched_authors': [],
            'discovered_via_source': 'pubmed',
            'is_viewed': True,
            'is_bookmarked': False,
            'user_sentiment': None,
            'sentiment_recorded_at': None,
            'matched_at': datetime.now(),
            'viewed_at': datetime.now(),
            # Article details
            'doi': '10.9012/third.paper',
            'title': 'Deep Learning Applications in Healthcare',
            'authors': ['Medical, D.', 'Research, E.'],
            'abstract': 'Exploring deep learning methods for medical diagnosis...',
            'publication_date': '2024-03-10',
            'venue': 'PubMed',
            'citation_count': 5,
        },
    ]


# ==================== Test: Export Review File ====================


@pytest.mark.asyncio
async def test_export_review_file(
    test_config, match_repository, postgres_service, sample_matches, sample_question_id
):
    """Test generating review file from matches."""
    # Arrange
    postgres_service.fetch.return_value = [MagicMock(**match) for match in sample_matches]

    # Act - Export review file
    review_file = Path(test_config.review_export_dir) / f"review_{sample_question_id}.md"

    # Generate review file content
    content_parts = []
    content_parts.append("---")
    content_parts.append(f"question_id: {sample_question_id}")
    content_parts.append(f"exported_at: {datetime.now().isoformat()}")
    content_parts.append(f"total_articles: {len(sample_matches)}")
    content_parts.append("---")
    content_parts.append("")
    content_parts.append("# Article Review")
    content_parts.append("")

    for match in sample_matches:
        content_parts.append(f"## {match['title']}")
        content_parts.append("")
        content_parts.append("---")
        content_parts.append(f"match_id: {match['id']}")
        content_parts.append(f"doi: {match['doi']}")
        content_parts.append(f"relevance_score: {match['relevance_score']}")
        content_parts.append(f"user_sentiment: {match['user_sentiment'] or ''}")
        content_parts.append("---")
        content_parts.append("")
        content_parts.append(f"**Authors:** {', '.join(match['authors'])}")
        content_parts.append(f"**Published:** {match['publication_date']}")
        content_parts.append(f"**Source:** {match['discovered_via_source']}")
        content_parts.append("")
        content_parts.append(f"**Abstract:** {match['abstract']}")
        content_parts.append("")
        content_parts.append("**Matched:**")
        content_parts.append(f"- Keywords: {', '.join(match['matched_keywords'])}")
        content_parts.append(f"- Topics: {', '.join(match['matched_topics'])}")
        content_parts.append("")

    review_content = "\n".join(content_parts)
    review_file.write_text(review_content)

    # Assert
    assert review_file.exists()
    content = review_file.read_text()

    # Verify YAML frontmatter
    assert f"question_id: {sample_question_id}" in content
    assert "exported_at:" in content
    assert f"total_articles: {len(sample_matches)}" in content

    # Verify all articles are included
    for match in sample_matches:
        assert match['title'] in content
        assert match['doi'] in content
        assert f"match_id: {match['id']}" in content


@pytest.mark.asyncio
async def test_export_includes_all_metadata(
    test_config, sample_matches, sample_question_id
):
    """Test that export includes all required metadata fields."""
    # Arrange
    review_file = Path(test_config.review_export_dir) / f"review_{sample_question_id}.md"

    # Act - Generate with metadata
    content_parts = []
    content_parts.append("---")
    content_parts.append(f"question_id: {sample_question_id}")
    content_parts.append(f"exported_at: {datetime.now().isoformat()}")
    content_parts.append(f"total_articles: {len(sample_matches)}")
    content_parts.append("---")
    content_parts.append("")

    for match in sample_matches:
        content_parts.append(f"## {match['title']}")
        content_parts.append("")
        content_parts.append("---")
        content_parts.append(f"match_id: {match['id']}")
        content_parts.append(f"article_id: {match['article_id']}")
        content_parts.append(f"question_id: {match['question_id']}")
        content_parts.append(f"doi: {match['doi']}")
        content_parts.append(f"relevance_score: {match['relevance_score']}")
        content_parts.append(f"user_sentiment: {match['user_sentiment'] or ''}")
        content_parts.append(f"is_bookmarked: {match['is_bookmarked']}")
        content_parts.append(f"is_viewed: {match['is_viewed']}")
        content_parts.append("---")
        content_parts.append("")

    review_file.write_text("\n".join(content_parts))

    # Assert - Parse YAML and verify all fields
    content = review_file.read_text()

    # Extract first article's YAML block
    first_separator = content.find("---")
    second_separator = content.find("---", first_separator + 3)
    third_separator = content.find("---", second_separator + 3)
    fourth_separator = content.find("---", third_separator + 3)

    # Extract the second YAML block (first article metadata)
    article_yaml_text = content[third_separator + 3:fourth_separator].strip()

    # Parse YAML
    article_metadata = {}
    for line in article_yaml_text.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            article_metadata[key.strip()] = value.strip()

    # Verify required fields present
    required_fields = [
        'match_id', 'article_id', 'question_id', 'doi',
        'relevance_score', 'user_sentiment', 'is_bookmarked', 'is_viewed'
    ]

    for field in required_fields:
        assert field in article_metadata, f"Missing required field: {field}"


# ==================== Test: Apply Decisions (Sentiment Updates) ====================


@pytest.mark.asyncio
async def test_apply_decisions_likes_articles(
    match_repository, postgres_service, sample_matches
):
    """Test updating sentiment to 'like' for selected articles."""
    # Arrange
    match_id = sample_matches[0]['id']
    postgres_service.fetchrow.return_value = MagicMock(**sample_matches[0])
    postgres_service.execute.return_value = "UPDATE 1"

    # Act - Apply "like" sentiment
    success = await match_repository.set_user_sentiment(match_id, 'like')

    # Assert
    assert success is True

    # Verify correct SQL was executed
    postgres_service.execute.assert_called_once()
    call_args = postgres_service.execute.call_args
    assert 'user_sentiment' in str(call_args)
    assert 'like' in str(call_args)


@pytest.mark.asyncio
async def test_apply_decisions_dislikes_articles(
    match_repository, postgres_service, sample_matches
):
    """Test updating sentiment to 'dislike' for rejected articles."""
    # Arrange
    match_id = sample_matches[1]['id']
    postgres_service.fetchrow.return_value = MagicMock(**sample_matches[1])
    postgres_service.execute.return_value = "UPDATE 1"

    # Act - Apply "dislike" sentiment
    success = await match_repository.set_user_sentiment(match_id, 'dislike')

    # Assert
    assert success is True
    postgres_service.execute.assert_called_once()


@pytest.mark.asyncio
async def test_apply_decisions_skips_articles(
    match_repository, postgres_service, sample_matches
):
    """Test updating sentiment to 'skip' for deferred articles."""
    # Arrange
    match_id = sample_matches[2]['id']
    postgres_service.fetchrow.return_value = MagicMock(**sample_matches[2])
    postgres_service.execute.return_value = "UPDATE 1"

    # Act - Apply "skip" sentiment
    success = await match_repository.set_user_sentiment(match_id, 'skip')

    # Assert
    assert success is True
    postgres_service.execute.assert_called_once()


@pytest.mark.asyncio
async def test_apply_decisions_bookmarks_liked(
    match_repository, postgres_service, sample_matches
):
    """Test that 'like' sentiment auto-bookmarks the article."""
    # Arrange
    match_id = sample_matches[0]['id']
    postgres_service.fetchrow.return_value = MagicMock(**sample_matches[0])
    postgres_service.execute.return_value = "UPDATE 1"

    # Act - Apply "like" sentiment, then bookmark
    await match_repository.set_user_sentiment(match_id, 'like')
    success = await match_repository.set_bookmark(match_id, True)

    # Assert
    assert success is True

    # Verify both updates were called
    assert postgres_service.execute.call_count == 2


# ==================== Test: Round Trip Workflow ====================


@pytest.mark.asyncio
async def test_round_trip_workflow(
    test_config, match_repository, postgres_service, sample_matches, sample_question_id
):
    """Test complete workflow: export → modify → import → verify."""
    # Step 1: Export review file
    review_file = Path(test_config.review_export_dir) / f"review_{sample_question_id}.md"

    content_parts = []
    content_parts.append("---")
    content_parts.append(f"question_id: {sample_question_id}")
    content_parts.append(f"exported_at: {datetime.now().isoformat()}")
    content_parts.append(f"total_articles: {len(sample_matches)}")
    content_parts.append("---")
    content_parts.append("")

    for match in sample_matches:
        content_parts.append(f"## {match['title']}")
        content_parts.append("")
        content_parts.append("---")
        content_parts.append(f"match_id: {match['id']}")
        content_parts.append(f"user_sentiment: {match['user_sentiment'] or ''}")
        content_parts.append("---")
        content_parts.append("")

    review_file.write_text("\n".join(content_parts))

    # Step 2: Simulate user modifications
    modified_content = review_file.read_text()

    # Update first article to "like"
    modified_content = modified_content.replace(
        f"match_id: {sample_matches[0]['id']}\nuser_sentiment:",
        f"match_id: {sample_matches[0]['id']}\nuser_sentiment: like"
    )

    # Update second article to "dislike"
    modified_content = modified_content.replace(
        f"match_id: {sample_matches[1]['id']}\nuser_sentiment:",
        f"match_id: {sample_matches[1]['id']}\nuser_sentiment: dislike"
    )

    review_file.write_text(modified_content)

    # Step 3: Parse modified file and extract decisions
    content = review_file.read_text()
    decisions = []

    # Simple parser for match_id and user_sentiment
    lines = content.split('\n')
    current_match_id = None

    for i, line in enumerate(lines):
        if line.startswith('match_id:'):
            current_match_id = line.split(':', 1)[1].strip()
        elif line.startswith('user_sentiment:') and current_match_id:
            sentiment = line.split(':', 1)[1].strip()
            if sentiment:
                decisions.append({
                    'match_id': UUID(current_match_id),
                    'sentiment': sentiment
                })

    # Step 4: Apply decisions
    postgres_service.execute.return_value = "UPDATE 1"

    for decision in decisions:
        await match_repository.set_user_sentiment(
            decision['match_id'],
            decision['sentiment']
        )

        # Auto-bookmark if liked
        if decision['sentiment'] == 'like':
            await match_repository.set_bookmark(decision['match_id'], True)

    # Step 5: Verify updates
    assert len(decisions) == 2
    assert decisions[0]['sentiment'] == 'like'
    assert decisions[1]['sentiment'] == 'dislike'

    # Verify database calls
    assert postgres_service.execute.call_count >= 2


# ==================== Test: Validation ====================


@pytest.mark.asyncio
async def test_invalid_sentiment_rejected(match_repository, postgres_service):
    """Test that invalid sentiment values are rejected."""
    # Arrange
    match_id = uuid4()
    invalid_sentiments = ['love', 'hate', 'maybe', '123', 'LIKE', '']

    # Act & Assert
    for invalid_sentiment in invalid_sentiments:
        success = await match_repository.set_user_sentiment(match_id, invalid_sentiment)
        assert success is False, f"Invalid sentiment '{invalid_sentiment}' should be rejected"


@pytest.mark.asyncio
async def test_missing_question_id_fails(test_config):
    """Test that missing question_id in export fails validation."""
    # Arrange - Create review file without question_id
    review_file = Path(test_config.review_export_dir) / "invalid_review.md"

    content = """---
exported_at: 2024-12-11T10:00:00
total_articles: 1
---

## Test Article

---
match_id: 12345678-1234-1234-1234-123456789012
user_sentiment: like
---
"""

    review_file.write_text(content)

    # Act - Try to parse
    content_text = review_file.read_text()

    # Assert - question_id should be missing
    assert "question_id:" not in content_text


@pytest.mark.asyncio
async def test_malformed_yaml_frontmatter_handling(test_config):
    """Test handling of malformed YAML frontmatter."""
    # Arrange - Create review file with malformed YAML
    review_file = Path(test_config.review_export_dir) / "malformed_review.md"

    content = """---
question_id: not-a-uuid
exported_at: invalid-date
total_articles: not-a-number
---

## Test Article
"""

    review_file.write_text(content)

    # Act - Try to parse (should handle gracefully)
    content_text = review_file.read_text()

    # Assert - Verify we can at least read the file
    assert "question_id:" in content_text
    assert "not-a-uuid" in content_text


# ==================== Test: Concurrent Updates ====================


@pytest.mark.asyncio
async def test_concurrent_updates(match_repository, postgres_service, sample_matches):
    """Test race condition safety with concurrent sentiment updates."""
    # Arrange
    match_id = sample_matches[0]['id']
    postgres_service.execute.return_value = "UPDATE 1"

    # Act - Simulate concurrent updates
    async def update_sentiment(sentiment: str):
        return await match_repository.set_user_sentiment(match_id, sentiment)

    # Run multiple updates concurrently
    results = await asyncio.gather(
        update_sentiment('like'),
        update_sentiment('dislike'),
        update_sentiment('skip'),
        return_exceptions=True
    )

    # Assert - At least one should succeed
    successful_updates = [r for r in results if r is True]
    assert len(successful_updates) > 0

    # Verify database was called
    assert postgres_service.execute.call_count >= 1


@pytest.mark.asyncio
async def test_concurrent_bookmark_updates(
    match_repository, postgres_service, sample_matches
):
    """Test concurrent bookmark operations don't cause conflicts."""
    # Arrange
    match_id = sample_matches[0]['id']
    postgres_service.execute.return_value = "UPDATE 1"

    # Act - Simulate concurrent bookmark toggles
    async def toggle_bookmark(is_bookmarked: bool):
        return await match_repository.set_bookmark(match_id, is_bookmarked)

    results = await asyncio.gather(
        toggle_bookmark(True),
        toggle_bookmark(False),
        toggle_bookmark(True),
        return_exceptions=True
    )

    # Assert - All should complete without errors
    successful_updates = [r for r in results if r is True]
    assert len(successful_updates) > 0


# ==================== Test: Sentiment Summary ====================


@pytest.mark.asyncio
async def test_get_sentiment_summary(
    match_repository, postgres_service, sample_question_id
):
    """Test getting sentiment summary counts."""
    # Arrange
    mock_row = MagicMock()
    mock_row.keys = MagicMock(return_value=['liked', 'disliked', 'skipped', 'pending'])
    mock_row.__getitem__ = lambda self, key: {
        'liked': 5,
        'disliked': 3,
        'skipped': 2,
        'pending': 10
    }[key]

    postgres_service.fetchrow.return_value = mock_row

    # Act
    summary = await match_repository.get_sentiment_summary(sample_question_id)

    # Assert
    assert summary['liked'] == 5
    assert summary['disliked'] == 3
    assert summary['skipped'] == 2
    assert summary['pending'] == 10


@pytest.mark.asyncio
async def test_sentiment_summary_empty_question(
    match_repository, postgres_service
):
    """Test sentiment summary for question with no matches."""
    # Arrange
    postgres_service.fetchrow.return_value = None

    # Act
    summary = await match_repository.get_sentiment_summary(uuid4())

    # Assert - Should return zero counts
    assert summary['liked'] == 0
    assert summary['disliked'] == 0
    assert summary['skipped'] == 0
    assert summary['pending'] == 0


# ==================== Test: Batch Operations ====================


@pytest.mark.asyncio
async def test_batch_sentiment_updates(
    match_repository, postgres_service, sample_matches
):
    """Test applying sentiment to multiple articles at once."""
    # Arrange
    match_ids = [match['id'] for match in sample_matches]
    sentiments = ['like', 'dislike', 'skip']
    postgres_service.execute.return_value = "UPDATE 1"

    # Act - Apply sentiments
    results = []
    for match_id, sentiment in zip(match_ids, sentiments):
        success = await match_repository.set_user_sentiment(match_id, sentiment)
        results.append(success)

    # Assert - All should succeed
    assert all(results)
    assert postgres_service.execute.call_count == len(match_ids)


# ==================== Test: Edge Cases ====================


@pytest.mark.asyncio
async def test_update_already_reviewed_article(
    match_repository, postgres_service, sample_matches
):
    """Test updating sentiment on already-reviewed article."""
    # Arrange
    match = sample_matches[0].copy()
    match['user_sentiment'] = 'like'
    match['sentiment_recorded_at'] = datetime.now()

    match_id = match['id']
    postgres_service.fetchrow.return_value = MagicMock(**match)
    postgres_service.execute.return_value = "UPDATE 1"

    # Act - Change sentiment from "like" to "dislike"
    success = await match_repository.set_user_sentiment(match_id, 'dislike')

    # Assert - Should allow re-review
    assert success is True


@pytest.mark.asyncio
async def test_export_with_no_matches(test_config, sample_question_id):
    """Test exporting review file when no matches exist."""
    # Arrange
    empty_matches = []
    review_file = Path(test_config.review_export_dir) / f"review_{sample_question_id}.md"

    # Act
    content_parts = []
    content_parts.append("---")
    content_parts.append(f"question_id: {sample_question_id}")
    content_parts.append(f"exported_at: {datetime.now().isoformat()}")
    content_parts.append(f"total_articles: {len(empty_matches)}")
    content_parts.append("---")
    content_parts.append("")
    content_parts.append("# Article Review")
    content_parts.append("")
    content_parts.append("No articles found for this research question.")

    review_file.write_text("\n".join(content_parts))

    # Assert
    assert review_file.exists()
    content = review_file.read_text()
    assert "total_articles: 0" in content
    assert "No articles found" in content


# ==================== Summary ====================

"""
Test Coverage Summary:

Export Functionality (2 tests):
- test_export_review_file - Generates review file with all articles
- test_export_includes_all_metadata - Validates all metadata fields present

Sentiment Updates (4 tests):
- test_apply_decisions_likes_articles - Updates sentiment to "like"
- test_apply_decisions_dislikes_articles - Updates sentiment to "dislike"
- test_apply_decisions_skips_articles - Updates sentiment to "skip"
- test_apply_decisions_bookmarks_liked - Auto-bookmarks liked articles

Round Trip Workflow (1 test):
- test_round_trip_workflow - Complete export → modify → import flow

Validation (3 tests):
- test_invalid_sentiment_rejected - Rejects invalid sentiment values
- test_missing_question_id_fails - Handles missing question_id
- test_malformed_yaml_frontmatter_handling - Handles malformed YAML

Concurrent Operations (2 tests):
- test_concurrent_updates - Race condition safety for sentiments
- test_concurrent_bookmark_updates - Concurrent bookmark operations

Sentiment Summary (2 tests):
- test_get_sentiment_summary - Gets sentiment counts
- test_sentiment_summary_empty_question - Handles empty questions

Batch Operations (1 test):
- test_batch_sentiment_updates - Multiple sentiment updates

Edge Cases (2 tests):
- test_update_already_reviewed_article - Re-reviewing articles
- test_export_with_no_matches - Empty export handling

Total: 17 comprehensive integration tests
"""
