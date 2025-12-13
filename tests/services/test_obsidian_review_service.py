"""
Tests for Obsidian Review Service.

Tests the import functionality for article review decisions from Obsidian
markdown files with YAML frontmatter.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from thoth.services.obsidian_review_service import ObsidianReviewService


@pytest.fixture
def mock_match_repo():
    """Mock article research match repository."""
    repo = MagicMock()
    repo.set_bookmark = AsyncMock(return_value=True)
    repo.set_user_rating = AsyncMock(return_value=True)
    repo.mark_as_viewed = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def review_service(mock_match_repo):
    """Create ObsidianReviewService with mocked repository."""
    return ObsidianReviewService(mock_match_repo)


@pytest.mark.asyncio
async def test_apply_review_decisions_liked(review_service, tmp_path):
    """Test applying 'liked' status sets bookmark and rating."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles:
  - id: "550e8400-e29b-41d4-a716-446655440000"
    title: "Test Article"
    status: "liked"
    notes: "Excellent paper"
---

# Test Review
""")

    stats = await review_service.apply_review_decisions(review_file)

    assert stats['liked'] == 1
    assert stats['updated'] == 1
    assert stats['errors'] == 0
    
    # Verify bookmark was set
    review_service.match_repo.set_bookmark.assert_called_once_with(
        UUID("550e8400-e29b-41d4-a716-446655440000"), True
    )
    
    # Verify rating was set to 5
    review_service.match_repo.set_user_rating.assert_called_once_with(
        UUID("550e8400-e29b-41d4-a716-446655440000"), 5, "Excellent paper"
    )


@pytest.mark.asyncio
async def test_apply_review_decisions_disliked(review_service, tmp_path):
    """Test applying 'disliked' status sets low rating."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles:
  - id: "660e8400-e29b-41d4-a716-446655440001"
    title: "Another Article"
    status: "disliked"
    notes: "Not relevant"
---

# Test Review
""")

    stats = await review_service.apply_review_decisions(review_file)

    assert stats['disliked'] == 1
    assert stats['updated'] == 1
    
    # Verify rating was set to 1
    review_service.match_repo.set_user_rating.assert_called_once_with(
        UUID("660e8400-e29b-41d4-a716-446655440001"), 1, "Not relevant"
    )


@pytest.mark.asyncio
async def test_apply_review_decisions_skip(review_service, tmp_path):
    """Test applying 'skip' status marks as viewed only."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles:
  - id: "770e8400-e29b-41d4-a716-446655440002"
    title: "Skipped Article"
    status: "skip"
---

# Test Review
""")

    stats = await review_service.apply_review_decisions(review_file)

    assert stats['skipped'] == 1
    assert stats['updated'] == 1
    
    # Verify marked as viewed
    review_service.match_repo.mark_as_viewed.assert_called_once_with(
        UUID("770e8400-e29b-41d4-a716-446655440002")
    )


@pytest.mark.asyncio
async def test_apply_review_decisions_pending(review_service, tmp_path):
    """Test that 'pending' status is ignored (no database updates)."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles:
  - id: "880e8400-e29b-41d4-a716-446655440003"
    title: "Pending Article"
    status: "pending"
---

# Test Review
""")

    stats = await review_service.apply_review_decisions(review_file)

    assert stats['updated'] == 0
    assert stats['errors'] == 0
    
    # Verify no repository methods were called
    review_service.match_repo.set_bookmark.assert_not_called()
    review_service.match_repo.set_user_rating.assert_not_called()
    review_service.match_repo.mark_as_viewed.assert_not_called()


@pytest.mark.asyncio
async def test_apply_review_decisions_mixed(review_service, tmp_path):
    """Test processing multiple articles with different statuses."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
