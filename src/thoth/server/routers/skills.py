"""
Skills REST API router for managing agent skills.

Provides CRUD operations for skills and skill bundles,
enabling Obsidian plugin and other clients to manage
the skills system.
"""

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from thoth.auth.context import UserContext
from thoth.auth.dependencies import get_user_context
from thoth.services.skill_service import SkillService

router = APIRouter(prefix='/api/skills', tags=['skills'])


# Request/Response Models
class SkillMetadata(BaseModel):
    """Skill metadata from YAML frontmatter."""

    id: str = Field(..., description='Skill identifier')
    name: str = Field(..., description='AgentSkills.io name field (matches directory)')
    display_name: str = Field(..., description='Human-readable display name')
    description: str = Field(..., description='Short description of skill purpose')
    source: Literal['bundled', 'vault', 'bundle'] = Field(
        ..., description='Skill source location'
    )
    bundle: str | None = Field(None, description="Bundle name if source is 'bundle'")
    path: str = Field(..., description='Filesystem path to skill')


class SkillContent(BaseModel):
    """Full skill content with metadata."""

    metadata: SkillMetadata
    content: str = Field(..., description='Full SKILL.md markdown content')


class SkillCreate(BaseModel):
    """Request model for creating a new skill."""

    skill_id: str = Field(
        ...,
        description='Skill identifier (alphanumeric with hyphens)',
        min_length=3,
        max_length=100,
    )
    name: str = Field(
        ..., description='Skill display name', min_length=1, max_length=200
    )
    description: str = Field(
        ..., description='Skill description', min_length=1, max_length=500
    )
    content: str = Field(
        ..., description='Skill markdown content (without frontmatter)', min_length=10
    )
    bundle: str | None = Field(
        None,
        description='Bundle name to create skill in (orchestrator, discovery, etc.)',
    )


class SkillUpdate(BaseModel):
    """Request model for updating a skill."""

    name: str | None = Field(None, description='Updated skill name')
    description: str | None = Field(None, description='Updated description')
    content: str | None = Field(None, description='Updated markdown content')


class SkillsListResponse(BaseModel):
    """Response model for listing skills."""

    total: int = Field(..., description='Total number of skills')
    skills: list[SkillMetadata]


class RoleBundleResponse(BaseModel):
    """Response model for role bundles."""

    role: str
    bundles: list[str]
    skills: list[str]


