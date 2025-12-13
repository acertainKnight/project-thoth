"""Unit tests for DiscoveryOrchestrator."""

import pytest
import asyncio
from datetime import datetime
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch, call

from thoth.services.discovery_orchestrator import DiscoveryOrchestrator
from thoth.utilities.schemas import ScrapedArticleMetadata
from thoth.config import Config


@pytest.fixture
def mock_config():
    """Create a mock Config object."""
    config = MagicMock(spec=Config)
    config.vault_root = '/tmp/test_vault'
    config.db_host = 'localhost'
    config.db_port = 5432
    config.db_name = 'test_thoth'
    config.db_user = 'test_user'
    config.db_password = 'test_password'
    return config


@pytest.fixture
def mock_llm_service():
    """Create a mock LLMService."""
    service = AsyncMock()
    service.generate_completion = MagicMock(return_value='{"score": 0.85, "matched_keywords": ["test"], "reasoning": "Highly relevant"}')
    return service


@pytest.fixture
def mock_discovery_manager():
    """Create a mock DiscoveryManager."""
    manager = MagicMock()
    return manager


@pytest.fixture
def mock_repositories():
    """Create mock repositories."""
    question_repo = AsyncMock()
    source_repo = AsyncMock()
    article_repo = AsyncMock()
    match_repo = AsyncMock()

    return {
        'question': question_repo,
        'source': source_repo,
        'article': article_repo,
        'match': match_repo,
    }


@pytest.fixture
def orchestrator(mock_config, mock_llm_service, mock_discovery_manager, mock_repositories):
    """Create a DiscoveryOrchestrator with mocked dependencies."""
    with patch('thoth.services.discovery_orchestrator.ResearchQuestionRepository'), \
         patch('thoth.services.discovery_orchestrator.AvailableSourceRepository'), \
         patch('thoth.services.discovery_orchestrator.ArticleRepository'), \
         patch('thoth.services.discovery_orchestrator.ArticleResearchMatchRepository'):

        orch = DiscoveryOrchestrator(
            config=mock_config,
            llm_service=mock_llm_service,
            discovery_manager=mock_discovery_manager,
        )

        # Replace repositories with mocks
        orch.question_repo = mock_repositories['question']
        orch.source_repo = mock_repositories['source']
        orch.article_repo = mock_repositories['article']
        orch.match_repo = mock_repositories['match']

        return orch


# ==================== Test: Source Resolution ====================


@pytest.mark.asyncio
async def test_resolve_sources_wildcard(orchestrator, mock_repositories):
    """Test resolving ['*'] to all active sources."""
    # Arrange
    mock_repositories['source'].list_all_source_names.return_value = [
        'arxiv', 'pubmed', 'crossref', 'openalex'
    ]

    # Act
    result = await orchestrator._resolve_sources(['*'])

    # Assert
    assert result == ['arxiv', 'pubmed', 'crossref', 'openalex']
    mock_repositories['source'].list_all_source_names.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_sources_specific_sources(orchestrator, mock_repositories):
    """Test resolving specific sources."""
    # Arrange
    mock_repositories['source'].list_all_source_names.return_value = [
        'arxiv', 'pubmed', 'crossref', 'openalex'
    ]

    # Act
    result = await orchestrator._resolve_sources(['arxiv', 'pubmed'])

    # Assert
    assert result == ['arxiv', 'pubmed']


@pytest.mark.asyncio
async def test_resolve_sources_invalid_source_filtered(orchestrator, mock_repositories):
    """Test that invalid sources are filtered out."""
    # Arrange
    mock_repositories['source'].list_all_source_names.return_value = [
        'arxiv', 'pubmed'
    ]

    # Act
    result = await orchestrator._resolve_sources(['arxiv', 'invalid_source', 'pubmed'])

    # Assert
    assert result == ['arxiv', 'pubmed']
    # 'invalid_source' should be filtered out


# ==================== Test: Parallel Source Querying ====================


