"""Base classes for discovery tools."""

from typing import Any

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult


class CreateSourceBaseTool(MCPTool):
    """Base class for discovery source creation tools."""
    
    source_type: str = ''
    source_emoji: str = '📚'
    
    def create_source(self, config: dict[str, Any]) -> MCPToolCallResult:
        """Create a discovery source with the given configuration."""
        try:
            # Save the source
            self.service_manager.discovery.create_source(config)

            # Format response
            response = f"{self.source_emoji} **{self.source_type.upper()} Discovery Source Created**\n\n"
            response += f"**Name:** {config['name']}\n"
            
            # Add type-specific details
            response += self.format_source_details(config)
            
            response += f"**Max Results:** {config.get('max_results', 50)}\n"
            response += f"**Status:** {'✅ Active' if config.get('enabled', True) else '❌ Disabled'}\n\n"
            response += f"The system will now periodically check {self.source_type.upper()} for new papers."

            return MCPToolCallResult(content=response, is_error=False)

        except ValueError as e:
            return MCPToolCallResult(
                content=f'Invalid configuration: {str(e)}', is_error=True
            )
        except Exception as e:
            return MCPToolCallResult(
                content=f'Error creating {self.source_type} source: {str(e)}', is_error=True
            )
    
    def format_source_details(self, config: dict[str, Any]) -> str:
        """Format source-specific details. Override in subclasses."""
        return ""