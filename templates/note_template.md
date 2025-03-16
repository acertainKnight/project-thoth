# {{ title }}

**Authors**: {{ authors | join(", ") }}
{% if year %}**Year**: {{ year }}{% endif %}
{% if doi %}**DOI**: {{ doi }}{% endif %}
{% if journal %}**Journal**: {{ journal }}{% endif %}

## Summary

{{ summary }}

## Key Points

{% for point in key_points %}
- {{ point }}
{% endfor %}

## Abstract

{{ abstract }}

## Citations

{% for citation in citations %}
- {{ citation.text }} {% if citation.uri %}[Link]({{ citation.uri }}){% endif %}
{% endfor %}

## Source Files

- [PDF]({{ source_files.pdf }})
- [Markdown]({{ source_files.markdown }})
