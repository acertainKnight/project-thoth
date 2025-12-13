"""
Integration tests for Research Questions API endpoints.

Tests HTTP endpoints for CRUD operations, validation, permissions,
and business logic for the research questions API layer.
"""

import pytest
from datetime import datetime, time
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException

# Import the router and dependencies
from thoth.server.routers.research_questions import router, ResearchQuestionCreate, ResearchQuestionUpdate
from thoth.services.service_manager import ServiceManager


# ==================== Fixtures ====================


@pytest.fixture
def mock_service_manager():
    """Create mock ServiceManager with research question service."""
    manager = MagicMock(spec=ServiceManager)

    # Mock research question service
    rq_service = AsyncMock()
    manager.research_question = rq_service

    # Mock discovery orchestrator
    discovery_orch = AsyncMock()
    manager.discovery_orchestrator = discovery_orch

    return manager


@pytest.fixture
def sample_question_id():
    """Sample question UUID."""
    return uuid4()


@pytest.fixture
def sample_user_id():
    """Sample user ID."""
    return "test_user_123"


@pytest.fixture
def sample_question_data():
    """Sample research question data."""
    return {
        "name": "Machine Learning Research",
        "description": "Research on neural networks and deep learning",
        "keywords": ["neural networks", "deep learning", "transformers"],
        "topics": ["artificial intelligence", "machine learning"],
        "authors": ["Geoffrey Hinton", "Yann LeCun"],
        "selected_sources": ["arxiv", "pubmed"],
        "schedule_frequency": "daily",
        "schedule_time": "02:00:00",
        "min_relevance_score": 0.7,
        "auto_download_enabled": False,
        "auto_download_min_score": 0.8,
    }


