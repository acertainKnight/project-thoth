# Thoth AI Research Agent – Comprehensive Project Plan

## 1. Overview

Thoth is an autonomous Python-based system that searches academic repositories (initially ArXiv, with future support for PubMed, Springer, etc.) for research papers matching a user's natural language query. Thoth downloads PDFs, uses an OCR engine (default: Mistral OCR) to convert them into Markdown, and then processes that Markdown with LLMs to generate detailed Obsidian-ready notes. These notes include:

- Article metadata (title, authors, abstract)
- Detailed bullet-point summaries (methodology, findings)
- Auto-generated tags based on LLM analysis
- A formatted table of citations rendered as wikilinks
- Backlinks generated from a citation knowledge graph stored in Neo4j

Thoth supports both an autonomous periodic search and an interactive conversational interface (via LangChain/LangGraph). Furthermore, Obsidian integration is built so that clicking a custom URI or wikilink in a note triggers re-processing of that article.

## 2. System Architecture

Thoth's architecture is divided into two layers: the Core Processing Pipeline and the Enhanced Modules for future features. The following outlines the key components:

### 2.1. Core Processing Pipeline

#### User Interface & Conversational Agent

- **ConversationalAgent**: Uses LangChain/LangGraph to refine natural language queries.
- **Input Options**: CLI interface.

#### Search & Retrieval

- **RepositorySearcherInterface**: A common interface for all repository searchers, supporting both API-based and web-crawling approaches.
- **SearchManager**: Aggregates results from all added repository searchers and coordinates the evaluation process.
- **ArticleEvaluator**: Evaluates article relevance based on title and abstract before downloading.
- **SearchSourceFactory**: Creates appropriate searcher instances based on repository type and available access methods.

##### API-Based Searchers:
- **ArxivSearcher**: Queries the ArXiv API with boolean filters and advanced query parameters.
- **PubMedSearcher**: Interfaces with the PubMed API for medical and biological research papers.
- **SpringerSearcher**: Connects to Springer's API for accessing their journal articles.
- **ScienceDirectSearcher**: Interfaces with Elsevier's ScienceDirect API.

##### Web Crawler-Based Searchers:
- **GoogleScholarCrawler**: Extracts research paper information from Google Scholar search results.
- **SemanticScholarCrawler**: Crawls Semantic Scholar for research papers.
- **ResearchGateCrawler**: Navigates ResearchGate to find relevant papers.
- **UniversityRepositoryCrawler**: Configurable crawler for university repositories.

#### PDF Management

- **PDFAccessManager**: Coordinates access to PDFs from various sources using appropriate strategies.
- **PDFDownloader**: Downloads PDFs to a designated folder using the appropriate access method.
- **FileMonitor**: Monitors the PDF folder and triggers processing when a new PDF is detected.

##### PDF Access Strategies:
- **DirectDownloadStrategy**: For repositories that allow direct PDF downloads via URL.
- **AuthenticatedDownloadStrategy**: Handles downloads requiring authentication (e.g., institutional access).
- **BrowserEmulationStrategy**: Uses headless browser automation for sources requiring complex navigation.

#### OCR & Markdown Generation

- **OCRManager**: Calls the Mistral OCR API (or alternative engines) to convert PDFs to Markdown.
*Note*: Once a Markdown file is generated, it serves as the single source for all subsequent LLM processing.

#### Prompt Management

- **PromptManager**: Centralized system for managing LLM prompts using Jinja templates.
- **TemplateRenderer**: Renders Jinja templates with context-specific variables for all LLM operations.

#### LLM Processing

- **QueryProcessor**: Refines user queries using templates from PromptManager.
- **ArticleEvaluator**: Evaluates article relevance based on title and abstract before downloading.
- **AbstractEvaluator**: Uses the full Markdown to perform in-depth evaluation of article relevance.
- **Summarizer**: Produces bullet-point summaries from the Markdown text.
- **TagGenerator**: Extracts topics to auto-generate tags.

##### Evaluation Strategies:
- **PreDownloadEvaluation**: Quick evaluation based on title, abstract, and metadata to determine if a paper should be downloaded.
- **PostDownloadEvaluation**: In-depth evaluation of the full paper content to determine relevance for note generation.
- **UserInterestModeling**: Builds and maintains a model of user interests to improve relevance scoring over time.
- **CitationNetworkAnalysis**: Evaluates papers based on their position in the citation network.

#### Note Generation (Obsidian Formatter)

- **ObsidianFormatter**: Combines metadata, summaries, citation tables, and tags into a final Markdown note formatted for Obsidian.
Wikilinks in notes follow a custom URI scheme (e.g., `thoth://trigger?article_id=...`).

#### Citation & Backlink Management