@pytest.mark.asyncio
async def test_query_sources_parallel_success(orchestrator, mock_repositories):
    """Test parallel source querying with successful results."""
    # Arrange
    article1 = ScrapedArticleMetadata(
        title='Article 1',
        abstract='Abstract 1',
        authors=['Author 1'],
        source='arxiv',
        url='http://arxiv.org/1',
    )
    article2 = ScrapedArticleMetadata(
        title='Article 2',
        abstract='Abstract 2',
        authors=['Author 2'],
        source='pubmed',
        url='http://pubmed.org/2',
    )

    async def mock_query_single_source(source, max_articles):
        if source == 'arxiv':
            return [article1]
        elif source == 'pubmed':
            return [article2]
        return []

    orchestrator._query_single_source = mock_query_single_source

    # Act
    result = await orchestrator._query_sources_parallel(
        sources=['arxiv', 'pubmed'],
        max_articles=50,
    )

    # Assert
    assert len(result) == 2
    assert article1 in result
    assert article2 in result


@pytest.mark.asyncio
async def test_query_sources_parallel_with_errors(orchestrator, mock_repositories):
    """Test parallel querying handles errors gracefully."""
    # Arrange
    article1 = ScrapedArticleMetadata(
        title='Article 1',
        abstract='Abstract 1',
        authors=['Author 1'],
        source='arxiv',
        url='http://arxiv.org/1',
    )

    async def mock_query_single_source(source, max_articles):
        if source == 'arxiv':
            return [article1]
        elif source == 'pubmed':
            raise Exception("Source error")
        return []

    orchestrator._query_single_source = mock_query_single_source
    mock_repositories['source'].increment_error_count = AsyncMock()

    # Act
    result = await orchestrator._query_sources_parallel(
        sources=['arxiv', 'pubmed'],
        max_articles=50,
    )

    # Assert
    assert len(result) == 1
    assert article1 in result
    # Error count should be incremented for failed source
    mock_repositories['source'].increment_error_count.assert_called_once_with('pubmed')


# ==================== Test: LLM Relevance Scoring ====================


@pytest.mark.asyncio
async def test_calculate_relevance_score_high_relevance(orchestrator, mock_llm_service):
    """Test LLM relevance scoring for highly relevant article."""
    # Arrange
    article_meta = ScrapedArticleMetadata(
        title='Deep Learning for Computer Vision',
        abstract='A comprehensive study of neural networks for image recognition',
        authors=['Bengio', 'Hinton'],
        source='arxiv',
        url='http://arxiv.org/1',
    )

    question = {
        'name': 'Machine Learning Research',
        'keywords': ['deep learning', 'neural networks'],
        'topics': ['artificial intelligence'],
        'authors': ['Bengio'],
    }

    mock_llm_service.generate_completion.return_value = '''
    {
        "score": 0.95,
        "matched_keywords": ["deep learning", "neural networks"],
        "reasoning": "Article directly addresses deep learning with preferred author"
    }
    '''

    # Act
    result = await orchestrator._calculate_relevance_score(
        article_meta=article_meta,
        question=question,
    )

    # Assert
    assert result['score'] == 0.95
    assert 'deep learning' in result['matched_keywords']
    assert 'neural networks' in result['matched_keywords']
    mock_llm_service.generate_completion.assert_called_once()


@pytest.mark.asyncio
async def test_calculate_relevance_score_low_relevance(orchestrator, mock_llm_service):
    """Test LLM relevance scoring for low relevance article."""
    # Arrange
    article_meta = ScrapedArticleMetadata(
        title='Quantum Mechanics Foundations',
        abstract='Study of quantum physics principles',
        authors=['Einstein'],
        source='arxiv',
        url='http://arxiv.org/1',
    )

    question = {
        'name': 'Machine Learning Research',
        'keywords': ['deep learning', 'neural networks'],
        'topics': ['artificial intelligence'],
        'authors': [],
    }

    mock_llm_service.generate_completion.return_value = '''
    {
        "score": 0.1,
        "matched_keywords": [],
        "reasoning": "Article is about quantum physics, not machine learning"
    }
    '''

    # Act
    result = await orchestrator._calculate_relevance_score(
        article_meta=article_meta,
        question=question,
    )

    # Assert
    assert result['score'] == 0.1
    assert len(result['matched_keywords']) == 0