question_id: "abc-123-def-456"
articles:
  - id: "550e8400-e29b-41d4-a716-446655440000"
    status: "liked"
  - id: "660e8400-e29b-41d4-a716-446655440001"
    status: "disliked"
  - id: "770e8400-e29b-41d4-a716-446655440002"
    status: "skip"
  - id: "880e8400-e29b-41d4-a716-446655440003"
    status: "pending"
---

# Test Review
""")

    stats = await review_service.apply_review_decisions(review_file)

    assert stats['liked'] == 1
    assert stats['disliked'] == 1
    assert stats['skipped'] == 1
    assert stats['updated'] == 3
    assert stats['errors'] == 0


@pytest.mark.asyncio
async def test_apply_review_decisions_invalid_uuid(review_service, tmp_path):
    """Test handling of invalid UUID format."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles:
  - id: "not-a-valid-uuid"
    status: "liked"
---

# Test Review
""")

    stats = await review_service.apply_review_decisions(review_file)

    assert stats['updated'] == 0
    assert stats['errors'] == 1


@pytest.mark.asyncio
async def test_apply_review_decisions_missing_id(review_service, tmp_path):
    """Test handling of missing article ID."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles:
  - title: "Article Without ID"
    status: "liked"
---

# Test Review
""")

    stats = await review_service.apply_review_decisions(review_file)

    assert stats['updated'] == 0
    assert stats['errors'] == 1


@pytest.mark.asyncio
async def test_apply_review_decisions_file_not_found(review_service):
    """Test handling of non-existent file."""
    with pytest.raises(FileNotFoundError):
        await review_service.apply_review_decisions(
            Path("/nonexistent/file.md")
        )


@pytest.mark.asyncio
async def test_apply_review_decisions_invalid_yaml(review_service, tmp_path):
    """Test handling of invalid YAML format."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles: [
  invalid yaml syntax here
---

# Test Review
""")

    with pytest.raises(ValueError, match="Invalid YAML format"):
        await review_service.apply_review_decisions(review_file)


@pytest.mark.asyncio
async def test_apply_review_decisions_no_frontmatter(review_service, tmp_path):
    """Test handling of file without frontmatter."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""# Test Review

No YAML frontmatter here.
""")

    with pytest.raises(ValueError, match="Expected YAML frontmatter"):
        await review_service.apply_review_decisions(review_file)


@pytest.mark.asyncio
async def test_validate_review_file_valid(review_service, tmp_path):
    """Test validation of valid review file."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles:
  - id: "550e8400-e29b-41d4-a716-446655440000"
    status: "liked"
---

# Test Review
""")

    result = await review_service.validate_review_file(review_file)

    assert result['valid'] is True
    assert result['article_count'] == 1
    assert len(result['errors']) == 0


@pytest.mark.asyncio
async def test_validate_review_file_invalid_uuid(review_service, tmp_path):
    """Test validation catches invalid UUID."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles:
  - id: "not-a-uuid"
    status: "liked"
---

# Test Review
""")

    result = await review_service.validate_review_file(review_file)

    assert result['valid'] is False
    assert len(result['errors']) > 0
    assert any('invalid UUID' in error for error in result['errors'])


@pytest.mark.asyncio
async def test_validate_review_file_unknown_status(review_service, tmp_path):
    """Test validation warns about unknown status."""
    review_file = tmp_path / "test_review.md"
    review_file.write_text("""---
articles:
  - id: "550e8400-e29b-41d4-a716-446655440000"
    status: "unknown"
---

# Test Review
""")

    result = await review_service.validate_review_file(review_file)

    assert result['valid'] is True  # Warnings don't make it invalid
    assert len(result['warnings']) > 0
    assert any('unknown status' in warning for warning in result['warnings'])


@pytest.mark.asyncio
async def test_validate_review_file_not_found(review_service):
    """Test validation of non-existent file."""
    result = await review_service.validate_review_file(
        Path("/nonexistent/file.md")
    )

    assert result['valid'] is False
    assert len(result['errors']) > 0
    assert any('not found' in error for error in result['errors'])
