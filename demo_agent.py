#!/usr/bin/env python3
"""
Demo script showing the enhanced Thoth Research Agent capabilities.

This script demonstrates how to interact with the agent to manage discovery sources.
"""


def demo_agent_usage():
    """Demonstrate agent usage examples."""
    print('🤖 Enhanced Thoth Research Agent - Discovery Management')
    print('=' * 60)

    print('\n📋 **Available Commands:**')

    print('\n🆘 **Help & Information:**')
    print("  • 'help' or '?' - Show all agent capabilities and commands")
    print("  • 'what can you do?' - Learn about the agent's features")

    print('\n🔍 **Discovery Source Management:**')
    print("  • 'list discovery sources' - Show all configured sources")
    print(
        '  • \'create an arxiv source called "ml_papers" for machine learning\' - Create ArXiv source'
    )
    print(
        '  • \'create a pubmed source called "bio_research" searching for neuroscience\' - Create PubMed source'
    )
    print("  • 'run discovery for arxiv_test' - Run specific source")
    print("  • 'run discovery with max 5 articles' - Run all sources with limit")
    print("  • 'edit arxiv_test source' - Modify existing source")
    print("  • 'delete old_source' - Remove a source")

    print('\n📝 **Research Query Management:**')
    print("  • 'create query' - Create new research query")
    print("  • 'list queries' - Show existing queries")

    print('\n🚀 **Getting Started:**')
    print('1. Run: python -m thoth agent')
    print("2. Type: 'help' to see all capabilities")
    print("3. Try: 'list discovery sources'")
    print(
        '4. Create: \'create an arxiv source called "my_research" for deep learning\''
    )
    print("5. Run: 'run discovery for my_research'")

    print('\n💡 **Example Conversation:**')
    print('You: help')
    print('Agent: Shows comprehensive list of all capabilities')
    print()
    print('You: list discovery sources')
    print('Agent: Shows current sources with status and options')
    print()
    print('You: create an arxiv source called "ai_papers" for artificial intelligence')
    print('Agent: ✅ ArXiv Discovery Source Created Successfully!')
    print()
    print('You: run discovery for ai_papers')
    print('Agent: 🚀 Running discovery... ✅ Found 5 articles, downloaded 3 PDFs')

    print('\n🎯 **Key Features:**')
    print('  ✅ Natural language interaction')
    print('  ✅ Comprehensive help system')
    print('  ✅ Automatic source creation from descriptions')
    print('  ✅ Real-time discovery execution')
    print('  ✅ Integration with existing filter system')
    print('  ✅ Complete source and query management')


if __name__ == '__main__':
    demo_agent_usage()