- **CitationExtractor**: Extracts citation details from the Markdown.
- **BacklinkManager**: Integrates with the graph database to manage wikilinks and citation relationships.

#### Knowledge Graph with Neo4j

- **GraphManager**: Uses Neo4j to store article nodes and citation relationships, facilitating backlink queries and network visualization.

#### Automation & Scheduling

- **Scheduler**: Manages periodic searches and event-driven triggers (e.g., new PDF, citation link click).

### 2.2. Enhanced Modules (Future Enhancements)

#### Multi-Repository Support:

- Implement additional repository searchers (e.g., `PubMedSearcher`, `SpringerSearcher`) following the `RepositorySearcherInterface`.
- The unified `SearchManager` aggregates and deduplicates results from all repositories.

#### Advanced Knowledge Graph:

- The `GraphManager` module integrates with Neo4j to support complex citation queries, backlink generation, and potential network visualization.

#### Obsidian Integration:

- Wikilinks in the Markdown notes follow a custom URI scheme to trigger Thoth via a helper script when clicked from Obsidian.

## 3. File Structure & Directory Layout

Below is an example directory structure encompassing all modules and future enhancements:

```
thoth/
├── main.py                     # Core processing entry point
├── config.py                   # Configuration (API keys, Neo4j settings, OCR settings, scheduling)
├── requirements.txt            # Dependencies (LangChain, LangGraph, neo4j-driver, requests, watchdog, etc.)
├── README.md                   # Project documentation and setup instructions
├── logs/
│   └── thoth.log
├── data/
│   ├── pdfs/                   # Folder for downloaded PDFs
│   ├── markdown/               # Folder for OCR-generated and processed Markdown notes
│   └── neo4j/                  # (Optional) Backup or local storage for Neo4j database files
├── templates/                  # Jinja templates for LLM prompts
│   ├── query_processor/
│   │   ├── refine_query.j2     # Template for refining user queries
│   ├── abstract_evaluator/
│   │   ├── relevance_score.j2  # Template for evaluating relevance
│   ├── summarizer/
│   │   ├── detailed_summary.j2 # Template for generating summaries
│   ├── tag_generator/
│   │   ├── extract_tags.j2     # Template for generating tags
│   └── citation_extractor/
│       ├── extract_citations.j2 # Template for extracting citations
├── modules/
│   ├── __init__.py
│   ├── search/
│   │   ├── __init__.py
│   │   ├── repository_searcher_interface.py  # Defines the search interface
│   │   ├── arxiv_searcher.py
│   │   ├── pubmed_searcher.py    # Future module
│   │   └── springer_searcher.py  # Future module
│   ├── pdf/
│   │   ├── __init__.py
│   │   ├── pdf_downloader.py
│   │   └── pdf_monitor.py
│   ├── ocr/
│   │   ├── __init__.py
│   │   └── ocr_manager.py      # Handles OCR (Mistral OCR API)
│   ├── prompt/
│   │   ├── __init__.py
│   │   ├── prompt_manager.py   # Manages and loads Jinja templates
│   │   └── template_renderer.py # Renders templates with variables
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── llm_provider.py     # Handles LLM API calls with consistent interface
│   │   ├── query_processor.py  # Processes and refines user queries
│   │   ├── abstract_evaluator.py  # Evaluates article relevance from Markdown
│   │   ├── summarizer.py       # Generates bullet-point summaries from Markdown
│   │   └── tag_generator.py    # Extracts topics and generates tags from Markdown
│   ├── markdown/
│   │   ├── __init__.py
│   │   └── obsidian_formatter.py   # Creates Obsidian-friendly Markdown notes
│   ├── citation/
│   │   ├── __init__.py
│   │   ├── citation_extractor.py   # Extracts citation details from Markdown
│   │   └── backlink_manager.py     # Manages wikilinks and updates Neo4j via GraphManager
│   ├── graph/
│   │   ├── __init__.py
│   │   └── graph_manager.py       # Manages the Neo4j database for citation graph
│   ├── agent/
│   │   ├── __init__.py
│   │   └── conversational_agent.py  # Conversational agent using LangChain/LangGraph
│   └── scheduler/
│       ├── __init__.py
│       └── scheduler.py        # Handles periodic and event-driven tasks
└── tests/
    ├── __init__.py
    ├── test_arxiv_searcher.py
    ├── test_pdf_downloader.py
    ├── test_ocr_manager.py
    ├── test_prompt_manager.py  # Tests for prompt management
    ├── test_obsidian_formatter.py
    └── test_graph_manager.py      # Tests for Neo4j integration
```

## 4. Module & Class Outlines

### 4.1. RepositorySearcherInterface (modules/search/repository_searcher_interface.py)

