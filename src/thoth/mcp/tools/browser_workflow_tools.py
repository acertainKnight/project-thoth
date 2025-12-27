"""
MCP-compliant browser workflow management tools.

This module provides MCP-compliant tools for AI agents to create and manage
browser-based discovery workflows, including action configuration, search setup,
execution, and monitoring.
"""

from typing import Any
from uuid import UUID
import json

from loguru import logger

from ..base_tools import MCPTool, MCPToolCallResult, NoInputTool


class CreateBrowserWorkflowMCPTool(MCPTool):
    """MCP tool for creating a new browser workflow."""

    @property
    def name(self) -> str:
        return 'create_browser_workflow'

    @property
    def description(self) -> str:
        return (
            'Create a new browser workflow for automated discovery. '
            'Returns workflow_id for use with other workflow tools.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': 'Unique name for the workflow',
                },
                'website_domain': {
                    'type': 'string',
                    'description': 'Domain of the target website (e.g., arxiv.org)',
                },
                'start_url': {
                    'type': 'string',
                    'description': 'Starting URL for the workflow',
                },
                'description': {
                    'type': 'string',
                    'description': 'Description of what this workflow does',
                },
                'extraction_rules': {
                    'type': 'object',
                    'description': 'JSON object defining how to extract article data',
                    'default': {},
                },
                'is_active': {
                    'type': 'boolean',
                    'description': 'Whether workflow is active',
                    'default': True,
                },
            },
            'required': ['name', 'website_domain', 'start_url', 'description'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create a new browser workflow."""
        try:
            from thoth.repositories.browser_workflow_repository import (
                BrowserWorkflowRepository,
            )

            # Get postgres service from service manager
            postgres_service = self.service_manager.postgres
            workflow_repo = BrowserWorkflowRepository(postgres_service)

            # Prepare workflow data
            workflow_data = {
                'name': arguments['name'],
                'website_domain': arguments['website_domain'],
                'start_url': arguments['start_url'],
                'description': arguments.get('description', ''),
                'extraction_rules': arguments.get('extraction_rules', {}),
                'is_active': arguments.get('is_active', True),
            }

            # Create workflow
            workflow_id = await workflow_repo.create(workflow_data)

            if workflow_id:
                result_text = f"""✓ Browser workflow created successfully!

**Workflow ID:** {workflow_id}
**Name:** {workflow_data['name']}
**Domain:** {workflow_data['website_domain']}
**Start URL:** {workflow_data['start_url']}
**Status:** {'Active' if workflow_data['is_active'] else 'Inactive'}

Next steps:
1. Add actions with `add_workflow_action`
2. Configure search with `configure_search`
3. Execute with `execute_workflow`
"""
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': result_text}]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '✗ Failed to create workflow. Check logs for details.',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            logger.error(f'Error creating browser workflow: {e}')
            return self.handle_error(e)


class AddWorkflowActionMCPTool(MCPTool):
    """MCP tool for adding an action step to a workflow."""

    @property
    def name(self) -> str:
        return 'add_workflow_action'

    @property
    def description(self) -> str:
        return (
            'Add an action step to a browser workflow. Actions define what the '
            'browser should do (navigate, click, extract, etc.). Returns action_id.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'workflow_id': {
                    'type': 'string',
                    'description': 'UUID of the workflow to add action to',
                },
                'action_type': {
                    'type': 'string',
                    'description': 'Type of action',
                    'enum': [
                        'navigate',
                        'click',
                        'type',
                        'extract',
                        'wait',
                        'scroll',
                        'screenshot',
                    ],
                },
                'selector': {
                    'type': 'string',
                    'description': 'CSS selector for the target element (optional for navigate)',
                },
                'value': {
                    'type': 'string',
                    'description': 'Value to use (e.g., text to type, URL to navigate)',
                },
                'step_number': {
                    'type': 'integer',
                    'description': 'Position in workflow sequence (auto-increments if not provided)',
                    'minimum': 1,
                },
                'action_config': {
                    'type': 'object',
                    'description': 'Additional configuration for the action',
                    'default': {},
                },
            },
            'required': ['workflow_id', 'action_type'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Add an action step to a workflow."""
        try:
            from thoth.repositories.workflow_actions_repository import (
                WorkflowActionsRepository,
            )

            postgres_service = self.service_manager.postgres
            actions_repo = WorkflowActionsRepository(postgres_service)

            workflow_id = UUID(arguments['workflow_id'])

            # Get current step count if step_number not provided
            if 'step_number' not in arguments:
                step_count = await actions_repo.get_step_count(workflow_id)
                arguments['step_number'] = step_count + 1

            # Prepare action data
            action_data = {
                'workflow_id': workflow_id,
                'step_number': arguments['step_number'],
                'action_type': arguments['action_type'],
                'action_config': arguments.get('action_config', {}),
            }

            # Add optional fields
            if 'selector' in arguments:
                action_data['selector'] = arguments['selector']
            if 'value' in arguments:
                action_data['value'] = arguments['value']

            # Create action
            action_id = await actions_repo.create(action_data)

            if action_id:
                result_text = f"""✓ Workflow action added successfully!

**Action ID:** {action_id}
**Workflow ID:** {workflow_id}
**Step:** {action_data['step_number']}
**Type:** {action_data['action_type']}
"""
                if 'selector' in action_data:
                    result_text += f"**Selector:** {action_data['selector']}\n"
                if 'value' in action_data:
                    result_text += f"**Value:** {action_data['value']}\n"

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': result_text}]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '✗ Failed to add action. Check logs for details.',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            logger.error(f'Error adding workflow action: {e}')
            return self.handle_error(e)


class ConfigureSearchMCPTool(MCPTool):
    """MCP tool for configuring search parameters for a workflow."""

    @property
    def name(self) -> str:
        return 'configure_search'

    @property
    def description(self) -> str:
        return (
            'Configure search result extraction for a browser workflow. '
            'Defines selectors for identifying and extracting search results. '
            'Returns config_id.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'workflow_id': {
                    'type': 'string',
                    'description': 'UUID of the workflow',
                },
                'search_input_selector': {
                    'type': 'string',
                    'description': 'CSS selector for search input field',
                },
                'search_button_selector': {
                    'type': 'string',
                    'description': 'CSS selector for search button',
                },
                'result_selector': {
                    'type': 'string',
                    'description': 'CSS selector for result containers',
                },
                'title_selector': {
                    'type': 'string',
                    'description': 'CSS selector for result titles (relative to result)',
                },
                'url_selector': {
                    'type': 'string',
                    'description': 'CSS selector for result URLs (relative to result)',
                },
                'snippet_selector': {
                    'type': 'string',
                    'description': 'CSS selector for result snippets (optional)',
                },
                'max_results': {
                    'type': 'integer',
                    'description': 'Maximum number of results to extract',
                    'default': 100,
                    'minimum': 1,
                },
                'pagination_config': {
                    'type': 'object',
                    'description': 'Configuration for handling pagination',
                    'default': None,
                },
            },
            'required': [
                'workflow_id',
                'result_selector',
                'title_selector',
                'url_selector',
            ],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Configure search parameters for a workflow."""
        try:
            from thoth.repositories.workflow_search_config_repository import (
                WorkflowSearchConfigRepository,
            )

            postgres_service = self.service_manager.postgres
            config_repo = WorkflowSearchConfigRepository(postgres_service)

            workflow_id = UUID(arguments['workflow_id'])

            # Prepare config data
            config_data = {
                'workflow_id': workflow_id,
                'result_selector': arguments['result_selector'],
                'title_selector': arguments['title_selector'],
                'url_selector': arguments['url_selector'],
                'max_results': arguments.get('max_results', 100),
            }

            # Add optional fields
            if 'snippet_selector' in arguments:
                config_data['snippet_selector'] = arguments['snippet_selector']
            if 'pagination_config' in arguments:
                config_data['pagination_config'] = arguments['pagination_config']

            # Create config
            config_id = await config_repo.create(config_data)

            if config_id:
                result_text = f"""✓ Search configuration created successfully!

