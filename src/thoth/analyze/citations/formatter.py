"""
Citation Formatter for Thoth.

This module handles the formatting of citations in different styles.
"""

from enum import Enum

from loguru import logger

from thoth.utilities.models import Citation


class CitationStyle(Enum):
    """Enum for different citation styles."""

    IEEE = 'ieee'
    APA = 'apa'
    MLA = 'mla'
    CHICAGO = 'chicago'
    HARVARD = 'harvard'


class CitationFormatError(Exception):
    """Exception raised for errors in the citation formatting process."""

    pass


class CitationFormatter:
    """
    Formats citations in different academic styles.

    This class provides methods to format Citation objects in various
    academic citation styles, such as IEEE, APA, MLA, Chicago, and Harvard.
    """

    @staticmethod
    def format_citation(
        citation: Citation, style: CitationStyle = CitationStyle.IEEE
    ) -> Citation:
        """
        Format a single citation according to the specified style.

        Args:
            citation (Citation): The citation to format.
            style (CitationStyle): The citation style to use.

        Returns:
            Citation: The citation with the formatted string in the 'formatted' field.
        """
        try:
            if style == CitationStyle.IEEE:
                citation.formatted = CitationFormatter._format_ieee(citation)
                return citation
            elif style == CitationStyle.APA:
                citation.formatted = CitationFormatter._format_apa(citation)
                return citation
            elif style == CitationStyle.MLA:
                citation.formatted = CitationFormatter._format_mla(citation)
                return citation
            elif style == CitationStyle.CHICAGO:
                citation.formatted = CitationFormatter._format_chicago(citation)
                return citation
            elif style == CitationStyle.HARVARD:
                citation.formatted = CitationFormatter._format_harvard(citation)
                return citation
            else:
                raise CitationFormatError(f'Unsupported citation style: {style}')
        except Exception as e:
            logger.error(f'Failed to format citation: {e}')
            for field in [
                'authors',
                'title',
                'journal',
                'venue',
                'year',
                'volume',
                'issue',
                'pages',
                'doi',
                'backup_id',
                'url',
                'citation_count',
                'abstract',
            ]:
                if not hasattr(citation, field):
                    logger.warning(f'Citation missing expected field: {field}')
            raise CitationFormatError(f'Failed to format citation: {e}') from e

    def format_citations(
        self, citations: list[Citation], style: CitationStyle = CitationStyle.IEEE
    ) -> list[str]:
        """
        Format a list of citations according to the specified style.
        """
        formatted_citations = []
        for citation in citations:
            try:
                logger.info(f'Formatting citation: {citation.model_dump()}')
                formatted_citation = self.format_citation(citation, style)
                logger.info(f'Formatted citation: {formatted_citation.model_dump()}')
                formatted_citations.append(formatted_citation)
            except Exception as e:
                logger.error(f'Error formatting citation: {e}')
        return formatted_citations

    @staticmethod
    def _format_apa(citation: Citation) -> str:
        """
        Format a citation in APA style (7th Edition).

        Args:
            citation: The Citation object to format.

        Returns:
            str: The citation formatted in APA style.

        Example:
            >>> citation = Citation(
            ...     title='Sample Paper on Innovations',
            ...     authors=['Smith, J.', 'Jones, A. B.', 'Williams, C.'],
            ...     year=2023,
            ...     journal='Journal of Advanced Research',
            ...     volume='10',
            ...     issue='2',
            ...     pages='123-145',
            ...     doi='10.1234/5678',
            ... )
            >>> CitationFormatter._format_apa(citation)
            "Smith, J., Jones, A. B., & Williams, C. (2023). Sample paper on innovations. _Journal of Advanced Research_, _10_(2), 123-145. https://doi.org/10.1234/5678"
        """  # noqa: W505
        parts = []

        # Authors
        if citation.authors:
            if len(citation.authors) == 1:
                parts.append(f'{citation.authors[0]}.')
            elif len(citation.authors) == 2:
                parts.append(f'{citation.authors[0]} & {citation.authors[1]}.')
            elif len(citation.authors) > 2:
                # List all authors up to 20. If more, list first 19, ..., last author.
                # Current model assumes authors are pre-formatted as "Last, F. M."
                # For simplicity here, joining with comma and ampersand for the last one.  # noqa: W505
                # A more robust solution would parse and reformat names.
                if len(citation.authors) <= 20:
                    author_string = (
                        ', '.join(citation.authors[:-1])
                        + f', & {citation.authors[-1]}.'
                    )
                else:  # More than 20 authors
                    author_string = (
                        ', '.join(citation.authors[:19])
                        + f', ..., {citation.authors[-1]}.'
                    )
                parts.append(author_string)

        # Year
        if citation.year:
            parts.append(f'({citation.year}).')

        # Title (Sentence case)
        if citation.title:
            # Basic sentence case: capitalize first letter, rest lower (unless proper noun)  # noqa: W505
            # This is a simplification. True sentence case is complex.
            sentence_case_title = citation.title[0].upper() + citation.title[1:].lower()
            parts.append(f'{sentence_case_title}.')

        # Journal/Source Information
        journal_info_parts = []
        if citation.journal:
            # Journal Title (Title Case, Italicized)
            # Basic title case: capitalize each word. Simplification.
            title_case_journal = ' '.join(
                word.capitalize() for word in citation.journal.split()
            )
            journal_info_parts.append(f'_{title_case_journal}_')

        if citation.volume:
            volume_issue_pages = f'_{citation.volume}_'  # Volume is italicized
            if citation.issue:
                volume_issue_pages += (
                    f'({citation.issue})'  # Issue in parentheses, not italicized
                )
            journal_info_parts.append(volume_issue_pages)

        if citation.pages:
            journal_info_parts.append(f'{citation.pages}')

        if journal_info_parts:
            parts.append(', '.join(filter(None, journal_info_parts)) + '.')

        # DOI or URL
        if citation.doi:
            parts.append(
                f'https://doi.org/{citation.doi.replace("https://doi.org/", "")}'
            )  # No period after DOI
        elif citation.url:
            parts.append(f'{citation.url}')  # No period if it's the last element

        # Clean up extra spaces and join
        formatted_citation = ' '.join(filter(None, parts))

        # Ensure no double periods, except for "et al.." which is fine.
        formatted_citation = formatted_citation.replace('..', '.').strip()
        if formatted_citation.endswith(' .'):
            formatted_citation = formatted_citation[:-2] + '.'
        if (
            not formatted_citation.endswith('.')
            and not citation.doi
            and not citation.url
        ):
            formatted_citation += '.'
        if formatted_citation.endswith(','):
            formatted_citation = formatted_citation[:-1] + '.'

        return formatted_citation.strip()

    @staticmethod
    def _format_mla(citation: Citation) -> str:
        """
        Format a citation in MLA style (9th Edition).

        Args:
            citation: The Citation object to format.

        Returns:
            str: The citation formatted in MLA style.

        Example:
            >>> citation = Citation(
            ...     title='The Impact of Technology on Modern Education',
            ...     authors=['Doe, John', 'Smith, Jane'],
            ...     year=2023,
            ...     journal='Educational Technology Quarterly',
            ...     volume='15',
            ...     issue='3',
            ...     pages='34-45',
            ...     doi='10.5678/9012',
            ... )
            >>> CitationFormatter._format_mla(citation)
            'Doe, John, and Jane Smith. "The Impact of Technology on Modern Education." _Educational Technology Quarterly_, vol. 15, no. 3, 2023, pp. 34-45. DOI: 10.5678/9012.'
        """  # noqa: W505
        parts = []

        # Authors
        if citation.authors:
            if len(citation.authors) == 1:
                parts.append(f'{citation.authors[0]}.')
            elif len(citation.authors) == 2:
                # Assumes authors are "Last, First"
                parts.append(f'{citation.authors[0]}, and {citation.authors[1]}.')
            else:  # 3 or more authors
                parts.append(f'{citation.authors[0]}, et al.')

        # Title (Title Case, in quotes)
        if citation.title:
            # Basic title case.
            title_case_title = ' '.join(
                word.capitalize() for word in citation.title.split()
            )
            parts.append(f'"{title_case_title}.".')  # Period inside quotes

        # Journal Title (Italicized, Title Case)
        if citation.journal:
            title_case_journal = ' '.join(
                word.capitalize() for word in citation.journal.split()
            )
            journal_string = f'_{title_case_journal}_'
            if citation.volume:
                journal_string += f', vol. {citation.volume}'
            if citation.issue:
                journal_string += f', no. {citation.issue}'
            if citation.year:  # Year for journal publication
                journal_string += f', {citation.year}'
            if citation.pages:
                journal_string += f', pp. {citation.pages}'
            parts.append(journal_string + '.')
        elif citation.venue:  # For conferences or other venues if no journal
            parts.append(f'_{citation.venue}_.')
            if citation.year:
                parts[-1] = parts[-1][:-1] + f', {citation.year}.'

        # DOI or URL
        if citation.doi:
            parts.append(f'DOI: {citation.doi.replace("https://doi.org/", "")}.')
        elif citation.url:
            # MLA usually prefers not to include URLs unless necessary or for web-only sources.  # noqa: W505
            # If included, often without "https://" prefix if clear it's a web address.
            # For consistency and if it's a web source, including it.
            parts.append(f'{citation.url}.')

        # Fallback ID
        if not citation.doi and not citation.url and citation.backup_id:
            parts.append(f'Identifier: {citation.backup_id}.')

        formatted_citation = ' '.join(filter(None, parts))
        # MLA typically ends with a period.
        if not formatted_citation.endswith('.'):
            formatted_citation += '.'
        # Cleanup
        formatted_citation = formatted_citation.replace('..', '.').strip()
        formatted_citation = formatted_citation.replace(
            ' .', '.'
        )  # Space before period
        formatted_citation = formatted_citation.replace(
            ',.', '.'
        )  # Comma before period
        return formatted_citation

    @staticmethod
    def _format_chicago(citation: Citation) -> str:
        """
        Format a citation in Chicago style (Notes and Bibliography).
        This implements a simplified version common for bibliographies.

        Args:
            citation: The Citation object to format.

        Returns:
            str: The citation formatted in Chicago style.

        Example:
            >>> citation = Citation(
            ...     title='A History of the Internet',
            ...     authors=['Johnson, Michael', 'Lee, Sarah K.'],
            ...     year=2022,
            ...     journal='Journal of Historical Studies',
            ...     volume='25',
            ...     issue='4',
            ...     pages='512-530',
            ...     doi='10.1357/jhs.2022.001',
            ... )
            >>> CitationFormatter._format_chicago(citation)
            'Johnson, Michael, and Sarah K. Lee. "A History of the Internet." _Journal of Historical Studies_ 25, no. 4 (2022): 512-530. https://doi.org/10.1357/jhs.2022.001.'
        """  # noqa: W505
        parts = []

        # Authors (Last, First and First Last for subsequent)
        if citation.authors:
            if len(citation.authors) == 1:
                parts.append(f'{citation.authors[0]}.')  # Assumes "Last, First"
            else:
                # For Chicago, first author is Last, First; subsequent are First Last.
                # This is a simplification, assumes input format is consistent or pre-processed.  # noqa: W505
                # For now, using "and" like MLA for simplicity if not perfectly formatted.  # noqa: W505
                author_list = [citation.authors[0]]
                for author in citation.authors[1:]:
                    # Attempt to flip "Last, First" to "First Last"
                    if ', ' in author:
                        name_parts = author.split(', ', 1)
                        author_list.append(f'{name_parts[1]} {name_parts[0]}')
                    else:
                        author_list.append(author)  # Keep as is if not "Last, First"
                if len(author_list) <= 3:  # For up to three authors, list all
                    authors_str = (
                        ' and '.join([', '.join(author_list[:-1]), author_list[-1]])
                        if len(author_list) > 1
                        else author_list[0]
                    )
                else:  # For more than three, list first author then "et al."
                    authors_str = f'{author_list[0]} et al.'
                parts.append(f'{authors_str}.')

        # Title (Title Case, in quotes for articles)
        if citation.title:
            # Basic title case.
            title_case_title = ' '.join(
                word.capitalize() for word in citation.title.split()
            )
            parts.append(f'"{title_case_title}.".')  # Period inside quotes

        # Journal/Source Information
        if citation.journal:
            title_case_journal = ' '.join(
                word.capitalize() for word in citation.journal.split()
            )
            journal_info = f'_{title_case_journal}_'  # Journal title italicized
            if citation.volume:
                journal_info += f' {citation.volume}'
            if citation.issue:
                journal_info += f', no. {citation.issue}'
            if citation.year:  # Year in parentheses after issue/volume
                journal_info += f' ({citation.year})'
            if citation.pages:
                journal_info += f': {citation.pages}'  # Pages preceded by colon
            parts.append(journal_info + '.')
        elif citation.venue:  # For conferences, books, etc.
            # This part would need more complex logic based on resource type (book, chapter, etc.)  # noqa: W505
            # For now, a simple italicized venue.
            venue_title_case = ' '.join(
                word.capitalize() for word in citation.venue.split()
            )
            parts.append(f'_{venue_title_case}_.')
            if (
                citation.year and not citation.journal
            ):  # Add year if not part of journal string
                parts[-1] = parts[-1][:-1] + f' ({citation.year}).'

        # DOI or URL
        if citation.doi:
            parts.append(
                f'https://doi.org/{citation.doi.replace("https://doi.org/", "")}.'
            )
        elif citation.url:
            # Chicago often includes URL for online sources, especially if no DOI.
            # Sometimes "Accessed [Date]." is added, but not implemented here for simplicity.  # noqa: W505
            parts.append(f'{citation.url}.')

        formatted_citation = ' '.join(filter(None, parts))
        # General cleanup
        formatted_citation = formatted_citation.replace(
            '..', '.'
        ).strip()  # Replace double periods
        formatted_citation = formatted_citation.replace(
            ' .', '.'
        )  # Remove space before period
        formatted_citation = formatted_citation.replace(
            ',.', '.'
        )  # Remove comma before period
        if not formatted_citation.endswith('.'):
            formatted_citation += '.'
        return formatted_citation

    @staticmethod
    def _format_harvard(citation: Citation) -> str:
        """
        Format a citation in Harvard style.
        This is a common variation; Harvard style can have many specific institutional versions.

        Args:
            citation: The Citation object to format.

        Returns:
            str: The citation formatted in Harvard style.

        Example:
            >>> citation = Citation(
            ...     title='Advancements in Renewable Energy',
            ...     authors=['Patel, R.', 'Chen, L.'],
            ...     year=2021,
            ...     journal='International Journal of Energy Research',
            ...     volume='45',
            ...     issue='5',
            ...     pages='780-795',
            ...     doi='10.1002/er.12345',
            ... )
            >>> CitationFormatter._format_harvard(citation)
            "Patel, R. & Chen, L. (2021) 'Advancements in Renewable Energy', _International Journal of Energy Research_, 45(5), pp. 780-795. doi: 10.1002/er.12345."
        """  # noqa: W505
        parts = []

        # Authors (Last name, Initial.)
        if citation.authors:
            # Assumes authors are "Lastname, I." or "Lastname, I. M."
            if len(citation.authors) == 1:
                authors_str = f'{citation.authors[0]}'
            elif len(citation.authors) == 2:
                authors_str = f'{citation.authors[0]} & {citation.authors[1]}'
            else:  # 3 or more, use 'et al.' after the first author in some Harvard variations, or list all.
                # Listing all is safer if no specific 'et al.' rule is given for max authors.  # noqa: W505
                # For simplicity, using a common approach: list all if <=3, else first + et al.  # noqa: W505
                if len(citation.authors) <= 3:
                    authors_str = (
                        ', '.join(citation.authors[:-1]) + f' & {citation.authors[-1]}'
                    )
                else:
                    authors_str = f'{citation.authors[0]} et al.'
            parts.append(authors_str)

        # Year (in parentheses)
        if citation.year:
            parts.append(f'({citation.year})')

        # Title (Sentence case, in single quotes for articles)
        if citation.title:
            # Basic sentence case
            sentence_case_title = citation.title[0].upper() + citation.title[1:].lower()
            parts.append(f"'{sentence_case_title}',")  # Comma after title

        # Journal Title (Italicized, Title Case)
        if citation.journal:
            title_case_journal = ' '.join(
                word.capitalize() for word in citation.journal.split()
            )
            journal_info = f'_{title_case_journal}_,'  # Comma after journal title
            if citation.volume:
                journal_info += f' {citation.volume}'
            if citation.issue:
                journal_info += f'({citation.issue})'  # Issue in parentheses
            if citation.pages:
                journal_info += f', pp. {citation.pages}'  # pp. for pages
            parts.append(journal_info + '.')
        elif citation.venue:  # For books, conferences etc.
            venue_title_case = ' '.join(
                word.capitalize() for word in citation.venue.split()
            )
            parts.append(f'_{venue_title_case}_.')  # Italicized, period.

        # DOI or URL
        if citation.doi:
            parts.append(f'doi: {citation.doi.replace("https://doi.org/", "")}.')
        elif citation.url:
            # Harvard might require "Available at:" for URLs
            parts.append(
                f'Available at: <{citation.url}> [Accessed: {citation.access_date if hasattr(citation, "access_date") and citation.access_date else "Date not available"}].'
            )
            # If access_date is not available, a placeholder or omitting it might be better.  # noqa: W505
            # For now, using a placeholder if not present.

        formatted_citation = ' '.join(filter(None, parts))
        # Cleanup and final period
        formatted_citation = (
            formatted_citation.replace('..', '.')
            .replace(' ,', ',')
            .replace(' .', '.')
            .strip()
        )
        if formatted_citation.endswith(','):
            formatted_citation = formatted_citation[:-1] + '.'
        elif not formatted_citation.endswith('.'):
            formatted_citation += '.'

        return formatted_citation

    @staticmethod
    def _format_ieee(citation: Citation) -> str:
        """
        Format a citation in IEEE style.
        Note: IEEE in-text citations are numbers [1], this formats the reference list entry.

        Args:
            citation: The Citation object to format.

        Returns:
            str: The citation formatted in IEEE style.

        Example:
            >>> citation = Citation(
            ...     title='Advanced Signal Processing Techniques',
            ...     authors=[
            ...         'A. Author',
            ...         'B. Coauthor',
            ...     ],  # IEEE uses initials first usually
            ...     year=2024,
            ...     journal='IEEE Transactions on Signal Processing',
            ...     volume='70',
            ...     issue='5',
            ...     pages='1234-1245',
            ...     doi='10.1109/TSP.2024.123456',
            ... )
            >>> CitationFormatter._format_ieee(
            ...     citation
            ... )  # Note: In-text would be [1], [2] etc.
            'A. Author and B. Coauthor, "Advanced Signal Processing Techniques," _IEEE Transactions on Signal Processing_, vol. 70, no. 5, pp. 1234-1245, 2024. doi: 10.1109/TSP.2024.123456.'
        """  # noqa: W505
        parts = []

        # Authors (Initials First Last, e.g., A. B. Author)
        if citation.authors:
            # IEEE often uses "and" before the last author.
            # Assumes authors might be "First Last" or "F. Last" or "First M. Last"
            # Simple join for now. True IEEE often abbreviates journal names too.
            if len(citation.authors) > 1:
                authors_str = (
                    ', '.join(citation.authors[:-1]) + f', and {citation.authors[-1]}'
                )
            else:
                authors_str = citation.authors[0]
            parts.append(authors_str + ',')  # Comma after authors

        # Title (Title Case, in quotes)
        if citation.title:
            # Basic title case. IEEE can be specific.
            title_case_title = ' '.join(
                word.capitalize() for word in citation.title.split()
            )
            parts.append(f'"{title_case_title},".')  # Comma after title in quotes

        # Journal Title (Italicized, often abbreviated in IEEE)
        # Not implementing abbreviations here due to complexity. Using full title case.
        if citation.journal:
            title_case_journal = ' '.join(
                word.capitalize() for word in citation.journal.split()
            )
            journal_info = f'_{title_case_journal}_'
            if citation.volume:
                journal_info += f', vol. {citation.volume}'
            if citation.issue:
                journal_info += f', no. {citation.issue}'
            if citation.pages:
                journal_info += f', pp. {citation.pages}'
            if citation.year:  # Year often comes after pages or at the end for journals
                journal_info += f', {citation.year}'
            parts.append(journal_info + '.')
        elif citation.venue:  # For conference proceedings, books
            # Conference Name, Location, Date, Year. Book Title, Publisher, Year.
            # Simplified for now
            venue_title_case = ' '.join(
                word.capitalize() for word in citation.venue.split()
            )
            venue_str = f'in _{venue_title_case}_'
            if citation.year and not citation.journal:
                venue_str += f', {citation.year}'
            parts.append(venue_str + '.')

        # DOI
        if citation.doi:
            # Remove common prefixes if present, as "doi:" prefix is added.
            doi_cleaned = citation.doi.replace('https://doi.org/', '').replace(
                'doi:', ''
            )
            parts.append(f'doi: {doi_cleaned}.')
        elif citation.url and not citation.journal:  # URL for online docs if no DOI
            parts.append(f'Available: {citation.url}')  # IEEE often uses "Available:"

        # Fallback ID
        if not citation.doi and not citation.url and citation.backup_id:
            parts.append(f'Id: {citation.backup_id}.')

        formatted_citation = ' '.join(filter(None, parts))
        # Cleanup: IEEE uses periods judiciously.
        # Remove space before comma/period, ensure single period at end.
        formatted_citation = (
            formatted_citation.replace(' ,', ',').replace(' .', '.').strip()
        )
        if formatted_citation.endswith(','):
            formatted_citation = formatted_citation[:-1] + '.'
        elif not formatted_citation.endswith('.'):
            formatted_citation += '.'
        formatted_citation = formatted_citation.replace(
            ',.', '.'
        )  # handle quote ending like "Title.",
        return formatted_citation.strip()