**Purpose**: Define standard methods for all repository searchers, supporting both API-based and web-crawling approaches.

**Methods (abstract)**:
- `search(query: str, filters: dict) -> List[Article]`
- `parse_response(response: Any) -> List[Article]`
- `get_access_method() -> str`
- `supports_direct_download() -> bool`
- `get_authentication_requirements() -> dict`

### 4.2. SearchSourceFactory (modules/search/search_source_factory.py)

**Class**: SearchSourceFactory

**Purpose**: Creates appropriate searcher instances based on repository type and available access methods.

**Methods**:
- `create_searcher(repository_type: str, config: dict) -> RepositorySearcherInterface`
- `register_searcher(repository_type: str, searcher_class: Type[RepositorySearcherInterface])`
- `get_available_searchers() -> List[str]`

### 4.3. ArticleEvaluator (modules/llm/article_evaluator.py)

**Class**: ArticleEvaluator

**Attributes**:
- `llm_provider`: LLMProvider
- `user_interest_model`: Optional[UserInterestModel]

**Methods**:
- `evaluate_pre_download(title: str, abstract: str, metadata: dict) -> float`
  - Uses template "article_evaluator/pre_download_evaluation.j2"
- `evaluate_post_download(markdown_path: str) -> float`
  - Uses template "article_evaluator/post_download_evaluation.j2"
- `update_user_interest_model(article: Article, user_feedback: float)`

### 4.4. ArxivSearcher (modules/search/api_searchers/arxiv_searcher.py)

**Class**: ArxivSearcher

**Attributes**:
- `base_url`: API endpoint
- `query_params`: Dictionary for query parameters

**Methods**:
- `search(query: str, filters: dict = {}) -> List[Article]`
- `parse_response(response: Any) -> List[Article]`

**Article Object**: Contains attributes such as title, abstract, pdf_url, authors, and a relevance_score.

### 4.5. SearchManager (modules/search/search_manager.py)

**Class**: SearchManager

**Attributes**:
- `searchers`: List[RepositorySearcherInterface]

**Methods**:
- `add_searcher(searcher: RepositorySearcherInterface)`
- `search_all(query: str, filters: dict) -> List[Article]`
  - Aggregates, deduplicates, and ranks search results from all repository searchers.

### 4.6. PDF Management Modules

#### PDFAccessManager (modules/pdf/pdf_access_manager.py)
**Class**: PDFAccessManager

**Attributes**:
- `strategies`: Dict[str, Type[AccessStrategy]]
- `config`: Dict[str, Any]

**Methods**:
- `get_access_strategy(article: Article) -> AccessStrategy`
  - Determines the appropriate access strategy based on the article source and metadata.
- `register_strategy(strategy_name: str, strategy_class: Type[AccessStrategy])`
  - Registers a new access strategy for use.
- `configure_strategy(strategy_name: str, config: dict)`
  - Updates configuration for a specific strategy.

#### AccessStrategy (modules/pdf/access_strategies/access_strategy.py)
**Class**: AccessStrategy (Abstract Base Class)

**Methods**:
- `download(article: Article, dest_folder: str) -> str`
  - Abstract method to be implemented by concrete strategies.
- `can_handle(article: Article) -> bool`
  - Determines if this strategy can handle the given article.
- `get_estimated_success_probability(article: Article) -> float`
  - Returns an estimate of how likely this strategy will succeed.

#### DirectDownloadStrategy (modules/pdf/access_strategies/direct_download_strategy.py)
**Class**: DirectDownloadStrategy (implements AccessStrategy)

**Methods**:
- `download(article: Article, dest_folder: str) -> str`
  - Downloads the PDF directly from the URL provided in the article metadata.
- `can_handle(article: Article) -> bool`
  - Returns True if the article has a direct download URL.

#### AuthenticatedDownloadStrategy (modules/pdf/access_strategies/authenticated_download_strategy.py)
**Class**: AuthenticatedDownloadStrategy (implements AccessStrategy)

**Attributes**:
- `credentials`: Dict[str, Dict[str, str]]
  - Dictionary mapping repository domains to credential information.

**Methods**:
- `download(article: Article, dest_folder: str) -> str`
  - Authenticates with the repository and downloads the PDF.
- `can_handle(article: Article) -> bool`
  - Returns True if credentials are available for the article's repository.

#### PDFDownloader (modules/pdf/pdf_downloader.py)
**Class**: PDFDownloader

**Attributes**:
- `access_manager`: PDFAccessManager
- `download_history`: Dict[str, Dict[str, Any]]
  - Tracks download attempts and results.

**Methods**:
- `download(article: Article, dest_folder: str) -> str`
  - Attempts to download the PDF using the appropriate access strategy.
  - Returns the path to the downloaded PDF if successful.
  - Raises DownloadError if all strategies fail.