@router.get('/', response_model=SkillsListResponse)
async def list_skills(
    source: Literal['all', 'bundled', 'vault', 'bundle'] | None = Query(
        None, description='Filter by source'
    ),
    role: str | None = Query(None, description='Filter by agent role'),
    search: str | None = Query(None, description='Search in name or description'),
) -> SkillsListResponse:
    """
    List all available skills with optional filtering.

    **Filters:**
    - `source`: Filter by source location (bundled, vault, bundle)
    - `role`: Filter by agent role (shows skills available for that role)
    - `search`: Search in skill names and descriptions

    Returns list of skill metadata without full content.
    """
    try:
        skill_service = SkillService()

        # Get skills based on filters
        if role:
            # Get skills for specific role (includes bundles)
            skill_ids = skill_service.get_skills_for_role(role)
            all_skills_dict = skill_service.discover_skills()
            bundles = skill_service.discover_bundle_skills()

            skills_list = []
            for skill_id in skill_ids:
                if skill_id.startswith('bundles/'):
                    # Bundle skill
                    parts = skill_id.split('/')
                    bundle_name = parts[1]
                    skill_name = parts[2]
                    skill_path = (
                        skill_service.bundles_dir
                        / bundle_name
                        / skill_name
                        / 'SKILL.md'
                    )

                    if skill_path.exists():
                        metadata = skill_service._parse_skill_metadata(skill_path)
                        skills_list.append(
                            SkillMetadata(
                                id=skill_id,
                                name=metadata.get('name', skill_name),
                                description=metadata.get('description', ''),
                                source='bundle',
                                bundle=bundle_name,
                                path=str(skill_path),
                            )
                        )
                elif skill_id in all_skills_dict:
                    skill_info = all_skills_dict[skill_id]
                    skills_list.append(
                        SkillMetadata(
                            id=skill_id,
                            name=skill_info['name'],
                            display_name=skill_info.get(
                                'display_name', skill_info['name']
                            ),
                            description=skill_info['description'],
                            source=skill_info['source'],
                            bundle=None,
                            path=str(skill_info['path']),
                        )
                    )
        else:
            # Get all skills
            all_skills_dict = skill_service.discover_skills()

            skills_list = [
                SkillMetadata(
                    id=skill_id,
                    name=info['name'],
                    display_name=info.get('display_name', info['name']),
                    description=info['description'],
                    source=info['source'],
                    bundle=None,
                    path=str(info['path']),
                )
                for skill_id, info in all_skills_dict.items()
            ]

            # Add bundle skills if no role filter
            bundles = skill_service.discover_bundle_skills()
            for bundle_name, skill_ids in bundles.items():
                for skill_id in skill_ids:
                    parts = skill_id.split('/')
                    skill_name = parts[2]
                    skill_path = (
                        skill_service.bundles_dir
                        / bundle_name
                        / skill_name
                        / 'SKILL.md'
                    )

                    if skill_path.exists():
                        metadata = skill_service._parse_skill_metadata(skill_path)
                        name = metadata.get('name', skill_name)
                        display_name = name.replace('-', ' ').title()

                        skills_list.append(
                            SkillMetadata(
                                id=skill_id,
                                name=name,
                                display_name=display_name,
                                description=metadata.get('description', ''),
                                source='bundle',
                                bundle=bundle_name,
                                path=str(skill_path),
                            )
                        )

        # Apply source filter
        if source and source != 'all':
            skills_list = [s for s in skills_list if s.source == source]

        # Apply search filter
        if search:
            search_lower = search.lower()
            skills_list = [
                s
                for s in skills_list
                if search_lower in s.name.lower()
                or search_lower in s.description.lower()
            ]

        # Sort by name
        skills_list.sort(key=lambda s: s.name)

        return SkillsListResponse(total=len(skills_list), skills=skills_list)

    except Exception as e:
        logger.error(f'Error listing skills: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to list skills: {e!s}'
        ) from e


@router.get('/{skill_id:path}', response_model=SkillContent)
async def get_skill(skill_id: str) -> SkillContent:
    """
    Get full content of a specific skill.

    **Parameters:**
    - `skill_id`: Skill identifier (e.g., 'research-deep-dive' or
      'bundles/orchestrator/research-workflow-coordination')

    Returns skill metadata and full markdown content.
    """
    try:
        skill_service = SkillService()

        # Get skill content
        content = skill_service.get_skill_content(skill_id)

        if content is None:
            raise HTTPException(status_code=404, detail=f'Skill not found: {skill_id}')

        # Get metadata
        if skill_id.startswith('bundles/'):
            parts = skill_id.split('/')
            bundle_name = parts[1]
            skill_name = parts[2]
            skill_path = (
                skill_service.bundles_dir / bundle_name / skill_name / 'SKILL.md'
            )
            metadata_dict = skill_service._parse_skill_metadata(skill_path)
            name = metadata_dict.get('name', skill_name)
            display_name = name.replace('-', ' ').title()

            metadata = SkillMetadata(
                id=skill_id,
                name=name,
                display_name=display_name,
                description=metadata_dict.get('description', ''),
                source='bundle',
                bundle=bundle_name,
                path=str(skill_path),
            )
        else:
            skills = skill_service.discover_skills()
            if skill_id not in skills:
                raise HTTPException(
                    status_code=404, detail=f'Skill not found: {skill_id}'
                )

            skill_info = skills[skill_id]
            metadata = SkillMetadata(
                id=skill_id,
                name=skill_info['name'],
                display_name=skill_info.get('display_name', skill_info['name']),
                description=skill_info['description'],
                source=skill_info['source'],
                bundle=None,
                path=str(skill_info['path']),
            )

        return SkillContent(metadata=metadata, content=content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting skill {skill_id}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get skill: {e!s}'
        ) from e


