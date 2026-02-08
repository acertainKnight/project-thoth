"""Tests for research_questions router endpoints.

Note: This router is 1056 lines and should be refactored into smaller modules:
- models.py (Pydantic models)
- crud.py (CRUD operations)
- operations.py (discovery, articles)
- statistics.py (stats, sentiment)

This router has complex dependencies on ResearchQuestionService which requires
PostgreSQL. Full testing is better in integration tests. These tests focus on
model validation and basic endpoint existence.
"""

import pytest

from thoth.server.routers import research_questions


class TestRouterModule:
    """Tests for router module structure."""

    def test_router_exists(self):
        """Test router object exists."""
        assert research_questions.router is not None

    def test_router_has_routes(self):
        """Test router has defined routes."""
        assert len(research_questions.router.routes) > 0


class TestPydanticModels:
    """Tests for Pydantic model validation."""

    def test_research_question_create_requires_name(self):
        """Test ResearchQuestionCreate requires name."""
        from thoth.server.routers.research_questions import ResearchQuestionCreate

        with pytest.raises(Exception):  # Pydantic validation error
            ResearchQuestionCreate(selected_sources=['arxiv'])

    def test_research_question_create_validates_sources(self):
        """Test ResearchQuestionCreate validates selected_sources."""
        from thoth.server.routers.research_questions import ResearchQuestionCreate

        # Should require at least one source
        with pytest.raises(Exception):  # Pydantic validation error
            ResearchQuestionCreate(name='Test', keywords=['test'], selected_sources=[])
