"""
MCP Deployment Configuration

Provides environment-specific configurations for different deployment scenarios:
- Local development
- Cloud services (AWS, GCP, Azure)
- Multi-server production deployments
- Container orchestration (Docker, Kubernetes)
"""

import os
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

from .connection_manager import ConnectionConfig


class DeploymentEnvironment(Enum):
    """Supported deployment environments."""

    DEVELOPMENT = 'development'
    STAGING = 'staging'
    PRODUCTION = 'production'
    CLOUD_AWS = 'cloud_aws'
    CLOUD_GCP = 'cloud_gcp'
    CLOUD_AZURE = 'cloud_azure'
    KUBERNETES = 'kubernetes'
    DOCKER_SWARM = 'docker_swarm'


@dataclass
class MCPDeploymentConfig:
    """Configuration for MCP deployment in different environments."""

    environment: DeploymentEnvironment

    # Connection settings
    servers: list[ConnectionConfig] = field(default_factory=list)
    load_balancing: bool = False
    high_availability: bool = False

    # Performance settings
    connection_pool_size: int = 10
    max_concurrent_requests: int = 100
    request_timeout: int = 30
    health_check_interval: int = 60

    # Reliability settings
    retry_attempts: int = 3
    retry_delay: float = 1.0
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60

    # Monitoring settings
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_distributed_tracing: bool = False
    log_level: str = 'INFO'

    # Security settings
    enable_tls: bool = False
    tls_cert_path: str | None = None
    tls_key_path: str | None = None
    api_key_required: bool = False

    # Cloud-specific settings
    cloud_region: str | None = None
    cloud_zone: str | None = None
    auto_scaling: bool = False

    # Container settings
    container_limits: dict[str, str] = field(
        default_factory=lambda: {'memory': '512Mi', 'cpu': '500m'}
    )

    def __post_init__(self):
        """Validate and adjust configuration based on environment."""
        if self.environment == DeploymentEnvironment.PRODUCTION:
            self.high_availability = True
            self.circuit_breaker_enabled = True
            self.enable_metrics = True
            self.log_level = 'INFO'

        elif self.environment == DeploymentEnvironment.DEVELOPMENT:
            self.connection_pool_size = 5
            self.health_check_interval = 30
            self.log_level = 'DEBUG'

        elif self.environment.value.startswith('cloud_'):
            self.high_availability = True
            self.auto_scaling = True
            self.enable_distributed_tracing = True
            self.enable_metrics = True

        elif self.environment == DeploymentEnvironment.KUBERNETES:
            self.load_balancing = True
            self.high_availability = True
            self.enable_metrics = True