**Config ID:** {config_id}
**Workflow ID:** {workflow_id}
**Result Selector:** {config_data['result_selector']}
**Title Selector:** {config_data['title_selector']}
**URL Selector:** {config_data['url_selector']}
**Max Results:** {config_data['max_results']}
"""
                if 'snippet_selector' in config_data:
                    result_text += (
                        f"**Snippet Selector:** {config_data['snippet_selector']}\n"
                    )

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': result_text}]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '✗ Failed to create search config. Check logs for details.',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            logger.error(f'Error configuring search: {e}')
            return self.handle_error(e)


class ExecuteWorkflowMCPTool(MCPTool):
    """MCP tool for executing a browser workflow."""

    @property
    def name(self) -> str:
        return 'execute_workflow'

    @property
    def description(self) -> str:
        return (
            'Execute a browser workflow to discover and extract articles. '
            'Returns execution results including articles found.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'workflow_id': {
                    'type': 'string',
                    'description': 'UUID of the workflow to execute',
                },
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Search keywords (optional)',
                    'default': [],
                },
                'date_range': {
                    'type': 'object',
                    'properties': {
                        'start': {'type': 'string', 'description': 'Start date (YYYY-MM-DD)'},
                        'end': {'type': 'string', 'description': 'End date (YYYY-MM-DD)'},
                    },
                    'description': 'Date range filter (optional)',
                },
                'max_articles': {
                    'type': 'integer',
                    'description': 'Maximum articles to extract',
                    'default': 50,
                    'minimum': 1,
                },
            },
            'required': ['workflow_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute a browser workflow."""
        try:
            from thoth.repositories.browser_workflow_repository import (
                BrowserWorkflowRepository,
            )
            from thoth.repositories.workflow_actions_repository import (
                WorkflowActionsRepository,
            )
            from thoth.repositories.workflow_search_config_repository import (
                WorkflowSearchConfigRepository,
            )
            from thoth.repositories.workflow_executions_repository import (
                WorkflowExecutionsRepository,
            )
            import time

            postgres_service = self.service_manager.postgres
            workflow_repo = BrowserWorkflowRepository(postgres_service)
            actions_repo = WorkflowActionsRepository(postgres_service)
            config_repo = WorkflowSearchConfigRepository(postgres_service)
            executions_repo = WorkflowExecutionsRepository(postgres_service)

            workflow_id = UUID(arguments['workflow_id'])
            start_time = time.time()

            # Get workflow details
            workflow = await workflow_repo.get_by_id(workflow_id)
            if not workflow:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'✗ Workflow not found: {workflow_id}',
                        }
                    ],
                    isError=True,
                )

            # Check if workflow is active
            if not workflow.get('is_active', True):
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'✗ Workflow is not active: {workflow["name"]}',
                        }
                    ],
                    isError=True,
                )

            # Get actions
            actions = await actions_repo.get_by_workflow_id(workflow_id)
            if not actions:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '✗ No actions defined for workflow. Add actions first.',
                        }
                    ],
                    isError=True,
                )

            # Get search config
            search_config = await config_repo.get_by_workflow_id(workflow_id)

            # TODO: This is a placeholder for actual browser automation
            # In production, this would use Playwright/Selenium to execute the workflow
            result_text = f"""✓ Workflow execution initiated!

**Workflow:** {workflow['name']}
**Domain:** {workflow['website_domain']}
**Actions:** {len(actions)} steps
**Search Config:** {'Configured' if search_config else 'Not configured'}

⚠️ Note: Full browser automation requires Playwright integration.
This is a placeholder response. Actual execution would:
1. Launch browser session
2. Execute {len(actions)} action steps
3. Extract articles using search config
4. Store results in database

**Execution Parameters:**
- Keywords: {arguments.get('keywords', [])}
- Max Articles: {arguments.get('max_articles', 50)}
"""

            # Record execution (placeholder)
            duration_ms = int((time.time() - start_time) * 1000)
            articles_found = 0  # Placeholder

            # Update workflow statistics
            await workflow_repo.update_statistics(
                workflow_id, success=True, articles_found=articles_found, duration_ms=duration_ms
            )

            result_text += f"\n**Duration:** {duration_ms}ms"
            result_text += f"\n**Articles Found:** {articles_found}"

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            logger.error(f'Error executing workflow: {e}')
            return self.handle_error(e)