- `retry_failed_download(article_id: str, dest_folder: str) -> str`
  - Attempts to download a previously failed article using alternative strategies.
- `get_download_statistics() -> Dict[str, Any]`
  - Returns statistics about download success rates by source and strategy.

#### FileMonitor (modules/pdf/pdf_monitor.py)
**Attributes**:
- `watch_folder`: str
- `callback`: Callable

**Methods**:
- `start()`
- `on_created(event: FileSystemEvent)`

### 4.7. OCRManager (modules/ocr/ocr_manager.py)

**Class**: OCRManager

**Methods**:
- `process_pdf(pdf_path: str) -> str`
  - Sends the PDF to the Mistral OCR API and saves the resulting Markdown to data/markdown/.

### 4.8. PromptManager (modules/prompt/prompt_manager.py)

**Class**: PromptManager

**Attributes**:
- `template_dir`: str (path to template directory, default: "templates/")
- `templates`: Dict[str, jinja2.Template] (cached templates)

**Methods**:
- `load_template(template_path: str) -> jinja2.Template`
  - Loads a Jinja template from the templates directory.
- `render_template(template_path: str, variables: dict) -> str`
  - Renders a template with the provided variables.
- `get_template_path(module_name: str, template_name: str) -> str`
  - Constructs a standardized path to a template.

### 4.9. TemplateRenderer (modules/prompt/template_renderer.py)

**Class**: TemplateRenderer

**Attributes**:
- `prompt_manager`: PromptManager

**Methods**:
- `render(module_name: str, template_name: str, variables: dict) -> str`
  - High-level method to render a template for a specific module.

### 4.10. LLMProvider (modules/llm/llm_provider.py)

**Class**: LLMProvider

**Attributes**:
- `api_key`: str (OpenRouter API key)
- `base_url`: str (default: "https://openrouter.ai/api/v1")
- `default_model`: str (default model to use)
- `template_renderer`: TemplateRenderer
- `session`: aiohttp.ClientSession (for async requests)

**Methods**:
- `async def __init__(self, api_key: str, default_model: str = "anthropic/claude-3-opus", template_renderer: TemplateRenderer | None = None) -> None`
  - Initializes the LLM provider with OpenRouter credentials and settings.

- `async def call_llm(self, messages: list[dict], **kwargs) -> dict`
  - Makes async API calls to OpenRouter with proper message formatting.
  - Parameters:
    - `messages`: List of message dicts with role and content
    - `model`: Optional model override
    - `temperature`: Optional temperature (0-2)
    - `max_tokens`: Optional max tokens
    - `stream`: Optional boolean for streaming
    - `tools`: Optional list of tool definitions
    - Other OpenRouter parameters as needed
  - Returns:
    - OpenRouter response with choices and usage stats

- `async def call_with_template(self, module_name: str, template_name: str, variables: dict, **llm_params) -> str`
  - High-level method that:
    1. Renders template using TemplateRenderer
    2. Constructs proper message format for OpenRouter
    3. Makes API call and processes response
  - Parameters:
    - `module_name`: Module requesting the call
    - `template_name`: Template to use
    - `variables`: Variables for template rendering
    - `**llm_params`: Additional OpenRouter parameters
  - Returns:
    - Processed response content

- `async def call_with_tools(self, messages: list[dict], tools: list[dict], **kwargs) -> dict`
  - Specialized method for tool-calling functionality
  - Handles the complete tool-calling flow:
    1. Send request with tools definition
    2. Get tool call suggestion from LLM
    3. Execute tool (via callback)
    4. Send tool result back to LLM
    5. Get final response
  - Parameters:
    - `messages`: Conversation history
    - `tools`: List of tool definitions in OpenRouter format
    - `tool_choice`: Optional tool choice parameter
    - Other OpenRouter parameters
  - Returns:
    - Final LLM response after tool execution

- `def _construct_request(self, messages: list[dict], **kwargs) -> dict`
  - Internal method to construct OpenRouter-compliant request
  - Handles proper formatting of messages, tools, and other parameters

- `def _process_response(self, response: dict) -> str | dict`
  - Internal method to process OpenRouter response
  - Extracts relevant content and handles any errors

**Example Usage**:

```python
async def example_usage():
    # Initialize provider
    provider = LLMProvider(
        api_key="your_openrouter_key",
        default_model="anthropic/claude-3-opus",
        template_renderer=template_renderer
    )

    # Basic template usage
    result = await provider.call_with_template(
        module_name="summarizer",
        template_name="detailed_summary.j2",
        variables={"markdown_content": content},
        temperature=0.7
    )

    # Tool calling example
    tools = [{
        "type": "function",
        "function": {
            "name": "get_paper_metadata",
            "description": "Get metadata for a research paper",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string"}
                },
                "required": ["paper_id"]
            }
        }
    }]

    result = await provider.call_with_tools(
        messages=[{
            "role": "user",
            "content": "Find metadata for paper XYZ"
        }],
        tools=tools,
        temperature=0.7
    )
```

