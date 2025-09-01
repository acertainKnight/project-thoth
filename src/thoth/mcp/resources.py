"""
MCP Resource Implementation

This module provides MCP-compliant resource management for files,
documents, and other data sources.
"""

import base64
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from .protocol import MCPResource, MCPResourceContents, MCPResourceTemplate


class MCPResourceProvider(ABC):
    """
    Abstract base class for MCP resource providers.

    Resource providers expose data sources like files, databases,
    or web APIs as MCP resources.
    """

    @abstractmethod
    async def list_resources(self) -> list[MCPResource]:
        """List all available resources."""
        pass

    @abstractmethod
    async def get_resource(self, uri: str) -> MCPResourceContents | None:
        """Get resource contents by URI."""
        pass

    @abstractmethod
    def get_resource_templates(self) -> list[MCPResourceTemplate]:
        """Get resource URI templates for dynamic resources."""
        pass

    @abstractmethod
    def supports_uri(self, uri: str) -> bool:
        """Check if this provider supports the given URI."""
        pass


class FileResourceProvider(MCPResourceProvider):
    """
    File system resource provider.

    Exposes files and directories as MCP resources with appropriate
    MIME types and content handling.
    """

    def __init__(
        self, base_paths: list[str], allowed_extensions: list[str] | None = None
    ):
        """
        Initialize file resource provider.

        Args:
            base_paths: List of base directory paths to expose
            allowed_extensions: Optional list of allowed file extensions
        """
        self.base_paths = [Path(p).resolve() for p in base_paths]
        self.allowed_extensions = allowed_extensions or []

        # Ensure base paths exist
        for path in self.base_paths:
            if not path.exists():
                logger.warning(f'Base path does not exist: {path}')

    async def list_resources(self) -> list[MCPResource]:
        """List all files in base paths as resources."""
        resources = []

        for base_path in self.base_paths:
            if not base_path.exists():
                continue

            for file_path in base_path.rglob('*'):
                if file_path.is_file() and self._is_allowed_file(file_path):
                    resource = await self._file_to_resource(file_path)
                    if resource:
                        resources.append(resource)

        return resources

    async def get_resource(self, uri: str) -> MCPResourceContents | None:
        """Get file contents by file:// URI."""
        if not uri.startswith('file://'):
            return None

        try:
            file_path = Path(urlparse(uri).path)

            # Security check: ensure file is under allowed base paths
            if not self._is_allowed_path(file_path):
                logger.warning(f'Access denied to file outside base paths: {file_path}')
                return None

            if not file_path.exists() or not file_path.is_file():
                return None

            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))

            # Read file contents
            if self._is_text_file(file_path, mime_type):
                # Read as text
                try:
                    content = file_path.read_text(encoding='utf-8')
                    return MCPResourceContents(
                        uri=uri, mimeType=mime_type, text=content
                    )
                except UnicodeDecodeError:
                    # Fall back to binary
                    pass

            # Read as binary and encode as base64
            content = file_path.read_bytes()
            blob = base64.b64encode(content).decode('utf-8')

            return MCPResourceContents(uri=uri, mimeType=mime_type, blob=blob)

        except Exception as e:
            logger.error(f'Error reading file resource {uri}: {e}')
            return None

    def get_resource_templates(self) -> list[MCPResourceTemplate]:
        """Get templates for file resources."""
        templates = []

        for base_path in self.base_paths:
            templates.append(
                MCPResourceTemplate(
                    uriTemplate=f'file://{base_path}/{{+path}}',
                    name=f'Files in {base_path.name}',
                    description=f'Access files in directory: {base_path}',
                    mimeType=None,  # Will be determined per file
                )
            )

        return templates

    def supports_uri(self, uri: str) -> bool:
        """Check if URI is a file:// URI in allowed paths."""
        if not uri.startswith('file://'):
            return False

        try:
            file_path = Path(urlparse(uri).path)
            return self._is_allowed_path(file_path)
        except Exception:
            return False

    def _is_allowed_file(self, file_path: Path) -> bool:
        """Check if file is allowed based on extension and path."""
        if not self._is_allowed_path(file_path):
            return False

        if self.allowed_extensions:
            return file_path.suffix.lower() in self.allowed_extensions

        return True

    def _is_allowed_path(self, file_path: Path) -> bool:
        """Check if file path is under allowed base paths."""
        try:
            resolved_path = file_path.resolve()
            for base_path in self.base_paths:
                if resolved_path.is_relative_to(base_path):
                    return True
        except Exception:
            pass
        return False

    def _is_text_file(self, file_path: Path, mime_type: str | None) -> bool:
        """Determine if file should be read as text."""
        if mime_type:
            if mime_type.startswith('text/'):
                return True
            if mime_type in [
                'application/json',
                'application/xml',
                'application/javascript',
            ]:
                return True

        # Check file extension
        text_extensions = {
            '.txt',
            '.md',
            '.py',
            '.js',
            '.ts',
            '.html',
            '.css',
            '.json',
            '.xml',
            '.yaml',
            '.yml',
            '.toml',
            '.ini',
            '.cfg',
            '.log',
        }
        return file_path.suffix.lower() in text_extensions

    async def _file_to_resource(self, file_path: Path) -> MCPResource | None:
        """Convert file path to MCP resource."""
        try:
            uri = f'file://{file_path.as_posix()}'
            mime_type, _ = mimetypes.guess_type(str(file_path))

            return MCPResource(
                uri=uri,
                name=file_path.name,
                description=f'File: {file_path.as_posix()}',
                mimeType=mime_type,
            )
        except Exception as e:
            logger.error(f'Error converting file to resource {file_path}: {e}')
            return None


