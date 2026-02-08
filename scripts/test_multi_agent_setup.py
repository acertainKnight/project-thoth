#!/usr/bin/env python3
import sys

from letta_client import Letta

print('Creating test agent with multi-agent tools...', flush=True)

try:
    client = Letta(base_url='http://localhost:8283')

    test_agent = client.agents.create(
        name='test_multi_agent_tooling',
        model='letta/letta-free',
        embedding='letta/letta-free',
        include_base_tools=True,
        include_multi_agent_tools=True,
    )

    print(f'✅ Created agent: {test_agent.id}', flush=True)
    print(f'Tools: {len(test_agent.tools)}', flush=True)

    for tool in test_agent.tools:
        if 'send' in tool.name:
            print(f'  ✅ {tool.name}', flush=True)

    # DON'T delete - we need to extract tool IDs
    print(f'✅ Agent ID: {test_agent.id}', flush=True)
    print('✅ Test complete (agent not deleted)', flush=True)

except Exception as e:
    print(f'❌ Error: {e}', flush=True)
    import traceback

    traceback.print_exc()
    sys.exit(1)
