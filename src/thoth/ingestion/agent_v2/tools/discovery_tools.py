"""
Discovery source management tools for the research assistant.

This module provides tools for managing discovery sources (ArXiv, PubMed, scrapers)
that automatically find and filter research articles.
"""

from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool
from thoth.ingestion.agent_v2.tools.decorators import tool


@tool
class ListDiscoverySourcesTool(BaseThothTool):
    """List all configured discovery sources."""

    name: str = 'list_discovery_sources'
    description: str = (
        'List all configured discovery sources with their status and configuration'
    )

    def _run(self) -> str:
        """List discovery sources."""
        try:
            sources = self.service_manager.discovery.list_sources()
            if not sources:
                return "No discovery sources configured. Use 'create_arxiv_source' or 'create_pubmed_source' to add one."

            result = ['**Discovery Sources:**\n']
            for source in sources:
                status = '🟢 Active' if source.is_active else '🔴 Inactive'
                result.append(f'**{source.name}** ({source.source_type}) - {status}')
                result.append(f'  Description: {source.description}')
                if source.last_run:
                    result.append(f'  Last run: {source.last_run}')
                if source.schedule_config:
                    result.append(
                        f'  Schedule: Every {source.schedule_config.interval_minutes} minutes'
                    )
                    result.append(
                        f'  Max articles: {source.schedule_config.max_articles_per_run}'
                    )
                result.append('')

            return '\n'.join(result)
        except Exception as e:
            return self.handle_error(e, 'listing discovery sources')


class CreateDiscoverySourceInput(BaseModel):
    name: str = Field(
        description="Name of the discovery source (e.g., 'arxiv_genai_daily')"
    )
    keywords: list[str] = Field(description='List of keywords to search for')
    categories: list[str] | None = Field(
        default=None, description='List of categories to filter by (optional)'
    )
    max_articles: int = Field(default=50, description='Maximum articles per run')
    schedule_hours: int = Field(default=24, description='Run interval in hours')


@tool
class CreateArxivSourceTool(BaseThothTool):
    """Create an ArXiv discovery source."""

    name: str = 'create_arxiv_source'
    description: str = (
        'Create an ArXiv discovery source to automatically find papers. '
        'Specify name, keywords, and optionally categories.'
    )
    args_schema: type[BaseModel] = CreateDiscoverySourceInput

    def _run(
        self,
        name: str,
        keywords: list[str],
        categories: list[str] | None = None,
        max_articles: int = 50,
        schedule_hours: int = 24,
    ) -> str:
        """Create ArXiv source."""
        try:
            categories = categories or ['cs.LG', 'cs.AI']

            source_config = {
                'name': name,
                'source_type': 'api',
                'description': f'ArXiv source for {", ".join(categories)} papers',
                'is_active': True,
                'api_config': {
                    'source': 'arxiv',
                    'categories': categories,
                    'keywords': keywords,
                    'sort_by': 'lastUpdatedDate',
                    'sort_order': 'descending',
                },
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                    'enabled': True,
                },
                'query_filters': [],
            }

            from thoth.utilities.schemas import DiscoverySource

            source = DiscoverySource(**source_config)
            self.service_manager.discovery.create_source(source)
            return (
                f'✅ **ArXiv Discovery Source Created Successfully!**\n\n'
                f'**Source Details:**\n'
                f'- Name: `{name}`\n'
                f'- Type: ArXiv API\n'
                f'- Categories: {", ".join(categories)}\n'
                f'- Keywords: {", ".join(keywords)}\n'
                f'- Schedule: Every {schedule_hours} hours, max {max_articles} articles\n\n'
                f'🚀 **Ready to use!** You can now:\n'
                f"- Run it: 'run_discovery' with source_name='{name}'\n"
                f"- View it: 'list_discovery_sources'\n"
            )

        except Exception as e:
            return self.handle_error(e, 'creating ArXiv source')


class CreatePubmedSourceInput(BaseModel):
    """Input schema for creating a PubMed source."""

    name: str = Field(description='Unique name for the source')
    keywords: list[str] = Field(description='Keywords to search for in PubMed')
    max_articles: int = Field(default=20, description='Maximum articles per run')
    schedule_hours: int = Field(default=48, description='Run interval in hours')


