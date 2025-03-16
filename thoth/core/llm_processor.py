"""
LLM Processor for Thoth.

This module handles the analysis of content and extraction of citations using LLM.
"""

import json
import logging
from typing import Any

import requests
from jinja2 import Environment, FileSystemLoader
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Exception raised for errors in the LLM processing."""

    pass


class OpenRouterClient:
    """Client for interacting with the OpenRouter API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        lite_mode: bool = False,
        templates_dir: str = "templates/prompts",
    ):
        """
        Initialize the OpenRouter client.

        Args:
            api_key (str): The OpenRouter API key.
            base_url (str): The base URL for the OpenRouter API.
            lite_mode (bool): Whether to use lite mode for simpler responses.
            templates_dir (str): Directory containing Jinja2 prompt templates.
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://thoth.ai",  # Replace with your actual domain
        }

        # Add lite mode header if requested
        if lite_mode:
            self.headers["OpenRouter-Lite"] = "true"

        # Set up Jinja2 environment for prompt templates
        self.templates_dir = templates_dir
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        logger.debug("OpenRouter client initialized")

    def call_api(
        self,
        messages: list[dict[str, str]],
        model: str = "anthropic/claude-3-opus",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: dict[str, str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        Call the OpenRouter API with the given messages.

        Args:
            messages (List[Dict[str, str]]): The messages to send to the API.
            model (str): The model to use for the API call.
            temperature (float): The temperature for the API call.
            max_tokens (int): The maximum number of tokens to generate.
            response_format (Optional[Dict[str, str]]): Format for structured responses.
            tools (Optional[List[Dict[str, Any]]]): List of tools the model can use.
            tool_choice (Optional[Union[str, Dict[str, Any]]]): Control over tool
                selection.
            stream (bool): Whether to stream the response.

        Returns:
            Dict[str, Any]: The API response.

        Raises:
            LLMError: If the API call fails.
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        # Add optional parameters if provided
        if response_format:
            payload["response_format"] = response_format

        if tools:
            payload["tools"] = tools

        if tool_choice:
            payload["tool_choice"] = tool_choice

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=300,  # 5-minute timeout for large requests
                stream=stream,
            )

            if response.status_code != 200:
                error_msg = (
                    f"OpenRouter API returned error: {response.status_code} - "
                    f"{response.text}"
                )
                logger.error(error_msg)
                raise LLMError(error_msg)

            if stream:
                return response  # Return the response object for streaming
            else:
                return response.json()

        except RequestException as e:
            error_msg = f"OpenRouter API request failed: {e!s}"
            logger.error(error_msg)
            raise LLMError(error_msg) from e

    def get_generation_stats(self, generation_id: str) -> dict[str, Any]:
        """
        Get detailed stats for a specific generation.

        Args:
            generation_id (str): The ID of the generation to query.

        Returns:
            Dict[str, Any]: Generation statistics including token counts and cost.

        Raises:
            LLMError: If the API call fails.
        """
        url = f"{self.base_url}/generation?id={generation_id}"

        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = (
                    f"OpenRouter API returned error: {response.status_code} - "
                    f"{response.text}"
                )
                logger.error(error_msg)
                raise LLMError(error_msg)

            return response.json()

        except RequestException as e:
            error_msg = f"OpenRouter stats request failed: {e!s}"
            logger.error(error_msg)
            raise LLMError(error_msg) from e

    def analyze_content(
        self,
        content: str,
        use_json_format: bool = False,
    ) -> dict[str, Any]:
        """
        Analyze content with LLM and return structured data.

        Args:
            content (str): The content to analyze.
            use_json_format (bool): Whether to request JSON formatted response.

        Returns:
            Dict[str, Any]: A dictionary containing structured analysis with keys:
                - summary: A concise summary of the paper
                - key_points: List of key points from the paper
                - limitations: List of limitations mentioned in the paper
                - research_question: The main research question addressed
        """
        logger.info("Analyzing content with LLM")

        # Render the prompt template
        try:
            template = self.jinja_env.get_template("analyze_content.j2")
            prompt_content = template.render(content=content)
        except Exception as e:
            logger.error(f"Failed to render prompt template: {e}")
            # Fallback to hardcoded prompt
            prompt_content = (
                f"Analyze the following academic paper content and provide a "
                f"structured response with:\n"
                f"1. A concise summary (2-3 sentences)\n"
                f"2. Key points (3-5 bullet points)\n"
                f"3. Limitations mentioned in the paper (if any)\n"
                f"4. The main research question addressed\n\n"
                f"Paper content:\n{content[:10000]}"
            )

        # Prepare the messages
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research assistant that analyzes academic papers."
                ),
            },
            {"role": "user", "content": prompt_content},
        ]

        try:
            # Set up response format if JSON is requested
            response_format = {"type": "json_object"} if use_json_format else None

            # Call the API
            response = self.call_api(
                messages=messages,
                response_format=response_format,
            )

            # Extract the content from the response
            generation_id = response.get("id")
            if generation_id:
                logger.debug(f"Generation ID: {generation_id}")

            # Extract content based on response structure
            content = self._extract_content_from_response(response)

            # Parse the content into structured data
            analysis = self._parse_analysis(content)

            logger.info("Successfully analyzed content with LLM")
            return analysis

        except Exception as e:
            error_msg = f"Content analysis failed: {e!s}"
            logger.error(error_msg)
            raise LLMError(error_msg) from e

    def extract_citations(
        self,
        content: str,
        use_json_format: bool = False,
        use_tools: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Extract citations from content using LLM.

        Args:
            content (str): The content to extract citations from.
            use_json_format (bool): Whether to request JSON formatted response.
            use_tools (bool): Whether to use tool calling for extraction.

        Returns:
            List[Dict[str, Any]]: A list of citation dictionaries with keys:
                - text: The full citation text
                - authors: List of author names
                - title: The title of the cited work
                - year: The publication year
                - journal: The journal name (if applicable)
                - context: The context in which the citation appears
        """
        logger.info("Extracting citations with LLM")

        # Look for a references section
        references_section = self._extract_references_section(content)
        if not references_section:
            logger.warning("No references section found in content")
            return []

        # If using tool calling, define the citation extraction tool
        if use_tools:
            return self._extract_citations_with_tools(references_section)

        # Otherwise use standard prompt approach
        # Render the prompt template
        try:
            template = self.jinja_env.get_template("extract_citations.j2")
            prompt_content = template.render(references_section=references_section)
        except Exception as e:
            logger.error(f"Failed to render prompt template: {e}")
            # Fallback to hardcoded prompt
            prompt_content = (
                f"Extract and structure the citations from the following references "
                f"section of an academic paper.\n"
                f"For each citation, provide:\n"
                f"1. The full citation text\n"
                f"2. List of authors\n"
                f"3. Title of the cited work\n"
                f"4. Publication year\n"
                f"5. Journal name (if applicable)\n"
                f"6. Any context from the paper where this citation is referenced "
                f"(if you can find it)\n\n"
                f"Format your response as a JSON array of citation objects.\n\n"
                f"References section:\n{references_section}"
            )

        # Prepare the messages
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research assistant that extracts citation information."
                ),
            },
            {"role": "user", "content": prompt_content},
        ]

        try:
            # Set up response format if JSON is requested
            response_format = {"type": "json_object"} if use_json_format else None

            # Call the API
            response = self.call_api(
                messages=messages,
                response_format=response_format,
            )

            # Extract the content from the response
            content = self._extract_content_from_response(response)

            # Parse the content into structured data
            citations = self._parse_citations(content)

            logger.info(f"Successfully extracted {len(citations)} citations with LLM")
            return citations

        except Exception as e:
            error_msg = f"Citation extraction failed: {e!s}"
            logger.error(error_msg)
            raise LLMError(error_msg) from e

    def _extract_citations_with_tools(
        self, references_section: str
    ) -> list[dict[str, Any]]:
        """
        Extract citations using tool calling.

        Args:
            references_section (str): The references section to extract citations from.

        Returns:
            List[Dict[str, Any]]: A list of structured citation dictionaries.
        """
        # Define the citation extraction tool
        citation_tool = {
            "type": "function",
            "function": {
                "name": "extract_citation",
                "description": "Extract structured information from a citation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The full citation text",
                        },
                        "authors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of author names",
                        },
                        "title": {
                            "type": "string",
                            "description": "Title of the cited work",
                        },
                        "year": {"type": "integer", "description": "Publication year"},
                        "journal": {
                            "type": "string",
                            "description": "Journal name (if applicable)",
                        },
                        "context": {
                            "type": "string",
                            "description": "Context in which the citation appears",
                        },
                    },
                    "required": ["text", "authors", "title"],
                },
            },
        }

        # Render the prompt template
        try:
            template = self.jinja_env.get_template("extract_citations_tools.j2")
            prompt_content = template.render(references_section=references_section)
        except Exception as e:
            logger.error(f"Failed to render prompt template: {e}")
            # Fallback to hardcoded prompt
            prompt_content = (
                f"Extract structured information from each citation in the following "
                f"references section.\n"
                f"Use the extract_citation tool for each citation you find.\n\n"
                f"References section:\n{references_section}"
            )

        # Prepare the prompt
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research assistant that extracts citation information."
                ),
            },
            {"role": "user", "content": prompt_content},
        ]

        # Call the API with tool
        response = self.call_api(
            messages=messages,
            tools=[citation_tool],
            tool_choice="auto",
        )

        # Process tool calls from response
        citations = []

        try:
            message = response["choices"][0]["message"]
            tool_calls = message.get("tool_calls", [])

            for tool_call in tool_calls:
                if tool_call["function"]["name"] == "extract_citation":
                    try:
                        citation_data = json.loads(tool_call["function"]["arguments"])
                        citations.append(citation_data)
                    except json.JSONDecodeError:
                        args = tool_call["function"]["arguments"]
                        logger.warning(f"Failed to parse tool call arguments: {args}")
        except (KeyError, IndexError) as e:
            logger.warning(f"Failed to extract tool calls from response: {e}")

        return citations

    def _extract_content_from_response(self, response: dict[str, Any]) -> str:
        """
        Extract content from the API response, handling different response structures.

        Args:
            response (Dict[str, Any]): The API response.

        Returns:
            str: The extracted content.

        Raises:
            LLMError: If content cannot be extracted from the response.
        """
        try:
            # Standard response structure
            if "choices" in response and len(response["choices"]) > 0:
                message = response["choices"][0].get("message", {})

                # Check for content in message
                if "content" in message and message["content"] is not None:
                    return message["content"]

                # Check for tool calls
                if "tool_calls" in message:
                    # For simplicity, we'll just return the arguments of the first tool
                    # call. In a real implementation, you'd want to handle this more
                    # robustly
                    tool_calls = message["tool_calls"]
                    if tool_calls and len(tool_calls) > 0:
                        return tool_calls[0]["function"]["arguments"]

            # If we can't find content in the expected places, return the whole response
            # as JSON
            return json.dumps(response)

        except (KeyError, IndexError, TypeError) as e:
            error_msg = f"Failed to extract content from response: {e}"
            logger.error(error_msg)
            raise LLMError(error_msg) from e

    def _extract_references_section(self, content: str) -> str | None:
        """
        Extract the references section from the content.

        Args:
            content (str): The content to extract the references section from.

        Returns:
            Optional[str]: The references section, or None if not found.
        """
        # Look for common references section headers
        for header in ["References", "Bibliography", "Works Cited", "Literature Cited"]:
            if f"## {header}" in content:
                parts = content.split(f"## {header}")
                if len(parts) > 1:
                    # Get the part after the header, up to the next section or the end
                    references = parts[1].split("##")[0].strip()
                    return references

        return None

    def _parse_analysis(self, content: str) -> dict[str, Any]:
        """
        Parse the analysis content into structured data.

        Args:
            content (str): The analysis content from the LLM.

        Returns:
            Dict[str, Any]: A structured analysis dictionary.
        """
        analysis = {
            "summary": "",
            "key_points": [],
            "limitations": [],
            "research_question": "",
        }

        # Try to extract JSON if the response is in JSON format
        try:
            # First check if the entire content is valid JSON
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return {**analysis, **parsed}
        except json.JSONDecodeError:
            # If not, try to extract JSON from within the content
            try:
                # Check if the content contains a JSON object
                json_start = content.find("{")
                json_end = content.rfind("}")
                if json_start != -1 and json_end != -1:
                    json_str = content[json_start : json_end + 1]
                    parsed = json.loads(json_str)
                    return {**analysis, **parsed}
            except json.JSONDecodeError:
                pass

        # If not JSON, parse the text format
        lines = content.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for section headers
            if "summary" in line.lower() and ":" in line:
                current_section = "summary"
                analysis["summary"] = line.split(":", 1)[1].strip()
            elif "key points" in line.lower() and ":" in line:
                current_section = "key_points"
            elif "limitations" in line.lower() and ":" in line:
                current_section = "limitations"
            elif "research question" in line.lower() and ":" in line:
                current_section = "research_question"
                analysis["research_question"] = line.split(":", 1)[1].strip()
            # Process bullet points
            elif line.startswith("- ") or line.startswith("* "):
                if current_section == "key_points":
                    analysis["key_points"].append(line[2:].strip())
                elif current_section == "limitations":
                    analysis["limitations"].append(line[2:].strip())

        return analysis

    def _parse_citations(self, content: str) -> list[dict[str, Any]]:
        """
        Parse the citations content into structured data.

        Args:
            content (str): The citations content from the LLM.

        Returns:
            List[Dict[str, Any]]: A list of structured citation dictionaries.
        """
        citations = []

        # Try to extract JSON if the response is in JSON format
        try:
            # First check if the entire content is valid JSON
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict) and "citations" in parsed:
                return parsed["citations"]
        except json.JSONDecodeError:
            # If not, try to extract JSON from within the content
            try:
                # Find JSON array in the content
                json_start = content.find("[")
                json_end = content.rfind("]")
                if json_start != -1 and json_end != -1:
                    json_str = content[json_start : json_end + 1]
                    parsed = json.loads(json_str)
                    if isinstance(parsed, list):
                        return parsed
            except json.JSONDecodeError:
                pass

        # If not JSON, parse the text format (fallback)
        # This is a simplified parser and may not work for all formats
        lines = content.split("\n")
        current_citation = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for citation number/index
            if line.startswith("[") and "]" in line:
                # Start a new citation
                if current_citation:
                    citations.append(current_citation)

                current_citation = {
                    "text": line,
                    "authors": [],
                    "title": "",
                    "year": None,
                    "journal": "",
                    "context": "",
                }
            elif current_citation:
                # Add to the current citation text
                current_citation["text"] += " " + line

        # Add the last citation
        if current_citation:
            citations.append(current_citation)

        return citations