@pytest.mark.asyncio
async def test_calculate_relevance_score_error_handling(orchestrator, mock_llm_service):
    """Test that LLM scoring errors are handled gracefully."""
    # Arrange
    article_meta = ScrapedArticleMetadata(
        title='Test Article',
        abstract='Test abstract',
        authors=['Test Author'],
        source='arxiv',
        url='http://arxiv.org/1',
    )

    question = {
        'name': 'Test Question',
        'keywords': ['test'],
        'topics': [],
        'authors': [],
    }

    mock_llm_service.generate_completion.side_effect = Exception("LLM API error")

    # Act
    result = await orchestrator._calculate_relevance_score(
        article_meta=article_meta,
        question=question,
    )

    # Assert
    assert result['score'] == 0.0  # Error should return low score
    assert 'Error during scoring' in result['reasoning']


def test_parse_relevance_response_valid_json(orchestrator):
    """Test parsing valid JSON response."""
    # Arrange
    response = '''
    {
        "score": 0.75,
        "matched_keywords": ["keyword1", "keyword2"],
        "reasoning": "Good match"
    }
    '''

    # Act
    result = orchestrator._parse_relevance_response(response)

    # Assert
    assert result['score'] == 0.75
    assert result['matched_keywords'] == ["keyword1", "keyword2"]
    assert result['reasoning'] == "Good match"


def test_parse_relevance_response_with_markdown(orchestrator):
    """Test parsing JSON wrapped in markdown code blocks."""
    # Arrange
    response = '''```json
    {
        "score": 0.8,
        "matched_keywords": ["test"],
        "reasoning": "Relevant"
    }
    ```'''

    # Act
    result = orchestrator._parse_relevance_response(response)

    # Assert
    assert result['score'] == 0.8
    assert result['matched_keywords'] == ["test"]


def test_parse_relevance_response_score_clamping(orchestrator):
    """Test that scores outside [0.0, 1.0] are clamped."""
    # Arrange
    response_high = '{"score": 1.5, "matched_keywords": [], "reasoning": "Test"}'
    response_low = '{"score": -0.2, "matched_keywords": [], "reasoning": "Test"}'

    # Act
    result_high = orchestrator._parse_relevance_response(response_high)
    result_low = orchestrator._parse_relevance_response(response_low)

    # Assert
    assert result_high['score'] == 1.0
    assert result_low['score'] == 0.0


def test_parse_relevance_response_invalid_json(orchestrator):
    """Test parsing invalid JSON returns error result."""
    # Arrange
    response = 'This is not valid JSON'

    # Act
    result = orchestrator._parse_relevance_response(response)

    # Assert
    assert result['score'] == 0.0
    assert 'Failed to parse' in result['reasoning']


# ==================== Test: Article Processing & Matching ====================


@pytest.mark.asyncio
async def test_process_and_match_articles_success(orchestrator, mock_repositories, mock_llm_service):
    """Test article processing and matching workflow."""
    # Arrange
    article_id = uuid4()
    question_id = uuid4()
    question = {
        'id': question_id,
        'name': 'Test Question',
        'keywords': ['test'],
        'topics': [],
        'authors': [],
        'min_relevance_score': 0.5,
    }

    articles = [
        ScrapedArticleMetadata(
            title='Relevant Article',
            abstract='Test abstract',
            authors=['Test Author'],
            source='arxiv',
            url='http://arxiv.org/1',
        ),
    ]

    # Mock article creation
    mock_repositories['article'].get_or_create_article = AsyncMock(return_value=article_id)

    # Mock no existing match
    mock_repositories['match'].get_by_article_and_question = AsyncMock(return_value=None)

    # Mock LLM scoring
    mock_llm_service.generate_completion.return_value = '''
    {
        "score": 0.85,
        "matched_keywords": ["test"],
        "reasoning": "Highly relevant"
    }
    '''

    # Mock match creation
    match_id = uuid4()
    mock_repositories['match'].create_match = AsyncMock(return_value=match_id)

    # Act
    matched_count, processed_count = await orchestrator._process_and_match_articles(
        articles=articles,
        question=question,
    )

    # Assert
    assert processed_count == 1
    assert matched_count == 1
    mock_repositories['article'].get_or_create_article.assert_called_once()
    mock_repositories['match'].create_match.assert_called_once()


