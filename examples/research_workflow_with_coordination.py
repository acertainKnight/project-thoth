#!/usr/bin/env python3
"""
Example research workflow using agent coordination via message queue.

This demonstrates how the orchestrator can delegate tasks to specialist agents
and track progress through the shared memory message queue.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from thoth.coordination.message_queue import (
    mark_message_complete,
    post_message,
    read_messages_for_agent,
)


def orchestrator_workflow():
    """
    Orchestrator delegates research tasks to specialist agents.
    """
    print('=== Orchestrator Starting Research Workflow ===\n')

    # Task 1: Discovery Scout finds papers
    print('📋 Task 1: Delegating paper discovery to scout...')
    post_message(
        sender='thoth_main_orchestrator',
        receiver='system_discovery_scout',
        task='Find recent papers on large language models and reasoning',
        priority='high',
        metadata={
            'search_terms': ['large language models', 'reasoning', 'chain of thought'],
            'max_results': 15,
            'year_filter': '2023-2025',
        },
    )
    print('✅ Task delegated to discovery scout\n')

    # Task 2: Citation Analyzer builds network
    print('📋 Task 2: Delegating citation analysis...')
    post_message(
        sender='thoth_main_orchestrator',
        receiver='system_citation_analyzer',
        task='Build citation network for discovered papers',
        priority='medium',
        metadata={'depends_on': 'discovery_scout_task', 'depth': 2},
    )
    print('✅ Task delegated to citation analyzer\n')

    # Task 3: Analysis Expert synthesizes findings
    print('📋 Task 3: Delegating synthesis analysis...')
    post_message(
        sender='thoth_main_orchestrator',
        receiver='system_analysis_expert',
        task='Synthesize findings and identify key themes',
        priority='high',
        metadata={
            'depends_on': ['discovery_scout_task', 'citation_analyzer_task'],
            'output_format': 'structured_summary',
        },
    )
    print('✅ Task delegated to analysis expert\n')

    print('=== All tasks delegated. Agents can now check their queues. ===\n')


def scout_workflow():
    """
    Discovery Scout checks for pending tasks and processes them.
    """
    print('=== Discovery Scout Checking Message Queue ===\n')

    pending_tasks = read_messages_for_agent('system_discovery_scout', status='pending')

    if not pending_tasks:
        print('ℹ️  No pending tasks for discovery scout\n')
        return

    print(f'📬 Found {len(pending_tasks)} pending task(s)\n')

    for task in pending_tasks:
        print(f'📋 Processing task from {task["sender"]}')
        print(f'   Task: {task["task"]}')
        print(f'   Priority: {task["priority"]}')
        print(f'   Metadata: {task.get("metadata", {})}')

        # Simulate task execution
        print('   🔍 Searching for papers...')
        print('   ✅ Found 15 papers, updated active_papers block')

        # Mark as complete
        mark_message_complete(
            sender=task['sender'],
            receiver=task['receiver'],
            timestamp=task['timestamp'],
        )
        print('   ✅ Task marked as complete\n')


def analyzer_workflow():
    """
    Citation Analyzer checks for pending tasks.
    """
    print('=== Citation Analyzer Checking Message Queue ===\n')

    pending_tasks = read_messages_for_agent(
        'system_citation_analyzer', status='pending'
    )

    if not pending_tasks:
        print('ℹ️  No pending tasks for citation analyzer\n')
        return

    print(f'📬 Found {len(pending_tasks)} pending task(s)\n')

    for task in pending_tasks:
        print(f'📋 Processing task from {task["sender"]}')
        print(f'   Task: {task["task"]}')

        # Check dependencies
        if 'depends_on' in task.get('metadata', {}):
            print(f'   ⏳ Waiting for dependency: {task["metadata"]["depends_on"]}')
            print('   ℹ️  Skipping for now, will retry later\n')
            continue

        print('   🔗 Building citation network...')
        print('   ✅ Citation network updated in citation_network block')

        mark_message_complete(
            sender=task['sender'],
            receiver=task['receiver'],
            timestamp=task['timestamp'],
        )
        print('   ✅ Task marked as complete\n')


def expert_workflow():
    """
    Analysis Expert checks for pending tasks.
    """
    print('=== Analysis Expert Checking Message Queue ===\n')

    pending_tasks = read_messages_for_agent('system_analysis_expert', status='pending')

    if not pending_tasks:
        print('ℹ️  No pending tasks for analysis expert\n')
        return

    print(f'📬 Found {len(pending_tasks)} pending task(s)\n')

    for task in pending_tasks:
        print(f'📋 Processing task from {task["sender"]}')
        print(f'   Task: {task["task"]}')

        # Check dependencies
        if 'depends_on' in task.get('metadata', {}):
            deps = task['metadata']['depends_on']
            print(f'   ⏳ Waiting for dependencies: {deps}')
            print('   ℹ️  Skipping for now, will retry later\n')
            continue

        print('   🧠 Synthesizing findings...')
        print('   ✅ Research findings updated in research_findings block')

        mark_message_complete(
            sender=task['sender'],
            receiver=task['receiver'],
            timestamp=task['timestamp'],
        )
        print('   ✅ Task marked as complete\n')


def main():
    """
    Run complete workflow demonstration.
    """
    print('\n' + '=' * 70)
    print('     Agent Coordination Workflow Demo')
    print('     Using Shared Memory Message Queue')
    print('=' * 70 + '\n')

    # Step 1: Orchestrator delegates tasks
    orchestrator_workflow()

    input('Press Enter to simulate scout checking queue...')
    print()

    # Step 2: Scout processes tasks
    scout_workflow()

    input('Press Enter to simulate analyzer checking queue...')
    print()

    # Step 3: Analyzer processes tasks (will skip due to dependency)
    analyzer_workflow()

    input('Press Enter to simulate expert checking queue...')
    print()

    # Step 4: Expert processes tasks (will skip due to dependencies)
    expert_workflow()

    print('\n' + '=' * 70)
    print('     Workflow Demo Complete')
    print('=' * 70)
    print('\nℹ️  In production, agents would:')
    print('   1. Poll the message queue periodically')
    print('   2. Check dependencies via shared memory blocks')
    print('   3. Execute tasks when dependencies are met')
    print('   4. Update shared memory blocks with results')
    print('   5. Mark messages as complete when done')
    print('\n✅ Coordination system is ready for production use!')


if __name__ == '__main__':
    main()
