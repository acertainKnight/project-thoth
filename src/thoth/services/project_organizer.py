"""
Project organizer service for Thoth.

Analyzes existing papers and organizes them into project folders based on
tag clustering and LLM-based naming.
"""

from collections import Counter, defaultdict
from typing import Any

from loguru import logger

from thoth.config import config


class ProjectOrganizer:
    """Service for auto-organizing papers into project folders."""

    def __init__(self, postgres_service, llm_service, knowledge_repo):
        """
        Initialize the project organizer.

        Args:
            postgres_service: PostgresService instance
            llm_service: LLM service for project naming
            knowledge_repo: KnowledgeCollectionRepository
        """
        self.db = postgres_service
        self.llm = llm_service
        self.knowledge_repo = knowledge_repo
        self.config = config

    async def analyze_papers(
        self,
        min_cluster_size: int = 5,
        max_clusters: int = 15,
        seed_categories: list[str] | None = None,
    ) -> dict[str, list[dict]]:
        """
        Analyze uncategorized papers and cluster them by tags.

        Args:
            min_cluster_size: Minimum papers per cluster
            max_clusters: Maximum number of clusters to create

        Returns:
            Dict mapping temporary cluster names to lists of paper records
        """
        logger.info('Analyzing uncategorized papers...')

        # Query papers without collection_id that have actual files on disk
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT
                    pm.id,
                    pm.title,
                    pm.abstract,
                    pm.keywords,
                    pm.fields_of_study,
                    pm.authors,
                    pm.year,
                    pm.created_at
                FROM paper_metadata pm
                INNER JOIN processed_papers pp ON pm.id = pp.paper_id
                WHERE pm.collection_id IS NULL
                AND pm.document_category = 'research_paper'
                ORDER BY pm.created_at DESC
                """
            )

        logger.info(f'Query returned {len(rows)} rows')

        if not rows:
            logger.info('No uncategorized papers found')
            return {}

        papers = [dict(row) for row in rows]
        logger.info(f'Found {len(papers)} uncategorized papers')

        # Extract all tags (keywords + fields_of_study)
        tag_counts = Counter()
        paper_tags: dict[str, set[str]] = {}

        for paper in papers:
            paper_id = str(paper['id'])
            tags = set()

            # Extract keywords
            if paper.get('keywords'):
                keywords = paper['keywords']
                if isinstance(keywords, list):
                    tags.update(k.lower() for k in keywords if isinstance(k, str))
                elif isinstance(keywords, str):
                    tags.add(keywords.lower())

            # Extract fields of study
            if paper.get('fields_of_study'):
                fields = paper['fields_of_study']
                if isinstance(fields, list):
                    tags.update(f.lower() for f in fields if isinstance(f, str))
                elif isinstance(fields, str):
                    tags.add(fields.lower())

            paper_tags[paper_id] = tags
            tag_counts.update(tags)

        # Find most common tags for clustering
        common_tags = [
            tag
            for tag, count in tag_counts.most_common(30)
            if count >= min_cluster_size
        ]

        if not common_tags:
            logger.warning('Not enough common tags for clustering')
            return {'Uncategorized': papers}

        logger.info(f'Found {len(common_tags)} common tags for clustering')

        # If seed categories provided, match papers to them
        if seed_categories:
            logger.info(f'Using {len(seed_categories)} seed categories for matching')
            clusters: dict[str, list[dict]] = defaultdict(list)
            assigned_papers = set()

            # Normalize seed categories to lowercase for matching
            seed_map = {cat.lower(): cat for cat in seed_categories}

            for paper in papers:
                paper_id = str(paper['id'])
                tags = paper_tags.get(paper_id, set())

                # Find best matching seed category
                best_match = None
                max_overlap = 0

                for seed_lower, seed_display in seed_map.items():
                    # Check if any paper tag contains the seed category words
                    seed_words = set(seed_lower.split())
                    overlap = sum(
                        1 for tag in tags if any(word in tag for word in seed_words)
                    )

                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_match = seed_display

                if best_match and max_overlap > 0:
                    clusters[best_match].append(paper)
                    assigned_papers.add(paper_id)

            logger.info(f'Matched {len(assigned_papers)} papers to seed categories')
        else:
            # Original tag-based clustering
            clusters: dict[str, list[dict]] = defaultdict(list)
            assigned_papers = set()

            for tag in common_tags[:max_clusters]:
                cluster_papers = []
                for paper in papers:
                    paper_id = str(paper['id'])
                    if paper_id in assigned_papers:
                        continue
                    if tag in paper_tags[paper_id]:
                        cluster_papers.append(paper)
                        assigned_papers.add(paper_id)

                if len(cluster_papers) >= min_cluster_size:
                    # Use tag as temp cluster name
                    clusters[tag.title()] = cluster_papers

        # Add remaining papers to "Uncategorized"
        uncategorized = [p for p in papers if str(p['id']) not in assigned_papers]
        if uncategorized:
            clusters['Uncategorized'] = uncategorized

        logger.info(f'Created {len(clusters)} initial clusters')
        for cluster_name, cluster_papers in clusters.items():
            logger.info(f'  {cluster_name}: {len(cluster_papers)} papers')

        return dict(clusters)

    async def refine_with_llm(
        self, clusters: dict[str, list[dict]]
    ) -> dict[str, list[str]]:
        """
        Use LLM to refine cluster names and reassign papers.

        Args:
            clusters: Initial clusters from tag-based analysis

        Returns:
            Dict mapping refined project names to lists of paper IDs
        """
        logger.info('Refining clusters with LLM...')

        refined_projects: dict[str, list[str]] = {}

        for temp_name, papers in clusters.items():
            if temp_name == 'Uncategorized':
                # Don't send uncategorized to LLM
                refined_projects['Uncategorized'] = [str(p['id']) for p in papers]
                continue

            # Prepare paper summaries for LLM
            summaries = []
            for i, paper in enumerate(papers[:20], 1):  # Limit to 20 papers
                title = paper.get('title', 'Untitled')
                abstract = paper.get('abstract') or ''
                abstract_preview = abstract[:200] if abstract else 'No abstract'
                summaries.append(f'{i}. {title}\n   {abstract_preview}...')

            paper_list = '\n'.join(summaries)

            # Ask LLM for a project name
            prompt = f"""Given these research papers, suggest a short, descriptive project name (2-4 words):