**Error Handling**:
- Implements proper error handling for OpenRouter API errors
- Includes rate limiting and retry logic
- Handles streaming responses appropriately
- Validates tool definitions and responses

**Configuration**:
- Uses environment variables for API keys
- Supports model configuration via config file
- Allows for proxy configuration if needed

### 4.11. LLM Processing Modules (Using Markdown and PromptManager)

#### QueryProcessor (modules/llm/query_processor.py)
**Attributes**:
- `llm_provider`: LLMProvider

**Methods**:
- `process(query: str) -> dict`
  - Uses template "query_processor/refine_query.j2"

#### AbstractEvaluator (modules/llm/abstract_evaluator.py)
**Attributes**:
- `llm_provider`: LLMProvider

**Methods**:
- `evaluate(markdown_path: str) -> float`
  - Uses template "abstract_evaluator/relevance_score.j2"

#### Summarizer (modules/llm/summarizer.py)
**Attributes**:
- `llm_provider`: LLMProvider

**Methods**:
- `summarize(markdown_path: str) -> List[str]`
  - Uses template "summarizer/detailed_summary.j2"

#### TagGenerator (modules/llm/tag_generator.py)
**Attributes**:
- `llm_provider`: LLMProvider

**Methods**:
- `generate_tags(markdown_path: str) -> List[str]`
  - Uses template "tag_generator/extract_tags.j2"

### 4.12. ObsidianFormatter (modules/markdown/obsidian_formatter.py)

**Class**: ObsidianFormatter

**Attributes**:
- `output_folder`: str (typically data/markdown/)

**Methods**:
- `create_note(metadata: dict, summary: List[str], citations: List[dict], tags: List[str]) -> str`
  - Generates a Markdown note with frontmatter (tags), abstract, detailed summaries, and a citation table with wikilinks (using a custom URI scheme, e.g., `thoth://trigger?article_id=...`).
- `format_citations(citations: List[dict]) -> str`

### 4.13. Citation & Backlink Modules

#### CitationExtractor (modules/citation/citation_extractor.py)
**Attributes**:
- `llm_provider`: LLMProvider

**Methods**:
- `extract(markdown_path: str) -> List[dict]`
  - Uses template "citation_extractor/extract_citations.j2"

#### BacklinkManager (modules/citation/backlink_manager.py)
**Methods**:
- `update_graph(new_article: dict, citations: List[dict])`
  - Integrates with the GraphManager to update Neo4j with new article nodes and citation edges.
- `get_wikilink(citation: dict) -> str`
  - Queries the Neo4j graph to return a wikilink if the cited article exists.

### 4.14. Neo4j GraphManager (modules/graph/graph_manager.py)

**Class**: GraphManager

**Attributes**:
- `driver`: Neo4j driver instance (configured via config.py)

**Methods**:
- `initialize_db()`: Create constraints, indices, and prepare the database.
- `add_article(article: dict)`: Create or update an article node in Neo4j.
- `add_citation(source_id: str, target_id: str)`: Create an edge between two article nodes.
- `get_backlinks(article_id: str) -> List[str]`: Return a list of wikilinks or node identifiers that cite the given article.
- `export_graph() -> Any`: Export graph data for visualization.

### 4.15. ConversationalAgent (modules/agent/conversational_agent.py)

**Class**: ConversationalAgent

**Attributes**:
- `llm_provider`: LLMProvider

**Methods**:
- `start_conversation(query: str) -> dict`
  - Uses LangChain/LangGraph to refine the user's query and return structured search parameters.

### 4.16. Scheduler (modules/scheduler/scheduler.py)

**Class**: Scheduler

**Methods**:
- `schedule_search(task: Callable, frequency: int)`
- `trigger_on_event(event_type: str, callback: Callable)`

## 5. Data Flow & Process Sequence

### A. User Query & Multi-Repository Search

#### Query Submission:
- The user submits a natural language query via CLI.
- `ConversationalAgent` uses `LLMProvider` with templates from `PromptManager` to refine the query into structured parameters (keywords, boolean filters).

#### Search Source Selection:
- `SearchSourceFactory` determines appropriate search sources based on the query domain and available access methods.
- For each selected source, the factory creates the appropriate searcher instance (API-based or web crawler).

