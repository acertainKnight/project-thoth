#!/usr/bin/env python3
"""
Demonstration script for the Research Assistant Agent.

This script shows how to use the Research Assistant Agent programmatically
to create queries, evaluate articles, and filter content.
"""

import sys
from pathlib import Path

# Add the src directory to the path so we can import thoth modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from thoth.ingestion.agent import ResearchAssistantAgent
from thoth.ingestion.filter import ArticleFilter
from thoth.utilities.models import AnalysisResponse, ResearchQuery


def create_sample_queries(agent: ResearchAssistantAgent) -> None:
    """Create some sample research queries for demonstration."""
    print('📝 Creating sample research queries...')

    # Query 1: Deep Learning for NLP
    nlp_query = ResearchQuery(
        name='deep_learning_nlp',
        description='Deep learning approaches to natural language processing',
        research_question='How are modern deep learning architectures being applied to NLP tasks?',
        keywords=[
            'transformer',
            'attention',
            'BERT',
            'GPT',
            'neural language model',
            'deep learning',
            'natural language processing',
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

    # Query 2: Computer Vision
    cv_query = ResearchQuery(
        name='computer_vision_ml',
        description='Machine learning approaches to computer vision problems',
        research_question='What are the latest advances in computer vision using machine learning?',
        keywords=[
            'computer vision',
            'convolutional neural network',
            'CNN',
            'image classification',
            'object detection',
            'deep learning',
        ],
        required_topics=['computer vision', 'machine learning'],
        preferred_topics=[
            'image recognition',
            'object detection',
            'semantic segmentation',
            'neural networks',
        ],
        excluded_topics=['natural language processing', 'audio processing'],
        methodology_preferences=['experimental validation', 'benchmark evaluation'],
        minimum_relevance_score=0.6,
    )

    # Query 3: Reinforcement Learning
    rl_query = ResearchQuery(
        name='reinforcement_learning',
        description='Reinforcement learning algorithms and applications',
        research_question='What are the current developments in reinforcement learning?',
        keywords=[
            'reinforcement learning',
            'Q-learning',
            'policy gradient',
            'deep reinforcement learning',
            'RL',
        ],
        required_topics=['reinforcement learning'],
        preferred_topics=[
            'deep reinforcement learning',
            'policy optimization',
            'value functions',
            'multi-agent systems',
        ],
        excluded_topics=['supervised learning', 'unsupervised learning'],
        methodology_preferences=['simulation studies', 'empirical evaluation'],
        minimum_relevance_score=0.65,
    )

    # Create the queries
    queries = [nlp_query, cv_query, rl_query]
    for query in queries:
        success = agent.create_query(query)
        if success:
            print(f'✅ Created query: {query.name}')
        else:
            print(f'❌ Failed to create query: {query.name}')


def create_sample_article() -> AnalysisResponse:
    """Create a sample article for demonstration."""
    return AnalysisResponse(
        abstract='This paper presents a novel transformer-based approach for natural language understanding tasks. We introduce a new attention mechanism that improves performance on text classification and sentiment analysis benchmarks.',
        key_points="""
Novel transformer architecture for NLP
Improved attention mechanism design
Evaluation on text classification tasks
Sentiment analysis benchmark results
Comparison with BERT and GPT models
Ablation studies on attention components
""".strip(),
        summary='This research introduces an enhanced transformer architecture specifically designed for natural language understanding. The proposed model incorporates a novel attention mechanism that demonstrates superior performance compared to existing approaches like BERT and GPT on various NLP benchmarks including text classification and sentiment analysis.',
        objectives='To develop an improved transformer architecture for natural language understanding tasks',
        methodology='The authors propose a modified attention mechanism within the transformer architecture. They conduct extensive experiments on multiple NLP benchmarks including text classification and sentiment analysis tasks. The methodology includes ablation studies to understand the contribution of different components.',
        data='The experiments use standard NLP benchmarks including GLUE, sentiment analysis datasets, and text classification corpora. The datasets contain thousands of labeled examples for training and evaluation.',
        experimental_setup='The model is trained using standard transformer training procedures with appropriate hyperparameter tuning. Comparisons are made against BERT, GPT, and other state-of-the-art models.',
        evaluation_metrics='Performance is measured using accuracy, F1-score, and other standard NLP metrics on benchmark datasets.',
        results='The proposed model achieves state-of-the-art results on several benchmarks, showing 2-3% improvement over BERT on text classification tasks.',
        discussion='The results demonstrate the effectiveness of the novel attention mechanism. The improvements are consistent across different tasks, suggesting the general applicability of the approach.',
        strengths='Novel attention mechanism, comprehensive evaluation, strong empirical results',
        limitations='Limited to English language tasks, computational overhead of the new attention mechanism',
        future_work='Extension to multilingual settings, optimization of computational efficiency',
        related_work='Builds upon transformer architecture, attention mechanisms, and recent advances in NLP',
        tags=[
            '#natural_language_processing',
            '#transformer',
            '#attention_mechanism',
            '#deep_learning',
        ],
    )


def demonstrate_article_evaluation(agent: ResearchAssistantAgent) -> None:
    """Demonstrate article evaluation against queries."""
    print('\n🔍 Demonstrating article evaluation...')

    # Create a sample article
    sample_article = create_sample_article()
    print(f'Sample article: {sample_article.summary[:100]}...')

    # Get available queries
    queries = agent.list_queries()
    print(f'Available queries: {queries}')

    # Evaluate against each query
    for query_name in queries:
        print(f'\n📊 Evaluating against query: {query_name}')
        try:
            evaluation = agent.evaluate_article(sample_article, query_name)
            if evaluation:
                print(f'  Score: {evaluation.relevance_score:.2f}')
                print(f'  Recommendation: {evaluation.recommendation}')
                print(f'  Meets criteria: {evaluation.meets_criteria}')
                print(f'  Keyword matches: {evaluation.keyword_matches}')
                print(f'  Reasoning: {evaluation.reasoning[:200]}...')
            else:
                print('  ❌ Evaluation failed')
        except Exception as e:
            print(f'  ❌ Error: {e}')


def demonstrate_article_filtering() -> None:
    """Demonstrate automatic article filtering."""
    print('\n🔄 Demonstrating article filtering...')

    # Create article filter
    article_filter = ArticleFilter()

    # Create sample article
    sample_article = create_sample_article()

    # Filter the article
    filter_result = article_filter.filter_article(sample_article)

    print(f'Overall recommendation: {filter_result["overall_recommendation"]}')
    print(f'Reason: {filter_result["reason"]}')
    print(f'Highest score: {filter_result.get("highest_score", "N/A")}')
    print(f'Matching queries: {filter_result.get("matching_queries", [])}')

    # Show statistics
    stats = article_filter.get_statistics()
    print('\n📈 Filter statistics:')
    print(f'  Total articles processed: {stats["total_articles"]}')
    print(f'  Approved: {stats["approved_count"]}')
    print(f'  Rejected: {stats["rejected_count"]}')
    print(f'  Needs review: {stats["review_count"]}')
    print(f'  Available queries: {stats["available_queries"]}')


def demonstrate_conversational_interface(agent: ResearchAssistantAgent) -> None:
    """Demonstrate the conversational interface."""
    print('\n💬 Demonstrating conversational interface...')

    # Simulate a conversation
    conversation_history = []

    messages = [
        'Hello, I need help creating a research query',
        'I want to find papers about machine learning for healthcare',
        'List my current queries',
    ]

    for message in messages:
        print(f'\nUser: {message}')
        try:
            response = agent.chat(message, conversation_history)
            print(f'Assistant: {response["agent_response"]}')

            # Update conversation history
            conversation_history.append({'role': 'user', 'content': message})
            if response.get('agent_response'):
                conversation_history.append(
                    {'role': 'assistant', 'content': response['agent_response']}
                )

        except Exception as e:
            print(f'Error: {e}')


def main() -> None:
    """Main demonstration function."""
    print('🔬 Research Assistant Agent Demonstration')
    print('=' * 50)

    try:
        # Initialize the agent
        print('🚀 Initializing Research Assistant Agent...')
        agent = ResearchAssistantAgent()
        print('✅ Agent initialized successfully')

        # Create sample queries
        create_sample_queries(agent)

        # Demonstrate article evaluation
        demonstrate_article_evaluation(agent)

        # Demonstrate article filtering
        demonstrate_article_filtering()

        # Demonstrate conversational interface
        demonstrate_conversational_interface(agent)

        print('\n✅ Demonstration completed successfully!')
        print('\nTo interact with the agent directly, run:')
        print('python -m thoth.ingestion.cli')

    except Exception as e:
        print(f'❌ Error during demonstration: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    main()