@router.post('/', response_model=SkillMetadata, status_code=201)
async def create_skill(
    skill_data: SkillCreate,
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> SkillMetadata:
    """
    Create a new skill in the vault.

    **Body:**
    - `skill_id`: Unique identifier (alphanumeric with hyphens)
    - `name`: Display name
    - `description`: Short description
    - `content`: Markdown content (frontmatter added automatically)
    - `bundle`: Optional bundle name (orchestrator, discovery, analysis, etc.)

    Creates skill in `vault/thoth/_thoth/skills/` or
    `vault/thoth/_thoth/skills/bundles/{bundle}/`.
    """
    try:
        skill_service = SkillService()

        # Validate skill_id format
        if not skill_data.skill_id.replace('-', '').isalnum():
            raise HTTPException(
                status_code=400,
                detail='Skill ID must be alphanumeric with hyphens only',
            )

        # Determine skill path
        if skill_data.bundle:
            skill_dir = (
                skill_service.bundles_dir / skill_data.bundle / skill_data.skill_id
            )
            skill_id = f'bundles/{skill_data.bundle}/{skill_data.skill_id}'
            source = 'bundle'
        else:
            skill_dir = skill_service.vault_skills_dir / skill_data.skill_id
            skill_id = skill_data.skill_id
            source = 'vault'

        # Check if skill already exists
        if skill_dir.exists():
            raise HTTPException(
                status_code=409, detail=f'Skill already exists: {skill_id}'
            )

        # Create skill directory
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Create SKILL.md with frontmatter
        skill_file = skill_dir / 'SKILL.md'
        skill_content = f"""---
name: {skill_data.name}
description: {skill_data.description}
---

{skill_data.content}
"""

        with open(skill_file, 'w', encoding='utf-8') as f:
            f.write(skill_content)

        logger.info(f'Created skill: {skill_id} at {skill_file}')

        # Generate display_name from skill_id
        display_name = (
            skill_id.split('/')[-1].replace('-', ' ').title()
            if '/' in skill_id
            else skill_id.replace('-', ' ').title()
        )

        return SkillMetadata(
            id=skill_id,
            name=skill_data.skill_id,  # AgentSkills.io: matches directory
            display_name=display_name,
            description=skill_data.description,
            source=source,
            bundle=skill_data.bundle,
            path=str(skill_file),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error creating skill: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to create skill: {e!s}'
        ) from e


@router.put('/{skill_id:path}', response_model=SkillMetadata)
async def update_skill(
    skill_id: str,
    skill_data: SkillUpdate,
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> SkillMetadata:
    """
    Update an existing skill in the vault.

    **Parameters:**
    - `skill_id`: Skill identifier

    **Body:**
    - `name`: Updated name (optional)
    - `description`: Updated description (optional)
    - `content`: Updated markdown content (optional)

    Only vault and bundle skills can be updated (bundled skills are read-only).
    """
    try:
        skill_service = SkillService()

        # Get current skill
        current_content = skill_service.get_skill_content(skill_id)
        if current_content is None:
            raise HTTPException(status_code=404, detail=f'Skill not found: {skill_id}')

        # Check if skill is in vault or bundle (not bundled)
        if skill_id.startswith('bundles/'):
            parts = skill_id.split('/')
            bundle_name = parts[1]
            skill_name = parts[2]
            skill_file = (
                skill_service.bundles_dir / bundle_name / skill_name / 'SKILL.md'
            )
        else:
            skills = skill_service.discover_skills()
            if skill_id not in skills:
                raise HTTPException(
                    status_code=404, detail=f'Skill not found: {skill_id}'
                )

            skill_info = skills[skill_id]
            if skill_info['source'] == 'bundled':
                raise HTTPException(
                    status_code=403, detail='Cannot update bundled skills'
                )

            skill_file = Path(skill_info['path'])

        # Parse current metadata
        current_metadata = skill_service._parse_skill_metadata(skill_file)

        # Update metadata
        new_name = skill_data.name or current_metadata.get('name', skill_id)
        new_desc = skill_data.description or current_metadata.get('description', '')

        # Update content
        if skill_data.content is not None:
            new_content = skill_data.content
        else:
            # Extract content (remove frontmatter)
            parts = current_content.split('---', 2)
            new_content = parts[2].strip() if len(parts) >= 3 else current_content

        # Write updated skill
        updated_content = f"""---
name: {new_name}
description: {new_desc}
---

{new_content}
"""

        with open(skill_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        logger.info(f'Updated skill: {skill_id}')

        # Return updated metadata
        if skill_id.startswith('bundles/'):
            parts = skill_id.split('/')
            source = 'bundle'
            bundle = parts[1]
            skill_name = parts[2]
        else:
            source = 'vault'
            bundle = None
            skill_name = skill_id

        display_name = skill_name.replace('-', ' ').title()

        return SkillMetadata(
            id=skill_id,
            name=skill_name,  # AgentSkills.io: matches directory
            display_name=display_name,
            description=new_desc,
            source=source,
            bundle=bundle,
            path=str(skill_file),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating skill {skill_id}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to update skill: {e!s}'
        ) from e


@router.delete('/{skill_id:path}', status_code=204)
async def delete_skill(
    skill_id: str,
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> None:
    """
    Delete a skill from the vault.

    **Parameters:**
    - `skill_id`: Skill identifier

    Only vault and bundle skills can be deleted (bundled skills are read-only).
    Returns 204 No Content on success.
    """
    try:
        skill_service = SkillService()

        # Check if skill exists and is not bundled
        if skill_id.startswith('bundles/'):
            parts = skill_id.split('/')
            bundle_name = parts[1]
            skill_name = parts[2]
            skill_dir = skill_service.bundles_dir / bundle_name / skill_name
        else:
            skills = skill_service.discover_skills()
            if skill_id not in skills:
                raise HTTPException(
                    status_code=404, detail=f'Skill not found: {skill_id}'
                )

            skill_info = skills[skill_id]
            if skill_info['source'] == 'bundled':
                raise HTTPException(
                    status_code=403, detail='Cannot delete bundled skills'
                )

            skill_dir = Path(skill_info['path']).parent

        # Delete skill directory
        if skill_dir.exists():
            import shutil

            shutil.rmtree(skill_dir)
            logger.info(f'Deleted skill: {skill_id} at {skill_dir}')
        else:
            raise HTTPException(
                status_code=404, detail=f'Skill directory not found: {skill_id}'
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error deleting skill {skill_id}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to delete skill: {e!s}'
        ) from e


@router.get('/roles/{role}/summary')
async def get_role_skills_summary(role: str) -> dict[str, Any]:
    """
    Get a token-efficient summary of skills for a specific agent role.

    **Parameters:**
    - `role`: Agent role (coordinator, discovery, analyst, etc.)

    Returns lightweight skill metadata without full content.
    Useful for injecting into agent system prompts.
    """
    try:
        skill_service = SkillService()
        summary = skill_service.format_role_skills_summary(role)

        return {'role': role, 'summary': summary, 'format': 'markdown'}

    except Exception as e:
        logger.error(f'Error getting role skills summary for {role}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get role skills summary: {e!s}'
        ) from e


@router.get('/bundles/', response_model=list[RoleBundleResponse])
async def list_bundles() -> list[RoleBundleResponse]:
    """
    List all skill bundles and their associated roles.

    Returns bundle information with skills included in each bundle.
    """
    try:
        skill_service = SkillService()
        bundles = skill_service.discover_bundle_skills()

        # Get role mappings
        role_bundles = []
        for role, bundle_names in SkillService.ROLE_BUNDLES.items():
            skills = []
            for bundle_name in bundle_names:
                if bundle_name in bundles:
                    skills.extend(bundles[bundle_name])

            role_bundles.append(
                RoleBundleResponse(role=role, bundles=bundle_names, skills=skills)
            )

        return role_bundles

    except Exception as e:
        logger.error(f'Error listing bundles: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to list bundles: {e!s}'
        ) from e
