# {{ title }}

**Authors**: {{ authors if authors else "N/A" }}
**Year**: {{ year if year else "N/A" }}
**DOI**: {{ doi if doi else "N/A" }}
**Journal**: {{ journal if journal else "N/A" }}
**Tags**: {{ tags | join(", ") if tags else "N/A" }}

{% if source_files and source_files.pdf_link %}
**PDF Link**: {{ source_files.pdf_link | safe }}
{% endif %}

{% if _schema_name and _schema_name != 'default' %}
*Analysis Schema*: {{ _schema_name }} (v{{ _schema_version | default('1.0') }})
{% endif %}

## Summary

{{ summary | default("N/A") }}

## Key Points

{% if key_points %}
{% if key_points is string %}
{# Handle key_points as newline-separated string #}
{% for point in key_points.split('\n') %}
{% if point.strip() %}
- {{ point.strip() }}
{% endif %}
{% endfor %}
{% else %}
{# Handle key_points as array #}
{% for point in key_points %}
- {{ point }}
{% endfor %}
{% endif %}
{% else %}
N/A
{% endif %}

{% if abstract %}
## Abstract

{{ abstract }}
{% endif %}

{% if objectives %}
## Objectives

{{ objectives }}
{% endif %}

{% if methodology %}
## Methodology

{{ methodology }}
{% endif %}

{% if data %}
## Data

{{ data }}
{% endif %}

{% if experimental_setup %}
## Experimental Setup

{{ experimental_setup }}
{% endif %}

{% if evaluation_metrics %}
## Evaluation Metrics

{{ evaluation_metrics }}
{% endif %}

{% if results %}
## Results

{{ results }}
{% endif %}

{% if discussion %}
## Discussion

{{ discussion }}
{% endif %}

{% if strengths %}
## Strengths

{{ strengths }}
{% endif %}

{% if weaknesses %}
## Weaknesses

{{ weaknesses }}
{% endif %}

{% if limitations %}
## Limitations

{{ limitations }}
{% endif %}

{% if future_work %}
## Future Work

{{ future_work }}
{% endif %}

{% if related_work %}
## Related Work

{{ related_work }}
{% endif %}

{% if analysis %}
## Additional Analysis Fields

{% set standard_fields = [
    'title', 'authors', 'year', 'doi', 'journal', 'abstract', 'key_points', 'summary',
    'objectives', 'methodology', 'data', 'experimental_setup', 'evaluation_metrics',
    'results', 'discussion', 'strengths', 'weaknesses', 'limitations', 'future_work',
    'related_work', 'tags', '_schema_name', '_schema_version'
] %}
{% set has_custom_fields = false %}
{% for key, value in analysis.items() %}
{% if key not in standard_fields and value and value != 'N/A' %}
{% if not has_custom_fields %}
{% set has_custom_fields = true %}
{% endif %}
{% endif %}
{% endfor %}

{% if has_custom_fields %}
{% for key, value in analysis.items() %}
{% if key not in standard_fields and value and value != 'N/A' %}
### {{ key.replace('_', ' ').title() }}

{{ value }}

{% endif %}
{% endfor %}
{% endif %}
{% endif %}

## Citations ({{ citation_count | default(0) }})

{% if citations %}
{% for c in citations %}
- **[{{ c.number }}]** {{ c.formatted }}{% if c.obsidian_link %} (See Note: {{ c.obsidian_link }}){% elif c.url %} [Link]({{ c.url }}){% endif %}

{% endfor %}
{% else %}
No citations found.
{% endif %}
