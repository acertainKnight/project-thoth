"""Pydantic schemas for browser-based discovery workflows.

This module defines the data models for browser automation workflows that enable
parameterized article discovery from websites requiring authentication or lacking APIs.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class SelectorStrategy(str, Enum):
    """Selector strategy types for locating elements."""

    CSS = 'css'
    XPATH = 'xpath'
    TEXT = 'text'
    ID = 'id'
    CLASS = 'class'
    ATTRIBUTE = 'attribute'


class ElementSelector(BaseModel):
    """Multi-strategy selector for robust element identification.

    Uses multiple selector strategies with fallback to handle dynamic page changes.

    Example:
        >>> selector = ElementSelector(
        ...     css='input#search-box',
        ...     xpath='//input[@id="search-box"]',
        ...     text='Search articles',
        ...     priority=['css', 'xpath', 'text']
        ... )
    """

    css: str | None = Field(
        default=None, description='CSS selector (e.g., "input#search-box")'
    )
    xpath: str | None = Field(
        default=None, description='XPath selector (e.g., "//input[@id=\'search-box\']")'
    )
    text: str | None = Field(
        default=None, description='Text content to match (e.g., "Search articles")'
    )
    id: str | None = Field(
        default=None, description='Element ID attribute (e.g., "search-box")'
    )
    class_name: str | None = Field(
        default=None, description='CSS class name (e.g., "search-input")'
    )
    attribute: dict[str, str] | None = Field(
        default=None,
        description='Attribute selector (e.g., {"data-testid": "search-input"})',
    )
    priority: list[SelectorStrategy] = Field(
        default_factory=lambda: [
            SelectorStrategy.CSS,
            SelectorStrategy.XPATH,
            SelectorStrategy.TEXT,
        ],
        description='Order to try selectors (first successful match is used)',
    )
    description: str | None = Field(
        default=None, description='Human-readable description of the element'
    )

    @field_validator('priority')
    def validate_priority(
        cls, priority: list[SelectorStrategy]
    ) -> list[SelectorStrategy]:  # noqa: N805
        """Ensure priority list contains at least one strategy."""
        if not priority:
            return [SelectorStrategy.CSS, SelectorStrategy.XPATH, SelectorStrategy.TEXT]
        return priority


class ActionType(str, Enum):
    """Browser action types."""

    NAVIGATE = 'navigate'
    CLICK = 'click'
    TYPE = 'type'
    SELECT = 'select'
    WAIT = 'wait'
    SCROLL = 'scroll'
    SCREENSHOT = 'screenshot'
    EXTRACT = 'extract'


class WaitCondition(str, Enum):
    """Wait conditions for browser actions."""

    LOAD = 'load'
    DOMCONTENTLOADED = 'domcontentloaded'
    NETWORKIDLE = 'networkidle'
    ELEMENT_VISIBLE = 'element_visible'
    ELEMENT_HIDDEN = 'element_hidden'
    TIMEOUT = 'timeout'


class WorkflowAction(BaseModel):
    """Individual action step in a browser workflow.

    Represents a single operation in the recorded workflow sequence.

    Example:
        >>> action = WorkflowAction(
        ...     step_number=1,
        ...     action_type=ActionType.TYPE,
        ...     target_selector=ElementSelector(css='input#search-box'),
        ...     action_value='neural pathways',
        ...     is_parameterized=True,
        ...     parameter_name='keywords'
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description='Unique action identifier')
    workflow_id: UUID | None = Field(
        default=None, description='Parent workflow identifier'
    )
    step_number: int = Field(description='Execution order in workflow (0-indexed)', ge=0)
    action_type: ActionType = Field(description='Type of browser action to perform')

    # Target element
    target_selector: ElementSelector | None = Field(
        default=None, description='Selector for target element'
    )
    target_description: str | None = Field(
        default=None,
        description='Human-readable description of target (e.g., "Search button")',
    )

    # Action parameters
    action_value: str | None = Field(
        default=None,
        description='Fixed value or placeholder for parameterized actions',
    )
    is_parameterized: bool = Field(
        default=False,
        description='If True, action_value receives value from execution parameters',
    )
    parameter_name: str | None = Field(
        default=None,
        description='Parameter key to inject (e.g., "keywords", "date_range")',
    )

    # Wait conditions
    wait_condition: WaitCondition | None = Field(
        default=None, description='Condition to wait for after action'
    )
    wait_timeout_ms: int = Field(
        default=30000, description='Maximum wait time in milliseconds', ge=0
    )

    # Error handling
    retry_on_failure: bool = Field(
        default=True, description='Retry action if it fails'
    )
    max_retries: int = Field(default=3, description='Maximum retry attempts', ge=0)
    continue_on_error: bool = Field(
        default=False, description='Continue workflow even if this action fails'
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description='Action creation timestamp'
    )


