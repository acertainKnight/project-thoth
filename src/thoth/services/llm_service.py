"""
LLM service for managing language model interactions.

This module consolidates all LLM-related operations including client
initialization, prompt management, and model selection.
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from thoth.services.base import BaseService, ServiceError
from thoth.services.llm.factory import LLMFactory
from thoth.services.llm.protocols import UnifiedLLMClient


class LLMService(BaseService):
    """
    Service for managing LLM operations.

    This service consolidates:
    - LLM client initialization and configuration
    - Prompt template management
    - Model selection and switching
    - Structured output generation
    - Error handling and retries
    """

    def __init__(self, config=None):
        """
        Initialize the LLMService.

        Args:
            config: Optional configuration object
        """
        super().__init__(config)
        self._clients = {}  # Cache for different model clients
        self._structured_clients: dict[str, Any] = {}
        self._prompt_templates: dict[str, ChatPromptTemplate] = {}
        self.factory = LLMFactory()

        # Register for config reload notifications
        if self.config:
            from thoth.config import Config

            Config.register_reload_callback('llm_service', self._on_config_reload)
            self.logger.debug('LLMService registered for config reload notifications')

    def initialize(self) -> None:
        """Initialize the LLM service."""
        self.logger.info('LLM service initialized')

    def _on_config_reload(self, config: 'Config') -> None:  # noqa: ARG002, F821
        """
        Handle configuration reload for LLM service.

        Args:
            config: Updated configuration object

        Updates:
        - Model settings (temperature, max_tokens, etc.)
        - Model selection if changed
        - API keys (from config)
        - Clears client cache to force recreation
        """
        try:
            self.logger.info('Reloading LLM configuration...')

            # Track what's changing
            old_cache_size = len(self._clients)

            # Clear client cache to force recreation with new config
            self._clients.clear()
            self._structured_clients.clear()

            # Log configuration changes
            self.logger.info(f'Cleared {old_cache_size} cached LLM clients')
            self.logger.info(f'Default model: {self.config.llm_config.model}')
            self.logger.info(
                f'Temperature: {self.config.llm_config.model_settings.temperature}'
            )
            self.logger.info(
                f'Max tokens: {self.config.llm_config.model_settings.max_tokens}'
            )

            # Log citation model if available
            if hasattr(self.config, 'llm_config') and hasattr(
                self.config.llm_config, 'citation'
            ):
                self.logger.info(
                    f'Citation model: {self.config.llm_config.citation.model}'
                )

            self.logger.success('✅ LLM config reloaded')

        except Exception as e:
            self.logger.error(f'LLM config reload failed: {e}')

    def _get_client(
        self,
        provider: str,
        **config: Any,
    ) -> UnifiedLLMClient:
        """Create a client using the LLM factory."""
        try:
            return self.factory.create_client(provider, config)
        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"creating client for provider '{provider}'")
            ) from e

    def get_client(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_rate_limiter: bool = True,
        provider: str | None = None,
        **kwargs,
    ) -> Any:
        """
        Get or create an LLM client with specified configuration.

        Args:
            model: Model to use (defaults to config)
            temperature: Temperature setting
            max_tokens: Maximum tokens
            use_rate_limiter: Whether to use rate limiting
            provider: Provider to use (openai, anthropic, openrouter, etc.)
            **kwargs: Additional model parameters

        Returns:
            Any: Configured LLM client

        Raises:
            ServiceError: If client creation fails
        """
        try:
            # Use defaults from config
            if model is None:
                model = self.config.llm_config.model
            if temperature is None:
                temperature = self.config.llm_config.model_settings.temperature
            if max_tokens is None:
                max_tokens = self.config.llm_config.model_settings.max_tokens
            if provider is None and hasattr(self.config.llm_config, 'provider'):
                provider = self.config.llm_config.provider

            # Create cache key including provider
            cache_key = f'{provider}_{model}_{temperature}_{max_tokens}'

            # Check cache
            if cache_key in self._clients:
                return self._clients[cache_key]

            # Merge kwargs with config
            model_kwargs = self.config.llm_config.model_settings.model_dump()
            model_kwargs.update(kwargs)

            # Remove parameters that we're passing explicitly to avoid conflicts
            model_kwargs.pop('model', None)  # We're passing model explicitly
            model_kwargs.pop('temperature', None)
            model_kwargs.pop('max_tokens', None)
            model_kwargs.pop('use_rate_limiter', None)

            # Remove Thoth-specific parameters that are not valid LangChain/API parameters  # noqa: W505
            thoth_specific_params = [
                'doc_processing',
                'max_output_tokens',
                'max_context_length',
                'chunk_size',
                'chunk_overlap',
                'refine_threshold_multiplier',
                'map_reduce_threshold_multiplier',
                'consolidate_model',
                'suggest_model',
                'map_model',
            ]
            for param in thoth_specific_params:
                model_kwargs.pop(param, None)

            # Determine provider - ALWAYS default to openrouter
            # unless explicitly specified
            # Provider precedence:
            # 1. Explicitly passed provider parameter
            # 2. Provider from config
            # 3. Default to openrouter (DO NOT extract from model string)
            if provider is None:
                # Default to OpenRouter - it supports all providers through unified API
                provider = 'openrouter'

            # For OpenRouter, ensure model has provider prefix
            if provider == 'openrouter' and '/' not in model:
                # Add appropriate prefix based on model name
                if 'gpt' in model.lower():
                    model = f'openai/{model}'
                elif 'claude' in model.lower():
                    model = f'anthropic/{model}'
                elif 'mistral' in model.lower() or 'mixtral' in model.lower():
                    model = f'mistralai/{model}'
                elif 'gemini' in model.lower():
                    model = f'google/{model}'
                # If we can't determine, keep as is and let OpenRouter handle it

            cfg = dict(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                use_rate_limiter=use_rate_limiter,
                **model_kwargs,
            )

            # Set appropriate API key based on provider
            if provider == 'openai' and self.config.api_keys.openai_key:
                cfg['api_key'] = self.config.api_keys.openai_key
            elif provider == 'anthropic' and self.config.api_keys.anthropic_key:
                cfg['api_key'] = self.config.api_keys.anthropic_key
            elif provider == 'openrouter':
                cfg['api_key'] = self.config.api_keys.openrouter_key
            else:
                # Default to openrouter if no specific provider key
                provider = 'openrouter'
                cfg['api_key'] = self.config.api_keys.openrouter_key

            client = self._get_client(provider, **cfg)

            # Cache and return
            self._clients[cache_key] = client

            self.log_operation(
                'client_created',
                model=model,
                provider=provider,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return client

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"creating LLM client for model '{model}'")
            ) from e

    def get_llm(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_rate_limiter: bool = True,
        **kwargs,
    ) -> Any:
        """
        Get an LLM client (alias for get_client for backward compatibility).

        Args:
            model: Model to use (defaults to config)
            temperature: Temperature setting
            max_tokens: Maximum tokens
            use_rate_limiter: Whether to use rate limiting
            **kwargs: Additional model parameters

        Returns:
            Any: Configured LLM client

        Raises:
            ServiceError: If client creation fails
        """
        return self.get_client(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            use_rate_limiter=use_rate_limiter,
            **kwargs,
        )

    def get_structured_client(
        self,
        schema: type[BaseModel],
        model: str | None = None,
        method: str = 'json_schema',
        include_raw: bool = False,
        **client_kwargs,
    ) -> Any:
        """
        Get an LLM client configured for structured output.

        Args:
            schema: Pydantic model schema for output
            model: Model to use
            method: Structured output method
            include_raw: Whether to include raw response
            **client_kwargs: Additional client parameters

        Returns:
            Structured LLM client

        Raises:
            ServiceError: If client creation fails
        """
        try:
            # Get base client
            client = self.get_client(model=model, **client_kwargs)

            # Create structured client
            structured_client = client.with_structured_output(
                schema,
                include_raw=include_raw,
                method=method,
            )

            self.log_operation(
                'structured_client_created',
                schema=schema.__name__,
                method=method,
            )

            return structured_client

        except Exception as e:
            raise ServiceError(
                self.handle_error(
                    e, f'creating structured client for {schema.__name__}'
                )
            ) from e

    def create_prompt_template(
        self,
        template: str,
        template_format: str = 'f-string',
        validate_template: bool = True,
    ) -> ChatPromptTemplate:
        """
        Create a chat prompt template.

        Args:
            template: Template string
            template_format: Format type ('f-string' or 'jinja2')
            validate_template: Whether to validate the template

        Returns:
            ChatPromptTemplate: Created template

        Raises:
            ServiceError: If template creation fails
        """
        try:
            prompt_template = ChatPromptTemplate.from_template(
                template=template,
                template_format=template_format,
                validate_template=validate_template,
            )

            self.log_operation(
                'prompt_template_created',
                format=template_format,
            )

            return prompt_template

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'creating prompt template')) from e

    def invoke_with_retry(
        self,
        client: Any,
        input_data: Any,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Any:
        """
        Invoke LLM with retry logic.

        Args:
            client: LLM client to invoke
            input_data: Input data for the client
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries

        Returns:
            Response from the LLM

        Raises:
            ServiceError: If all retries fail
        """
        import time

        last_error = None

        for attempt in range(max_retries):
            try:
                response = client.invoke(input_data)

                self.log_operation(
                    'llm_invoked',
                    attempt=attempt + 1,
                    success=True,
                )

                return response

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f'LLM invocation failed (attempt {attempt + 1}/{max_retries}): {e}'
                )

                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue

        raise ServiceError(
            self.handle_error(last_error, f'invoking LLM after {max_retries} attempts')
        )

    def get_model_config(self, model_type: str) -> dict[str, Any]:
        """
        Get configuration for a specific model type.

        Args:
            model_type: Type of model (e.g., 'analysis', 'citation', 'filter')

        Returns:
            dict[str, Any]: Model configuration
        """
        try:
            configs = {
                'analysis': {
                    'model': self.config.llm_config.model,
                    'settings': self.config.llm_config.model_settings.model_dump(),
                    'max_output_tokens': self.config.llm_config.max_output_tokens,
                    'max_context_length': self.config.llm_config.max_context_length,
                },
                'citation': {
                    'model': self.config.llm_config.citation.model,
                    'temperature': self.config.llm_config.citation.temperature,
                    'max_tokens': self.config.llm_config.citation.max_tokens,
                    'max_output_tokens': self.config.llm_config.citation.max_output_tokens,
                },
                'filter': {
                    'model': self.config.llm_config.scrape_filter.model,
                    'settings': self.config.llm_config.scrape_filter.model_settings.model_dump(),
                    'max_output_tokens': self.config.llm_config.scrape_filter.max_output_tokens,
                },
                'agent': {
                    'model': self.config.llm_config.research_agent.model,
                    'settings': self.config.llm_config.research_agent.model_settings.model_dump(),
                    'max_output_tokens': self.config.llm_config.research_agent.max_output_tokens,
                },
                'tag': {
                    'consolidate_model': self.config.llm_config.tag_consolidator.consolidate_model,
                    'suggest_model': self.config.llm_config.tag_consolidator.suggest_model,
                    'map_model': self.config.llm_config.tag_consolidator.map_model,
                    'settings': self.config.llm_config.tag_consolidator.model_dump(),
                },
            }

            return configs.get(model_type, configs['analysis'])

        except Exception as e:
            self.logger.error(self.handle_error(e, f'getting config for {model_type}'))
            return {}

    def clear_cache(self) -> None:
        """Clear the client cache."""
        self._clients.clear()

        self.log_operation('cache_cleared', count=len(self._clients))

    async def extract_json(
        self, prompt: str, model: str | None = None, **kwargs
    ) -> dict:
        """
        Extract structured JSON from an LLM response.

        Args:
            prompt: The prompt to send to the LLM
            model: Optional model to use (defaults to configured model)
            **kwargs: Additional arguments for the LLM client

        Returns:
            dict: Parsed JSON response

        Raises:
            ServiceError: If JSON extraction fails
        """
        import json
        import re

        try:
            # Get LLM client
            client = self.get_client(model=model, **kwargs)

            # Add JSON formatting instructions to prompt
            enhanced_prompt = f"""
            {prompt}

            IMPORTANT: Return ONLY valid JSON. Do not include any explanations or text outside the JSON object.
            """

            # Get response from LLM
            response = self.invoke_with_retry(client, enhanced_prompt)

            # Extract content from response
            content = (
                response.content if hasattr(response, 'content') else str(response)
            )

            # Try to extract JSON from the response
            # Look for JSON object patterns
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
            else:
                json_str = content.strip()

            # Parse JSON
            parsed_json = json.loads(json_str)

            self.log_operation(
                'json_extracted',
                prompt_length=len(prompt),
                response_length=len(content),
                success=True,
            )

            return parsed_json

        except json.JSONDecodeError as e:
            self.logger.error(f'Failed to parse JSON from LLM response: {e}')
            self.logger.debug(f'Raw response: {content}')

            # Return a fallback structure
            return {
                'type': 'research',
                'name': 'custom-agent',
                'domain': None,
                'focus': 'academic research',
                'capabilities': [
                    'Research assistance',
                    'Literature analysis',
                    'Knowledge synthesis',
                ],
            }

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, 'extracting JSON from LLM response')
            ) from e

    def health_check(self) -> dict[str, str]:
        """Basic health status for the LLMService."""
        return super().health_check()
