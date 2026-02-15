#!/usr/bin/env python3
"""
Check if agentic_research_question is properly registered in the MCP server.

This script inspects the MCP tool registry to see if the tool was successfully
registered when the MCP server started up.
"""

import asyncio
import sys
from pathlib import Path

from loguru import logger

# Add project to path so thoth can be imported
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

logger.remove()
logger.add(sys.stdout, format='<level>{level: <8}</level> | {message}', colorize=True)


async def main():
    """Check MCP tool registration."""
    logger.info('=' * 70)
    logger.info('MCP TOOL REGISTRATION DIAGNOSTIC')
    logger.info('=' * 70)

    try:
        # Step 1: Import tool classes
        logger.info('\n1. Importing MCP tool classes...')
        from thoth.mcp.tools import MCP_TOOL_CLASSES
        from thoth.mcp.tools.research_qa_tools import AgenticResearchQuestionMCPTool

        logger.success(f'   ✓ Found {len(MCP_TOOL_CLASSES)} total tool classes')

        # Step 2: Check if AgenticResearchQuestionMCPTool is in the list
        logger.info(
            '\n2. Checking if AgenticResearchQuestionMCPTool is in MCP_TOOL_CLASSES...'
        )
        if AgenticResearchQuestionMCPTool in MCP_TOOL_CLASSES:
            logger.success('   ✓ AgenticResearchQuestionMCPTool is in MCP_TOOL_CLASSES')
            index = MCP_TOOL_CLASSES.index(AgenticResearchQuestionMCPTool)
            logger.info(f'   Position: {index + 1} of {len(MCP_TOOL_CLASSES)}')
        else:
            logger.error('   ✗ AgenticResearchQuestionMCPTool NOT in MCP_TOOL_CLASSES')
            logger.error('   This is a registration bug!')
            return

        # Step 3: Try to create a ServiceManager
        logger.info('\n3. Initializing ServiceManager...')
        from thoth.services import ServiceManager

        sm = ServiceManager()
        logger.success('   ✓ ServiceManager initialized')

        # Step 4: Try to instantiate the tool
        logger.info('\n4. Attempting to instantiate AgenticResearchQuestionMCPTool...')
        try:
            tool = AgenticResearchQuestionMCPTool(sm)
            logger.success('   ✓ Tool instantiated successfully')
            logger.info(f'   Tool name: {tool.name}')
            logger.info(f'   Tool description: {tool.description[:80]}...')
        except Exception as e:
            logger.error(f'   ✗ Instantiation failed: {type(e).__name__}: {e}')
            logger.error(
                "   This means the tool fails during __init__ and won't be registered"
            )
            logger.error(
                "   Check if the tool requires a specific service that's not available"
            )
            import traceback

            traceback.print_exc()
            return

        # Step 5: Try to register it with the MCP registry
        logger.info('\n5. Testing MCP tool registry registration...')
        from thoth.mcp.base_tools import MCPToolRegistry

        registry = MCPToolRegistry(sm)
        try:
            registry.register_class(AgenticResearchQuestionMCPTool)
            logger.success('   ✓ Tool registered with MCPToolRegistry')
        except Exception as e:
            logger.error(f'   ✗ Registration failed: {type(e).__name__}: {e}')
            import traceback

            traceback.print_exc()
            return

        # Step 6: Check if we can get the tool schema
        logger.info('\n6. Getting tool schema...')
        try:
            schemas = registry.get_tool_schemas()
            agentic_schema = next(
                (s for s in schemas if s.name == 'agentic_research_question'), None
            )
            if agentic_schema:
                logger.success('   ✓ Found agentic_research_question in tool schemas')
                logger.info(f'   Description: {agentic_schema.description[:80]}...')
            else:
                logger.error('   ✗ agentic_research_question NOT in tool schemas')
                logger.info('\n   Available tools:')
                for schema in schemas[:10]:
                    logger.info(f'     - {schema.name}')
                logger.info(f'     ... and {len(schemas) - 10} more')
        except Exception as e:
            logger.error(f'   ✗ Failed to get tool schemas: {e}')
            return

        logger.info('\n' + '=' * 70)
        logger.info('DIAGNOSTIC COMPLETE')
        logger.info('=' * 70)

        if agentic_schema:
            logger.success(
                '\n✓ Tool is properly registered in MCP. The issue is likely in how Letta'
            )
            logger.success('  discovers tools from the MCP server.')
            logger.info('\nNext steps:')
            logger.info('1. Check MCP server logs for errors during startup')
            logger.info('2. Verify Letta is configured to use the thoth MCP server')
            logger.info('3. Try restarting BOTH the MCP server AND Letta')
            logger.info(
                "4. Check Letta's MCP server configuration in your settings.json or environment"
            )

    except Exception as e:
        logger.error(f'\nFailed during diagnostic: {e}')
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