class SearchType(str, Enum):
    """Search interface types."""

    SIMPLE = 'simple'  # Single search box + filters
    ADVANCED = 'advanced'  # Multi-field search form
    NONE = 'none'  # No search, browse latest articles


class FilterType(str, Enum):
    """Filter input types."""

    DROPDOWN = 'dropdown'
    DATE_INPUT = 'date_input'
    DATE_RANGE = 'date_range'
    CHECKBOX = 'checkbox'
    RADIO = 'radio'
    TEXT_INPUT = 'text_input'


class KeywordsFormat(str, Enum):
    """Format for combining multiple keywords."""

    SPACE_SEPARATED = 'space_separated'  # "neural pathways decision making"
    COMMA_SEPARATED = 'comma_separated'  # "neural, pathways, decision making"
    BOOLEAN_AND = 'boolean_and'  # "neural AND pathways AND decision AND making"
    BOOLEAN_OR = 'boolean_or'  # "neural OR pathways OR decision OR making"


class SearchFilter(BaseModel):
    """Configuration for a search filter element.

    Example:
        >>> filter_config = SearchFilter(
        ...     name='date_range',
        ...     filter_type=FilterType.DROPDOWN,
        ...     selector=ElementSelector(css='select#date-filter'),
        ...     parameter_name='date_range',
        ...     options={
        ...         'last_24h': 'Last 24 hours',
        ...         'last_7d': 'Last 7 days',
        ...         'last_30d': 'Last 30 days'
        ...     }
        ... )
    """

    name: str = Field(description='Filter identifier (e.g., "date_range", "subject")')
    filter_type: FilterType = Field(description='Type of filter input')
    selector: ElementSelector = Field(description='Selector for filter element')
    parameter_name: str = Field(
        description='Parameter key to receive value (e.g., "date_range")'
    )
    options: dict[str, str] | None = Field(
        default=None,
        description='Available options for dropdowns (key=value_to_select, value=display_text)',
    )
    optional: bool = Field(
        default=False, description='If True, filter can be omitted from parameters'
    )
    default_value: str | None = Field(
        default=None, description='Default value if parameter not provided'
    )
    date_format: str | None = Field(
        default=None,
        description='Date format string for date inputs (e.g., "MM/DD/YYYY")',
    )
    description: str | None = Field(
        default=None, description='Human-readable description'
    )


