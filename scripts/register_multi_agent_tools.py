#!/usr/bin/env python3
"""
Register multi-agent communication tools using Letta Python SDK.
This script runs inside the Letta container to properly register the tools.
"""

import asyncio

from letta.functions.function_sets import multi_agent
from letta.server.rest_api.dependencies import get_letta_server


async def register_tools():
    """Register multi-agent communication tools."""
    print('Initializing Letta server...')
    server = await get_letta_server()

    print('Getting default actor...')
    actor = await server.user_manager.get_default_actor_async()

    print('\nRegistering multi-agent communication tools...')

    # List of functions to register
    functions = [
        ('send_message_to_agent_async', multi_agent.send_message_to_agent_async),
        (
            'send_message_to_agent_and_wait_for_reply',
            multi_agent.send_message_to_agent_and_wait_for_reply,
        ),
    ]

    tool_ids = {}

    for name, func in functions:
        print(f'\n  Processing: {name}')
        try:
            # Create tool from function
            tool = server.tool_manager.create_or_update_tool_from_function(
                func=func, actor=actor
            )
            tool_ids[name] = tool.id
            print(f'    ✅ Created: {tool.id}')
        except Exception as e:
            print(f'    ❌ Error: {e}')

    return tool_ids


async def attach_to_agents(tool_ids):
    """Attach communication tools to all agents."""
    if not tool_ids:
        print('\n❌ No tools to attach')
        return

    print('\n\nAttaching tools to agents...')
    server = await get_letta_server()
    actor = await server.user_manager.get_default_actor_async()

    agent_ids = [
        'agent-10418b8d-37a5-4923-8f70-69ccc58d66ff',  # thoth_main_orchestrator
        'agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5',  # system_citation_analyzer
        'agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64',  # system_discovery_scout
        'agent-8a4183a6-fffc-4082-b40b-aab29727a3ab',  # system_analysis_expert
    ]

    # Use async version for attaching tools
    for agent_id in agent_ids:
        try:
            agent = server.agent_manager.get_agent_by_id(agent_id=agent_id, actor=actor)
            print(f'\n  {agent.name}:')

            # Get current tools
            current_tools = agent.tools or []
            current_tool_ids = [t.id for t in current_tools]

            # Add new tools (just async version to avoid confusion)
            async_tool_id = tool_ids.get('send_message_to_agent_async')
            if async_tool_id and async_tool_id not in current_tool_ids:
                new_tool_ids = current_tool_ids + [async_tool_id]

                # Update agent
                server.agent_manager.update_agent(
                    agent_id=agent_id, tool_ids=new_tool_ids, actor=actor
                )
                print('    ✅ Added send_message_to_agent_async')
            else:
                print('    ℹ️  Tool already attached or not available')

        except Exception as e:
            print(f'    ❌ Error: {e}')


async def main():
    """Main function."""
    print('=' * 60)
    print('  Registering Multi-Agent Communication Tools')
    print('=' * 60 + '\n')

    tool_ids = await register_tools()
    await attach_to_agents(tool_ids)

    print('\n' + '=' * 60)
    print('  ✅ Registration complete!')
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(main())