#### Unified Search:
- `SearchManager` coordinates the search process across all selected repository searchers.
- Each searcher (e.g., `ArxivSearcher`, `GoogleScholarCrawler`) executes the search using its specific method.
- Results are aggregated, deduplicated, and initially ranked based on basic metadata.

#### Pre-Download Evaluation:
- For each candidate article, `ArticleEvaluator` performs a preliminary evaluation using:
  - Title and abstract analysis
  - Metadata relevance (publication date, authors, venue)
  - Citation count and impact metrics (if available)
  - User interest model (based on previous interactions)
- Only articles that pass a configurable relevance threshold proceed to the download phase.

### B. PDF Access & Download

#### Access Strategy Determination:
- For each article that passes pre-download evaluation, `PDFAccessManager` determines the appropriate access strategy.
- The manager selects from available strategies (DirectDownload, Authenticated, Proxy, etc.) based on:
  - Article source repository
  - Available credentials
  - Institutional access rights
  - Previous download success rates

#### PDF Retrieval:
- `PDFDownloader` attempts to download the PDF using the selected strategy.
- If the primary strategy fails, the downloader falls back to alternative strategies in order of estimated success probability.
- Successfully downloaded PDFs are saved to `data/pdfs/` with appropriate metadata.

#### File Monitoring:
- `FileMonitor` watches `data/pdfs/` and triggers processing when a new PDF is detected.

### C. OCR & Post-Download Evaluation

#### OCR Conversion:
- `OCRManager` processes the PDF, calling the Mistral OCR API.
- The resulting Markdown file is saved in `data/markdown/` (named correspondingly to the PDF).

#### Post-Download Evaluation:
- `ArticleEvaluator` performs a more in-depth evaluation using the full text to determine if the article should proceed to note generation.
- This evaluation uses the `post_download_evaluation.j2` template and considers:
  - Full text content relevance
  - Methodology alignment with user interests
  - Citation network position
  - Detailed findings analysis

### D. LLM Processing & Note Generation (Using PromptManager)

#### Markdown-Based Processing:
- The Markdown file is fed into `Summarizer` and `TagGenerator` which use `LLMProvider` with standardized templates from `PromptManager`.
- `CitationExtractor` uses templates to extract citation details consistently.

#### Obsidian Note Creation:
- `ObsidianFormatter` composes a complete Markdown note incorporating:
  - Frontmatter with auto-generated tags
  - Article metadata (title, authors, abstract)
  - Detailed summaries
  - A citation table with wikilinks using a custom URI (e.g., `thoth://trigger?article_id=...`)
- The note is saved in `data/markdown/`.

### E. Citation Graph & Backlink Integration

#### Graph Update:
- `BacklinkManager` calls `GraphManager` to update Neo4j:
  - `add_article`: Inserts or updates the article node.
  - `add_citation`: Creates relationships (edges) for each extracted citation.
  - `get_backlinks`: Queries existing nodes to generate wikilinks for the note.

#### Obsidian Trigger Integration:
- Wikilinks in the note (e.g., `thoth://trigger?article_id=XYZ`) allow Obsidian users to click and trigger a re-processing via a helper script.

### F. Automation

#### Scheduler:
- `Scheduler` manages periodic search tasks and event-based triggers (e.g., new file addition, manual re-processing).

## 6. Example Pseudocode

### main.py (Core Entry)

