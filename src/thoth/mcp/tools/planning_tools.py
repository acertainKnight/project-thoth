"""
MCP tools for creating and managing research plan documents in the Obsidian vault.

Plans are stored as markdown files in two locations:
- Internal plans (thoth/_thoth/plans/): Agent's own working research plans
- User plans (thoth/plans/): Formalized plans written for the user

Both locations are indexed into the RAG vector store so the agent can search and
reference them alongside research papers. Each plan is registered in paper_metadata
with document_category='plan', following the same pattern as external knowledge docs.
"""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from thoth.mcp.auth import get_current_user_paths
from thoth.mcp.base_tools import MCPTool, MCPToolCallResult


def _slugify(title: str) -> str:
    """Convert a plan title to a URL/filesystem-safe slug (max 100 chars).

    Args:
        title: The human-readable plan title.

    Returns:
        str: Lowercase hyphen-separated slug safe for use as a filename stem.

    Example:
        >>> _slugify('My Research Plan: 2026!')
        'my-research-plan-2026'
    """
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)
    slug = slug[:100].strip('-')
    return slug or 'untitled-plan'


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Returns:
        str: ISO 8601 datetime string (e.g. '2026-03-02T14:30:00Z').
    """
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def _resolve_plan_dirs(plan_type: str, config: Any) -> tuple[Path, str]:
    """Resolve the plans directory and a display label for the given plan_type.

    Prefers per-request UserPaths in multi-user mode so each user operates
    inside their own vault.

    Args:
        plan_type: Either 'internal' or 'user'.
        config: The global Config object.

    Returns:
        tuple[Path, str]: (absolute_plans_directory, human_readable_label)
    """
    user_paths = get_current_user_paths()
    vault_root = user_paths.vault_root if user_paths else config.vault_root
    workspace_dir = user_paths.workspace_dir if user_paths else config.workspace_dir

    if plan_type == 'internal':
        return workspace_dir / 'plans', 'internal (_thoth/plans)'
    return vault_root / 'thoth' / 'plans', 'user (plans)'


def _build_frontmatter(
    title: str,
    plan_type: str,
    status: str,
    tags: list[str],
    created: str,
    updated: str,
) -> str:
    """Render YAML frontmatter for a plan markdown file.

    Args:
        title: Plan title.
        plan_type: 'internal' or 'user'.
        status: Plan lifecycle status.
        tags: Optional list of tags.
        created: ISO 8601 creation timestamp.
        updated: ISO 8601 last-updated timestamp.

    Returns:
        str: Complete frontmatter block including leading/trailing '---' delimiters.
    """
    data: dict[str, Any] = {
        'title': title,
        'created': created,
        'updated': updated,
        'plan_type': plan_type,
        'status': status,
    }
    if tags:
        data['tags'] = tags
    return (
        '---\n' + yaml.dump(data, default_flow_style=False, allow_unicode=True) + '---'
    )


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter out of a markdown file's raw text.

    Args:
        content: Full raw file content starting with '---'.

    Returns:
        tuple[dict[str, Any], str]: (frontmatter_dict, body_text_without_frontmatter)
    """
    if not content.startswith('---'):
        return {}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        frontmatter = {}

    return frontmatter, parts[2].lstrip('\n')