{paper_list}

Respond with ONLY the project name, nothing else."""

            try:
                # Use configured research agent model
                response = await self.llm.agenerate(prompt=prompt)
                project_name = response.strip().title()

                # Sanitize project name
                project_name = project_name.replace('/', '-').replace('\\', '-')
                project_name = project_name[:50]  # Limit length

                if not project_name or len(project_name) < 3:
                    project_name = temp_name

                logger.info(f'Refined "{temp_name}" -> "{project_name}"')

                refined_projects[project_name] = [str(p['id']) for p in papers]

            except Exception as e:
                logger.warning(f'LLM refinement failed for {temp_name}: {e}')
                # Fall back to tag-based name
                refined_projects[temp_name] = [str(p['id']) for p in papers]

        return refined_projects

    async def execute_organization(
        self, projects: dict[str, list[str]], dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Execute the organization by moving files and updating database.

        Args:
            projects: Dict mapping project names to paper IDs
            dry_run: If True, don't actually move files

        Returns:
            Summary dict with counts and any errors
        """
        logger.info(f'{"[DRY RUN] " if dry_run else ""}Executing organization...')

        import shutil

        from thoth.utilities.vault_path_resolver import VaultPathResolver

        vault_resolver = VaultPathResolver(self.config.vault_root)

        moved_count = 0
        error_count = 0
        errors = []

        for project_name, paper_ids in projects.items():
            if project_name == 'Uncategorized':
                continue  # Skip uncategorized

            logger.info(
                f'Processing project "{project_name}" ({len(paper_ids)} papers)...'
            )

            # Create collection
            if not dry_run:
                try:
                    collection = await self.knowledge_repo.get_by_name(project_name)
                    if not collection:
                        collection = await self.knowledge_repo.create(
                            name=project_name,
                            description=f'Auto-organized project: {project_name}',
                        )
                    collection_id = collection['id']
                except Exception as e:
                    logger.error(f'Failed to create collection {project_name}: {e}')
                    errors.append(f'{project_name}: Collection creation failed')
                    continue
            else:
                collection_id = None

            # Create project folders
            pdf_project_dir = self.config.pdf_dir / project_name
            markdown_project_dir = self.config.markdown_dir / project_name
            notes_project_dir = self.config.notes_dir / project_name

            if not dry_run:
                pdf_project_dir.mkdir(parents=True, exist_ok=True)
                markdown_project_dir.mkdir(parents=True, exist_ok=True)
                notes_project_dir.mkdir(parents=True, exist_ok=True)

            # Move each paper
            for paper_id in paper_ids:
                try:
                    async with self.db.acquire() as conn:
                        row = await conn.fetchrow(
                            """
                            SELECT pp.pdf_path, pp.markdown_path, pp.note_path
                            FROM processed_papers pp
                            WHERE pp.paper_id = $1
                            """,
                            paper_id,
                        )

                    if not row:
                        continue

                    # Get current paths
                    pdf_path_rel = row['pdf_path']
                    markdown_path_rel = row['markdown_path']
                    note_path_rel = row['note_path']

                    # Convert to absolute
                    pdf_path = (
                        vault_resolver.resolve(pdf_path_rel) if pdf_path_rel else None
                    )
                    markdown_path = (
                        vault_resolver.resolve(markdown_path_rel)
                        if markdown_path_rel
                        else None
                    )
                    note_path = (
                        vault_resolver.resolve(note_path_rel) if note_path_rel else None
                    )

                    # Compute new paths
                    new_pdf_path = pdf_project_dir / pdf_path.name if pdf_path else None
                    new_markdown_path = (
                        markdown_project_dir / markdown_path.name
                        if markdown_path
                        else None
                    )
                    new_note_path = (
                        notes_project_dir / note_path.name if note_path else None
                    )

                    # Move files
                    if not dry_run:
                        if pdf_path and pdf_path.exists():
                            shutil.move(str(pdf_path), str(new_pdf_path))
                        if markdown_path and markdown_path.exists():
                            shutil.move(str(markdown_path), str(new_markdown_path))
                        if note_path and note_path.exists():
                            shutil.move(str(note_path), str(new_note_path))

                        # Update database
                        new_pdf_rel = (
                            vault_resolver.make_relative(new_pdf_path)
                            if new_pdf_path
                            else None
                        )
                        new_markdown_rel = (
                            vault_resolver.make_relative(new_markdown_path)
                            if new_markdown_path
                            else None
                        )
                        new_note_rel = (
                            vault_resolver.make_relative(new_note_path)
                            if new_note_path
                            else None
                        )

                        async with self.db.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE processed_papers
                                SET pdf_path = $1, markdown_path = $2, note_path = $3, updated_at = NOW()
                                WHERE paper_id = $4
                                """,
                                new_pdf_rel,
                                new_markdown_rel,
                                new_note_rel,
                                paper_id,
                            )

                            await conn.execute(
                                """
                                UPDATE paper_metadata
                                SET collection_id = $1, updated_at = NOW()
                                WHERE id = $2
                                """,
                                collection_id,
                                paper_id,
                            )

                    moved_count += 1

                except Exception as e:
                    error_count += 1
                    logger.error(f'Error organizing paper {paper_id}: {e}')
                    errors.append(f'{paper_id[:8]}: {e!s}')

        summary = {
            'dry_run': dry_run,
            'projects_created': len([p for p in projects if p != 'Uncategorized']),
            'papers_moved': moved_count,
            'errors': error_count,
            'error_details': errors,
        }

        logger.info(
            f'Organization complete: {moved_count} papers, {error_count} errors'
        )

        return summary