@tool
class CreatePubmedSourceTool(BaseThothTool):
    """Create a PubMed discovery source."""

    name: str = 'create_pubmed_source'
    description: str = (
        'Create a PubMed discovery source to automatically find biomedical papers. '
        'Specify name and keywords.'
    )
    args_schema: type[BaseModel] = CreatePubmedSourceInput

    def _run(
        self,
        name: str,
        keywords: list[str],
        max_articles: int = 20,
        schedule_hours: int = 48,
    ) -> str:
        """Create PubMed source."""
        try:
            source_config = {
                'name': name,
                'source_type': 'api',
                'description': f'PubMed source for {", ".join(keywords)} research',
                'is_active': True,
                'api_config': {
                    'source': 'pubmed',
                    'keywords': keywords,
                    'sort_by': 'date',
                    'sort_order': 'descending',
                },
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                    'enabled': True,
                },
                'query_filters': [],
            }

            from thoth.utilities.schemas import DiscoverySource

            source = DiscoverySource(**source_config)
            self.service_manager.discovery.create_source(source)
            return (
                f'✅ **PubMed Discovery Source Created Successfully!**\n\n'
                f'**Source Details:**\n'
                f'- Name: `{name}`\n'
                f'- Type: PubMed API\n'
                f'- Keywords: {", ".join(keywords)}\n'
                f'- Schedule: Every {schedule_hours} hours, max {max_articles} articles\n\n'
                f'🚀 **Ready to use!**'
            )

        except Exception as e:
            return self.handle_error(e, 'creating PubMed source')


class CreateCrossrefSourceInput(BaseModel):
    """Input schema for creating a CrossRef source."""

    name: str = Field(description='Unique name for the source')
    keywords: list[str] = Field(description='Keywords to search for in CrossRef')
    max_articles: int = Field(default=50, description='Maximum articles per run')
    schedule_hours: int = Field(default=24, description='Run interval in hours')


class CreateCrossrefSourceTool(BaseThothTool):
    """Create a CrossRef discovery source."""

    name: str = 'create_crossref_source'
    description: str = (
        'Create a CrossRef discovery source to automatically find papers. '
        'Specify name and keywords.'
    )
    args_schema: type[BaseModel] = CreateCrossrefSourceInput

    def _run(
        self,
        name: str,
        keywords: list[str],
        max_articles: int = 50,
        schedule_hours: int = 24,
    ) -> str:
        """Create CrossRef source."""
        try:
            source_config = {
                'name': name,
                'source_type': 'api',
                'description': f'CrossRef source for {", ".join(keywords)} research',
                'is_active': True,
                'api_config': {
                    'source': 'crossref',
                    'keywords': keywords,
                    'sort_by': 'relevance',
                    'sort_order': 'desc',
                },
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                    'enabled': True,
                },
                'query_filters': [],
            }

            if self.adapter.create_discovery_source(source_config):
                return (
                    f'✅ **CrossRef Discovery Source Created Successfully!**\n\n'
                    f'**Source Details:**\n'
                    f'- Name: `{name}`\n'
                    f'- Type: CrossRef API\n'
                    f'- Keywords: {", ".join(keywords)}\n'
                    f'- Schedule: Every {schedule_hours} hours, max {max_articles} articles\n\n'
                    f'🚀 **Ready to use!**'
                )
            else:
                return f"❌ Failed to create CrossRef source '{name}'"

        except Exception as e:
            return self.handle_error(e, 'creating CrossRef source')


class CreateOpenalexSourceInput(BaseModel):
    """Input schema for creating an OpenAlex source."""

    name: str = Field(description='Unique name for the source')
    keywords: list[str] = Field(description='Keywords to search for in OpenAlex')
    max_articles: int = Field(default=50, description='Maximum articles per run')
    schedule_hours: int = Field(default=24, description='Run interval in hours')


class CreateOpenalexSourceTool(BaseThothTool):
    """Create an OpenAlex discovery source."""

    name: str = 'create_openalex_source'
    description: str = (
        'Create an OpenAlex discovery source to automatically find papers. '
        'Specify name and keywords.'
    )
    args_schema: type[BaseModel] = CreateOpenalexSourceInput

    def _run(
        self,
        name: str,
        keywords: list[str],
        max_articles: int = 50,
        schedule_hours: int = 24,
    ) -> str:
        """Create OpenAlex source."""
        try:
            source_config = {
                'name': name,
                'source_type': 'api',
                'description': f'OpenAlex source for {", ".join(keywords)} research',
                'is_active': True,
                'api_config': {
                    'source': 'openalex',
                    'keywords': keywords,
                    'sort_by': 'relevance',
                },
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                    'enabled': True,
                },
                'query_filters': [],
            }

            if self.adapter.create_discovery_source(source_config):
                return (
                    f'✅ **OpenAlex Discovery Source Created Successfully!**\n\n'
                    f'**Source Details:**\n'
                    f'- Name: `{name}`\n'
                    f'- Type: OpenAlex API\n'
                    f'- Keywords: {", ".join(keywords)}\n'
                    f'- Schedule: Every {schedule_hours} hours, max {max_articles} articles\n\n'
                    f'🚀 **Ready to use!**'
                )
            else:
                return f"❌ Failed to create OpenAlex source '{name}'"

        except Exception as e:
            return self.handle_error(e, 'creating OpenAlex source')