async def _register_and_index_plan(
    title: str,
    markdown_content: str,
    service_manager: Any,
    config: Any,
) -> str | None:
    """Register a plan in paper_metadata and index it into the RAG vector store.

    Creates a paper_metadata row with document_category='plan' and a
    processed_papers row, then triggers async RAG indexing. Uses the same
    pattern as KnowledgeService.upload_document().

    Errors are caught and logged rather than re-raised so the calling tool
    can still report a successful file write even if DB/RAG is unavailable.

    Args:
        title: Human-readable plan title.
        markdown_content: Full markdown content of the plan.
        service_manager: Tool's ServiceManager for DB access.
        config: Global Config object for RAGService initialisation.

    Returns:
        str | None: The new paper_id (UUID string) on success, None on failure.
    """
    try:
        from thoth.mcp.auth import get_mcp_user_id
        from thoth.services.rag_service import RAGService

        postgres_service = service_manager.postgres
        user_id = get_mcp_user_id()

        async with postgres_service.acquire() as conn:
            # Check if a plan row already exists for this path to support re-indexing
            existing = await conn.fetchrow(
                """
                SELECT id FROM paper_metadata
                WHERE title = $1 AND document_category = 'plan'
                """,
                title,
            )

            if existing:
                paper_id = existing['id']
                # Update processed_papers content for re-index
                await conn.execute(
                    """
                    UPDATE processed_papers
                    SET markdown_content = $1, processed_at = NOW()
                    WHERE paper_id = $2
                    """,
                    markdown_content,
                    paper_id,
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO paper_metadata (title, title_normalized, document_category, user_id)
                    VALUES ($1, lower($1), 'plan', $2)
                    RETURNING id
                    """,
                    title,
                    user_id,
                )
                paper_id = row['id']

                await conn.execute(
                    """
                    INSERT INTO processed_papers
                        (paper_id, markdown_content, processing_status, processed_at)
                    VALUES ($1, $2, 'completed', NOW())
                    """,
                    paper_id,
                    markdown_content,
                )

        paper_id_str = str(paper_id)

        rag_service = RAGService(config)
        rag_service.initialize()
        await rag_service.index_paper_by_id_async(paper_id_str, markdown_content)

        logger.info(f'Indexed plan "{title}" as paper_id={paper_id_str}')
        return paper_id_str

    except Exception as exc:
        logger.warning(f'Could not register/index plan "{title}": {exc}')
        return None


async def _delete_plan_from_db(
    title: str,
    service_manager: Any,
) -> None:
    """Remove a plan's paper_metadata entry (cascades to document_chunks).

    Args:
        title: Title of the plan to remove (used as lookup key).
        service_manager: Tool's ServiceManager for DB access.
    """
    try:
        postgres_service = service_manager.postgres
        async with postgres_service.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM paper_metadata
                WHERE title = $1 AND document_category = 'plan'
                """,
                title,
            )
        logger.info(f'Deleted plan DB entry for "{title}"')
    except Exception as exc:
        logger.warning(f'Could not delete plan DB entry for "{title}": {exc}')