class ListWorkflowsMCPTool(NoInputTool):
    """MCP tool for listing all browser workflows."""

    @property
    def name(self) -> str:
        return 'list_workflows'

    @property
    def description(self) -> str:
        return 'List all browser workflows with their statistics and health status'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """List all browser workflows."""
        try:
            from thoth.repositories.browser_workflow_repository import (
                BrowserWorkflowRepository,
            )

            postgres_service = self.service_manager.postgres
            workflow_repo = BrowserWorkflowRepository(postgres_service)

            # Get all active workflows
            workflows = await workflow_repo.get_active_workflows()

            if not workflows:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No browser workflows found. Create one with create_browser_workflow!',
                        }
                    ]
                )

            # Get overall statistics
            stats = await workflow_repo.get_statistics()

            # Format response
            result_text = f"""**Browser Workflows Summary**

Total Workflows: {stats.get('total_workflows', 0)}
Active: {stats.get('active_workflows', 0)}
Healthy: {stats.get('healthy_workflows', 0)}
Total Executions: {stats.get('total_executions', 0) or 0}
Success Rate: {(stats.get('successful_executions', 0) or 0) / max(stats.get('total_executions', 1), 1) * 100:.1f}%
Total Articles: {stats.get('total_articles_extracted', 0) or 0}

---

**Individual Workflows:**

"""

            for workflow in workflows:
                result_text += f"""**{workflow['name']}**
  - ID: {workflow['id']}
  - Domain: {workflow['website_domain']}
  - Health: {workflow.get('health_status', 'unknown')}
  - Executions: {workflow.get('total_executions', 0)}
  - Success Rate: {(workflow.get('successful_executions', 0) / max(workflow.get('total_executions', 1), 1) * 100):.1f}%
  - Articles Extracted: {workflow.get('total_articles_extracted', 0) or 0}
  - Avg Duration: {workflow.get('average_execution_time_ms', 0) or 0:.0f}ms
  - Last Run: {workflow.get('last_executed_at', 'Never')}

"""

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            logger.error(f'Error listing workflows: {e}')
            return self.handle_error(e)