@pytest.fixture
def sample_question_response(sample_question_id, sample_user_id, sample_question_data):
    """Sample question response from service."""
    return {
        "id": sample_question_id,
        "user_id": sample_user_id,
        **sample_question_data,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "last_run_at": None,
        "next_run_at": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_articles():
    """Sample matched articles."""
    return [
        {
            "id": uuid4(),
            "article_id": uuid4(),
            "doi": "10.1234/test1",
            "title": "Test Paper 1",
            "authors": ["Author 1", "Author 2"],
            "abstract": "This is a test abstract",
            "relevance_score": 0.85,
            "matched_keywords": ["neural networks"],
            "publication_date": "2024-01-15",
            "is_viewed": False,
            "is_bookmarked": False,
        },
        {
            "id": uuid4(),
            "article_id": uuid4(),
            "doi": "10.1234/test2",
            "title": "Test Paper 2",
            "authors": ["Author 3"],
            "abstract": "Another test abstract",
            "relevance_score": 0.72,
            "matched_keywords": ["deep learning"],
            "publication_date": "2024-02-20",
            "is_viewed": True,
            "is_bookmarked": True,
        },
    ]


@pytest.fixture
def app(mock_service_manager):
    """Create FastAPI test application."""
    app = FastAPI()
    app.include_router(router)  # Router already has prefix in definition

    # Inject mock service manager
    app.state.service_manager = mock_service_manager

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# ==================== Test: Create Research Question ====================


@pytest.mark.asyncio
async def test_create_research_question_success(
    client, mock_service_manager, sample_question_id, sample_user_id, sample_question_data
):
    """Test successful research question creation."""
    # Arrange
    mock_service_manager.research_question.create_research_question.return_value = sample_question_id

    # Act
    response = client.post(
        "/api/research/questions",
        json=sample_question_data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 201
    assert response.json()["id"] == str(sample_question_id)
    assert response.json()["name"] == sample_question_data["name"]

    # Verify service was called correctly
    mock_service_manager.research_question.create_research_question.assert_called_once()
    call_kwargs = mock_service_manager.research_question.create_research_question.call_args[1]
    assert call_kwargs["user_id"] == sample_user_id
    assert call_kwargs["name"] == sample_question_data["name"]
    assert call_kwargs["keywords"] == sample_question_data["keywords"]


@pytest.mark.asyncio
async def test_create_research_question_missing_name(client, sample_user_id):
    """Test creation fails with missing name."""
    # Arrange
    data = {
        "keywords": ["test"],
        "topics": ["testing"],
        "selected_sources": ["arxiv"],
    }

    # Act
    response = client.post(
        "/api/research/questions",
        json=data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_research_question_empty_name(client, sample_user_id):
    """Test creation fails with empty name."""
    # Arrange
    data = {
        "name": "   ",
        "keywords": ["test"],
        "topics": ["testing"],
        "selected_sources": ["arxiv"],
    }

    # Act
    response = client.post(
        "/api/research/questions",
        json=data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_research_question_no_keywords_or_topics(client, sample_user_id):
    """Test creation fails without keywords or topics."""
    # Arrange
    data = {
        "name": "Test Question",
        "keywords": [],
        "topics": [],
        "selected_sources": ["arxiv"],
    }

    # Act
    response = client.post(
        "/api/research/questions",
        json=data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 400
    assert "keyword or topic" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_research_question_empty_sources(client, sample_user_id):
    """Test creation fails with empty sources."""
    # Arrange
    data = {
        "name": "Test Question",
        "keywords": ["test"],
        "topics": [],
        "selected_sources": [],
    }

    # Act
    response = client.post(
        "/api/research/questions",
        json=data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 400
    assert "source" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_research_question_invalid_relevance_score(client, sample_user_id):
    """Test creation fails with invalid relevance score."""
    # Arrange
    data = {
        "name": "Test Question",
        "keywords": ["test"],
        "topics": [],
        "selected_sources": ["arxiv"],
        "min_relevance_score": 1.5,  # Invalid: > 1.0
    }

    # Act
    response = client.post(
        "/api/research/questions",
        json=data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 400
    assert "0.0 and 1.0" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_research_question_duplicate_name(
    client, mock_service_manager, sample_user_id, sample_question_data
):
    """Test creation fails with duplicate name."""
    # Arrange
    mock_service_manager.research_question.create_research_question.side_effect = ValueError(
        "Question name already exists"
    )

    # Act
    response = client.post(
        "/api/research/questions",
        json=sample_question_data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_research_question_no_auth_header(client, sample_question_data):
    """Test creation fails without authentication header."""
    # Act
    response = client.post(
        "/api/research/questions",
        json=sample_question_data,
    )

    # Assert
    assert response.status_code == 401


# ==================== Test: List Research Questions ====================


@pytest.mark.asyncio
async def test_list_research_questions_active_only(
    client, mock_service_manager, sample_user_id, sample_question_response
):
    """Test listing active research questions."""
    # Arrange
    mock_service_manager.research_question.get_user_questions.return_value = [
        sample_question_response
    ]

    # Act
    response = client.get(
        "/api/research/questions",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["questions"]) == 1
    assert data["questions"][0]["id"] == str(sample_question_response["id"])

    # Verify service was called with active_only=True
    mock_service_manager.research_question.get_user_questions.assert_called_once_with(
        user_id=sample_user_id, active_only=True
    )


@pytest.mark.asyncio
async def test_list_research_questions_include_inactive(
    client, mock_service_manager, sample_user_id, sample_question_response
):
    """Test listing all questions including inactive."""
    # Arrange
    inactive_question = {**sample_question_response, "is_active": False}
    mock_service_manager.research_question.get_user_questions.return_value = [
        sample_question_response,
        inactive_question,
    ]

    # Act
    response = client.get(
        "/api/research/questions?active_only=false",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["questions"]) == 2

    # Verify service was called with active_only=False
    mock_service_manager.research_question.get_user_questions.assert_called_once_with(
        user_id=sample_user_id, active_only=False
    )


@pytest.mark.asyncio
async def test_list_research_questions_empty(client, mock_service_manager, sample_user_id):
    """Test listing returns empty list when no questions exist."""
    # Arrange
    mock_service_manager.research_question.get_user_questions.return_value = []

    # Act
    response = client.get(
        "/api/research/questions",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["questions"] == []


# ==================== Test: Get Single Research Question ====================


@pytest.mark.asyncio
async def test_get_research_question_success(
    client, mock_service_manager, sample_question_id, sample_user_id, sample_question_response
):
    """Test getting a single research question."""
    # Arrange
    mock_service_manager.research_question.get_question_by_id.return_value = sample_question_response

    # Act
    response = client.get(
        f"/api/research/questions/{sample_question_id}",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == str(sample_question_id)
    assert response.json()["name"] == sample_question_response["name"]


@pytest.mark.asyncio
async def test_get_research_question_not_found(
    client, mock_service_manager, sample_user_id
):
    """Test getting non-existent question returns 404."""
    # Arrange
    question_id = uuid4()
    mock_service_manager.research_question.get_question_by_id.side_effect = ValueError(
        "Question not found"
    )

    # Act
    response = client.get(
        f"/api/research/questions/{question_id}",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_research_question_permission_denied(
    client, mock_service_manager, sample_question_id
):
    """Test getting another user's question returns 403."""
    # Arrange
    mock_service_manager.research_question.get_question_by_id.side_effect = PermissionError(
        "User does not have permission"
    )

    # Act
    response = client.get(
        f"/api/research/questions/{sample_question_id}",
        headers={"X-User-ID": "different_user"},
    )

    # Assert
    assert response.status_code == 403


# ==================== Test: Update Research Question ====================


@pytest.mark.asyncio
async def test_update_research_question_success(
    client, mock_service_manager, sample_question_id, sample_user_id
):
    """Test successful research question update."""
    # Arrange
    update_data = {
        "name": "Updated Question Name",
        "min_relevance_score": 0.8,
    }
    mock_service_manager.research_question.update_research_question.return_value = True

    # Act
    response = client.patch(
        f"/api/research/questions/{sample_question_id}",
        json=update_data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify service was called
    mock_service_manager.research_question.update_research_question.assert_called_once()


@pytest.mark.asyncio
async def test_update_research_question_partial_update(
    client, mock_service_manager, sample_question_id, sample_user_id
):
    """Test partial update with only one field."""
    # Arrange
    update_data = {"keywords": ["new keyword", "another keyword"]}
    mock_service_manager.research_question.update_research_question.return_value = True

    # Act
    response = client.patch(
        f"/api/research/questions/{sample_question_id}",
        json=update_data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_research_question_invalid_relevance_score(
    client, sample_question_id, sample_user_id
):
    """Test update fails with invalid relevance score."""
    # Arrange
    update_data = {"min_relevance_score": -0.5}

    # Act
    response = client.patch(
        f"/api/research/questions/{sample_question_id}",
        json=update_data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_research_question_not_found(
    client, mock_service_manager, sample_user_id
):
    """Test update of non-existent question."""
    # Arrange
    question_id = uuid4()
    mock_service_manager.research_question.update_research_question.side_effect = ValueError(
        "Question not found"
    )

    # Act
    response = client.patch(
        f"/api/research/questions/{question_id}",
        json={"name": "Updated Name"},
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_research_question_permission_denied(
    client, mock_service_manager, sample_question_id
):
    """Test update by wrong user fails."""
    # Arrange
    mock_service_manager.research_question.update_research_question.side_effect = PermissionError(
        "User does not have permission"
    )

    # Act
    response = client.patch(
        f"/api/research/questions/{sample_question_id}",
        json={"name": "Updated Name"},
        headers={"X-User-ID": "different_user"},
    )

    # Assert
    assert response.status_code == 403


# ==================== Test: Delete Research Question ====================


@pytest.mark.asyncio
async def test_delete_research_question_soft_delete(
    client, mock_service_manager, sample_question_id, sample_user_id
):
    """Test soft delete (default behavior)."""
    # Arrange
    mock_service_manager.research_question.delete_research_question.return_value = True

    # Act
    response = client.delete(
        f"/api/research/questions/{sample_question_id}",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify soft delete was called (hard_delete=False)
    mock_service_manager.research_question.delete_research_question.assert_called_once_with(
        question_id=sample_question_id,
        user_id=sample_user_id,
        hard_delete=False,
    )


@pytest.mark.asyncio
async def test_delete_research_question_hard_delete(
    client, mock_service_manager, sample_question_id, sample_user_id
):
    """Test hard delete with query parameter."""
    # Arrange
    mock_service_manager.research_question.delete_research_question.return_value = True

    # Act
    response = client.delete(
        f"/api/research/questions/{sample_question_id}?hard_delete=true",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200

    # Verify hard delete was called
    mock_service_manager.research_question.delete_research_question.assert_called_once_with(
        question_id=sample_question_id,
        user_id=sample_user_id,
        hard_delete=True,
    )


@pytest.mark.asyncio
async def test_delete_research_question_not_found(
    client, mock_service_manager, sample_user_id
):
    """Test delete of non-existent question."""
    # Arrange
    question_id = uuid4()
    mock_service_manager.research_question.delete_research_question.side_effect = ValueError(
        "Question not found"
    )

    # Act
    response = client.delete(
        f"/api/research/questions/{question_id}",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_research_question_permission_denied(
    client, mock_service_manager, sample_question_id
):
    """Test delete by wrong user fails."""
    # Arrange
    mock_service_manager.research_question.delete_research_question.side_effect = PermissionError(
        "User does not have permission"
    )

    # Act
    response = client.delete(
        f"/api/research/questions/{sample_question_id}",
        headers={"X-User-ID": "different_user"},
    )

    # Assert
    assert response.status_code == 403


# ==================== Test: Manual Discovery Trigger ====================


@pytest.mark.asyncio
async def test_trigger_manual_discovery_success(
    client, mock_service_manager, sample_question_id, sample_user_id
):
    """Test successful manual discovery trigger."""
    # Arrange
    run_id = uuid4()
    mock_service_manager.discovery_orchestrator.run_discovery_for_question.return_value = {
        "run_id": run_id,
        "articles_found": 15,
        "articles_matched": 8,
        "status": "completed",
    }

    # Act
    response = client.post(
        f"/api/research/questions/{sample_question_id}/discover",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == str(run_id)
    assert data["articles_found"] == 15
    assert data["articles_matched"] == 8


@pytest.mark.asyncio
async def test_trigger_manual_discovery_with_max_articles(
    client, mock_service_manager, sample_question_id, sample_user_id
):
    """Test manual discovery with custom max_articles."""
    # Arrange
    mock_service_manager.discovery_orchestrator.run_discovery_for_question.return_value = {
        "run_id": uuid4(),
        "articles_found": 5,
        "articles_matched": 3,
        "status": "completed",
    }

    # Act
    response = client.post(
        f"/api/research/questions/{sample_question_id}/discover?max_articles=5",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200

    # Verify service was called with max_articles parameter
    mock_service_manager.discovery_orchestrator.run_discovery_for_question.assert_called_once()
    call_kwargs = mock_service_manager.discovery_orchestrator.run_discovery_for_question.call_args[1]
    assert call_kwargs.get("max_articles") == 5


@pytest.mark.asyncio
async def test_trigger_manual_discovery_not_found(
    client, mock_service_manager, sample_user_id
):
    """Test manual discovery for non-existent question."""
    # Arrange
    question_id = uuid4()
    mock_service_manager.discovery_orchestrator.run_discovery_for_question.side_effect = ValueError(
        "Question not found"
    )

    # Act
    response = client.post(
        f"/api/research/questions/{question_id}/discover",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trigger_manual_discovery_error_handling(
    client, mock_service_manager, sample_question_id, sample_user_id
):
    """Test manual discovery handles errors gracefully."""
    # Arrange
    mock_service_manager.discovery_orchestrator.run_discovery_for_question.side_effect = Exception(
        "Discovery service unavailable"
    )

    # Act
    response = client.post(
        f"/api/research/questions/{sample_question_id}/discover",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 500


# ==================== Test: Get Matched Articles ====================


@pytest.mark.asyncio
async def test_get_matched_articles_success(
    client, mock_service_manager, sample_question_id, sample_user_id, sample_articles
):
    """Test getting matched articles for a question."""
    # Arrange
    mock_service_manager.research_question.get_matched_articles.return_value = sample_articles

    # Act
    response = client.get(
        f"/api/research/questions/{sample_question_id}/articles",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["articles"]) == 2
    assert data["articles"][0]["relevance_score"] == 0.85


@pytest.mark.asyncio
async def test_get_matched_articles_with_pagination(
    client, mock_service_manager, sample_question_id, sample_user_id, sample_articles
):
    """Test article pagination."""
    # Arrange
    mock_service_manager.research_question.get_matched_articles.return_value = [sample_articles[0]]

    # Act
    response = client.get(
        f"/api/research/questions/{sample_question_id}/articles?limit=1&offset=0",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["articles"]) == 1

    # Verify service was called with pagination params
    mock_service_manager.research_question.get_matched_articles.assert_called_once()
    call_kwargs = mock_service_manager.research_question.get_matched_articles.call_args[1]
    assert call_kwargs.get("limit") == 1
    assert call_kwargs.get("offset") == 0


@pytest.mark.asyncio
async def test_get_matched_articles_filter_by_relevance(
    client, mock_service_manager, sample_question_id, sample_user_id, sample_articles
):
    """Test filtering articles by minimum relevance score."""
    # Arrange
    # Return only high-relevance articles
    mock_service_manager.research_question.get_matched_articles.return_value = [sample_articles[0]]

    # Act
    response = client.get(
        f"/api/research/questions/{sample_question_id}/articles?min_relevance=0.8",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["articles"]) == 1
    assert data["articles"][0]["relevance_score"] >= 0.8


@pytest.mark.asyncio
async def test_get_matched_articles_not_found(
    client, mock_service_manager, sample_user_id
):
    """Test getting articles for non-existent question."""
    # Arrange
    question_id = uuid4()
    mock_service_manager.research_question.get_matched_articles.side_effect = ValueError(
        "Question not found"
    )

    # Act
    response = client.get(
        f"/api/research/questions/{question_id}/articles",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 404


# ==================== Test: Get Statistics ====================


@pytest.mark.asyncio
async def test_get_question_statistics_success(
    client, mock_service_manager, sample_question_id, sample_user_id
):
    """Test getting question statistics."""
    # Arrange
    stats = {
        "total_matches": 50,
        "high_relevance_matches": 20,
        "viewed": 30,
        "bookmarked": 5,
        "avg_relevance": 0.68,
        "total_runs": 10,
        "successful_runs": 9,
        "last_run_at": datetime.now().isoformat(),
    }
    mock_service_manager.research_question.get_question_statistics.return_value = stats

    # Act
    response = client.get(
        f"/api/research/questions/{sample_question_id}/statistics",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total_matches"] == 50
    assert data["high_relevance_matches"] == 20
    assert data["avg_relevance"] == 0.68


@pytest.mark.asyncio
async def test_get_question_statistics_not_found(
    client, mock_service_manager, sample_user_id
):
    """Test getting statistics for non-existent question."""
    # Arrange
    question_id = uuid4()
    mock_service_manager.research_question.get_question_statistics.side_effect = ValueError(
        "Question not found"
    )

    # Act
    response = client.get(
        f"/api/research/questions/{question_id}/statistics",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_question_statistics_permission_denied(
    client, mock_service_manager, sample_question_id
):
    """Test statistics access by wrong user."""
    # Arrange
    mock_service_manager.research_question.get_question_statistics.side_effect = PermissionError(
        "User does not have permission"
    )

    # Act
    response = client.get(
        f"/api/research/questions/{sample_question_id}/statistics",
        headers={"X-User-ID": "different_user"},
    )

    # Assert
    assert response.status_code == 403


# ==================== Test: Edge Cases & Error Handling ====================


@pytest.mark.asyncio
async def test_invalid_uuid_format(client, sample_user_id):
    """Test endpoints handle invalid UUID format."""
    # Act
    response = client.get(
        "/api/research/questions/invalid-uuid-format",
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_question_with_wildcard_source(
    client, mock_service_manager, sample_user_id, sample_question_id
):
    """Test creating question with wildcard source ['*']."""
    # Arrange
    data = {
        "name": "All Sources Question",
        "keywords": ["test"],
        "topics": [],
        "authors": [],
        "selected_sources": ["*"],
    }
    mock_service_manager.research_question.create_research_question.return_value = sample_question_id

    # Act
    response = client.post(
        "/api/research/questions",
        json=data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_update_question_empty_update(
    client, mock_service_manager, sample_question_id, sample_user_id
):
    """Test update with no fields should still succeed."""
    # Arrange
    mock_service_manager.research_question.update_research_question.return_value = True

    # Act
    response = client.patch(
        f"/api/research/questions/{sample_question_id}",
        json={},
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_question_creation(
    client, mock_service_manager, sample_user_id, sample_question_data
):
    """Test handling concurrent creation requests."""
    # Arrange
    mock_service_manager.research_question.create_research_question.side_effect = [
        uuid4(),
        ValueError("Question name already exists"),
    ]

    # Act
    response1 = client.post(
        "/api/research/questions",
        json=sample_question_data,
        headers={"X-User-ID": sample_user_id},
    )
    response2 = client.post(
        "/api/research/questions",
        json=sample_question_data,
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response1.status_code == 201
    assert response2.status_code == 400


# ==================== Summary ====================

"""
Test Coverage Summary:
- Create endpoint: 7 tests (success, validation errors, duplicates)
- List endpoint: 3 tests (active, inactive, empty)
- Get single: 3 tests (success, not found, permission denied)
- Update endpoint: 5 tests (success, partial, validation, not found, permission)
- Delete endpoint: 4 tests (soft delete, hard delete, not found, permission)
- Manual trigger: 4 tests (success, custom params, not found, error handling)
- Get articles: 4 tests (success, pagination, filtering, not found)
- Get statistics: 3 tests (success, not found, permission denied)
- Edge cases: 4 tests (invalid UUID, wildcard source, empty update, concurrency)

Total: 37 comprehensive test cases covering all endpoints and error conditions
"""
