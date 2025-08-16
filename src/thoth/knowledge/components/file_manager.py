"""
Citation file management component.

Handles file operations and Obsidian integration.
"""

import re
from pathlib import Path
from typing import Any

import networkx as nx
from loguru import logger


class CitationFileManager:
    """Handles file operations and Obsidian path management."""
    
    def __init__(
        self,
        graph: nx.DiGraph,
        knowledge_base_dir: Path,
        markdown_dir: Path | None = None,
        notes_dir: Path | None = None,
    ):
        """
        Initialize the file manager component.
        
        Args:
            graph: The citation graph
            knowledge_base_dir: Base directory for knowledge base
            markdown_dir: Directory for markdown files
            notes_dir: Directory for notes
        """
        self.graph = graph
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.markdown_dir = markdown_dir
        self.notes_dir = notes_dir
    
    def sanitize_title(self, title: str) -> str:
        """
        Sanitize a title for use as a filename.
        
        Args:
            title: Original title
            
        Returns:
            Sanitized title safe for filesystem
        """
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', title)
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        # Limit length to avoid filesystem issues
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
        return sanitized
    
    def get_obsidian_path(self, article_id: str) -> str | None:
        """
        Get the Obsidian path for an article.
        
        Args:
            article_id: Article ID
            
        Returns:
            Obsidian path if exists, None otherwise
        """
        if article_id not in self.graph:
            return None
        
        data = self.graph.nodes[article_id]
        return data.get('obsidian_path')
    
    def update_obsidian_path(self, article_id: str, path: str) -> None:
        """
        Update the Obsidian path for an article.
        
        Args:
            article_id: Article ID
            path: New Obsidian path
        """
        if article_id in self.graph:
            self.graph.nodes[article_id]['obsidian_path'] = path
    
    def get_markdown_path(self, article_id: str) -> Path | None:
        """
        Get the markdown file path for an article.
        
        Args:
            article_id: Article ID
            
        Returns:
            Path to markdown file if exists
        """
        if not self.markdown_dir:
            return None
        
        if article_id not in self.graph:
            return None
        
        data = self.graph.nodes[article_id]
        title = data.get('title', article_id)
        sanitized_title = self.sanitize_title(title)
        
        return self.markdown_dir / f"{sanitized_title}.md"
    
    def update_obsidian_links(self, article_id: str) -> None:
        """
        Update Obsidian links in the markdown file for an article.
        
        Args:
            article_id: Article ID to update links for
        """
        if not self.notes_dir:
            logger.warning('Notes directory not configured')
            return
        
        if article_id not in self.graph:
            logger.warning(f'Article {article_id} not found in graph')
            return
        
        data = self.graph.nodes[article_id]
        obsidian_path = data.get('obsidian_path')
        
        if not obsidian_path:
            logger.warning(f'No Obsidian path for article {article_id}')
            return
        
        note_path = self.notes_dir / f"{obsidian_path}.md"
        if not note_path.exists():
            logger.warning(f'Note file not found: {note_path}')
            return
        
        try:
            # Read the current note
            content = note_path.read_text(encoding='utf-8')
            
            # Update citing articles section
            citing_ids = list(self.graph.predecessors(article_id))
            citing_section = self._generate_citing_section(citing_ids)
            
            # Update cited articles section
            cited_ids = list(self.graph.successors(article_id))
            cited_section = self._generate_cited_section(cited_ids)
            
            # Replace sections in content
            content = self._replace_section(
                content, '## Cited By', citing_section
            )
            content = self._replace_section(
                content, '## References', cited_section
            )
            
            # Write back
            note_path.write_text(content, encoding='utf-8')
            logger.info(f'Updated Obsidian links for {article_id}')
            
        except Exception as e:
            logger.error(f'Failed to update Obsidian links for {article_id}: {e}')
    
    def _generate_citing_section(self, citing_ids: list[str]) -> str:
        """Generate the 'Cited By' section content."""
        if not citing_ids:
            return "## Cited By\n\nNo citations found.\n"
        
        lines = ["## Cited By\n"]
        for citer_id in citing_ids:
            if citer_id in self.graph:
                citer_data = self.graph.nodes[citer_id]
                title = citer_data.get('title', citer_id)
                obsidian_path = citer_data.get('obsidian_path')
                
                if obsidian_path:
                    lines.append(f"- [[{obsidian_path}|{title}]]\n")
                else:
                    lines.append(f"- {title}\n")
        
        return ''.join(lines)
    
    def _generate_cited_section(self, cited_ids: list[str]) -> str:
        """Generate the 'References' section content."""
        if not cited_ids:
            return "## References\n\nNo references found.\n"
        
        lines = ["## References\n"]
        for cited_id in cited_ids:
            if cited_id in self.graph:
                cited_data = self.graph.nodes[cited_id]
                title = cited_data.get('title', cited_id)
                obsidian_path = cited_data.get('obsidian_path')
                
                if obsidian_path:
                    lines.append(f"- [[{obsidian_path}|{title}]]\n")
                else:
                    lines.append(f"- {title}\n")
        
        return ''.join(lines)
    
    def _replace_section(self, content: str, section_header: str, new_section: str) -> str:
        """Replace a section in the content."""
        # Find the section
        pattern = rf'{re.escape(section_header)}\n.*?(?=\n##|\Z)'
        
        if re.search(pattern, content, re.DOTALL):
            # Replace existing section
            return re.sub(pattern, new_section.strip(), content, flags=re.DOTALL)
        else:
            # Append new section
            return content.rstrip() + '\n\n' + new_section
    
    def get_article_files(self, article_id: str) -> dict[str, Path | None]:
        """
        Get all file paths associated with an article.
        
        Args:
            article_id: Article ID
            
        Returns:
            Dictionary with pdf_path, markdown_path, and note_path
        """
        if article_id not in self.graph:
            return {'pdf_path': None, 'markdown_path': None, 'note_path': None}
        
        data = self.graph.nodes[article_id]
        
        # Get PDF path
        pdf_path = data.get('pdf_path')
        if pdf_path:
            pdf_path = Path(pdf_path)
        
        # Get markdown path
        markdown_path = self.get_markdown_path(article_id)
        
        # Get note path
        note_path = None
        obsidian_path = data.get('obsidian_path')
        if obsidian_path and self.notes_dir:
            note_path = self.notes_dir / f"{obsidian_path}.md"
        
        return {
            'pdf_path': pdf_path,
            'markdown_path': markdown_path,
            'note_path': note_path,
        }