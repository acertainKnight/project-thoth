"""MCP tool for checking whether new Thoth features are available."""

from typing import Any

from thoth import __version__
from thoth.mcp.base_tools import MCPTool, MCPToolCallResult

# Version-keyed changelog entries. Add a new entry here when shipping features
# worth surfacing to users. Keep entries concise -- the agent will narrate them.
_CHANGELOG: dict[str, list[str]] = {
    '1.0.0': [
        'Initial release: paper discovery, PDF processing, knowledge base Q&A',
        'Dynamic skill system: load specialized capabilities on demand',
        'Research questions: automated recurring searches across ArXiv, Semantic Scholar, and more',
        'RAG search: hybrid semantic + keyword search with optional LLM reranking',
        'Customizable extraction schemas: control what information is pulled from papers',
        'MCP server support: connect external tools and data sources',
        'Multi-user mode: isolated vaults and agents per user',
    ],
}


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a semver string into a comparable tuple, ignoring pre-release suffixes."""
    core = v.split('-')[0]
    try:
        return tuple(int(x) for x in core.split('.'))
    except ValueError:
        return (0,)


def _changes_since(last_seen: str) -> list[tuple[str, list[str]]]:
    """Return changelog entries for versions strictly newer than last_seen."""
    last = _parse_version(last_seen)
    newer = [
        (version, items)
        for version, items in sorted(
            _CHANGELOG.items(), key=lambda x: _parse_version(x[0])
        )
        if _parse_version(version) > last
    ]
    return newer


class CheckWhatsNewMCPTool(MCPTool):
    """Check whether there are new Thoth features since the user's last walkthrough."""

    @property
    def name(self) -> str:
        return 'check_whats_new'

    @property
    def description(self) -> str:
        return (
            "Check whether Thoth has new features since the user's last onboarding or update "
            'walkthrough. Returns the current server version and a list of changes for any '
            'versions newer than last_seen_version. Pass the last_seen_version from the human '
            "memory block (or '0.0.0' if not set). Use this at the start of a conversation "
            "when you notice the user's last_seen_version doesn't match the current version."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'last_seen_version': {
                    'type': 'string',
                    'description': (
                        "The version string from the user's human memory block "
                        "(last_seen_version field). Pass '0.0.0' if not set."
                    ),
                },
            },
            'required': ['last_seen_version'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        last_seen = (arguments.get('last_seen_version') or '0.0.0').strip()
        current = __version__

        newer = _changes_since(last_seen)

        if not newer:
            return MCPToolCallResult(
                content=f'No new features since version {last_seen}. Current version: {current}.'
            )

        lines = [
            f'Current version: {current}\n',
            "What's new since your last walkthrough:\n",
        ]
        for version, items in newer:
            lines.append(f'Version {version}:')
            for item in items:
                lines.append(f'  - {item}')
            lines.append('')

        lines.append(
            'You can walk the user through any of these. After they acknowledge, '
            f'update last_seen_version to {current!r} in the human memory block.'
        )

        return MCPToolCallResult(content='\n'.join(lines))
