#!/usr/bin/env python3
"""
Health check script for Thoth Docker containers.

This script performs comprehensive health checks for all Thoth services
and reports the overall system health status.
"""

import asyncio
import json
import logging
import sys
import time
from typing import Any

import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ThothHealthChecker:
    """Comprehensive health checker for Thoth services."""

    def __init__(self):
        self.api_url = 'http://localhost:8000'
        self.mcp_url = 'http://localhost:8001'
        self.chromadb_url = 'http://chromadb:8003'
        self.timeout = 10

    async def check_api_server(self) -> dict[str, Any]:
        """Check main API server health."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(self.timeout)
            ) as session:
                async with session.get(f'{self.api_url}/health') as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'status': 'healthy',
                            'response_time': response.headers.get(
                                'X-Response-Time', 'N/A'
                            ),
                            'data': data,
                        }
                    else:
                        return {
                            'status': 'unhealthy',
                            'error': f'HTTP {response.status}',
                            'response_time': response.headers.get(
                                'X-Response-Time', 'N/A'
                            ),
                        }
        except TimeoutError:
            return {'status': 'unhealthy', 'error': 'Timeout'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}

    async def check_mcp_server(self) -> dict[str, Any]:
        """Check MCP server health."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(self.timeout)
            ) as session:
                # Try to access MCP health endpoint (if available)
                async with session.get(f'{self.mcp_url}/health') as response:
                    if response.status == 200:
                        return {
                            'status': 'healthy',
                            'response_time': response.headers.get(
                                'X-Response-Time', 'N/A'
                            ),
                        }
                    else:
                        return {
                            'status': 'unhealthy',
                            'error': f'HTTP {response.status}',
                        }
        except TimeoutError:
            return {'status': 'unhealthy', 'error': 'Timeout'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}

    async def check_chromadb(self) -> dict[str, Any]:
        """Check ChromaDB health."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(self.timeout)
            ) as session:
                async with session.get(
                    f'{self.chromadb_url}/api/v1/heartbeat'
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'status': 'healthy',
                            'response_time': response.headers.get(
                                'X-Response-Time', 'N/A'
                            ),
                            'nanosecond_heartbeat': data.get('nanosecond heartbeat'),
                        }
                    else:
                        return {
                            'status': 'unhealthy',
                            'error': f'HTTP {response.status}',
                        }
        except TimeoutError:
            return {'status': 'unhealthy', 'error': 'Timeout'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}

    async def check_agent_system(self) -> dict[str, Any]:
        """Check research agent system health."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(self.timeout)
            ) as session:
                async with session.get(f'{self.api_url}/agent/status') as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'status': 'healthy'
                            if data.get('agent_initialized')
                            else 'unhealthy',
                            'agent_initialized': data.get('agent_initialized', False),
                            'tools_count': data.get('tools_count', 0),
                        }
                    else:
                        return {
                            'status': 'unhealthy',
                            'error': f'HTTP {response.status}',
                        }
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}

    async def check_basic_functionality(self) -> dict[str, Any]:
        """Check basic functionality with a simple test."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(self.timeout)
            ) as session:
                test_data = {'message': 'health check test'}
                async with session.post(
                    f'{self.api_url}/research/chat', json=test_data
                ) as response:
                    if response.status == 200:
                        return {
                            'status': 'healthy',
                            'functionality': 'basic_chat_working',
                        }
                    elif response.status == 503:
                        return {
                            'status': 'degraded',
                            'functionality': 'service_unavailable',
                        }
                    else:
                        return {
                            'status': 'unhealthy',
                            'error': f'HTTP {response.status}',
                        }
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}

    async def run_all_checks(self) -> dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        start_time = time.time()

        logger.info('Starting comprehensive health checks...')

        # Run all checks concurrently
        checks = await asyncio.gather(
            self.check_api_server(),
            self.check_mcp_server(),
            self.check_chromadb(),
            self.check_agent_system(),
            self.check_basic_functionality(),
            return_exceptions=True,
        )

        api_health, mcp_health, chromadb_health, agent_health, functionality_health = (
            checks
        )

        # Determine overall status
        all_checks = [
            api_health,
            mcp_health,
            chromadb_health,
            agent_health,
            functionality_health,
        ]
        healthy_count = sum(
            1 for check in all_checks if check.get('status') == 'healthy'
        )
        degraded_count = sum(
            1 for check in all_checks if check.get('status') == 'degraded'
        )
        unhealthy_count = sum(
            1 for check in all_checks if check.get('status') == 'unhealthy'
        )

        if unhealthy_count == 0 and degraded_count == 0:
            overall_status = 'healthy'
        elif unhealthy_count == 0:
            overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'

        total_time = time.time() - start_time

        return {
            'overall_status': overall_status,
            'timestamp': int(time.time()),
            'check_duration_seconds': round(total_time, 2),
            'services': {
                'api_server': api_health,
                'mcp_server': mcp_health,
                'chromadb': chromadb_health,
                'agent_system': agent_health,
                'basic_functionality': functionality_health,
            },
            'summary': {
                'total_checks': len(all_checks),
                'healthy': healthy_count,
                'degraded': degraded_count,
                'unhealthy': unhealthy_count,
            },
        }


async def main():
    """Main health check function."""
    checker = ThothHealthChecker()

    try:
        results = await checker.run_all_checks()

        # Print results
        print(json.dumps(results, indent=2))

        # Exit with appropriate code
        if results['overall_status'] == 'healthy':
            logger.info('All systems healthy')
            sys.exit(0)
        elif results['overall_status'] == 'degraded':
            logger.warning('Some systems degraded')
            sys.exit(1)
        else:
            logger.error('System unhealthy')
            sys.exit(2)

    except Exception as e:
        logger.error(f'Health check failed: {e}')
        print(
            json.dumps(
                {
                    'overall_status': 'unhealthy',
                    'error': str(e),
                    'timestamp': int(time.time()),
                },
                indent=2,
            )
        )
        sys.exit(3)


if __name__ == '__main__':
    # Simple synchronous version for Docker health checks
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--simple':
        # Simple health check for Docker
        import requests

        try:
            response = requests.get('http://localhost:8000/health', timeout=5)
            if response.status_code == 200:
                print('healthy')
                sys.exit(0)
            else:
                print('unhealthy')
                sys.exit(1)
        except Exception:
            print('unhealthy')
            sys.exit(1)
    else:
        # Full async health check
        asyncio.run(main())
