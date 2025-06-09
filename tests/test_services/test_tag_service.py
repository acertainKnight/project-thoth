"""
Tests for TagService.
"""

from unittest.mock import MagicMock

import pytest

from thoth.services.base import ServiceError
from thoth.services.llm_service import LLMService
from thoth.services.tag_service import TagService


@pytest.fixture
def mock_citation_tracker():
    """Create a mock citation tracker."""
    return MagicMock()


def test_tag_service_initialization(thoth_config, mock_citation_tracker):
    """Test that TagService can be initialized."""
    llm_service = LLMService(config=thoth_config)
    service = TagService(
        config=thoth_config,
        llm_service=llm_service,
        citation_tracker=mock_citation_tracker,
    )
    assert service is not None
    assert service.llm_service is not None
    assert service.citation_tracker is not None


def test_consolidate_and_retag_all_no_tracker(thoth_config):
    """Test that consolidate_and_retag_all raises an error if no citation
    tracker is set."""
    llm_service = LLMService(config=thoth_config)
    service = TagService(
        config=thoth_config, llm_service=llm_service, citation_tracker=None
    )
    with pytest.raises(ServiceError, match='Citation tracker not available'):
        service.consolidate_and_retag_all()