class WorkflowSearchConfig(BaseModel):
    """Search and filter configuration for a workflow.

    Defines how query parameters are injected into the website's search interface.

    Example:
        >>> search_config = WorkflowSearchConfig(
        ...     workflow_id=uuid4(),
        ...     search_type=SearchType.SIMPLE,
        ...     search_input_selector=ElementSelector(css='input#search-box'),
        ...     search_button_selector=ElementSelector(css='button#search-btn'),
        ...     keywords_format=KeywordsFormat.SPACE_SEPARATED,
        ...     filters=[
        ...         SearchFilter(
        ...             name='date_range',
        ...             filter_type=FilterType.DROPDOWN,
        ...             selector=ElementSelector(css='select#date'),
        ...             parameter_name='date_range'
        ...         )
        ...     ]
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description='Unique configuration identifier')
    workflow_id: UUID = Field(description='Parent workflow identifier')

    # Search type
    search_type: SearchType = Field(
        description='Type of search interface (simple, advanced, or none)'
    )

    # Simple/Advanced search configuration
    search_input_selector: ElementSelector | None = Field(
        default=None, description='Selector for main search input (simple search)'
    )
    search_button_selector: ElementSelector | None = Field(
        default=None, description='Selector for search submit button'
    )
    keywords_format: KeywordsFormat = Field(
        default=KeywordsFormat.SPACE_SEPARATED,
        description='How to combine multiple keywords',
    )

    # Filters
    filters: list[SearchFilter] = Field(
        default_factory=list, description='Search filters (date, subject, etc.)'
    )

    # Advanced search configuration
    advanced_fields: dict[str, ElementSelector] | None = Field(
        default=None,
        description='Multiple input fields for advanced search forms (field_name -> selector)',
    )

    # Browse configuration (for search_type=none)
    browse_start_url: str | None = Field(
        default=None, description='URL to start browsing (if no search)'
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description='Configuration creation timestamp'
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description='Last update timestamp'
    )


class HealthStatus(str, Enum):
    """Workflow health status."""

    UNKNOWN = 'unknown'
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    FAILING = 'failing'


class CredentialType(str, Enum):
    """Authentication credential types."""

    USERNAME_PASSWORD = 'username_password'
    OAUTH = 'oauth'
    API_KEY = 'api_key'
    SESSION_COOKIE = 'session_cookie'


class WorkflowCredentials(BaseModel):
    """Metadata for encrypted workflow credentials.

    NOTE: This model stores METADATA about credentials, NOT the encrypted data itself.
    Actual encrypted credentials are stored separately in the database.

    Example:
        >>> creds = WorkflowCredentials(
        ...     workflow_id=uuid4(),
        ...     credential_type=CredentialType.USERNAME_PASSWORD,
        ...     encryption_algorithm='fernet',
        ...     session_valid_until=datetime(2025, 12, 27)
        ... )
    """

    id: UUID = Field(
        default_factory=uuid4, description='Unique credential record identifier'
    )
    workflow_id: UUID = Field(description='Parent workflow identifier')

    # Credential type
    credential_type: CredentialType = Field(
        description='Type of authentication credentials'
    )

    # Encryption metadata
    encryption_algorithm: str = Field(
        default='fernet', description='Encryption algorithm used'
    )

    # Session management
    session_valid_until: datetime | None = Field(
        default=None, description='Session expiry timestamp'
    )
    session_storage_state: dict[str, Any] | None = Field(
        default=None,
        description='Playwright storage state (cookies, localStorage) - JSON serialized',
    )

    # Audit
    last_used_at: datetime | None = Field(
        default=None, description='Last time credentials were accessed'
    )
    access_log: list[dict[str, Any]] = Field(
        default_factory=list, description='Audit trail of credential access'
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description='Credential creation timestamp'
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description='Last update timestamp'
    )


class ExecutionStatus(str, Enum):
    """Workflow execution status."""

    PENDING = 'pending'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class ExecutionTrigger(str, Enum):
    """What triggered the workflow execution."""

    SCHEDULE = 'schedule'  # Scheduled by discovery orchestrator
    MANUAL = 'manual'  # User-initiated
    QUERY = 'query'  # Triggered by specific research question


class WorkflowExecution(BaseModel):
    """Log entry for a workflow execution.

    Records the complete execution history including parameters, results, and errors.

    Example:
        >>> execution = WorkflowExecution(
        ...     workflow_id=uuid4(),
        ...     status=ExecutionStatus.SUCCESS,
        ...     execution_parameters={
        ...         'keywords': ['neural', 'pathways'],
        ...         'date_range': 'last_24h'
        ...     },
        ...     articles_extracted=42,
        ...     triggered_by=ExecutionTrigger.QUERY,
        ...     triggered_by_query_id=uuid4()
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description='Unique execution identifier')
    workflow_id: UUID = Field(description='Parent workflow identifier')

    # Execution details
    status: ExecutionStatus = Field(description='Current execution status')
    started_at: datetime = Field(
        default_factory=datetime.utcnow, description='Execution start timestamp'
    )
    completed_at: datetime | None = Field(
        default=None, description='Execution completion timestamp'
    )
    duration_ms: int | None = Field(
        default=None, description='Total execution time in milliseconds', ge=0
    )

    # Parameters used
    execution_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description='Parameters injected into workflow (keywords, filters, etc.)',
    )

    # Results
    articles_extracted: int = Field(
        default=0, description='Number of articles successfully extracted', ge=0
    )
    pages_visited: int = Field(
        default=0, description='Number of pages visited during execution', ge=0
    )

    # Error information
    error_message: str | None = Field(
        default=None, description='Error message if execution failed'
    )
    error_step_number: int | None = Field(
        default=None,
        description='Step number where error occurred (if applicable)',
        ge=0,
    )
    error_screenshot_url: str | None = Field(
        default=None, description='URL to screenshot at time of error'
    )

    # Execution metadata
    execution_log: list[dict[str, Any]] = Field(
        default_factory=list,
        description='Detailed log of actions performed during execution',
    )
    browser_console_logs: list[dict[str, Any]] = Field(
        default_factory=list, description='Browser console output during execution'
    )

    # Trigger information
    triggered_by: ExecutionTrigger = Field(
        description='What triggered this execution'
    )
    triggered_by_query_id: UUID | None = Field(
        default=None,
        description='Research question ID if triggered by query',
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description='Execution record creation timestamp'
    )


class ExecutionParameters(BaseModel):
    """Parameters passed to workflow execution.

    These parameters are injected into the workflow's search fields and filters.

    Example:
        >>> params = ExecutionParameters(
        ...     keywords=['neural', 'pathways', 'decision making'],
        ...     date_range='last_24h',
        ...     subject='neuroscience',
        ...     max_articles=50
        ... )
    """

    keywords: list[str] = Field(
        default_factory=list,
        description='Search keywords to inject into search input',
    )
    date_range: str | None = Field(
        default=None,
        description='Date range filter value (e.g., "last_24h", "last_7d")',
    )
    date_from: str | None = Field(
        default=None, description='Start date for custom date range (ISO format)'
    )
    date_to: str | None = Field(
        default=None, description='End date for custom date range (ISO format)'
    )
    subject: str | None = Field(
        default=None, description='Subject/category filter value'
    )
    custom_filters: dict[str, Any] = Field(
        default_factory=dict,
        description='Additional custom filter values (filter_name -> value)',
    )
    max_articles: int | None = Field(
        default=None, description='Maximum articles to extract', ge=1
    )