@pytest.mark.asyncio
async def test_process_and_match_articles_below_threshold(orchestrator, mock_repositories, mock_llm_service):
    """Test that articles below relevance threshold are not matched."""
    # Arrange
    article_id = uuid4()
    question_id = uuid4()
    question = {
        'id': question_id,
        'name': 'Test Question',
        'keywords': ['test'],
        'topics': [],
        'authors': [],
        'min_relevance_score': 0.7,
    }

    articles = [
        ScrapedArticleMetadata(
            title='Low Relevance Article',
            abstract='Not very relevant',
            authors=['Test Author'],
            source='arxiv',
            url='http://arxiv.org/1',
        ),
    ]

    mock_repositories['article'].get_or_create_article = AsyncMock(return_value=article_id)
    mock_repositories['match'].get_by_article_and_question = AsyncMock(return_value=None)

    # Mock LLM scoring below threshold
    mock_llm_service.generate_completion.return_value = '''
    {
        "score": 0.3,
        "matched_keywords": [],
        "reasoning": "Low relevance"
    }
    '''

    mock_repositories['match'].create_match = AsyncMock()

    # Act
    matched_count, processed_count = await orchestrator._process_and_match_articles(
        articles=articles,
        question=question,
    )

    # Assert
    assert processed_count == 1
    assert matched_count == 0
    # Match should not be created for low relevance
    mock_repositories['match'].create_match.assert_not_called()


@pytest.mark.asyncio
async def test_process_and_match_articles_skip_existing_match(orchestrator, mock_repositories):
    """Test that existing matches are skipped."""
    # Arrange
    article_id = uuid4()
    question_id = uuid4()
    question = {
        'id': question_id,
        'name': 'Test Question',
        'keywords': ['test'],
        'topics': [],
        'authors': [],
        'min_relevance_score': 0.5,
    }

    articles = [
        ScrapedArticleMetadata(
            title='Already Matched Article',
            abstract='Test abstract',
            authors=['Test Author'],
            source='arxiv',
            url='http://arxiv.org/1',
        ),
    ]

    mock_repositories['article'].get_or_create_article = AsyncMock(return_value=article_id)

    # Mock existing match
    mock_repositories['match'].get_by_article_and_question = AsyncMock(
        return_value={'id': uuid4(), 'relevance_score': 0.8}
    )

    mock_repositories['match'].create_match = AsyncMock()

    # Act
    matched_count, processed_count = await orchestrator._process_and_match_articles(
        articles=articles,
        question=question,
    )

    # Assert
    assert processed_count == 1
    assert matched_count == 0
    # Match creation should be skipped
    mock_repositories['match'].create_match.assert_not_called()


# ==================== Test: run_discovery_for_question ====================


@pytest.mark.asyncio
async def test_run_discovery_for_question_success(orchestrator, mock_repositories, mock_llm_service):
    """Test complete discovery workflow for a question."""
    # Arrange
    question_id = uuid4()
    article_id = uuid4()

    question = {
        'id': question_id,
        'name': 'Machine Learning Research',
        'keywords': ['deep learning'],
        'topics': ['AI'],
        'authors': [],
        'selected_sources': ['arxiv'],
        'max_articles_per_run': 50,
        'min_relevance_score': 0.5,
    }

    mock_repositories['question'].get_by_id.return_value = question
    mock_repositories['source'].list_all_source_names.return_value = ['arxiv', 'pubmed']

    # Mock article discovery
    article = ScrapedArticleMetadata(
        title='Deep Learning Article',
        abstract='About neural networks',
        authors=['Test Author'],
        source='arxiv',
        url='http://arxiv.org/1',
    )

    async def mock_query_single_source(source, max_articles):
        return [article] if source == 'arxiv' else []

    orchestrator._query_single_source = mock_query_single_source

    # Mock article and match creation
    mock_repositories['article'].get_or_create_article = AsyncMock(return_value=article_id)
    mock_repositories['match'].get_by_article_and_question = AsyncMock(return_value=None)
    mock_repositories['match'].create_match = AsyncMock(return_value=uuid4())

    # Mock LLM scoring
    mock_llm_service.generate_completion.return_value = '''
    {"score": 0.85, "matched_keywords": ["deep learning"], "reasoning": "Relevant"}
    '''

    mock_repositories['source'].update_statistics = AsyncMock()

    # Act
    result = await orchestrator.run_discovery_for_question(
        question_id=question_id,
        max_articles=None,
    )

    # Assert
    assert result['success'] is True
    assert result['question_id'] == str(question_id)
    assert result['articles_found'] == 1
    assert result['articles_matched'] == 1
    assert 'arxiv' in result['sources_queried']


