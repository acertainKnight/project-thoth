import time

from loguru import logger

from thoth.ingestion.agent_v2 import create_research_assistant
from thoth.pipeline import ThothPipeline


def run_agent_chat(_args, pipeline: ThothPipeline):
    """
    Start an interactive chat with the research assistant agent.
    """
    try:
        logger.info('Starting modern research assistant agent chat...')
        agent = create_research_assistant(
            service_manager=pipeline.services,
            enable_memory=True,
        )

        print('\\n' + '=' * 70)
        print('🤖 Welcome to Thoth Research Assistant!')
        print('=' * 70)
        print(
            'I am your AI research assistant, powered by LangGraph and MCP framework.'
        )
        print('I can help you manage your research with these capabilities:')

        print('\\n📚 **Research Management:**')
        print('  • Discovery Sources - Automatically find papers from ArXiv, PubMed')
        print('  • Research Queries - Filter articles based on your interests')
        print('  • Knowledge Base - Search and analyze your paper collection')
        print('  • Paper Analysis - Find connections and analyze research topics')

        print('\\n💡 **Example Commands:**')
        print('  • "Show me my discovery sources"')
        print('  • "Create an ArXiv source for machine learning papers"')
        print('  • "What papers do I have on transformers?"')
        print('  • "Explain the connection between paper A and paper B"')
        print('  • "Analyze deep learning research in my collection"')

        print('\\n🚀 **Tips:**')
        print('  • I can use multiple tools to provide comprehensive answers')
        print('  • I remember our conversation context')
        print('  • Type "exit" or "quit" to end the session')
        print('=' * 70 + '\\n')

        session_id = f'chat_{int(time.time())}'

        while True:
            try:
                user_message = input('You: ').strip()

                if user_message.lower() in {'exit', 'quit', 'bye', 'done'}:
                    print('\\n👋 Thank you for using Thoth Research Assistant!')
                    print('Your research configuration has been saved.')
                    break

                if not user_message:
                    continue

                response = agent.chat(
                    message=user_message,
                    session_id=session_id,
                )

                print(f'\\nAssistant: {response["response"]}')

                if response.get('tool_calls'):
                    print('\\n🔧 Tools used:')
                    for tool_call in response['tool_calls']:
                        print(f'  - {tool_call["tool"]}')

                print()

            except KeyboardInterrupt:
                print('\\n\\n👋 Session interrupted. Goodbye!')
                break
            except Exception as e:
                logger.error(f'Error in agent chat: {e}')
                print(f'\\n❌ Error: {e}')
                print("Please try again or type 'exit' to quit.")

        return 0

    except Exception as e:
        logger.error(f'Failed to start agent chat: {e}')
        print(f'❌ Failed to start agent chat: {e}')
        return 1


def configure_subparser(subparsers):
    """Configure the subparser for the agent command."""
    parser = subparsers.add_parser(
        'agent', help='Start an interactive chat with the research assistant agent'
    )
    parser.set_defaults(func=run_agent_chat)