class BrowserWorkflow(BaseModel):
    """Main browser workflow configuration.

    Represents a complete parameterized workflow for article discovery from a website.

    Example:
        >>> workflow = BrowserWorkflow(
        ...     name='nature_journal',
        ...     description='Nature journal article discovery',
        ...     website_domain='nature.com',
        ...     start_url='https://www.nature.com/search',
        ...     requires_authentication=True,
        ...     authentication_type='username_password',
        ...     extraction_rules={
        ...         'title': {'css': 'h3.article-title'},
        ...         'authors': {'css': 'span.author-name'},
        ...         'abstract': {'css': 'div.abstract-content'}
        ...     }
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description='Unique workflow identifier')

    # Basic information
    name: str = Field(
        description='Unique workflow name (e.g., "nature_journal", "ieee_xplore")'
    )
    description: str | None = Field(
        default=None, description='Human-readable description of workflow purpose'
    )
    website_domain: str = Field(
        description='Domain of target website (e.g., "nature.com")'
    )

    # Access configuration
    start_url: str = Field(description='Starting URL for workflow execution')
    requires_authentication: bool = Field(
        default=False, description='Whether site requires login'
    )
    authentication_type: str | None = Field(
        default=None,
        description='Type of authentication (username_password, oauth, etc.)',
    )

    # Extraction configuration
    extraction_rules: dict[str, Any] = Field(
        description='Rules for extracting article metadata (title, authors, abstract, etc.)'
    )
    pagination_config: dict[str, Any] | None = Field(
        default=None,
        description='Configuration for handling multi-page results',
    )

    # Execution settings
    max_articles_per_run: int = Field(
        default=100, description='Maximum articles to extract per execution', ge=1
    )
    timeout_seconds: int = Field(
        default=60, description='Maximum time for workflow execution', ge=1
    )

    # Status & statistics
    is_active: bool = Field(default=True, description='Whether workflow is enabled')
    health_status: HealthStatus = Field(
        default=HealthStatus.UNKNOWN, description='Current health status'
    )
    total_executions: int = Field(
        default=0, description='Total number of executions', ge=0
    )
    successful_executions: int = Field(
        default=0, description='Number of successful executions', ge=0
    )
    failed_executions: int = Field(
        default=0, description='Number of failed executions', ge=0
    )
    total_articles_extracted: int = Field(
        default=0, description='Total articles extracted across all executions', ge=0
    )
    average_execution_time_ms: int | None = Field(
        default=None, description='Average execution time in milliseconds', ge=0
    )

    # Timing
    last_executed_at: datetime | None = Field(
        default=None, description='Last execution timestamp'
    )
    last_success_at: datetime | None = Field(
        default=None, description='Last successful execution timestamp'
    )
    last_failure_at: datetime | None = Field(
        default=None, description='Last failed execution timestamp'
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description='Workflow creation timestamp'
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description='Last update timestamp'
    )

    @field_validator('name')
    def validate_name(cls, name: str) -> str:  # noqa: N805
        """Normalize workflow name to valid identifier."""
        import re

        return re.sub(r'[^\w\-_.]', '_', name.lower())


# Create/Update schemas for API endpoints
class BrowserWorkflowCreate(BaseModel):
    """Schema for creating a new browser workflow."""

    name: str = Field(description='Unique workflow name')
    description: str | None = Field(default=None)
    website_domain: str
    start_url: str
    requires_authentication: bool = Field(default=False)
    authentication_type: str | None = Field(default=None)
    extraction_rules: dict[str, Any]
    pagination_config: dict[str, Any] | None = Field(default=None)
    max_articles_per_run: int = Field(default=100)
    timeout_seconds: int = Field(default=60)


class BrowserWorkflowUpdate(BaseModel):
    """Schema for updating an existing browser workflow."""

    name: str | None = Field(default=None)
    description: str | None = Field(default=None)
    website_domain: str | None = Field(default=None)
    start_url: str | None = Field(default=None)
    requires_authentication: bool | None = Field(default=None)
    authentication_type: str | None = Field(default=None)
    extraction_rules: dict[str, Any] | None = Field(default=None)
    pagination_config: dict[str, Any] | None = Field(default=None)
    max_articles_per_run: int | None = Field(default=None)
    timeout_seconds: int | None = Field(default=None)
    is_active: bool | None = Field(default=None)