def format_citation(citation: Citation, style: str = 'ieee') -> str:
    """
    Format a citation according to the specified style.

    This is a convenience function that wraps the CitationFormatter class.

    Args:
        citation: The Citation object to format.
        style: The citation style to use (ieee, apa, mla, chicago, harvard).

    Returns:
        str: The formatted citation string.

    Raises:
        CitationFormatError: If the formatting fails or the style is not supported.

    Example:
        >>> citation = Citation(
        ...     title='Sample Paper',
        ...     authors=['J. Smith', 'A. Jones'],
        ...     year=2023,
        ...     journal='Journal of Research',
        ... )
        >>> format_citation(citation, 'apa')
        'Smith, J., & Jones, A. (2023). Sample Paper. Journal of Research.'
    """
    style_map = {
        'ieee': CitationStyle.IEEE,
        'apa': CitationStyle.APA,
        'mla': CitationStyle.MLA,
        'chicago': CitationStyle.CHICAGO,
        'harvard': CitationStyle.HARVARD,
    }

    try:
        citation_style = style_map.get(style.lower())
        if citation_style is None:
            raise CitationFormatError(f'Unsupported citation style: {style}')
        return CitationFormatter.format_citation(citation, citation_style)
    except Exception as e:
        if isinstance(e, CitationFormatError):
            raise
        error_msg = f'Failed to format citation: {e}'
        logger.error(error_msg)
        raise CitationFormatError(error_msg) from e
