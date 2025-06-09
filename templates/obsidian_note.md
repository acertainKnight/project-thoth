# {{ title }}

**Authors**: {{ authors | join(", ") if authors else "N/A" }}
**Year**: {{ year if year else "N/A" }}
**DOI**: {{ doi if doi else "N/A" }}
**Journal**: {{ journal if journal else "N/A" }}
**Tags**: {{ tags | join(", ") if tags else "N/A" }}

**PDF Link**: {{ source_files.pdf_link | safe if source_files.pdf_link else "N/A" }}


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

## Full Analysis Details

{% for key, value in analysis.items() %}
{% if key not in [
    'summary', 'key_points', 'abstract', 'methodology', 'results', 'limitations', 'related_work', 'tags'
] and value %}
- **{{ key.replace('_', ' ').title() }}**: {{ value }}
{% endif %}
{% endfor %}

## Citations

{% if citations %}
{% for citation_item in citations %}
- {{ citation_item.generated_markdown_link | safe if citation_item.generated_markdown_link else (citation_item.formatted or citation_item.title or "N/A") }}
{% endfor %}
{% else %}
No citations found.
{% endif %}
