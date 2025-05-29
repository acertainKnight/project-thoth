"""
CLI interface for the Research Assistant Agent.

This module provides a command-line interface for interacting with the research
assistant agent to create and manage research queries.
"""

import sys
from typing import Any

from loguru import logger

from thoth.ingestion.agent import ResearchAgentError, ResearchAssistantAgent
from thoth.utilities.models import ResearchQuery


class ResearchAssistantCLI:
    """
    Command-line interface for the Research Assistant Agent.

    Provides an interactive chat interface for users to create, manage, and refine
    research queries that will be used for automatic article filtering.
    """

    def __init__(self):
        """Initialize the CLI with the research assistant agent."""
        try:
            self.agent = ResearchAssistantAgent()
            self.conversation_history: list[dict[str, str]] = []
            logger.info('Research Assistant CLI initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize Research Assistant: {e}')
            print(f'Error: Failed to initialize Research Assistant: {e}')
            sys.exit(1)

    def run(self) -> None:
        """
        Run the interactive CLI session.

        Provides a conversational interface where users can interact with the
        research assistant to create and manage research queries.
        """
        print('🔬 Welcome to the Thoth Research Assistant!')
        print(
            'I help you create and refine research queries for automatic article filtering.'
        )
        print('Type "help" for available commands or "quit" to exit.\n')

        while True:
            try:
                # Get user input
                user_input = input('You: ').strip()

                if not user_input:
                    continue

                # Handle special commands
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print('\n🔬 Thank you for using the Research Assistant!')
                    break
                elif user_input.lower() == 'help':
                    self._show_help()
                    continue
                elif user_input.lower() == 'clear':
                    self.conversation_history.clear()
                    print('Conversation history cleared.')
                    continue

                # Process the message with the agent
                response = self._process_message(user_input)

                # Display the agent's response
                if response.get('agent_response'):
                    print(f'\n🤖 Assistant: {response["agent_response"]}\n')

                # Handle any errors
                if response.get('error_message'):
                    print(f'❌ Error: {response["error_message"]}\n')

                # Update conversation history
                self.conversation_history.append(
                    {'role': 'user', 'content': user_input}
                )
                if response.get('agent_response'):
                    self.conversation_history.append(
                        {'role': 'assistant', 'content': response['agent_response']}
                    )

            except KeyboardInterrupt:
                print('\n\n🔬 Thank you for using the Research Assistant!')
                break
            except Exception as e:
                logger.error(f'Unexpected error in CLI: {e}')
                print(f'❌ Unexpected error: {e}')

    def _process_message(self, user_message: str) -> dict[str, Any]:
        """
        Process a user message through the research assistant agent.

        Args:
            user_message: The user's input message.

        Returns:
            dict: The agent's response and metadata.
        """
        try:
            response = self.agent.chat(
                user_message=user_message,
                conversation_history=self.conversation_history,
            )
            return response
        except ResearchAgentError as e:
            logger.error(f'Research agent error: {e}')
            return {
                'agent_response': None,
                'error_message': str(e),
                'needs_user_input': True,
            }
        except Exception as e:
            logger.error(f'Unexpected error processing message: {e}')
            return {
                'agent_response': None,
                'error_message': f'Unexpected error: {e!s}',
                'needs_user_input': True,
            }

    def _show_help(self) -> None:
        """Display help information about available commands and features."""
        help_text = """
🔬 Research Assistant Help

Available Commands:
  help          - Show this help message
  clear         - Clear conversation history
  quit/exit/bye - Exit the assistant

What I can help you with:
  • Create new research queries
  • List existing queries
  • Edit and refine queries
  • Evaluate articles against queries
  • Delete queries

Example interactions:
  "Create a new query for machine learning papers"
  "List my queries"
  "Help me refine my deep learning query"
  "Evaluate this article against my NLP query"

Research Query Components:
  • Research Question: Your main research interest
  • Keywords: Important terms that should appear
  • Required Topics: Must-have topics for relevance
  • Preferred Topics: Nice-to-have topics
  • Excluded Topics: Topics that disqualify articles
  • Methodology Preferences: Preferred research methods

Just describe what you want to do in natural language, and I'll guide you through the process!
        """
        print(help_text)

    def create_sample_query(self) -> None:
        """
        Create a sample research query for demonstration purposes.

        This method creates an example query to show users how the system works.
        """
        sample_query = ResearchQuery(
            name='deep_learning_nlp_sample',
            description='Deep learning approaches to natural language processing tasks',
            research_question='How are modern deep learning architectures being applied to solve NLP challenges?',
            keywords=[
                'transformer',
                'attention',
                'BERT',
                'GPT',
                'neural language model',
                'deep learning',
            ],
            required_topics=['natural language processing', 'deep learning'],
            preferred_topics=[
                'transformer architecture',
                'attention mechanisms',
                'language modeling',
                'text classification',
                'machine translation',
            ],
            excluded_topics=['computer vision', 'robotics', 'hardware optimization'],
            methodology_preferences=[
                'experimental evaluation',
                'benchmark datasets',
                'ablation studies',
            ],
            minimum_relevance_score=0.7,
        )

        success = self.agent.create_query(sample_query)
        if success:
            print(f'✅ Created sample query: {sample_query.name}')
        else:
            print('❌ Failed to create sample query')


def main() -> None:
    """
    Main entry point for the Research Assistant CLI.

    Initializes and runs the interactive CLI session.
    """
    cli = ResearchAssistantCLI()

    # Optionally create a sample query for demonstration
    if '--create-sample' in sys.argv:
        cli.create_sample_query()

    cli.run()


if __name__ == '__main__':
    main()
