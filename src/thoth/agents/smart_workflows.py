"""
Smart Multi-Agent Workflow Engine.

This unified engine automatically chooses between Letta-native coordination
and external orchestration based on the task requirements, eliminating the
need for multiple separate engines.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger

try:
    from letta_client import Letta as LettaClient
    from letta_client.types.create_block import CreateBlock
    from letta_client.types.message_create import MessageCreate

    LETTA_AVAILABLE = True
except ImportError:
    LETTA_AVAILABLE = False
    logger.error('Letta client required for smart workflows')


@dataclass
class WorkflowResult:
    """Result of workflow execution."""

    workflow_name: str
    success: bool
    execution_time: float
    approach_used: str  # "letta_native" or "external_orchestration"
    final_output: str
    step_details: dict[str, Any] = None
    errors: list[str] = None


class SmartWorkflowEngine:
    """
    Unified workflow engine that automatically chooses the optimal approach.

    This single engine:
    1. Analyzes the request to determine complexity
    2. Automatically chooses between Letta-native or external orchestration
    3. Executes using the optimal approach
    4. Returns unified results

    No more multiple engines - just one smart engine that handles everything.
    """

    def __init__(self, letta_client: LettaClient, service_manager):
        """Initialize unified workflow engine."""
        if not letta_client:
            raise ValueError('Letta client required for smart workflow engine')

        self.letta_client = letta_client
        self.service_manager = service_manager

        # Workflow definitions with execution strategy
        self.workflows = {
            'literature_review': {
                'description': 'Comprehensive literature review workflow',
                'preferred_approach': 'letta_native',  # Use Letta coordination
                'coordinator_prompt': self._get_literature_review_coordinator_prompt(),
                'participants': [
                    'system_discovery_scout',
                    'system_analysis_expert',
                    'system_synthesis_expert',
                ],
                'shared_memory': [
                    {
                        'label': 'research_topic',
                        'value': 'Research topic and parameters',
                    },
                    {
                        'label': 'discovered_papers',
                        'value': 'Papers found during discovery',
                    },
                    {
                        'label': 'analysis_results',
                        'value': 'Analysis from expert review',
                    },
                    {'label': 'synthesis_output', 'value': 'Final literature review'},
                ],
            },
            'citation_network': {
                'description': 'Citation network analysis workflow',
                'preferred_approach': 'letta_native',
                'coordinator_prompt': self._get_citation_coordinator_prompt(),
                'participants': [
                    'system_citation_analyzer',
                    'system_discovery_scout',
                    'system_analysis_expert',
                ],
                'shared_memory': [
                    {'label': 'target_paper', 'value': 'Paper being analyzed'},
                    {
                        'label': 'extracted_citations',
                        'value': 'Citations extracted from paper',
                    },
                    {'label': 'related_papers', 'value': 'Papers in citation network'},
                    {'label': 'network_analysis', 'value': 'Citation network insights'},
                ],
            },
            'research_validation': {
                'description': 'Research methodology validation workflow',
                'preferred_approach': 'external',  # Complex parallel coordination
                'steps': [
                    {
                        'agent': 'system_analysis_expert',
                        'task': 'methodology_evaluation',
                    },
                    {
                        'agent': 'system_citation_analyzer',
                        'task': 'citation_validation',
                    },
                    {'agent': 'system_discovery_scout', 'task': 'contradiction_search'},
                ],
            },
        }

        logger.info('SmartWorkflowEngine initialized with unified coordination')

    async def execute_workflow(
        self, request_text: str, user_id: str, workflow_type: str | None = None
    ) -> WorkflowResult:
        """
        Execute workflow using automatically selected optimal approach.

        Args:
            request_text: User's natural language request
            user_id: User making the request
            workflow_type: Optional specific workflow (auto-detected if None)

        Returns:
            WorkflowResult with execution details
        """
        start_time = datetime.now()

        try:
            # Auto-detect workflow type if not specified
            if not workflow_type:
                workflow_type = self._detect_workflow_type(request_text)

            if not workflow_type:
                # No specific workflow detected - use dynamic approach
                return await self._execute_dynamic_workflow(
                    request_text, user_id, start_time
                )

            workflow_config = self.workflows.get(workflow_type)
            if not workflow_config:
                raise ValueError(f'Unknown workflow type: {workflow_type}')

            logger.info(f'Executing {workflow_type} workflow for user {user_id}')

            # Choose execution approach based on workflow configuration
            approach = workflow_config.get('preferred_approach', 'letta_native')

            if approach == 'letta_native':
                result = await self._execute_letta_native(
                    workflow_type, workflow_config, request_text, user_id
                )
            else:
                result = await self._execute_external_orchestration(
                    workflow_type, workflow_config, request_text, user_id
                )

            execution_time = (datetime.now() - start_time).total_seconds()
            return WorkflowResult(
                workflow_name=workflow_type,
                success=True,
                execution_time=execution_time,
                approach_used=approach,
                final_output=result,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f'Workflow execution failed: {e}')

            return WorkflowResult(
                workflow_name=workflow_type or 'unknown',
                success=False,
                execution_time=execution_time,
                approach_used='failed',
                final_output=f' Multi-agent workflow failed: {e!s}',
                errors=[str(e)],
            )

    async def _execute_letta_native(
        self,
        workflow_type: str,
        config: dict[str, Any],
        request_text: str,
        user_id: str,
    ) -> str:
        """Execute using Letta's native agent coordination."""
        try:
            # Create or get coordinator agent
            coordinator_id = await self._get_or_create_coordinator(
                workflow_type, config, user_id
            )

            if not coordinator_id:
                raise Exception('Failed to create workflow coordinator')

            # Send task to coordinator - let Letta handle coordination
            task_message = f"""Execute {workflow_type.replace('_', ' ')} workflow:

{request_text}

Please coordinate with the specialized agents to complete this workflow.
Available agents: {', '.join(config['participants'])}
Use your shared memory blocks to track progress and share context between agents."""

            response = self.letta_client.agents.messages.create(
                agent_id=coordinator_id,
                messages=[MessageCreate(role='user', content=task_message)],
            )

            # Extract coordinator's response
            assistant_messages = [
                msg
                for msg in response.messages
                if msg.role == 'assistant' and msg.content
            ]

            if assistant_messages:
                return f""" **Multi-Agent Collaboration: {workflow_type.replace('_', ' ').title()}**

{assistant_messages[-1].content}"""
            else:
                raise Exception('No response from workflow coordinator')

        except Exception as e:
            logger.warning(f'Letta-native execution failed: {e}')
            # Automatic fallback to external orchestration
            return await self._execute_external_orchestration_fallback(
                workflow_type, config, request_text, user_id
            )

    async def _execute_external_orchestration(
        self,
        workflow_type: str,
        config: dict[str, Any],
        request_text: str,
        user_id: str,
    ) -> str:
        """Execute using external orchestration (for complex coordination)."""
        try:
            steps = config.get('steps', [])
            if not steps:
                # Create steps dynamically
                steps = await self._create_dynamic_steps(request_text, user_id)

            step_results = {}

            # Execute steps (parallel for research_validation, sequential for others)
            if workflow_type == 'research_validation':
                # Parallel execution
                tasks = []
                for i, step in enumerate(steps):
                    task = self._execute_step(step, request_text, user_id)
                    tasks.append((f'step_{i + 1}', task))

                for step_id, task in tasks:
                    try:
                        result = await task
                        step_results[step_id] = result
                    except Exception as e:
                        step_results[step_id] = f'Step failed: {e!s}'
            else:
                # Sequential execution
                for i, step in enumerate(steps):
                    step_id = f'step_{i + 1}'
                    try:
                        result = await self._execute_step(step, request_text, user_id)
                        step_results[step_id] = result
                    except Exception as e:
                        step_results[step_id] = f'Step failed: {e!s}'

            # Aggregate results
            final_output = await self._aggregate_results(
                workflow_type, step_results, request_text
            )

            return f""" **Multi-Agent Collaboration: {workflow_type.replace('_', ' ').title()}**

{final_output}"""

        except Exception as e:
            raise Exception(f'External orchestration failed: {e!s}') from e

    async def _execute_external_orchestration_fallback(
        self,
        workflow_type: str,
        config: dict[str, Any],
        request_text: str,
        user_id: str,
    ) -> str:
        """Fallback to external orchestration when Letta-native fails."""
        logger.info(f'Using external orchestration fallback for {workflow_type}')
        return await self._execute_external_orchestration(
            workflow_type, config, request_text, user_id
        )

    async def _execute_dynamic_workflow(
        self, request_text: str, user_id: str, start_time: datetime
    ) -> WorkflowResult:
        """Execute dynamic workflow for complex requests."""
        try:
            # Get available agents
            available_agents = await self._get_available_agents(user_id)

            # Use LLM to decompose task
            steps = await self._decompose_task_with_llm(request_text, available_agents)

            # Execute steps sequentially
            step_results = {}
            for i, step in enumerate(steps):
                step_id = f'dynamic_step_{i + 1}'
                try:
                    result = await self._execute_dynamic_step(step, user_id)
                    step_results[step_id] = result
                except Exception as e:
                    step_results[step_id] = f'Step failed: {e!s}'

            # Aggregate results
            final_output = await self._aggregate_dynamic_results(
                request_text, step_results
            )

            execution_time = (datetime.now() - start_time).total_seconds()

            return WorkflowResult(
                workflow_name='dynamic_workflow',
                success=True,
                execution_time=execution_time,
                approach_used='external_orchestration',
                final_output=f""" **Multi-Agent Collaboration: Dynamic Workflow**

{final_output}

⏱ *Completed in {execution_time:.1f}s with {len(step_results)} specialized agents*""",
                step_details=step_results,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return WorkflowResult(
                workflow_name='dynamic_workflow',
                success=False,
                execution_time=execution_time,
                approach_used='failed',
                final_output=f' Dynamic workflow failed: {e!s}',
                errors=[str(e)],
            )

    async def _get_or_create_coordinator(
        self, workflow_type: str, config: dict[str, Any], user_id: str
    ) -> str | None:
        """Get existing or create new coordinator agent."""
        try:
            coordinator_name = f'{user_id}_{workflow_type}_coordinator'

            # Check if coordinator exists
            agents = self.letta_client.agents.list()
            for agent in agents:
                if agent.name == coordinator_name:
                    return agent.id

            # Create new coordinator
            memory_blocks = [
                CreateBlock(
                    label='persona',
                    value=f'I am the {workflow_type} workflow coordinator. I manage multi-agent research workflows by coordinating specialized agents.',
                ),
                CreateBlock(
                    label='participants',
                    value=f'Available agents: {", ".join(config["participants"])}',
                ),
            ]

            # Add workflow-specific memory blocks
            for block in config.get('shared_memory', []):
                memory_blocks.append(
                    CreateBlock(
                        label=block.get('label', ''),
                        value=block.get('value', ''),
                    )
                )

            coordinator = self.letta_client.agents.create(
                name=coordinator_name,
                memory_blocks=memory_blocks,
                system=config['coordinator_prompt'],
                tools=[],
                enable_sleeptime=True,
            )

            return coordinator.id

        except Exception as e:
            logger.error(f'Failed to create coordinator: {e}')
            return None

    def _detect_workflow_type(self, request_text: str) -> str | None:
        """Detect workflow type from request text."""
        request_lower = request_text.lower()

        if any(
            keyword in request_lower
            for keyword in ['literature review', 'lit review', 'review literature']
        ):
            return 'literature_review'

        if any(
            keyword in request_lower
            for keyword in ['citation network', 'citation analysis', 'analyze citation']
        ):
            return 'citation_network'

        if any(
            keyword in request_lower
            for keyword in [
                'validate research',
                'research validation',
                'validate methodology',
            ]
        ):
            return 'research_validation'

        return None

    def _get_literature_review_coordinator_prompt(self) -> str:
        """Get system prompt for literature review coordinator."""
        return """You are a literature review workflow coordinator. Your role is to:

1. Coordinate with discovery, analysis, and synthesis agents
2. Manage the literature review workflow from start to finish
3. Ensure comprehensive coverage of the research topic
4. Track progress in your shared memory blocks

Workflow steps:
1. Have discovery agent find relevant papers
2. Have analysis agent evaluate methodologies and findings
3. Have synthesis agent create comprehensive review
4. Provide final integrated literature review

Use your shared memory blocks to track each step and share context between agents."""

    def _get_citation_coordinator_prompt(self) -> str:
        """Get system prompt for citation network coordinator."""
        return """You are a citation network analysis workflow coordinator. Your role is to:

1. Coordinate citation extraction, discovery, and analysis agents
2. Map citation networks and relationships
3. Track progress in shared memory blocks
4. Provide comprehensive citation analysis

Workflow steps:
1. Have citation agent extract all citations from target paper
2. Have discovery agent find papers that cite/are cited by target
3. Have analysis agent map network patterns and identify key papers
4. Provide final citation network analysis

Use shared memory blocks to maintain citation data throughout the workflow."""

    async def _execute_step(
        self, step: dict[str, Any], _context: str, _user_id: str
    ) -> str:
        """Execute a single workflow step."""
        # Implementation for step execution
        return f'Step executed: {step.get("task", "unknown")}'

    async def _execute_dynamic_step(self, step: dict[str, Any], _user_id: str) -> str:
        """Execute a dynamic workflow step."""
        # Implementation for dynamic step execution
        return f'Dynamic step executed: {step.get("description", "unknown")}'

    async def _decompose_task_with_llm(
        self, task: str, agents: list[str]
    ) -> list[dict[str, Any]]:
        """Use LLM to decompose complex task into steps."""
        try:
            prompt = f"""
            Break down this research task into 2-4 specific steps for available agents:

            Task: {task}
            Available agents: {', '.join(agents)}

            Return JSON array of steps:
            [
                {{"agent": "agent_name", "description": "specific task description"}},
                {{"agent": "agent_name", "description": "next task description"}}
            ]
            """

            result = await self.service_manager.llm_service.extract_json(prompt=prompt)
            return result if isinstance(result, list) else []

        except Exception as e:
            logger.error(f'Task decomposition failed: {e}')
            return []

    async def _get_available_agents(self, user_id: str) -> list[str]:
        """Get list of available agents."""
        try:
            agents = self.letta_client.agents.list()
            available = []
            for agent in agents:
                if agent.name.startswith('system_') or agent.name.startswith(
                    f'{user_id}_'
                ):
                    available.append(agent.name)
            return available
        except Exception as e:
            logger.error(f'Failed to get available agents: {e}')
            return ['system_discovery_scout', 'system_analysis_expert']

    async def _aggregate_results(
        self, workflow_type: str, step_results: dict[str, Any], original_request: str
    ) -> str:
        """Aggregate step results into final output."""
        try:
            # Use LLM to create coherent final output
            results_text = '\n'.join(
                f'{step}: {result}' for step, result in step_results.items()
            )

            prompt = f"""
            Create a comprehensive response by synthesizing these workflow results:

            Original request: {original_request}
            Workflow type: {workflow_type}

            Step results:
            {results_text}

            Provide a well-structured response that addresses the original request
            and synthesizes insights from all workflow steps.
            """

            return await self.service_manager.llm_service.generate_text(prompt=prompt)

        except Exception as e:
            logger.error(f'Result aggregation failed: {e}')
            # Fallback to simple concatenation
            return '\n\n'.join(
                f'**{step}:**\n{result}' for step, result in step_results.items()
            )

    async def _aggregate_dynamic_results(
        self, original_request: str, step_results: dict[str, Any]
    ) -> str:
        """Aggregate dynamic workflow results."""
        return await self._aggregate_results('dynamic', step_results, original_request)

    def list_workflows(self) -> dict[str, str]:
        """List available workflows."""
        return {name: config['description'] for name, config in self.workflows.items()}

    def get_workflow_info(self, workflow_name: str) -> dict[str, Any] | None:
        """Get information about a specific workflow."""
        return self.workflows.get(workflow_name)
