"""
LLM Router Service for dynamically selecting the best model for a given query.
"""

from __future__ import annotations  # noqa: I001

from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

from thoth.services.base import BaseService
from thoth.services.llm_service import LLMService
from thoth.config import config, Config  # noqa: F401
from thoth.utilities.openrouter import ModelRegistry, OpenRouterClient

if TYPE_CHECKING:
    pass


class LLMRouter(BaseService):
    """
    Selects the best LLM for a given query based on configured candidate models
    and their capabilities.
    """

    def __init__(
        self,
        config: Config | None = None,  # noqa: F811
        llm_service: LLMService | None = None,
    ):
        """
        Initialize the LLMRouter.

        Args:
            config: The Thoth configuration object.
            llm_service: The LLM service object.
        """
        super().__init__(config)
        self.routing_config = self.config.query_based_routing_config
        self.agent_llm_config = self.config.research_agent_llm_config
        self.candidate_models = self.agent_llm_config.model
        if isinstance(self.candidate_models, str):
            self.candidate_models = [self.candidate_models]

        self.requirements = {
            'tool_calling': self.agent_llm_config.use_auto_model_selection
            and self.agent_llm_config.auto_model_require_tool_calling,
            'structured_output': self.agent_llm_config.use_auto_model_selection
            and self.agent_llm_config.auto_model_require_structured_output,
        }
        self.router_llm = OpenRouterClient(
            api_key=self.config.api_keys.openrouter_key,
            model=self.routing_config.routing_model,
        )
        self.llm_service = llm_service or LLMService(self.config)
        self.routing_model = self.llm_service.get_client(
            model=self.config.query_based_routing_config.routing_model
        )

        # Set up Jinja2 environment for dynamic prompts
        self.use_dynamic_prompt = (
            self.config.query_based_routing_config.use_dynamic_prompt
        )
        if self.use_dynamic_prompt:
            self.env = Environment(
                loader=FileSystemLoader(self.config.prompts_dir / 'agent'),
                autoescape=select_autoescape(['html', 'xml']),
            )
        else:
            self.env = None

    def initialize(self) -> None:
        """Initialize the router."""
        self.logger.info('LLM Router initialized')

    def _filter_models_by_capability(self) -> list[dict]:
        """
        Filter candidate models based on their capabilities.

        Uses ModelRegistry to fetch models and checks supported_parameters
        for structured_outputs (not the non-existent architecture.json_grammar field).

        Returns:
            List of model dicts matching requirements, or fallback to first candidate
        """
        all_models = ModelRegistry.get_openrouter_models_sync()
        model_details_map = {m.id: m for m in all_models}

        filtered_models = []
        for model_id in self.candidate_models:
            if model_id not in model_details_map:
                self.logger.warning(
                    f"Candidate model '{model_id}' not found in OpenRouter models."
                )
                continue

            model_info = model_details_map[model_id]

            # Check structured output support via supported_parameters
            if self.requirements['structured_output'] and (
                'structured_outputs' not in model_info.supported_parameters
            ):
                continue

            # Note: tool_calling check removed as ModelInfo doesn't have tool_use
            # OpenRouter's tool calling is now part of supported_parameters
            if self.requirements['tool_calling'] and (
                'tools' not in model_info.supported_parameters
            ):
                continue

            # Convert ModelInfo to dict for compatibility with existing code
            filtered_models.append({
                'id': model_info.id,
                'name': model_info.name,
                'context_length': model_info.context_length,
                'supported_parameters': model_info.supported_parameters,
                'description': model_info.name,  # Use name as description
            })

        if not filtered_models:
            self.logger.error('No candidate models meet the required capabilities.')
            if self.candidate_models:
                first_candidate = self.candidate_models[0]
                if first_candidate in model_details_map:
                    model_info = model_details_map[first_candidate]
                    return [{
                        'id': model_info.id,
                        'name': model_info.name,
                        'context_length': model_info.context_length,
                        'supported_parameters': model_info.supported_parameters,
                        'description': model_info.name,
                    }]
                return []
        return filtered_models

    def select_model(self, query: str) -> str:
        """
        Select the best model for a given query.

        If query-based routing is disabled, this method will return 'auto' if multiple
        models are provided (for OpenRouter's native routing), or the single model name.

        Args:
            query: The user's query.

        Returns:
            The ID of the selected model.
        """
        if not self.routing_config.enabled:
            if (
                isinstance(self.agent_llm_config.model, list)
                and len(self.agent_llm_config.model) > 1
            ):
                return 'auto'
            return self.agent_llm_config.model

        candidate_details = self._filter_models_by_capability()
        if not candidate_details:
            raise ValueError('Could not find any suitable models for routing.')
        if len(candidate_details) == 1:
            return candidate_details[0]['id']

        if self.use_dynamic_prompt and self.env:
            template = self.env.get_template('select_model.j2')
            prompt = template.render(query=query, models=candidate_details)
        else:
            model_list_str = '\n'.join(
                [
                    f'- `{m["id"]}`: {m.get("description", "No description")}'
                    for m in candidate_details
                ]
            )
            prompt = f"""
            Based on the user's query, select the most appropriate language model from the following list.
            Consider the model's description and its likely strengths. For example, some models are better for creative tasks, some for coding, and some for general reasoning.

            User Query:
            "{query}"

            Available Models:
            {model_list_str}

            Your selection should be only the model ID (e.g., `openai/gpt-4o-mini`).
            """

        response = self.router_llm.invoke(prompt)
        selected_model_id = response.content.strip().strip('`')

        valid_ids = {m['id'] for m in candidate_details}
        if selected_model_id in valid_ids:
            self.logger.info(f"Router selected model '{selected_model_id}' for query.")
            return selected_model_id
        else:
            self.logger.warning(
                f"Router selected an invalid model '{selected_model_id}'. Falling back to the first candidate."
            )
            return candidate_details[0]['id']

    def get_models(self) -> list[dict]:
        """
        Gets the list of available models from OpenRouter.

        Returns:
            List of model dicts with id, name, context_length, etc.
        """
        models = ModelRegistry.get_openrouter_models_sync()
        return [{
            'id': m.id,
            'name': m.name,
            'context_length': m.context_length,
            'supported_parameters': m.supported_parameters,
        } for m in models]

    def health_check(self) -> dict[str, str]:
        """Basic health status for the LLMRouter."""
        return super().health_check()