class CreatePlanMCPTool(MCPTool):
    """Create a new research plan markdown file in the Obsidian vault."""

    @property
    def name(self) -> str:
        return 'create_plan'

    @property
    def description(self) -> str:
        return (
            'Create a new research plan as a markdown file in the Obsidian vault. '
            'Use plan_type="internal" to save a working agent research plan inside '
            "_thoth/plans/ (the agent's own editable workspace). "
            'Use plan_type="user" (default) to write a formalized deliverable plan '
            'for the user in thoth/plans/. '
            'Plans are automatically indexed into the RAG system so they are '
            'searchable by answer_research_question and similar tools.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'title': {
                    'type': 'string',
                    'description': (
                        'Human-readable plan title '
                        '(e.g. "Literature Review: Transformers 2026").'
                    ),
                    'minLength': 1,
                    'maxLength': 200,
                },
                'content': {
                    'type': 'string',
                    'description': (
                        'Full markdown body of the plan (without frontmatter). '
                        'Recommended sections: ## Objective, ## Steps, ## Notes.'
                    ),
                    'minLength': 10,
                },
                'plan_type': {
                    'type': 'string',
                    'enum': ['internal', 'user'],
                    'description': (
                        '"internal" saves to _thoth/plans/ (agent working space). '
                        '"user" (default) saves to thoth/plans/ (user-facing deliverable).'
                    ),
                    'default': 'user',
                },
                'status': {
                    'type': 'string',
                    'enum': ['draft', 'active', 'complete', 'archived'],
                    'description': 'Initial plan status. Defaults to "active".',
                    'default': 'active',
                },
                'tags': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Optional list of tags for the plan.',
                    'default': [],
                },
            },
            'required': ['title', 'content'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create a new plan file, register it in the DB, and index it into RAG.

        Args:
            arguments: Tool arguments matching the input schema.

        Returns:
            MCPToolCallResult: Confirmation with file path and plan_id.
        """
        try:
            from thoth.config import config

            title = arguments.get('title', '').strip()
            content = arguments.get('content', '').strip()
            plan_type = arguments.get('plan_type', 'user').strip().lower()
            status = arguments.get('status', 'active').strip().lower()
            tags = arguments.get('tags', [])

            if not title:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Error: title is required.'}],
                    isError=True,
                )
            if not content:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Error: content is required.'}],
                    isError=True,
                )
            if plan_type not in ('internal', 'user'):
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: plan_type must be "internal" or "user".',
                        }
                    ],
                    isError=True,
                )

            plans_dir, location_label = _resolve_plan_dirs(plan_type, config)
            plans_dir.mkdir(parents=True, exist_ok=True)

            plan_id = _slugify(title)
            plan_path = plans_dir / f'{plan_id}.md'

            if plan_path.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': (
                                f'Error: A plan with id "{plan_id}" already exists at '
                                f'{plan_path}.\n'
                                'Use update_plan to modify it, or choose a different title.'
                            ),
                        }
                    ],
                    isError=True,
                )

            now = _utc_now()
            frontmatter = _build_frontmatter(
                title=title,
                plan_type=plan_type,
                status=status,
                tags=tags,
                created=now,
                updated=now,
            )
            full_content = frontmatter + '\n\n' + content + '\n'
            plan_path.write_text(full_content, encoding='utf-8')
            logger.info(f'Created plan file: {plan_path}')

            indexed = False
            if self.service_manager:
                paper_id = await _register_and_index_plan(
                    title=title,
                    markdown_content=full_content,
                    service_manager=self.service_manager,
                    config=config,
                )
                indexed = paper_id is not None
            else:
                logger.warning(
                    'No service_manager available; skipping RAG indexing for plan.'
                )

            result_lines = [
                'Plan created successfully.',
                '',
                f'**Plan ID**: `{plan_id}`',
                f'**Title**: {title}',
                f'**Type**: {location_label}',
                f'**Status**: {status}',
                f'**Location**: {plan_path}',
            ]
            if tags:
                result_lines.append(f'**Tags**: {", ".join(tags)}')
            result_lines.append('')
            if indexed:
                result_lines.append(
                    'The plan has been indexed into the RAG system and is now searchable.'
                )
            else:
                result_lines.append(
                    'Note: RAG indexing was skipped (DB unavailable). '
                    'The file has been written and will be indexed by the watcher service.'
                )
            result_lines.extend(
                [
                    'Use `update_plan` to revise it, or `get_plan` to read it back.',
                ]
            )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(result_lines)}]
            )

        except Exception as exc:
            logger.error(f'Error creating plan: {exc}')
            return self.handle_error(exc)


class ListPlansMCPTool(MCPTool):
    """List all research plans in the vault."""

    @property
    def name(self) -> str:
        return 'list_plans'

    @property
    def description(self) -> str:
        return (
            'List all research plan documents stored in the vault. '
            'Returns plan_id, title, type, status, created, and updated for each plan. '
            'Optionally filter by plan_type ("internal" or "user") or by status.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'plan_type': {
                    'type': 'string',
                    'enum': ['internal', 'user'],
                    'description': (
                        'Filter to only "internal" or "user" plans. '
                        'Omit to list all plans.'
                    ),
                },
                'status': {
                    'type': 'string',
                    'description': (
                        'Filter by status (e.g. "active", "draft", "complete"). '
                        'Omit to list all.'
                    ),
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """List plans with optional type and status filtering.

        Args:
            arguments: Tool arguments matching the input schema.

        Returns:
            MCPToolCallResult: Formatted summary list of matching plans.
        """
        try:
            from thoth.config import config

            filter_type = arguments.get('plan_type', '').strip().lower() or None
            filter_status = arguments.get('status', '').strip().lower() or None

            types_to_scan = []
            if filter_type is None or filter_type == 'internal':
                types_to_scan.append('internal')
            if filter_type is None or filter_type == 'user':
                types_to_scan.append('user')

            plans: list[dict[str, Any]] = []

            for plan_type in types_to_scan:
                plans_dir, _ = _resolve_plan_dirs(plan_type, config)
                if not plans_dir.exists():
                    continue

                for md_file in sorted(plans_dir.glob('*.md')):
                    try:
                        raw = md_file.read_text(encoding='utf-8')
                        fm, _ = _parse_frontmatter(raw)
                        entry_status = str(fm.get('status', 'unknown'))
                        if filter_status and entry_status != filter_status:
                            continue
                        plans.append(
                            {
                                'plan_id': md_file.stem,
                                'title': str(fm.get('title', md_file.stem)),
                                'plan_type': str(fm.get('plan_type', plan_type)),
                                'status': entry_status,
                                'created': str(fm.get('created', '')),
                                'updated': str(fm.get('updated', '')),
                                'tags': fm.get('tags', []),
                            }
                        )
                    except Exception as exc:
                        logger.warning(f'Could not read plan {md_file.name}: {exc}')

            if not plans:
                parts = []
                if filter_type:
                    parts.append(f'type="{filter_type}"')
                if filter_status:
                    parts.append(f'status="{filter_status}"')
                suffix = f' matching {", ".join(parts)}' if parts else ''
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': f'No plans found{suffix}.'}]
                )

            lines = [f'Found {len(plans)} plan(s):\n']
            for plan in plans:
                tag_str = f' [{", ".join(plan["tags"])}]' if plan.get('tags') else ''
                lines.append(
                    f'- **{plan["plan_id"]}** | {plan["title"]}'
                    f' | type={plan["plan_type"]} | status={plan["status"]}'
                    f'{tag_str}'
                    f'\n  created: {plan["created"]}  updated: {plan["updated"]}'
                )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(lines)}]
            )

        except Exception as exc:
            logger.error(f'Error listing plans: {exc}')
            return self.handle_error(exc)


class GetPlanMCPTool(MCPTool):
    """Read the full content of a specific research plan."""

    @property
    def name(self) -> str:
        return 'get_plan'

    @property
    def description(self) -> str:
        return (
            'Read the full markdown content of a research plan by its plan_id. '
            'Use list_plans to discover available plan IDs. '
            'Returns the complete file including frontmatter and body.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'plan_id': {
                    'type': 'string',
                    'description': (
                        'The plan ID (filename without .md extension). '
                        'Obtain from list_plans.'
                    ),
                },
                'plan_type': {
                    'type': 'string',
                    'enum': ['internal', 'user'],
                    'description': (
                        'Which directory to search. '
                        'Omit to search both (internal checked first).'
                    ),
                },
            },
            'required': ['plan_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Return the full content of a plan file.

        Args:
            arguments: Tool arguments matching the input schema.

        Returns:
            MCPToolCallResult: Full plan file content.
        """
        try:
            from thoth.config import config

            plan_id = arguments.get('plan_id', '').strip()
            plan_type_hint = arguments.get('plan_type', '').strip().lower() or None

            if not plan_id:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Error: plan_id is required.'}],
                    isError=True,
                )

            search_types = [plan_type_hint] if plan_type_hint else ['internal', 'user']

            for plan_type in search_types:
                plans_dir, _ = _resolve_plan_dirs(plan_type, config)
                plan_path = plans_dir / f'{plan_id}.md'
                if plan_path.exists():
                    content = plan_path.read_text(encoding='utf-8')
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': (
                                    f'**Plan**: {plan_id} ({plan_type})\n'
                                    f'**Path**: {plan_path}\n\n'
                                    '---\n\n' + content
                                ),
                            }
                        ]
                    )

            return MCPToolCallResult(
                content=[
                    {
                        'type': 'text',
                        'text': (
                            f'Error: No plan found with id "{plan_id}". '
                            'Use list_plans to see available plans.'
                        ),
                    }
                ],
                isError=True,
            )

        except Exception as exc:
            logger.error(f'Error getting plan: {exc}')
            return self.handle_error(exc)


