"""
Browser action executor with retry logic and parameter substitution.

This module provides the ActionExecutor class for executing individual browser
actions with intelligent element selection, retry mechanisms, and dynamic content handling.
"""  # noqa: W505

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union  # noqa: F401, UP035

# Make playwright imports optional to avoid blocking if not installed
if TYPE_CHECKING:
    from playwright.async_api import ElementHandle, Page

    PlaywrightTimeout = TimeoutError
else:
    try:
        from playwright.async_api import ElementHandle, Page
        from playwright.async_api import TimeoutError as PlaywrightTimeout
    except ImportError:
        # Playwright not installed - create placeholders
        Page = None  # type: ignore
        ElementHandle = None  # type: ignore
        PlaywrightTimeout = TimeoutError  # type: ignore

from thoth.utilities.schemas.browser_workflow import (
    ElementSelector,
    WaitCondition,
    WorkflowAction,
)

logger = logging.getLogger(__name__)


# Simple result class for action execution
class ActionResult:
    def __init__(self, success: bool, data: Any = None, error: str = None):  # noqa: RUF013
        self.success = success
        self.data = data
        self.error = error


class ActionExecutor:
    """Execute browser actions with retry logic and parameter substitution."""

    def __init__(
        self,
        page: Page,
        default_timeout: int = 30000,
        max_retries: int = 3,
    ):
        """
        Initialize action executor.

        Args:
            page: Playwright page instance
            default_timeout: Default timeout in milliseconds
            max_retries: Maximum retry attempts
        """
        self.page = page
        self.default_timeout = default_timeout
        self.max_retries = max_retries

    async def execute_action(
        self,
        action: WorkflowAction,
        parameters: Dict[str, Any] | None = None,  # noqa: UP006
    ) -> ActionResult:
        """
        Execute single workflow action with retries.

        Args:
            action: Workflow action to execute
            parameters: Parameters for substitution

        Returns:
            ActionResult with success status and extracted data
        """
        parameters = parameters or {}

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f'Executing action {action.action_type.value} '
                    f'(attempt {attempt + 1}/{self.max_retries})'
                )

                # Execute based on action type
                if action.action_type == ActionType.NAVIGATE:  # noqa: F821
                    result = await self._execute_navigate(action, parameters)
                elif action.action_type == ActionType.CLICK:  # noqa: F821
                    result = await self._execute_click(action, parameters)
                elif action.action_type == ActionType.TYPE:  # noqa: F821
                    result = await self._execute_type(action, parameters)
                elif action.action_type == ActionType.WAIT:  # noqa: F821
                    result = await self._execute_wait(action, parameters)
                elif action.action_type == ActionType.SELECT:  # noqa: F821
                    result = await self._execute_select(action, parameters)
                elif action.action_type == ActionType.EXTRACT:  # noqa: F821
                    result = await self._execute_extract(action, parameters)
                else:
                    raise ValueError(f'Unknown action type: {action.action_type}')

                logger.info(f'Action {action.action_type.value} succeeded')
                return result

            except PlaywrightTimeout as e:
                logger.warning(
                    f'Timeout on attempt {attempt + 1}/{self.max_retries}: {e}'
                )
                if attempt < self.max_retries - 1:
                    await self._exponential_backoff(attempt)
                else:
                    return ActionResult(
                        success=False,
                        error=f'Timeout after {self.max_retries} attempts: {str(e)}',  # noqa: RUF010
                    )

            except Exception as e:
                logger.error(
                    f'Error on attempt {attempt + 1}/{self.max_retries}: {e}',
                    exc_info=True,
                )
                if attempt < self.max_retries - 1:
                    await self._exponential_backoff(attempt)
                else:
                    return ActionResult(
                        success=False,
                        error=f'Failed after {self.max_retries} attempts: {str(e)}',  # noqa: RUF010
                    )

        return ActionResult(
            success=False,
            error=f'Failed after {self.max_retries} attempts',
        )

    async def _execute_navigate(
        self,
        action: WorkflowAction,
        parameters: Dict[str, Any],  # noqa: UP006
    ) -> ActionResult:
        """Execute navigation action."""
        url = await self._substitute_parameters(action.value, parameters)
        wait_strategy = action.wait_strategy or WaitStrategy.NETWORKIDLE  # noqa: F821

        await self.page.goto(
            url,
            wait_until=wait_strategy.value,
            timeout=action.timeout or self.default_timeout,
        )

        return ActionResult(
            success=True,
            data={'url': self.page.url},
        )

    async def _execute_click(
        self,
        action: WorkflowAction,
        parameters: Dict[str, Any],  # noqa: ARG002, UP006
    ) -> ActionResult:
        """Execute click action."""
        if not action.selector:
            raise ValueError('Click action requires selector')

        element = await self._find_element(
            action.selector,
            timeout=action.timeout or self.default_timeout,
        )

        await element.click()

        # Wait for navigation if specified
        if action.wait_strategy:
            await self._wait_for_strategy(
                action.wait_strategy,
                action.timeout or self.default_timeout,
            )

        return ActionResult(success=True)

    async def _execute_type(
        self,
        action: WorkflowAction,
        parameters: Dict[str, Any],  # noqa: UP006
    ) -> ActionResult:
        """Execute type action."""
        if not action.selector:
            raise ValueError('Type action requires selector')

        value = await self._substitute_parameters(action.value, parameters)

        element = await self._find_element(
            action.selector,
            timeout=action.timeout or self.default_timeout,
        )

        # Clear existing content
        await element.click(click_count=3)  # Select all
        await element.press('Backspace')

        # Type new content
        await element.type(value, delay=50)  # 50ms delay between keystrokes

        return ActionResult(
            success=True,
            data={'typed_value': value},
        )

    async def _execute_wait(
        self,
        action: WorkflowAction,
        parameters: Dict[str, Any],  # noqa: ARG002, UP006
    ) -> ActionResult:
        """Execute wait action."""
        wait_strategy = action.wait_strategy or WaitStrategy.TIMEOUT  # noqa: F821

        if wait_strategy == WaitStrategy.TIMEOUT:  # noqa: F821
            # Wait for specified duration
            timeout = action.timeout or 1000
            await asyncio.sleep(timeout / 1000.0)
        elif wait_strategy == WaitStrategy.SELECTOR:  # noqa: F821
            # Wait for selector to appear
            if not action.selector:
                raise ValueError('Selector wait strategy requires selector')
            await self._find_element(
                action.selector,
                timeout=action.timeout or self.default_timeout,
            )
        else:
            # Wait for page load state
            await self._wait_for_strategy(
                wait_strategy,
                action.timeout or self.default_timeout,
            )

        return ActionResult(success=True)

    async def _execute_select(
        self,
        action: WorkflowAction,
        parameters: Dict[str, Any],  # noqa: UP006
    ) -> ActionResult:
        """Execute select action."""
        if not action.selector:
            raise ValueError('Select action requires selector')

        value = await self._substitute_parameters(action.value, parameters)

        element = await self._find_element(
            action.selector,
            timeout=action.timeout or self.default_timeout,
        )

        # Select by value, label, or index
        await element.select_option(value)

        return ActionResult(
            success=True,
            data={'selected_value': value},
        )

    async def _execute_extract(
        self,
        action: WorkflowAction,
        parameters: Dict[str, Any],  # noqa: ARG002, UP006
    ) -> ActionResult:
        """Execute extract action."""
        if not action.selector:
            raise ValueError('Extract action requires selector')

        element = await self._find_element(
            action.selector,
            timeout=action.timeout or self.default_timeout,
        )

        # Extract based on extraction_type
        extraction_type = action.extraction_type or 'text'

        if extraction_type == 'text':
            data = await element.inner_text()
        elif extraction_type == 'html':
            data = await element.inner_html()
        elif extraction_type == 'attribute':
            if not action.value:
                raise ValueError('Attribute extraction requires value (attribute name)')
            data = await element.get_attribute(action.value)
        else:
            raise ValueError(f'Unknown extraction type: {extraction_type}')

        return ActionResult(
            success=True,
            data={'extracted_data': data},
        )

    async def _find_element(
        self,
        selector: ElementSelector,
        timeout: int,
    ) -> ElementHandle:
        """
        Find element with multi-strategy fallback.

        Args:
            selector: Element selector with multiple strategies
            timeout: Timeout in milliseconds

        Returns:
            ElementHandle instance

        Raises:
            PlaywrightTimeout: If element not found
        """
        # Try CSS selector first
        if selector.css:
            try:
                element = await self.page.wait_for_selector(
                    selector.css,
                    timeout=timeout,
                    state='visible',
                )
                if element:
                    return element
            except PlaywrightTimeout:
                logger.debug(f'CSS selector failed: {selector.css}')

        # Try XPath selector
        if selector.xpath:
            try:
                element = await self.page.wait_for_selector(
                    f'xpath={selector.xpath}',
                    timeout=timeout,
                    state='visible',
                )
                if element:
                    return element
            except PlaywrightTimeout:
                logger.debug(f'XPath selector failed: {selector.xpath}')

        # Try text content selector
        if selector.text:
            try:
                element = await self.page.wait_for_selector(
                    f'text={selector.text}',
                    timeout=timeout,
                    state='visible',
                )
                if element:
                    return element
            except PlaywrightTimeout:
                logger.debug(f'Text selector failed: {selector.text}')

        # All strategies failed
        raise PlaywrightTimeout(
            f'Element not found with any strategy: '
            f'css={selector.css}, xpath={selector.xpath}, text={selector.text}'
        )

    async def _substitute_parameters(
        self,
        value: str,
        parameters: Dict[str, Any],  # noqa: UP006
    ) -> str:
        """
        Replace {param_name} with actual values.

        Args:
            value: String containing parameter placeholders
            parameters: Dictionary of parameter values

        Returns:
            String with substituted values
        """
        if not value:
            return value

        # Find all parameter placeholders
        pattern = r'\{([^}]+)\}'

        def replace_param(match: re.Match) -> str:
            param_name = match.group(1)
            if param_name in parameters:
                return str(parameters[param_name])
            logger.warning(f'Parameter not found: {param_name}')
            return match.group(0)  # Return original if not found

        return re.sub(pattern, replace_param, value)

    async def _wait_for_strategy(
        self,
        strategy: WaitCondition,
        timeout: int,
    ) -> None:
        """
        Wait for specific page load strategy.

        Args:
            strategy: Wait strategy to use
            timeout: Timeout in milliseconds
        """
        if strategy == WaitStrategy.LOAD:  # noqa: F821
            await self.page.wait_for_load_state('load', timeout=timeout)
        elif strategy == WaitStrategy.DOMCONTENTLOADED:  # noqa: F821
            await self.page.wait_for_load_state('domcontentloaded', timeout=timeout)
        elif strategy == WaitStrategy.NETWORKIDLE:  # noqa: F821
            await self.page.wait_for_load_state('networkidle', timeout=timeout)

    async def _exponential_backoff(self, attempt: int) -> None:
        """
        Wait with exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
        """
        wait_time = min(2**attempt, 8)  # Max 8 seconds
        logger.info(f'Retrying in {wait_time} seconds...')
        await asyncio.sleep(wait_time)