```python
from modules.agent.conversational_agent import ConversationalAgent
from modules.scheduler.scheduler import Scheduler
from modules.pdf.pdf_monitor import FileMonitor
from modules.search.search_source_factory import SearchSourceFactory
from modules.search.search_manager import SearchManager
from modules.pdf.pdf_access_manager import PDFAccessManager
from modules.pdf.access_strategies.direct_download_strategy import DirectDownloadStrategy
from modules.pdf.access_strategies.authenticated_download_strategy import AuthenticatedDownloadStrategy
from modules.pdf.pdf_downloader import PDFDownloader
from modules.ocr.ocr_manager import OCRManager
from modules.markdown.obsidian_formatter import ObsidianFormatter
from modules.graph.graph_manager import GraphManager
from modules.citation.citation_extractor import CitationExtractor
from modules.citation.backlink_manager import BacklinkManager
from modules.llm.article_evaluator import ArticleEvaluator
from modules.llm.summarizer import Summarizer
from modules.llm.tag_generator import TagGenerator
from modules.prompt.prompt_manager import PromptManager
from modules.prompt.template_renderer import TemplateRenderer
from modules.llm.llm_provider import LLMProvider

def main():
    # Initialize Prompt Manager and LLM Provider
    prompt_manager = PromptManager(template_dir="templates/")
    template_renderer = TemplateRenderer(prompt_manager=prompt_manager)
    llm_provider = LLMProvider(api_key="YOUR_API_KEY", model="mistral-large", template_renderer=template_renderer)

    # Initialize Conversational Agent and Scheduler
    agent = ConversationalAgent(llm_provider=llm_provider)
    scheduler = Scheduler()

    # Initialize File Monitor to watch the PDF folder; trigger processing on new PDF
    pdf_monitor = FileMonitor(watch_folder="data/pdfs/", callback=lambda path: process_new_pdf(path, graph_manager, llm_provider))
    pdf_monitor.start()

    # Initialize PDF Access Manager and register strategies
    pdf_access_manager = PDFAccessManager()
    pdf_access_manager.register_strategy("direct", DirectDownloadStrategy())
    pdf_access_manager.register_strategy("authenticated", AuthenticatedDownloadStrategy(credentials={
        "springer.com": {"username": "user", "password": "pass"},
        "sciencedirect.com": {"api_key": "YOUR_API_KEY"}
    }))

    # Initialize PDF Downloader with access manager
    pdf_downloader = PDFDownloader(access_manager=pdf_access_manager)

    # Initialize the SearchSourceFactory and SearchManager
    search_factory = SearchSourceFactory()
    search_manager = SearchManager()

    # Register available searchers with the factory
    search_factory.register_searcher("arxiv", "api", ArxivSearcher)
    search_factory.register_searcher("pubmed", "api", PubMedSearcher)
    search_factory.register_searcher("google_scholar", "crawler", GoogleScholarCrawler)

    # Initialize Article Evaluator
    article_evaluator = ArticleEvaluator(llm_provider=llm_provider)

    # Initialize Neo4j GraphManager
    graph_manager = GraphManager()
    graph_manager.initialize_db()

    # Process user query via CLI
    user_query = input("Enter your research query: ")
    refined_params = agent.start_conversation(user_query)

    # Determine appropriate search sources based on query domain
    search_sources = search_factory.get_recommended_sources(refined_params)

    # Add selected searchers to the search manager
    for source_type, access_method in search_sources:
        searcher = search_factory.create_searcher(source_type, access_method)
        search_manager.add_searcher(searcher)

    # Perform multi-repository search
    results = search_manager.search_all(query=refined_params["query"], filters=refined_params.get("filters", {}))

    # Evaluate articles before downloading
    for article in results:
        # Pre-download evaluation based on title and abstract
        relevance_score = article_evaluator.evaluate_pre_download(
            title=article.title,
            abstract=article.abstract,
            metadata=article.metadata
        )

        if relevance_score > 0.7:  # Configurable threshold
            try:
                # Download PDF using appropriate access strategy
                pdf_path = pdf_downloader.download(article, dest_folder="data/pdfs/")
                # PDF Monitor will trigger processing automatically
            except DownloadError as e:
                print(f"Failed to download {article.title}: {e}")
                continue

    # Schedule periodic searches based on user-defined frequency (e.g., every 60 minutes)
    scheduler.schedule_search(
        task=lambda: search_and_evaluate(search_manager, article_evaluator, pdf_downloader, refined_params),
        frequency=60
    )

def search_and_evaluate(search_manager, article_evaluator, pdf_downloader, params):
    """Periodic search function that runs on schedule."""
    results = search_manager.search_all(query=params["query"], filters=params.get("filters", {}))

    for article in results:
        # Skip articles we've already processed
        if article.id in pdf_downloader.download_history:
            continue

        relevance_score = article_evaluator.evaluate_pre_download(
            title=article.title,
            abstract=article.abstract,
            metadata=article.metadata
        )

        if relevance_score > 0.7:
            try:
                pdf_downloader.download(article, dest_folder="data/pdfs/")
            except DownloadError:
                continue

def process_new_pdf(pdf_path: str, graph_manager, llm_provider):
    """Process a newly downloaded PDF."""
    # Step 1: Convert PDF to Markdown using OCR
    markdown_path = OCRManager().process_pdf(pdf_path)

    # Step 2: Perform post-download evaluation
    article_evaluator = ArticleEvaluator(llm_provider=llm_provider)
    post_download_score = article_evaluator.evaluate_post_download(markdown_path)

    # If the article doesn't pass post-download evaluation, stop processing
    if post_download_score < 0.6:  # Configurable threshold
        print(f"Article at {pdf_path} did not pass post-download evaluation. Skipping note generation.")
        return

    # Step 3: Process Markdown using templated LLM calls
    summarizer = Summarizer(llm_provider=llm_provider)
    tag_generator = TagGenerator(llm_provider=llm_provider)
    citation_extractor = CitationExtractor(llm_provider=llm_provider)

    summary = summarizer.summarize(markdown_path)
    tags = tag_generator.generate_tags(markdown_path)
    citations = citation_extractor.extract(markdown_path)

    # Step 4: Generate the Obsidian-friendly Markdown note
    metadata = {"title": "Extracted Title", "authors": "Author List", "abstract": "Extracted Abstract"}
    note_path = ObsidianFormatter().create_note(metadata, summary, citations, tags)

    # Step 5: Update the citation graph in Neo4j
    BacklinkManager().update_graph(metadata, citations)

    print(f"Note generated at {note_path}")

if __name__ == "__main__":
    main()
```

