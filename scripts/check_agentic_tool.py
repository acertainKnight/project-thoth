"""
Diagnostic script to check if agentic_research_question tool is registered.

Run this from the project root:
    python scripts/check_agentic_tool.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    # Check if tool class can be imported
    print('1. Checking if AgenticResearchQuestionMCPTool can be imported...')
    from thoth.mcp.tools.research_qa_tools import AgenticResearchQuestionMCPTool

    print('   ✓ Tool class imported successfully')

    # Check if it's in the MCP_TOOL_CLASSES list
    print('\n2. Checking if tool is in MCP_TOOL_CLASSES...')
    from thoth.mcp.tools import MCP_TOOL_CLASSES

    if AgenticResearchQuestionMCPTool in MCP_TOOL_CLASSES:
        print('   ✓ Tool is in MCP_TOOL_CLASSES')
        index = MCP_TOOL_CLASSES.index(AgenticResearchQuestionMCPTool)
        print(f'   Position in list: {index + 1} of {len(MCP_TOOL_CLASSES)}')
    else:
        print('   ✗ Tool is NOT in MCP_TOOL_CLASSES')
        print("   This is the problem - the tool won't be registered!")
        sys.exit(1)

    # Check tool properties
    print('\n3. Checking tool properties...')
    print(f'   Tool name: {AgenticResearchQuestionMCPTool(None).name}')
    print(
        f'   Tool description: {AgenticResearchQuestionMCPTool(None).description[:80]}...'
    )

    # List all tool names in the registry
    print('\n4. All registered tool names:')
    for tool_class in MCP_TOOL_CLASSES:
        try:
            tool_name = tool_class(None).name
            print(f'   - {tool_name}')
            if tool_name == 'agentic_research_question':
                print('     ^ This is our tool!')
        except Exception as e:
            print(f'   - {tool_class.__name__} (failed to instantiate: {e})')

    print('\n✓ All checks passed! Tool should be available.')
    print("\nIf tool still shows as 'Not found' in Letta:")
    print('1. Restart the MCP server: docker-compose restart mcp')
    print('2. Check MCP server logs: docker-compose logs mcp')
    print('3. Check if Letta has the MCP server registered')

except Exception as e:
    print(f'\n✗ Error: {e}')
    import traceback

    traceback.print_exc()
    sys.exit(1)