class CreateBiorxivSourceInput(BaseModel):
    """Input schema for creating a bioRxiv source."""

    name: str = Field(description='Unique name for the source')
    start_date: str | None = Field(default=None, description='Start date YYYY-MM-DD')
    end_date: str | None = Field(default=None, description='End date YYYY-MM-DD')
    max_articles: int = Field(default=50, description='Maximum articles per run')
    schedule_hours: int = Field(default=24, description='Run interval in hours')


class CreateBiorxivSourceTool(BaseThothTool):
    """Create a bioRxiv discovery source."""

    name: str = 'create_biorxiv_source'
    description: str = (
        'Create a bioRxiv discovery source to automatically find preprints.'
    )
    args_schema: type[BaseModel] = CreateBiorxivSourceInput

    def _run(
        self,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        max_articles: int = 50,
        schedule_hours: int = 24,
    ) -> str:
        """Create bioRxiv source."""
        try:
            api_config = {
                'source': 'biorxiv',
            }
            if start_date:
                api_config['start_date'] = start_date
            if end_date:
                api_config['end_date'] = end_date

            source_config = {
                'name': name,
                'source_type': 'api',
                'description': 'bioRxiv preprint source',
                'is_active': True,
                'api_config': api_config,
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                    'enabled': True,
                },
                'query_filters': [],
            }

            if self.adapter.create_discovery_source(source_config):
                return (
                    f'✅ **bioRxiv Discovery Source Created Successfully!**\n\n'
                    f'**Source Details:**\n'
                    f'- Name: `{name}`\n'
                    f'- Type: bioRxiv API\n'
                    f'- Schedule: Every {schedule_hours} hours, max {max_articles} articles\n\n'
                    f'🚀 **Ready to use!**'
                )
            else:
                return f"❌ Failed to create bioRxiv source '{name}'"

        except Exception as e:
            return self.handle_error(e, 'creating bioRxiv source')


class RunDiscoveryInput(BaseModel):
    """Input schema for running discovery."""

    source_name: str | None = Field(
        default=None, description='Name of the discovery source to run (optional)'
    )
    max_articles: int | None = Field(
        default=None, description='Maximum number of articles to fetch (optional)'
    )


@tool
class RunDiscoveryTool(BaseThothTool):
    """Run article discovery."""

    name: str = 'run_discovery'
    description: str = (
        'Runs the discovery process for a specified source or all sources. '
        'This tool fetches new articles based on predefined criteria and stores them '
        'for further processing. It helps keep the knowledge base up-to-date with '
        'the latest research.'
    )
    args_schema: type[BaseModel] = RunDiscoveryInput

    def _run(
        self, source_name: str | None = None, max_articles: int | None = None
    ) -> str:
        """Run discovery."""
        try:
            if source_name:
                message = f"🚀 **Running discovery for '{source_name}'**...\n\n"
            else:
                message = '🚀 **Running discovery for all active sources**...\n\n'

            result = self.service_manager.discovery.run_discovery(
                source_name, max_articles
            )

            if result.articles_found > 0:
                message += '✅ **Discovery completed successfully!**\n\n'
                message += '📊 **Results:**\n'
                message += f'- Articles found: {result.articles_found}\n'
                message += f'- Articles filtered: {result.articles_filtered}\n'
                message += f'- Articles downloaded: {result.articles_downloaded}\n'
                message += f'- Execution time: {result.execution_time_seconds:.2f}s\n'

                if result.errors:
                    message += '\n⚠️ **Warnings:**\n'
                    for error in result.errors[:3]:
                        message += f'- {error}\n'

                if result.articles_downloaded > 0:
                    message += '\n📁 **New articles saved to:** `knowledge/agent/pdfs/`'
                    message += (
                        '\n📋 **Detailed evaluations:** `knowledge/agent/evaluations/`'
                    )
            else:
                message += (
                    '✅ **Discovery completed successfully!** No new articles found.'
                )

            return message

        except Exception as e:
            return self.handle_error(e, 'running discovery')


class DeleteSourceInput(BaseModel):
    """Input schema for deleting a source."""

    source_name: str = Field(description='Name of the source to delete')


@tool
class DeleteDiscoverySourceTool(BaseThothTool):
    """Delete a discovery source."""

    name: str = 'delete_discovery_source'
    description: str = 'Delete a discovery source'
    args_schema: type[BaseModel] = DeleteSourceInput

    def _run(self, source_name: str) -> str:
        """Delete a discovery source."""
        try:
            self.service_manager.discovery.delete_source(source_name)
            return f"✅ Successfully deleted discovery source '{source_name}'"
        except Exception as e:
            return self.handle_error(e, f"deleting source '{source_name}'")
