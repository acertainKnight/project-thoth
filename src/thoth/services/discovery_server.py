"""
Discovery server for continuous discovery operations with auto-activation.

This module provides a standalone server that monitors for new discovery source
configurations and automatically activates them in the scheduler.
"""

import json
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from thoth.services.base import BaseService
from thoth.services.discovery_service import DiscoveryService
from thoth.utilities.schemas import DiscoverySource


class DiscoveryConfigHandler(FileSystemEventHandler):
    """Handler for discovery configuration file changes."""

    def __init__(self, server: 'DiscoveryServer'):
        """Initialize the file handler."""
        self.server = server
        super().__init__()

    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and event.src_path.endswith('.json'):
            logger.info(f'New discovery config detected: {event.src_path}')
            self.server.load_source_from_file(Path(event.src_path))

    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith('.json'):
            logger.info(f'Discovery config modified: {event.src_path}')
            self.server.load_source_from_file(Path(event.src_path))


class DiscoveryServerError(Exception):
    """Exception raised for discovery server errors."""

    pass


class DiscoveryServer(BaseService):
    """
    Standalone discovery server with auto-activation capabilities.

    This server provides continuous discovery operations by:
    1. Monitoring discovery source configuration directory
    2. Auto-loading and activating new discovery sources
    3. Managing the discovery scheduler continuously
    4. Providing status and health monitoring
    """

    def __init__(self, config=None, discovery_service: DiscoveryService | None = None):
        """
        Initialize the discovery server.

        Args:
            config: Optional configuration object
            discovery_service: Optional DiscoveryService instance
        """
        super().__init__(config)

        # Initialize discovery service
        self.discovery_service = discovery_service or DiscoveryService(
            config=self.config
        )

        # Server state
        self.running = False
        self.server_thread = None

        # File monitoring
        self.file_observer = None
        self.config_handler = DiscoveryConfigHandler(self)

        # Shutdown handling
        self.shutdown_event = threading.Event()

        # Statistics
        self.start_time = None
        self.sources_loaded = 0
        self.errors_count = 0

    def initialize(self) -> None:
        """Initialize the discovery server."""
        self.discovery_service.initialize()
        self.logger.info('Discovery server initialized')

    def start(self) -> None:
        """
        Start the discovery server.

        Raises:
            DiscoveryServerError: If server is already running
        """
        if self.running:
            raise DiscoveryServerError('Discovery server is already running')

        try:
            self.logger.info('Starting discovery server...')

            # Set up signal handlers for graceful shutdown
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)

            # Mark as running
            self.running = True
            self.start_time = datetime.now()

            # Start file monitoring
            self._start_file_monitoring()

            # Load existing sources and start scheduler
            self._load_existing_sources()
            self.discovery_service.start_scheduler()

            # Start main server loop
            self.server_thread = threading.Thread(
                target=self._server_loop, daemon=False
            )
            self.server_thread.start()

            self.logger.info('Discovery server started successfully')
            self.log_operation('server_started')

        except Exception as e:
            self.running = False
            raise DiscoveryServerError(f'Failed to start discovery server: {e}') from e

    def stop(self) -> None:
        """Stop the discovery server gracefully."""
        if not self.running:
            return

        self.logger.info('Stopping discovery server...')

        # Signal shutdown
        self.running = False
        self.shutdown_event.set()

        # Stop scheduler
        try:
            self.discovery_service.stop_scheduler()
        except Exception as e:
            self.logger.error(f'Error stopping scheduler: {e}')

        # Stop file monitoring
        self._stop_file_monitoring()

        # Wait for server thread to finish
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=10.0)

        self.logger.info('Discovery server stopped')
        self.log_operation('server_stopped')

    def load_source_from_file(self, config_file: Path) -> bool:
        """
        Load and auto-activate a discovery source from a configuration file.

        Args:
            config_file: Path to the source configuration file

        Returns:
            bool: True if successfully loaded and activated
        """
        try:
            if not config_file.exists():
                self.logger.warning(f'Config file does not exist: {config_file}')
                return False

            # Load configuration
            with open(config_file) as f:
                config_data = json.load(f)

            # Validate and create source
            source = DiscoverySource(**config_data)

            # Check if source already exists
            existing_source = self.discovery_service.get_source(source.name)

            if existing_source:
                # Update existing source
                self.discovery_service.update_source(source)
                self.logger.info(f'Updated discovery source: {source.name}')
                action = 'updated'
            else:
                # Create new source
                self.discovery_service.create_source(source)
                self.logger.info(f'Created discovery source: {source.name}')
                action = 'created'
                self.sources_loaded += 1

            # Auto-activate if scheduler is running and source is active
            if self.discovery_service.scheduler_running and source.is_active:
                self._activate_source_in_scheduler(source)

            self.log_operation(
                f'source_{action}', name=source.name, file=str(config_file)
            )
            return True

        except Exception as e:
            error_msg = f'Failed to load source from {config_file}: {e}'
            self.logger.error(error_msg)
            self.errors_count += 1
            return False

    def get_server_status(self) -> dict[str, Any]:
        """
        Get comprehensive server status information.

        Returns:
            dict[str, Any]: Server status and statistics
        """
        # Get discovery service status
        discovery_status = self.discovery_service.get_schedule_status()

        # Calculate uptime
        uptime_seconds = 0
        if self.start_time:
            uptime_seconds = (datetime.now() - self.start_time).total_seconds()

        return {
            'server_running': self.running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'uptime_seconds': uptime_seconds,
            'sources_loaded': self.sources_loaded,
            'errors_count': self.errors_count,
            'file_monitoring': self.file_observer is not None
            and self.file_observer.is_alive(),
            'discovery_service': discovery_status,
            'configuration': {
                'sources_dir': str(self.discovery_service.sources_dir),
                'results_dir': str(self.discovery_service.results_dir),
                'schedule_file': str(self.discovery_service.schedule_file),
            },
        }

    def list_active_sources(self) -> list[DiscoverySource]:
        """
        Get all currently active discovery sources.

        Returns:
            list[DiscoverySource]: List of active sources
        """
        return self.discovery_service.list_sources(active_only=True)

    def run_server_blocking(self) -> None:
        """
        Run the server in blocking mode until shutdown signal.

        This method starts the server and blocks until a shutdown signal
        is received or an error occurs.
        """
        try:
            self.start()

            # Block until shutdown signal
            self.logger.info('Discovery server running. Press Ctrl+C to stop.')

            while self.running:
                try:
                    time.sleep(1)
                except KeyboardInterrupt:
                    self.logger.info('Shutdown signal received')
                    break

        except Exception as e:
            self.logger.error(f'Server error: {e}')
            raise
        finally:
            self.stop()

    def _signal_handler(self, signum, frame):  # noqa: ARG002
        """Handle shutdown signals."""
        self.logger.info(f'Received signal {signum}, shutting down...')
        self.running = False
        self.shutdown_event.set()

    def _server_loop(self) -> None:
        """Main server loop running in separate thread."""
        self.logger.info('Server loop started')

        while self.running:
            try:
                # Check for shutdown signal
                if self.shutdown_event.wait(timeout=60):
                    break

                # Perform periodic maintenance
                self._perform_maintenance()

            except Exception as e:
                self.logger.error(f'Error in server loop: {e}')
                self.errors_count += 1
                time.sleep(60)  # Continue after error

        self.logger.info('Server loop stopped')

    def _start_file_monitoring(self) -> None:
        """Start monitoring the discovery sources directory."""
        try:
            sources_dir = self.discovery_service.sources_dir

            self.file_observer = Observer()
            self.file_observer.schedule(
                self.config_handler, path=str(sources_dir), recursive=False
            )
            self.file_observer.start()

            self.logger.info(f'Started file monitoring on: {sources_dir}')

        except Exception as e:
            self.logger.error(f'Failed to start file monitoring: {e}')
            self.errors_count += 1

    def _stop_file_monitoring(self) -> None:
        """Stop file monitoring."""
        if self.file_observer:
            try:
                self.file_observer.stop()
                self.file_observer.join(timeout=5.0)
                self.logger.info('Stopped file monitoring')
            except Exception as e:
                self.logger.error(f'Error stopping file monitoring: {e}')

    def _load_existing_sources(self) -> None:
        """Load all existing discovery source configurations."""
        try:
            sources_dir = self.discovery_service.sources_dir
            config_files = list(sources_dir.glob('*.json'))

            self.logger.info(
                f'Loading {len(config_files)} existing source configurations'
            )

            for config_file in config_files:
                self.load_source_from_file(config_file)

        except Exception as e:
            self.logger.error(f'Error loading existing sources: {e}')
            self.errors_count += 1

    def _activate_source_in_scheduler(self, source: DiscoverySource) -> None:
        """Activate a source in the scheduler if it's not already active."""
        try:
            if not source.schedule_config or not source.schedule_config.enabled:
                self.logger.debug(f'Source {source.name} not enabled for scheduling')
                return

            # The discovery service scheduler will automatically pick up
            # sources that have schedule configs when it runs its check loop
            self.logger.info(f'Source {source.name} will be activated in scheduler')

        except Exception as e:
            self.logger.error(f'Error activating source {source.name}: {e}')
            self.errors_count += 1

    def _perform_maintenance(self) -> None:
        """Perform periodic maintenance tasks."""
        try:
            # Sync scheduler with any changes
            if (
                hasattr(self.discovery_service, '_scheduler')
                and self.discovery_service._scheduler
            ):
                # The scheduler's check loop handles maintenance automatically
                pass

            # Log status periodically
            if hasattr(self, '_last_status_log'):
                if time.time() - self._last_status_log > 3600:  # Every hour
                    self._log_status_summary()
            else:
                self._last_status_log = time.time()

        except Exception as e:
            self.logger.error(f'Error in maintenance: {e}')
            self.errors_count += 1

    def _log_status_summary(self) -> None:
        """Log a summary of server status."""
        status = self.get_server_status()

        self.logger.info(
            f'Discovery Server Status: '
            f'Sources: {status["discovery_service"]["total_sources"]}, '
            f'Enabled: {status["discovery_service"]["enabled_sources"]}, '
            f'Uptime: {status["uptime_seconds"]:.0f}s, '
            f'Errors: {status["errors_count"]}'
        )

        self._last_status_log = time.time()

    def health_check(self) -> dict[str, str]:
        """Health check for the discovery server."""
        base_health = super().health_check()

        if not self.running:
            base_health['status'] = 'unhealthy'
            base_health['message'] = 'Server not running'
        elif self.errors_count > 10:  # Arbitrary threshold
            base_health['status'] = 'degraded'
            base_health['message'] = f'High error count: {self.errors_count}'

        return base_health
