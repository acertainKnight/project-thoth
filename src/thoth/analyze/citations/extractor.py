import re

from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from thoth.utilities.schemas import ReferencesSection


class ReferenceExtractor:
    """Extracts the references section from a document."""

    HEADING_REGEX = re.compile(
        r"""
        ^
        [ \t]*
        (?:
            # ATX style: #, ##, etc.
            (?P<atx_hashes>\#{1,6})
            [ \t]+
            (?P<atx_text>.+?)
            [ \t]*
            (?:\#+)?
        |
            # Setext style: === or ---
            (?P<setext_text>[^\n]+)
            [ \t]*
            \n
            [ \t]*
            (?P<setext_underline>[=\-]+)
        )
        [ \t]*
        $
        """,
        re.VERBOSE | re.MULTILINE,
    )

    def __init__(self, llm, prompt_template: ChatPromptTemplate):
        self.llm = llm
        self.prompt = prompt_template

    def extract(self, content: str) -> str:
        """
        Identifies and extracts the text of the references section from the
        document content.
        """
        headings = self._get_section_headings(content)
        if not headings:
            logger.warning('No section headings found in the document.')
            return ''
        references_heading = self._identify_references_heading(headings)
        return self._extract_references_section_text(content, references_heading)

    def _get_section_headings(self, content: str) -> list[str]:
        """Extract all section headings from the content."""
        logger.debug('Extracting section headings')
        headings = []
        for match in self.HEADING_REGEX.finditer(content):
            text = match.group('atx_text') or match.group('setext_text')
            if text:
                headings.append(text.strip())
        logger.debug(f'Found {len(headings)} headings')
        return headings

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
        result = chain.invoke(
            {
                'headings': headings,
                'json_schema': ReferencesSection.model_json_schema(),
            }
        )
        logger.debug(f'LLM identified references heading: {result.heading}')
        return result.heading if result and result.heading else ''

    def _extract_references_section_text(self, content: str, heading: str) -> str:
        """Extract the references section text using the identified heading."""
        logger.debug('Extracting references section text')
        if not heading:
            logger.warning('No references section heading found to extract text.')
            return ''

        heading_positions = []
        for match in self.HEADING_REGEX.finditer(content):
            text = match.group('atx_text') or match.group('setext_text')
            if text:
                heading_positions.append((match.start(), match.end(), text.strip()))

        # Sort by start position, just in case
        heading_positions.sort(key=lambda x: x[0])

        target_heading_info = None
        next_heading_start_pos = len(content)

        for i, (start_pos, end_pos, text) in enumerate(heading_positions):
            if text == heading:
                target_heading_info = (start_pos, end_pos, text)
                if i < len(heading_positions) - 1:
                    next_heading_start_pos = heading_positions[i + 1][0]
                break

        if not target_heading_info:
            logger.warning(f"References heading '{heading}' not located in document")
            return ''

        _, heading_end_pos, _ = target_heading_info

        # The content of the section is from the end of the current heading to the
        # start of the next one.
        section_text = content[heading_end_pos:next_heading_start_pos].strip()

        logger.debug(
            f'Extracted references section with {len(section_text)} characters'
        )
        return section_text