class GetWorkflowDetailsMCPTool(MCPTool):
    """MCP tool for getting detailed information about a specific workflow."""

    @property
    def name(self) -> str:
        return 'get_workflow_details'

    @property
    def description(self) -> str:
        return (
            'Get detailed information about a browser workflow including '
            'actions, search config, and execution history'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'workflow_id': {
                    'type': 'string',
                    'description': 'UUID of the workflow',
                },
            },
            'required': ['workflow_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get detailed workflow information."""
        try:
            from thoth.repositories.browser_workflow_repository import (
                BrowserWorkflowRepository,
            )
            from thoth.repositories.workflow_actions_repository import (
                WorkflowActionsRepository,
            )
            from thoth.repositories.workflow_search_config_repository import (
                WorkflowSearchConfigRepository,
            )

            postgres_service = self.service_manager.postgres
            workflow_repo = BrowserWorkflowRepository(postgres_service)
            actions_repo = WorkflowActionsRepository(postgres_service)
            config_repo = WorkflowSearchConfigRepository(postgres_service)

            workflow_id = UUID(arguments['workflow_id'])

            # Get workflow
            workflow = await workflow_repo.get_by_id(workflow_id)
            if not workflow:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'✗ Workflow not found: {workflow_id}',
                        }
                    ],
                    isError=True,
                )

            # Get actions
            actions = await actions_repo.get_by_workflow_id(workflow_id)

            # Get search config
            search_config = await config_repo.get_by_workflow_id(workflow_id)

            # Format response
            result_text = f"""**Workflow Details: {workflow['name']}**

**Basic Information:**
- ID: {workflow['id']}
- Domain: {workflow['website_domain']}
- Start URL: {workflow['start_url']}
- Description: {workflow.get('description', 'N/A')}
- Status: {'Active' if workflow.get('is_active') else 'Inactive'}
- Health: {workflow.get('health_status', 'unknown')}

**Statistics:**
- Total Executions: {workflow.get('total_executions', 0)}
- Successful: {workflow.get('successful_executions', 0)}
- Failed: {workflow.get('failed_executions', 0)}
- Success Rate: {(workflow.get('successful_executions', 0) / max(workflow.get('total_executions', 1), 1) * 100):.1f}%
- Articles Extracted: {workflow.get('total_articles_extracted', 0) or 0}
- Avg Duration: {workflow.get('average_execution_time_ms', 0) or 0:.0f}ms
- Last Executed: {workflow.get('last_executed_at', 'Never')}
- Last Success: {workflow.get('last_success_at', 'Never')}

**Actions ({len(actions)} steps):**
"""

            for action in actions:
                result_text += f"""  Step {action['step_number']}: {action['action_type']}
"""
                if action.get('selector'):
                    result_text += f"    - Selector: {action['selector']}\n"
                if action.get('value'):
                    result_text += f"    - Value: {action['value']}\n"

            if search_config:
                result_text += f"""
**Search Configuration:**
- Result Selector: {search_config['result_selector']}
- Title Selector: {search_config['title_selector']}
- URL Selector: {search_config['url_selector']}
"""
                if search_config.get('snippet_selector'):
                    result_text += (
                        f"- Snippet Selector: {search_config['snippet_selector']}\n"
                    )
                result_text += f"- Max Results: {search_config.get('max_results', 100)}\n"
            else:
                result_text += "\n**Search Configuration:** Not configured\n"

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            logger.error(f'Error getting workflow details: {e}')
            return self.handle_error(e)