class LLMProcessor:
    """
    Processes content using LLM for analysis and citation extraction.

    This class handles the analysis of content and extraction of citations
    using the OpenRouter API.
    """

    def __init__(
        self,
        api_key: str,
        lite_mode: bool = False,
        use_json_format: bool = False,
        use_tools: bool = False,
        templates_dir: str = "templates/prompts",
    ):
        """
        Initialize the LLM Processor.

        Args:
            api_key (str): The OpenRouter API key.
            lite_mode (bool): Whether to use lite mode for simpler responses.
            use_json_format (bool): Whether to request JSON formatted responses.
            use_tools (bool): Whether to use tool calling for structured extraction.
            templates_dir (str): Directory containing Jinja2 prompt templates.
        """
        self.client = OpenRouterClient(
            api_key, lite_mode=lite_mode, templates_dir=templates_dir
        )
        self.use_json_format = use_json_format
        self.use_tools = use_tools
        logger.debug("LLM Processor initialized")

    def analyze_content(
        self,
        content: str,
    ) -> dict[str, Any]:
        """
        Analyze content with LLM and return structured data.

        Args:
            content (str): The content to analyze.

        Returns:
            Dict[str, Any]: A dictionary containing structured analysis.

        Raises:
            LLMError: If the analysis fails.
        """
        return self.client.analyze_content(
            content=content,
            use_json_format=self.use_json_format,
        )

    def extract_citations(
        self,
        content: str,
    ) -> list[dict[str, Any]]:
        """
        Extract citations from content using LLM.

        Args:
            content (str): The content to extract citations from.

        Returns:
            List[Dict[str, Any]]: A list of citation dictionaries.

        Raises:
            LLMError: If the extraction fails.
        """
        return self.client.extract_citations(
            content=content,
            use_json_format=self.use_json_format,
            use_tools=self.use_tools,
        )

    def get_generation_stats(self, generation_id: str) -> dict[str, Any]:
        """
        Get detailed stats for a specific generation.

        Args:
            generation_id (str): The ID of the generation to query.

        Returns:
            Dict[str, Any]: Generation statistics including token counts and cost.
        """
        return self.client.get_generation_stats(generation_id)
