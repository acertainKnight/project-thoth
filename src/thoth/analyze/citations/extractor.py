import re

from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from thoth.utilities.schemas import ReferencesSection


class ReferenceExtractor:
    """Extracts the references section from a document."""

    def __init__(self, llm, prompt_template: ChatPromptTemplate):
        self.llm = llm
        self.prompt = prompt_template

    def extract(self, content: str) -> str:
        """
        Identifies and extracts the text of the references section from the
        document content.
        """
        headings = self._get_section_headings(content)
        references_heading = self._identify_references_heading(headings)
        return self._extract_references_section_text(content, references_heading)

    def _get_section_headings(self, content: str) -> list[str]:
        """Extract all section headings from the content."""
        logger.debug('Extracting section headings')
        atx_headers = re.findall(
            r'^(#{1,6})\\s+(.+?)(?:\\s+#+)?$', content, re.MULTILINE
        )
        atx_heading_texts = [text.strip() for _, text in atx_headers]
        setext_headers = re.findall(r'^([^\\n]+)\\n([=\\-]+)$', content, re.MULTILINE)
        setext_heading_texts = [text.strip() for text, _ in setext_headers]
        all_headings = atx_heading_texts + setext_heading_texts
        logger.debug(f'Found {len(all_headings)} headings')
        return all_headings

    def _identify_references_heading(self, headings: list[str]) -> str:
        """Identify the heading for the references section."""
        logger.debug('Identifying references section heading')
        default_options = ['references', 'bibliography', 'citations']
        for heading in headings:
            if any(option in heading.lower() for option in default_options):
                logger.debug(
                    f'Found references section heading using default options: {heading}'
                )
                return heading

        logger.debug('No default references heading found, using LLM')
        structured_llm = self.llm.with_structured_output(
            ReferencesSection, include_raw=False, method='json_schema'
        )
        chain = self.prompt | structured_llm
        result = chain.invoke({'headings': headings})
        logger.debug(f'LLM identified references heading: {result.heading}')
        return result.heading

    def _extract_references_section_text(self, content: str, heading: str) -> str:
        """Extract the references section text using the identified heading."""
        logger.debug('Extracting references section text')
        if not heading:
            logger.warning('No references section heading found')
            return ''

        heading_positions = []
        for match in re.finditer(
            r'^(#{1,6})\\s+(.+?)(?:\\s+#+)?$', content, re.MULTILINE
        ):
            heading_positions.append((match.start(), match.group(2).strip()))
        for match in re.finditer(r'^([^\\n]+)\\n([=\\-]+)$', content, re.MULTILINE):
            heading_positions.append((match.start(), match.group(1).strip()))

        heading_positions.sort()

        target_pos = -1
        next_pos = len(content)
        for i, (pos, text) in enumerate(heading_positions):
            if text == heading:
                target_pos = pos
                if i < len(heading_positions) - 1:
                    next_pos = heading_positions[i + 1][0]
                break

        if target_pos == -1:
            logger.warning(f"References heading '{heading}' not located in document")
            return ''

        heading_end = content.find('\\n', target_pos)
        if heading_end == -1:
            heading_end = len(content)

        section_text = content[heading_end + 1 : next_pos].strip()
        logger.debug(
            f'Extracted references section with {len(section_text)} characters'
        )
        return section_text
