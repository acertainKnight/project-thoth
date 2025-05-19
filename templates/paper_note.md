# {{ title }}

**Authors**: {{ authors | join(", ") if authors else "N/A" }}
{% if year %}**Year**: {{ year }}{% endif %}
{% if doi %}**DOI**: {{ doi }}{% endif %}
{% if journal %}**Journal**: {{ journal }}{% endif %}

## Summary

{{ summary | default("N/A") }}

## Key Points

{% if key_points %}
{% for point in key_points %}
- {{ point }}
{% endfor %}
{% else %}
N/A
{% endif %}

## Abstract

{{ abstract | default("N/A") }}

## Methodology

{{ methodology | default("N/A") }}

## Results

{{ results | default("N/A") }}

## Limitations

{{ limitations | default("N/A") }}

## Related Work

{{ related_work | default("N/A") }}

## Citations

{% if citations %}
{% for citation_item in citations %}
- {{ citation_item.generated_markdown_link | safe if citation_item.generated_markdown_link else (citation_item.formatted or citation_item.title or "N/A") }}
{% endfor %}
{% else %}
No citations found.
{% endif %}

## Source Files

- PDF Link: {{ source_files.pdf_link | safe if source_files.pdf_link else "N/A" }}
- Markdown Link: {{ source_files.markdown_link | safe if source_files.markdown_link else "N/A" }}