class KnowledgeBaseResourceProvider(MCPResourceProvider):
    """
    Knowledge base resource provider.

    Exposes documents and articles from the Thoth knowledge base
    as MCP resources.
    """

    def __init__(self, service_manager):
        """Initialize with service manager for database access."""
        self.service_manager = service_manager

    async def list_resources(self) -> list[MCPResource]:
        """List all documents in the knowledge base."""
        resources = []

        try:
            # Knowledge base integration is not yet implemented
            # This provider is currently a stub
            logger.warning('Knowledge base resource provider not yet implemented')

        except Exception as e:
            logger.error(f'Error listing knowledge base resources: {e}')

        return resources

    async def get_resource(self, uri: str) -> MCPResourceContents | None:
        """Get article content by knowledge:// URI."""
        if not uri.startswith('knowledge://'):
            return None

        try:
            # Knowledge base integration is not yet implemented
            logger.warning('Knowledge base resource retrieval not yet implemented')
            return None

        except Exception as e:
            logger.error(f'Error getting knowledge base resource {uri}: {e}')
            return None

    def get_resource_templates(self) -> list[MCPResourceTemplate]:
        """Get templates for knowledge base resources."""
        return [
            MCPResourceTemplate(
                uriTemplate='knowledge://{article_id}',
                name='Knowledge Base Articles',
                description='Access articles from the Thoth knowledge base',
                mimeType='text/plain',
            )
        ]

    def supports_uri(self, uri: str) -> bool:
        """Check if URI is a knowledge:// URI."""
        return uri.startswith('knowledge://')


class MCPResourceManager:
    """
    Manager for all MCP resource providers.

    Coordinates multiple resource providers and provides a unified
    interface for resource discovery and access.
    """

    def __init__(self):
        self.providers: list[MCPResourceProvider] = []

    def add_provider(self, provider: MCPResourceProvider):
        """Add a resource provider."""
        self.providers.append(provider)
        logger.info(f'Added resource provider: {provider.__class__.__name__}')

    async def list_all_resources(self) -> list[MCPResource]:
        """List resources from all providers."""
        all_resources = []

        for provider in self.providers:
            try:
                resources = await provider.list_resources()
                all_resources.extend(resources)
            except Exception as e:
                logger.error(
                    f'Error listing resources from {provider.__class__.__name__}: {e}'
                )

        return all_resources

    async def get_resource(self, uri: str) -> MCPResourceContents | None:
        """Get resource contents from appropriate provider."""
        for provider in self.providers:
            try:
                if provider.supports_uri(uri):
                    contents = await provider.get_resource(uri)
                    if contents:
                        return contents
            except Exception as e:
                logger.error(
                    f'Error getting resource {uri} from {provider.__class__.__name__}: {e}'
                )

        return None

    def get_all_resource_templates(self) -> list[MCPResourceTemplate]:
        """Get resource templates from all providers."""
        all_templates = []

        for provider in self.providers:
            try:
                templates = provider.get_resource_templates()
                all_templates.extend(templates)
            except Exception as e:
                logger.error(
                    f'Error getting templates from {provider.__class__.__name__}: {e}'
                )

        return all_templates

    def get_supported_uri_schemes(self) -> list[str]:
        """Get list of supported URI schemes."""
        schemes = set()

        for provider in self.providers:
            templates = provider.get_resource_templates()
            for template in templates:
                uri_scheme = template.uriTemplate.split('://')[0]
                schemes.add(uri_scheme)

        return list(schemes)
