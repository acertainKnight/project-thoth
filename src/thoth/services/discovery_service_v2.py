"""
Discovery service V2 with PostgreSQL repository integration.

This module extends the original DiscoveryService to use PostgreSQL repositories
while maintaining backward compatibility with file-based storage.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from thoth.repositories.discovery_source_repository import DiscoverySourceRepository
from thoth.repositories.paper_discovery_repository import PaperDiscoveryRepository
from thoth.services.discovery_service import DiscoveryService
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas import DiscoverySource, ScrapedArticleMetadata


class DiscoveryServiceV2(DiscoveryService):
    """
    Enhanced DiscoveryService with PostgreSQL repository support.

    This service extends the file-based DiscoveryService to use PostgreSQL
    repositories when available, with automatic fallback to file storage.
    """

    def __init__(
        self,
        config=None,
        sources_dir: Path | None = None,
        results_dir: Path | None = None,
        article_service=None,
        postgres_service: Optional[PostgresService] = None,
        use_postgres: bool = True,
    ):
        """
        Initialize the DiscoveryServiceV2.

        Args:
            config: Optional configuration object
            sources_dir: Directory for storing source configurations (file fallback)
            results_dir: Directory for storing discovery results
            article_service: Optional ArticleService instance
            postgres_service: Optional PostgresService instance
            use_postgres: Whether to use PostgreSQL repositories (defaults to True)
        """
        super().__init__(config, sources_dir, results_dir, article_service)

        self.postgres = postgres_service
        self.use_postgres = use_postgres and postgres_service is not None

        # Initialize repositories if PostgreSQL is available
        self.source_repo: Optional[DiscoverySourceRepository] = None
        self.discovery_repo: Optional[PaperDiscoveryRepository] = None

        if self.use_postgres:
            self.source_repo = DiscoverySourceRepository(self.postgres)
            self.discovery_repo = PaperDiscoveryRepository(self.postgres)
            self.logger.info('DiscoveryService initialized with PostgreSQL repositories')
        else:
            self.logger.info('DiscoveryService initialized with file-based storage')

    async def initialize(self) -> None:
        """Initialize the discovery service."""
        if self.use_postgres and self.postgres:
            await self.postgres.initialize()
        super().initialize()

    def create_source(self, source: DiscoverySource) -> bool:
        """
        Create a new discovery source.

        Args:
            source: Discovery source configuration

        Returns:
            bool: True if successful
        """
        if self.use_postgres:
            return self._create_source_postgres(source)
        else:
            return super().create_source(source)

    def _create_source_postgres(self, source: DiscoverySource) -> bool:
        """Create source using PostgreSQL repository."""
        try:
            # Set timestamps
            now = datetime.now()
            if not source.created_at:
                source.created_at = now.isoformat()
            source.updated_at = now.isoformat()

            # Map DiscoverySource to database schema
            data = {
                'source_type': source.source_type,
                'source_name': source.name,
                'config': source.model_dump(
                    include={
                        'api_config',
                        'scraper_config',
                        'browser_recording',
                        'query_filters',
                        'description',
                    }
                ),
                'enabled': source.is_active,
                'schedule_interval_minutes': source.schedule_config.interval_minutes
                if source.schedule_config
                else None,
                'created_at': now,
                'updated_at': now,
            }

            # Calculate next run time if schedule is configured
            if source.schedule_config and source.schedule_config.enabled:
                next_run = self._calculate_next_run(source.schedule_config)
                data['next_run_at'] = datetime.fromisoformat(next_run)

            # Use asyncio to run async repository method
            import asyncio

            loop = asyncio.get_event_loop()
            source_id = loop.run_until_complete(self.source_repo.create(data))

            if source_id:
                self.log_operation(
                    'source_created_postgres', name=source.name, id=source_id
                )
                # Also save to file for backward compatibility
                super().create_source(source)
                return True

            return False

        except Exception as e:
            self.logger.error(f'Failed to create source in PostgreSQL: {e}')
            # Fallback to file storage
            return super().create_source(source)

    def get_source(self, name: str) -> DiscoverySource | None:
        """
        Get a discovery source by name.

        Args:
            name: Name of the source

        Returns:
            DiscoverySource: The source if found, None otherwise
        """
        if self.use_postgres:
            return self._get_source_postgres(name)
        else:
            return super().get_source(name)

    def _get_source_postgres(self, name: str) -> DiscoverySource | None:
        """Get source from PostgreSQL repository."""
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            source_data = loop.run_until_complete(self.source_repo.get_by_name(name))

            if source_data:
                return self._map_db_to_discovery_source(source_data)

            # Fallback to file
            return super().get_source(name)

        except Exception as e:
            self.logger.error(f'Failed to get source from PostgreSQL: {e}')
            return super().get_source(name)

    def list_sources(self, active_only: bool = False) -> list[DiscoverySource]:
        """
        List all discovery sources.

        Args:
            active_only: If True, only return active sources

        Returns:
            list[DiscoverySource]: List of sources
        """
        if self.use_postgres:
            return self._list_sources_postgres(active_only)
        else:
            return super().list_sources(active_only)

    def _list_sources_postgres(self, active_only: bool = False) -> list[DiscoverySource]:
        """List sources from PostgreSQL repository."""
        try:
            import asyncio

            loop = asyncio.get_event_loop()

            if active_only:
                sources_data = loop.run_until_complete(
                    self.source_repo.get_active_sources()
                )
            else:
                sources_data = loop.run_until_complete(self.source_repo.list_all())

            return [self._map_db_to_discovery_source(s) for s in sources_data]

        except Exception as e:
            self.logger.error(f'Failed to list sources from PostgreSQL: {e}')
            return super().list_sources(active_only)

    def update_source(self, source: DiscoverySource) -> bool:
        """
        Update an existing discovery source.

        Args:
            source: Updated source configuration

        Returns:
            bool: True if successful
        """
        if self.use_postgres:
            return self._update_source_postgres(source)
        else:
            return super().update_source(source)

    def _update_source_postgres(self, source: DiscoverySource) -> bool:
        """Update source in PostgreSQL repository."""
        try:
            import asyncio

            loop = asyncio.get_event_loop()

            # Get existing source to get ID
            existing = loop.run_until_complete(self.source_repo.get_by_name(source.name))
            if not existing:
                self.logger.warning(f"Source '{source.name}' not found in database")
                return super().update_source(source)

            # Update data
            data = {
                'config': source.model_dump(
                    include={
                        'api_config',
                        'scraper_config',
                        'browser_recording',
                        'query_filters',
                        'description',
                    }
                ),
                'enabled': source.is_active,
                'schedule_interval_minutes': source.schedule_config.interval_minutes
                if source.schedule_config
                else None,
                'updated_at': datetime.now(),
            }

            success = loop.run_until_complete(
                self.source_repo.update(existing['id'], data)
            )

            if success:
                # Also update file for backward compatibility
                super().update_source(source)
                return True

            return False

        except Exception as e:
            self.logger.error(f'Failed to update source in PostgreSQL: {e}')
            return super().update_source(source)

    def delete_source(self, name: str) -> bool:
        """
        Delete a discovery source.

        Args:
            name: Name of the source to delete

        Returns:
            bool: True if successful
        """
        if self.use_postgres:
            return self._delete_source_postgres(name)
        else:
            return super().delete_source(name)

    def _delete_source_postgres(self, name: str) -> bool:
        """Delete source from PostgreSQL repository."""
        try:
            import asyncio

            loop = asyncio.get_event_loop()

            # Get source to get ID
            source = loop.run_until_complete(self.source_repo.get_by_name(name))
            if not source:
                return super().delete_source(name)

            success = loop.run_until_complete(self.source_repo.delete(source['id']))

            if success:
                # Also delete file
                super().delete_source(name)
                return True

            return False

        except Exception as e:
            self.logger.error(f'Failed to delete source from PostgreSQL: {e}')
            return super().delete_source(name)

    async def record_article_discovery(
        self,
        paper_id: str,
        source_id: str,
        metadata: ScrapedArticleMetadata,
    ) -> Optional[str]:
        """
        Record that an article was discovered by a source.

        Args:
            paper_id: UUID of the paper in the papers table
            source_id: UUID of the discovery source
            metadata: Article metadata from discovery

        Returns:
            Optional[str]: Discovery record ID or None
        """
        if not self.use_postgres or not self.discovery_repo:
            self.logger.debug('PostgreSQL not available, skipping discovery recording')
            return None

        try:
            source_metadata = {
                'title': metadata.title,
                'doi': metadata.doi,
                'arxiv_id': metadata.arxiv_id,
                'pdf_url': metadata.pdf_url,
                'source_url': metadata.source_url,
            }

            return await self.discovery_repo.record_discovery(
                paper_id=paper_id,
                source_id=source_id,
                source_metadata=source_metadata,
            )

        except Exception as e:
            self.logger.error(f'Failed to record article discovery: {e}')
            return None

    async def is_article_processed(
        self, doi: Optional[str] = None, arxiv_id: Optional[str] = None
    ) -> bool:
        """
        Check if an article has already been processed.

        Args:
            doi: DOI of the article
            arxiv_id: arXiv ID of the article

        Returns:
            bool: True if article has been processed
        """
        if not self.use_postgres or not self.discovery_repo:
            return False

        try:
            # Query paper_discoveries to see if this article exists
            # This is a simplified check - in production you'd want to:
            # 1. First lookup paper by DOI/arXiv ID in papers table
            # 2. Then check if it has any discoveries
            # 3. Or check if it has been fully processed

            # For now, just return False to allow processing
            return False

        except Exception as e:
            self.logger.error(f'Failed to check if article is processed: {e}')
            return False

    def _map_db_to_discovery_source(self, db_data: dict[str, Any]) -> DiscoverySource:
        """
        Map database record to DiscoverySource model.

        Args:
            db_data: Database record dictionary

        Returns:
            DiscoverySource: Mapped discovery source
        """
        config = db_data.get('config', {})

        from thoth.utilities.schemas import ScheduleConfig

        schedule_config = ScheduleConfig(
            enabled=db_data.get('enabled', True),
            interval_minutes=db_data.get('schedule_interval_minutes', 60),
        )

        return DiscoverySource(
            name=db_data['source_name'],
            source_type=db_data['source_type'],
            description=config.get('description', ''),
            is_active=db_data.get('enabled', True),
            api_config=config.get('api_config'),
            scraper_config=config.get('scraper_config'),
            browser_recording=config.get('browser_recording'),
            query_filters=config.get('query_filters', []),
            schedule_config=schedule_config,
            last_run=db_data.get('last_run_at').isoformat()
            if db_data.get('last_run_at')
            else None,
            created_at=db_data['created_at'].isoformat(),
            updated_at=db_data['updated_at'].isoformat(),
        )

    async def close(self) -> None:
        """Close database connections."""
        if self.use_postgres and self.postgres:
            await self.postgres.close()