class UpdatePlanMCPTool(MCPTool):
    """Update an existing research plan in the vault."""

    @property
    def name(self) -> str:
        return 'update_plan'

    @property
    def description(self) -> str:
        return (
            'Update an existing research plan. '
            'Supply only the fields you want to change; all others are preserved. '
            'The updated timestamp is refreshed automatically and the plan is '
            're-indexed into the RAG system after saving.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'plan_id': {
                    'type': 'string',
                    'description': 'The plan ID (filename without .md extension) to update.',
                },
                'plan_type': {
                    'type': 'string',
                    'enum': ['internal', 'user'],
                    'description': (
                        'Which directory the plan lives in. '
                        'Omit to search both (internal checked first).'
                    ),
                },
                'title': {
                    'type': 'string',
                    'description': 'New title. Omit to keep existing.',
                    'minLength': 1,
                    'maxLength': 200,
                },
                'content': {
                    'type': 'string',
                    'description': (
                        'New full markdown body (without frontmatter). '
                        'Omit to keep existing.'
                    ),
                    'minLength': 10,
                },
                'status': {
                    'type': 'string',
                    'enum': ['draft', 'active', 'complete', 'archived'],
                    'description': 'New status. Omit to keep existing.',
                },
                'tags': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'New tag list (replaces existing tags). Omit to keep existing.',
                },
            },
            'required': ['plan_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Update a plan file and re-index it into RAG.

        Args:
            arguments: Tool arguments matching the input schema.

        Returns:
            MCPToolCallResult: Confirmation of the fields that were updated.
        """
        try:
            from thoth.config import config

            plan_id = arguments.get('plan_id', '').strip()
            plan_type_hint = arguments.get('plan_type', '').strip().lower() or None
            new_title = arguments.get('title', '').strip() or None
            new_content = arguments.get('content', '').strip() or None
            new_status = arguments.get('status', '').strip().lower() or None
            new_tags = arguments.get('tags', None)

            if not plan_id:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Error: plan_id is required.'}],
                    isError=True,
                )

            search_types = [plan_type_hint] if plan_type_hint else ['internal', 'user']

            plan_path: Path | None = None
            found_type: str | None = None
            for plan_type in search_types:
                plans_dir, _ = _resolve_plan_dirs(plan_type, config)
                candidate = plans_dir / f'{plan_id}.md'
                if candidate.exists():
                    plan_path = candidate
                    found_type = plan_type
                    break

            if plan_path is None:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': (
                                f'Error: No plan found with id "{plan_id}". '
                                'Use list_plans to see available plans.'
                            ),
                        }
                    ],
                    isError=True,
                )

            raw = plan_path.read_text(encoding='utf-8')
            fm, body = _parse_frontmatter(raw)

            updated_fields: list[str] = []
            old_title = str(fm.get('title', plan_id))

            if new_title is not None:
                fm['title'] = new_title
                updated_fields.append('title')
            if new_status is not None:
                fm['status'] = new_status
                updated_fields.append('status')
            if new_tags is not None:
                fm['tags'] = new_tags
                updated_fields.append('tags')
            if new_content is not None:
                body = new_content
                updated_fields.append('content')

            fm['updated'] = _utc_now()

            new_fm = (
                '---\n'
                + yaml.dump(fm, default_flow_style=False, allow_unicode=True)
                + '---'
            )
            full_content = new_fm + '\n\n' + body + '\n'
            plan_path.write_text(full_content, encoding='utf-8')
            logger.info(
                f'Updated plan {plan_id} ({found_type}): fields={updated_fields}'
            )

            current_title = str(fm.get('title', old_title))
            indexed = False
            if self.service_manager:
                paper_id = await _register_and_index_plan(
                    title=current_title,
                    markdown_content=full_content,
                    service_manager=self.service_manager,
                    config=config,
                )
                indexed = paper_id is not None
            else:
                logger.warning(
                    'No service_manager; skipping RAG re-index for plan update.'
                )

            changes = (
                ', '.join(updated_fields)
                if updated_fields
                else 'none (timestamp refreshed only)'
            )
            result_lines = [
                'Plan updated successfully.',
                '',
                f'**Plan ID**: `{plan_id}`',
                f'**Location**: {plan_path}',
                f'**Updated fields**: {changes}',
                '',
                'Re-indexed into RAG.' if indexed else 'Note: RAG re-index skipped.',
            ]

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(result_lines)}]
            )

        except Exception as exc:
            logger.error(f'Error updating plan: {exc}')
            return self.handle_error(exc)


class DeletePlanMCPTool(MCPTool):
    """Delete a research plan from the vault."""

    @property
    def name(self) -> str:
        return 'delete_plan'

    @property
    def description(self) -> str:
        return (
            'Delete a research plan from the vault. '
            'Requires confirm=true to prevent accidental deletion. '
            'The plan file is removed from disk and its RAG index entries are cleared.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'plan_id': {
                    'type': 'string',
                    'description': 'The plan ID (filename without .md extension) to delete.',
                },
                'plan_type': {
                    'type': 'string',
                    'enum': ['internal', 'user'],
                    'description': (
                        'Which directory the plan lives in. '
                        'Omit to search both (internal checked first).'
                    ),
                },
                'confirm': {
                    'type': 'boolean',
                    'description': (
                        'Must be true to confirm deletion. '
                        'This action permanently removes the file and cannot be undone.'
                    ),
                },
            },
            'required': ['plan_id', 'confirm'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Delete a plan file and remove its DB/RAG entries.

        Args:
            arguments: Tool arguments matching the input schema.

        Returns:
            MCPToolCallResult: Confirmation of deletion.
        """
        try:
            from thoth.config import config

            plan_id = arguments.get('plan_id', '').strip()
            plan_type_hint = arguments.get('plan_type', '').strip().lower() or None
            confirm = arguments.get('confirm', False)

            # LLMs sometimes pass booleans as strings
            if isinstance(confirm, str):
                confirm = confirm.lower() in ('true', '1', 'yes')

            if not plan_id:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Error: plan_id is required.'}],
                    isError=True,
                )
            if not confirm:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': (
                                'Error: confirm=true is required to delete a plan. '
                                'This action cannot be undone.'
                            ),
                        }
                    ],
                    isError=True,
                )

            search_types = [plan_type_hint] if plan_type_hint else ['internal', 'user']

            plan_path: Path | None = None
            found_type: str | None = None
            for plan_type in search_types:
                plans_dir, _ = _resolve_plan_dirs(plan_type, config)
                candidate = plans_dir / f'{plan_id}.md'
                if candidate.exists():
                    plan_path = candidate
                    found_type = plan_type
                    break

            if plan_path is None:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': (
                                f'Error: No plan found with id "{plan_id}". '
                                'Use list_plans to see available plans.'
                            ),
                        }
                    ],
                    isError=True,
                )

            raw = plan_path.read_text(encoding='utf-8')
            fm, _ = _parse_frontmatter(raw)
            title = str(fm.get('title', plan_id))

            if self.service_manager:
                await _delete_plan_from_db(title, self.service_manager)

            plan_path.unlink()
            logger.info(f'Deleted plan {plan_id} ({found_type}) at {plan_path}')

            return MCPToolCallResult(
                content=[
                    {
                        'type': 'text',
                        'text': (
                            f'Plan "{plan_id}" ({found_type}) deleted successfully.\n'
                            f'Path: {plan_path}\n'
                            'DB and RAG entries have been removed.'
                        ),
                    }
                ]
            )

        except Exception as exc:
            logger.error(f'Error deleting plan: {exc}')
            return self.handle_error(exc)