## 7. Example Jinja Template Files

### templates/article_evaluator/pre_download_evaluation.j2

```jinja
You are evaluating whether a research paper is relevant to a user's interests based on its title, abstract, and metadata.

User's research interests: {{ user_interests }}

Paper information:
- Title: {{ title }}
- Abstract: {{ abstract }}
- Authors: {{ metadata.authors }}
- Publication Date: {{ metadata.publication_date }}
- Journal/Conference: {{ metadata.venue }}
- Keywords: {{ metadata.keywords }}

Please evaluate the relevance of this paper to the user's interests on a scale from 0.0 to 1.0, where:
- 0.0: Not relevant at all
- 0.5: Somewhat relevant
- 1.0: Highly relevant

Consider the following factors:
1. Topic alignment with user interests
2. Recency and impact (if available)
3. Methodology relevance
4. Potential insights for the user's research

Format your response as a single float value between 0.0 and 1.0.
```

### templates/article_evaluator/post_download_evaluation.j2

```jinja
You are performing an in-depth evaluation of a research paper to determine if it should be included in the user's knowledge base.
The full text of the paper is provided below.

User's research interests: {{ user_interests }}

{{ markdown_content }}

Please evaluate the paper on the following dimensions:
1. Relevance to user's interests (0-10)
2. Methodological quality (0-10)
3. Novelty of findings (0-10)
4. Clarity of presentation (0-10)
5. Potential impact on user's research (0-10)

For each dimension, provide a brief justification for your score.
Then, calculate an overall relevance score as a float between 0.0 and 1.0.

Format your response as a JSON object with the following structure:
{
  "dimension_scores": {
    "relevance": {"score": X, "justification": "..."},
    "methodology": {"score": X, "justification": "..."},
    "novelty": {"score": X, "justification": "..."},
    "clarity": {"score": X, "justification": "..."},
    "impact": {"score": X, "justification": "..."}
  },
  "overall_score": X.X
}
```

### templates/query_processor/refine_query.j2

```jinja
You are a research assistant helping to refine a user's query for academic search.

User query: {{ query }}

Please convert this query into a structured format with the following:
1. Main research topic
2. Key concepts to include (max 5)
3. Any constraints or filters (e.g., date range, specific authors)
4. Suggested boolean operators (AND, OR, NOT)

Format your response as a JSON object with the following structure:
{
  "main_topic": "...",
  "key_concepts": ["...", "..."],
  "constraints": {"date_range": "...", "authors": ["..."]},
  "boolean_query": "..."
}
```

### templates/summarizer/detailed_summary.j2

```jinja
You are summarizing a research paper. The paper's content is provided below.

{{ markdown_content }}

Please generate a detailed bullet-point summary of this paper following this structure:
1. Key Research Question/Objective
2. Methodology
3. Main Findings
4. Implications
5. Limitations

Format each section as bullet points with a maximum of 3-5 points per section.
Each bullet point should be concise yet informative.
```

### templates/tag_generator/extract_tags.j2

```jinja
You are analyzing a research paper to extract relevant tags. The paper's content is provided below.

{{ markdown_content }}

Please generate:
1. 5-10 specific topic tags relevant to this paper
2. Research methodology tags
3. Domain/field tags

Format your response as a JSON array of strings representing tags.
Each tag should be a single word or short phrase (1-3 words).
```

## 8. Testing, Documentation, and Deployment

### Testing

#### Unit Tests:
- Create tests for each module in the `tests/` folder (e.g., `test_arxiv_searcher.py`, `test_pdf_downloader.py`, `test_ocr_manager.py`, `test_prompt_manager.py`, `test_obsidian_formatter.py`, `test_graph_manager.py`).

#### Integration Tests:
- Simulate end-to-end flows from query submission to note generation and Neo4j graph updates.
- Test Obsidian-triggered re-processing (via helper script).

### Documentation

#### README.md:
- Include project overview, setup instructions (dependencies, config, Docker), and usage examples.

#### In-Line Comments & Docstrings:
- Document each class and method with clear explanations.

### Deployment

#### Containerization:
- Use Docker to containerize the application. Include a separate container for Neo4j if needed.

#### CI/CD Pipelines:
- Configure pipelines (e.g., with GitHub Actions) to run tests and build deployment images automatically.