@pytest.mark.asyncio
async def test_run_discovery_for_question_not_found(orchestrator, mock_repositories):
    """Test discovery for non-existent question."""
    # Arrange
    question_id = uuid4()
    mock_repositories['question'].get_by_id.return_value = None

    # Act
    result = await orchestrator.run_discovery_for_question(question_id=question_id)

    # Assert
    assert result['success'] is False
    assert 'not found' in result['error']


@pytest.mark.asyncio
async def test_run_discovery_for_question_no_sources(orchestrator, mock_repositories):
    """Test discovery when no sources are available."""
    # Arrange
    question_id = uuid4()
    question = {
        'id': question_id,
        'name': 'Test Question',
        'selected_sources': ['*'],
    }

    mock_repositories['question'].get_by_id.return_value = question
    mock_repositories['source'].list_all_source_names.return_value = []

    # Act
    result = await orchestrator.run_discovery_for_question(question_id=question_id)

    # Assert
    assert result['success'] is True
    assert result['articles_found'] == 0
    assert result['articles_matched'] == 0


# ==================== Test: run_discovery_batch ====================


@pytest.mark.asyncio
async def test_run_discovery_batch_success(orchestrator, mock_repositories):
    """Test batch discovery for multiple questions."""
    # Arrange
    question_ids = [uuid4(), uuid4(), uuid4()]

    # Mock individual discoveries
    async def mock_run_discovery(question_id):
        return {
            'success': True,
            'question_id': str(question_id),
            'articles_found': 10,
            'articles_processed': 8,
            'articles_matched': 5,
        }

    orchestrator.run_discovery_for_question = mock_run_discovery

    # Act
    result = await orchestrator.run_discovery_batch(question_ids=question_ids)

    # Assert
    assert result['success'] is True
    assert result['questions_processed'] == 3
    assert result['questions_successful'] == 3
    assert result['questions_failed'] == 0
    assert result['total_articles_found'] == 30  # 10 * 3
    assert result['total_articles_matched'] == 15  # 5 * 3


@pytest.mark.asyncio
async def test_run_discovery_batch_with_failures(orchestrator, mock_repositories):
    """Test batch discovery handles individual failures."""
    # Arrange
    question_ids = [uuid4(), uuid4(), uuid4()]

    # Mock mixed success/failure
    call_count = [0]

    async def mock_run_discovery(question_id):
        call_count[0] += 1
        if call_count[0] == 2:
            return {'success': False, 'error': 'Test error'}
        return {
            'success': True,
            'question_id': str(question_id),
            'articles_found': 10,
            'articles_processed': 8,
            'articles_matched': 5,
        }

    orchestrator.run_discovery_for_question = mock_run_discovery

    # Act
    result = await orchestrator.run_discovery_batch(question_ids=question_ids)

    # Assert
    assert result['success'] is True
    assert result['questions_processed'] == 3
    assert result['questions_successful'] == 2
    assert result['questions_failed'] == 1
    assert result['total_articles_found'] == 20  # 10 * 2


# ==================== Test: Prompt Building ====================


def test_build_relevance_prompt_complete(orchestrator):
    """Test building relevance prompt with all fields."""
    # Act
    prompt = orchestrator._build_relevance_prompt(
        article_title='Deep Learning for Image Recognition',
        article_abstract='A study of convolutional neural networks',
        article_authors=['LeCun', 'Bengio'],
        question_name='Machine Learning Research',
        keywords=['deep learning', 'neural networks'],
        topics=['computer vision', 'AI'],
        preferred_authors=['Bengio', 'Hinton'],
    )

    # Assert
    assert 'Deep Learning for Image Recognition' in prompt
    assert 'convolutional neural networks' in prompt
    assert 'LeCun' in prompt
    assert 'Bengio' in prompt
    assert 'Machine Learning Research' in prompt
    assert 'deep learning' in prompt
    assert 'computer vision' in prompt
    assert 'JSON' in prompt  # Should ask for JSON output


def test_build_relevance_prompt_minimal(orchestrator):
    """Test building prompt with minimal fields."""
    # Act
    prompt = orchestrator._build_relevance_prompt(
        article_title='Test Article',
        article_abstract='No abstract available',
        article_authors=[],
        question_name='Test Question',
        keywords=[],
        topics=[],
        preferred_authors=[],
    )

    # Assert
    assert 'Test Article' in prompt
    assert 'Test Question' in prompt
    assert 'None specified' in prompt  # For empty lists