class MCPDeploymentManager:
    """
    Manages MCP deployment configurations for different environments.

    Provides environment detection, configuration loading, and
    deployment-specific optimizations.
    """

    def __init__(self):
        self.current_environment = self._detect_environment()
        self.config = self._load_config()

    def _detect_environment(self) -> DeploymentEnvironment:
        """Auto-detect deployment environment from environment variables."""
        env_name = os.getenv('THOTH_ENVIRONMENT', 'development').lower()

        # Check for cloud environments
        if os.getenv('AWS_REGION'):
            return DeploymentEnvironment.CLOUD_AWS
        elif os.getenv('GOOGLE_CLOUD_PROJECT'):
            return DeploymentEnvironment.CLOUD_GCP
        elif os.getenv('AZURE_RESOURCE_GROUP'):
            return DeploymentEnvironment.CLOUD_AZURE

        # Check for container orchestration
        elif os.getenv('KUBERNETES_SERVICE_HOST'):
            return DeploymentEnvironment.KUBERNETES
        elif os.getenv('DOCKER_SWARM_MODE'):
            return DeploymentEnvironment.DOCKER_SWARM

        # Standard environments
        elif env_name in ['production', 'prod']:
            return DeploymentEnvironment.PRODUCTION
        elif env_name in ['staging', 'stage']:
            return DeploymentEnvironment.STAGING
        else:
            return DeploymentEnvironment.DEVELOPMENT

    def _load_config(self) -> MCPDeploymentConfig:
        """Load environment-specific configuration."""
        logger.info(
            f'Loading MCP configuration for environment: {self.current_environment.value}'
        )

        config = MCPDeploymentConfig(environment=self.current_environment)

        # Load environment variables
        self._apply_env_overrides(config)

        # Add server configurations
        self._configure_servers(config)

        return config

    def _apply_env_overrides(self, config: MCPDeploymentConfig) -> None:
        """Apply environment variable overrides."""
        # Connection settings
        if pool_size := os.getenv('MCP_POOL_SIZE'):
            config.connection_pool_size = int(pool_size)

        if timeout := os.getenv('MCP_TIMEOUT'):
            config.request_timeout = int(timeout)

        if health_interval := os.getenv('MCP_HEALTH_INTERVAL'):
            config.health_check_interval = int(health_interval)

        # Reliability settings
        if retry_attempts := os.getenv('MCP_RETRY_ATTEMPTS'):
            config.retry_attempts = int(retry_attempts)

        if circuit_threshold := os.getenv('MCP_CIRCUIT_THRESHOLD'):
            config.circuit_breaker_threshold = int(circuit_threshold)

        # Monitoring
        if metrics_port := os.getenv('MCP_METRICS_PORT'):
            config.metrics_port = int(metrics_port)

        if log_level := os.getenv('MCP_LOG_LEVEL'):
            config.log_level = log_level.upper()

        # Security
        config.enable_tls = os.getenv('MCP_ENABLE_TLS', '').lower() == 'true'
        config.tls_cert_path = os.getenv('MCP_TLS_CERT_PATH')
        config.tls_key_path = os.getenv('MCP_TLS_KEY_PATH')
        config.api_key_required = (
            os.getenv('MCP_API_KEY_REQUIRED', '').lower() == 'true'
        )

        # Cloud settings
        config.cloud_region = os.getenv('CLOUD_REGION')
        config.cloud_zone = os.getenv('CLOUD_ZONE')
        config.auto_scaling = os.getenv('MCP_AUTO_SCALING', '').lower() == 'true'

    def _configure_servers(self, config: MCPDeploymentConfig) -> None:
        """Configure MCP servers based on environment."""
        # Get server configuration from environment
        mcp_urls = os.getenv('MCP_SERVERS', 'http://localhost:8001/mcp').split(',')

        for i, url in enumerate(mcp_urls):
            server_name = f'thoth-{i}' if len(mcp_urls) > 1 else 'thoth'

            server_config = ConnectionConfig(
                server_name=server_name,
                url=url.strip(),
                transport='streamable_http',
                max_connections=config.connection_pool_size,
                connection_timeout=config.request_timeout,
                retry_attempts=config.retry_attempts,
                retry_delay=config.retry_delay,
                health_check_interval=config.health_check_interval,
            )

            config.servers.append(server_config)

        # Enable load balancing if multiple servers
        if len(config.servers) > 1:
            config.load_balancing = True
            logger.info(
                f'Configured {len(config.servers)} MCP servers with load balancing'
            )

    def get_config(self) -> MCPDeploymentConfig:
        """Get the current deployment configuration."""
        return self.config

    def get_docker_compose_config(self) -> dict[str, any]:
        """Generate Docker Compose configuration for MCP services."""
        return {
            'version': '3.8',
            'services': {
                'thoth-mcp': {
                    'image': 'thoth:latest',
                    'environment': [
                        f'THOTH_ENVIRONMENT={self.current_environment.value}',
                        f'MCP_POOL_SIZE={self.config.connection_pool_size}',
                        f'MCP_TIMEOUT={self.config.request_timeout}',
                        f'MCP_LOG_LEVEL={self.config.log_level}',
                    ],
                    'ports': ['8001:8001'],
                    'healthcheck': {
                        'test': [
                            'CMD',
                            'curl',
                            '-f',
                            'http://localhost:8001/mcp/health',
                        ],
                        'interval': f'{self.config.health_check_interval}s',
                        'timeout': '10s',
                        'retries': 3,
                        'start_period': '30s',
                    },
                    'deploy': {
                        'replicas': 2 if self.config.high_availability else 1,
                        'resources': {
                            'limits': self.config.container_limits,
                            'reservations': {'memory': '256Mi', 'cpu': '250m'},
                        },
                    },
                }
            },
        }

    def get_kubernetes_config(self) -> dict[str, any]:
        """Generate Kubernetes configuration for MCP services."""
        replicas = 3 if self.config.high_availability else 1

        return {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {'name': 'thoth-mcp', 'labels': {'app': 'thoth-mcp'}},
            'spec': {
                'replicas': replicas,
                'selector': {'matchLabels': {'app': 'thoth-mcp'}},
                'template': {
                    'metadata': {'labels': {'app': 'thoth-mcp'}},
                    'spec': {
                        'containers': [
                            {
                                'name': 'thoth-mcp',
                                'image': 'thoth:latest',
                                'ports': [{'containerPort': 8001}],
                                'env': [
                                    {
                                        'name': 'THOTH_ENVIRONMENT',
                                        'value': self.current_environment.value,
                                    },
                                    {
                                        'name': 'MCP_POOL_SIZE',
                                        'value': str(self.config.connection_pool_size),
                                    },
                                    {
                                        'name': 'MCP_LOG_LEVEL',
                                        'value': self.config.log_level,
                                    },
                                ],
                                'resources': {
                                    'limits': self.config.container_limits,
                                    'requests': {'memory': '256Mi', 'cpu': '250m'},
                                },
                                'livenessProbe': {
                                    'httpGet': {'path': '/mcp/health', 'port': 8001},
                                    'initialDelaySeconds': 30,
                                    'periodSeconds': self.config.health_check_interval,
                                },
                                'readinessProbe': {
                                    'httpGet': {'path': '/mcp/health', 'port': 8001},
                                    'initialDelaySeconds': 5,
                                    'periodSeconds': 10,
                                },
                            }
                        ]
                    },
                },
            },
        }


# Global deployment manager instance
mcp_deployment_manager = MCPDeploymentManager()