class UpdateWorkflowStatusMCPTool(MCPTool):
    """MCP tool for updating workflow status (activate/deactivate)."""

    @property
    def name(self) -> str:
        return 'update_workflow_status'

    @property
    def description(self) -> str:
        return 'Activate or deactivate a browser workflow'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'workflow_id': {
                    'type': 'string',
                    'description': 'UUID of the workflow',
                },
                'is_active': {
                    'type': 'boolean',
                    'description': 'Set workflow active status',
                },
            },
            'required': ['workflow_id', 'is_active'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Update workflow status."""
        try:
            from thoth.repositories.browser_workflow_repository import (
                BrowserWorkflowRepository,
            )

            postgres_service = self.service_manager.postgres
            workflow_repo = BrowserWorkflowRepository(postgres_service)

            workflow_id = UUID(arguments['workflow_id'])
            is_active = arguments['is_active']

            # Update status
            if is_active:
                success = await workflow_repo.activate(workflow_id)
            else:
                success = await workflow_repo.deactivate(workflow_id)

            if success:
                status_text = 'activated' if is_active else 'deactivated'
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'✓ Workflow {status_text} successfully!',
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '✗ Failed to update workflow status. Check logs.',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            logger.error(f'Error updating workflow status: {e}')
            return self.handle_error(e)


class DeleteWorkflowMCPTool(MCPTool):
    """MCP tool for deleting a browser workflow."""

    @property
    def name(self) -> str:
        return 'delete_workflow'

    @property
    def description(self) -> str:
        return 'Delete a browser workflow and all its associated data (actions, config, executions)'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'workflow_id': {
                    'type': 'string',
                    'description': 'UUID of the workflow to delete',
                },
            },
            'required': ['workflow_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Delete a workflow."""
        try:
            from thoth.repositories.browser_workflow_repository import (
                BrowserWorkflowRepository,
            )

            postgres_service = self.service_manager.postgres
            workflow_repo = BrowserWorkflowRepository(postgres_service)

            workflow_id = UUID(arguments['workflow_id'])

            # Get workflow name before deleting
            workflow = await workflow_repo.get_by_id(workflow_id)
            if not workflow:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'✗ Workflow not found: {workflow_id}',
                        }
                    ],
                    isError=True,
                )

            workflow_name = workflow['name']

            # Delete workflow (cascade will delete actions, config, executions)
            success = await workflow_repo.delete(workflow_id)

            if success:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'✓ Workflow "{workflow_name}" deleted successfully!',
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '✗ Failed to delete workflow. Check logs.',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            logger.error(f'Error deleting workflow: {e}')
            return self.handle_error(e)
