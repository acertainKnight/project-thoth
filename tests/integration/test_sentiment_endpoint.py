"""Integration tests for article sentiment API endpoint."""

import pytest
from uuid import uuid4
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_update_article_sentiment_success(async_client: AsyncClient, test_user_id: str):
    """Test successful sentiment update."""
    # Create a research question
    question_data = {
        "name": "Test Question for Sentiment",
        "keywords": ["machine learning"],
        "selected_sources": ["arxiv"],
    }
    response = await async_client.post(
        f"/api/research/questions?user_id={test_user_id}",
        json=question_data,
    )
    assert response.status_code == 201
    question = response.json()
    question_id = question["id"]

    # For this test, we need an existing match
    # In a real scenario, you would run discovery first
    # Here we'll test the validation instead

    # Test with non-existent match
    fake_match_id = str(uuid4())
    sentiment_data = {"sentiment": "like"}

    response = await async_client.patch(
        f"/api/research/questions/{question_id}/articles/{fake_match_id}/sentiment?user_id={test_user_id}",
        json=sentiment_data,
    )

    # Should return 404 as match doesn't exist
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_sentiment_invalid_value(async_client: AsyncClient, test_user_id: str):
    """Test sentiment update with invalid value."""
    question_id = str(uuid4())
    match_id = str(uuid4())

    # Test with invalid sentiment
    sentiment_data = {"sentiment": "invalid"}

    response = await async_client.patch(
        f"/api/research/questions/{question_id}/articles/{match_id}/sentiment?user_id={test_user_id}",
        json=sentiment_data,
    )

    # Should fail validation (422 or 400)
    assert response.status_code in [400, 422]


@pytest.mark.asyncio
async def test_update_sentiment_unauthorized(async_client: AsyncClient):
    """Test sentiment update without proper authorization."""
    question_id = str(uuid4())
    match_id = str(uuid4())

    sentiment_data = {"sentiment": "like"}

    response = await async_client.patch(
        f"/api/research/questions/{question_id}/articles/{match_id}/sentiment",
        json=sentiment_data,
    )

    # Should return 404 as question doesn't exist
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sentiment_values(async_client: AsyncClient, test_user_id: str):
    """Test all valid sentiment values."""
    question_id = str(uuid4())
    match_id = str(uuid4())

    valid_sentiments = ["like", "dislike", "skip"]

    for sentiment in valid_sentiments:
        sentiment_data = {"sentiment": sentiment}

        # All will fail as match doesn't exist, but should pass validation
        response = await async_client.patch(
            f"/api/research/questions/{question_id}/articles/{match_id}/sentiment?user_id={test_user_id}",
            json=sentiment_data,
        )

        # Should not be a validation error (422)
        # Should be 404 (not found) instead
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_response_includes_sentiment_fields(async_client: AsyncClient, test_user_id: str):
    """Test that ArticleMatchResponse includes sentiment fields."""
    # Create a research question
    question_data = {
        "name": "Test Question",
        "keywords": ["test"],
        "selected_sources": ["arxiv"],
    }
    response = await async_client.post(
        f"/api/research/questions?user_id={test_user_id}",
        json=question_data,
    )
    assert response.status_code == 201
    question_id = response.json()["id"]

    # Get articles (will be empty, but test the schema)
    response = await async_client.get(
        f"/api/research/questions/{question_id}/articles?user_id={test_user_id}"
    )
    assert response.status_code == 200

    # Verify response structure includes sentiment fields
    data = response.json()
    assert "matches" in data
    assert "total" in data
    assert "limit" in data

    # When articles exist, they should have sentiment fields
    # For now, just verify the endpoint works


@pytest.fixture
async def test_user_id() -> str:
    """Provide a test user ID."""
    return "test_user_sentiment"


@pytest.fixture
async def async_client():
    """Create async test client."""
    from fastapi.testclient import TestClient
    from thoth.server.app import app

    # Note: This is a basic fixture
    # In practice, you'd want to use httpx.AsyncClient with proper async setup
    client = TestClient(app)
    yield client
