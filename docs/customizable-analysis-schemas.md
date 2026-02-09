# Customizable Analysis Schemas

Thoth's customizable analysis schema system allows you to control exactly what information is extracted from academic papers during document processing.

## Overview

Instead of a fixed set of fields (title, authors, abstract, summary, etc.), you can now:

- **Choose from presets**: Standard, Detailed, or Minimal extraction
- **Add custom fields**: Extract any information you need
- **Provide custom instructions**: Guide the LLM on what to extract
- **Switch schemas anytime**: Different papers can use different schemas

## Quick Start

### 1. Locate Your Schema File

On first run, Thoth creates a schema file at:
```
<vault>/thoth/_thoth/analysis_schema.json
```

This file controls all document analysis behavior.

### 2. Select a Preset

Edit `analysis_schema.json` and change the `active_preset`:

```json
{
  "version": "1.0",
  "active_preset": "detailed",  // Change this: "standard", "detailed", "minimal", or "custom"
  "presets": { ... }
}
```

### 3. Process Documents

Process PDFs normally - they'll use your selected schema:

```bash
python -m thoth pdf process paper.pdf
```

## Available Presets

### Standard (Default)
**Best for**: Most papers - balanced detail level

**14 fields**: title, authors, year, doi, journal, abstract, key_points, summary, objectives, methodology, results, discussion, strengths, weaknesses, tags

**Use when**: You want comprehensive analysis without overwhelming detail

### Detailed
**Best for**: Important papers requiring deep analysis

**20 fields**: All standard fields PLUS data, experimental_setup, evaluation_metrics, limitations, future_work, related_work

**Use when**: You need exhaustive extraction for critical papers

### Minimal
**Best for**: Quick screening of many papers

**6 fields**: title, authors, year, abstract, key_points (3-5), tags (3-5)

**Use when**: You're rapidly screening papers and need just the essentials

### Custom
**Best for**: Specialized research domains

**User-defined fields**: You define exactly what to extract

**Use when**: You have specific extraction needs not covered by presets

## Customizing a Preset

You can modify any preset to add or remove fields.

### Example: Add a Field to Standard

```json
{
  "presets": {
    "standard": {
      "fields": {
        // ... existing fields ...

        "practical_applications": {
          "type": "string",
          "required": false,
          "description": "Real-world applications of this research"
        }
      }
    }
  }
}
```

### Field Specification

Each field has:

- **type**: `"string"`, `"integer"`, `"number"`, `"boolean"`, or `"array"`
- **required**: `true` or `false` (missing required fields will cause validation errors)
- **description**: Guides the LLM on what to extract
- **items** (for arrays): Type of array elements (`"string"`, `"integer"`, etc.)

### Example Field Types

```json
{
  "title": {
    "type": "string",
    "required": true,
    "description": "Paper title"
  },
  "year": {
    "type": "integer",
    "required": false,
    "description": "Publication year"
  },
  "authors": {
    "type": "array",
    "items": "string",
    "required": true,
    "description": "List of authors"
  },
  "impact_score": {
    "type": "number",
    "required": false,
    "description": "Estimated impact score (0.0-10.0)"
  }
}
```

## Custom Instructions

Provide additional guidance to the LLM for each preset:

```json
{
  "presets": {
    "standard": {
      "instructions": "Focus on methodology and results. Be specific about algorithms and metrics used.",
      "fields": { ... }
    }
  }
}
```

The LLM will follow these instructions when extracting information.

## Creating a Custom Preset

Create your own preset from scratch:

```json
{
  "presets": {
    "my_domain": {
      "name": "My Research Domain",
      "description": "Custom schema for my specific research area",
      "fields": {
        "title": {
          "type": "string",
          "required": true,
          "description": "Paper title"
        },
        "authors": {
          "type": "array",
          "items": "string",
          "required": true,
          "description": "Authors"
        },
        "domain_specific_metric": {
          "type": "number",
          "required": false,
          "description": "The specialized metric we track in our field"
        },
        "research_paradigm": {
          "type": "string",
          "required": false,
          "description": "Which paradigm does this follow: empirical, theoretical, or experimental"
        }
      },
      "instructions": "Extract domain-specific information carefully. Focus on the paradigm and metrics."
    }
  }
}
```

Then set it as active:

```json
{
  "active_preset": "my_domain"
}
```

## Schema Versioning

Every paper records which schema was used:

- **analysis_schema_name**: The preset name (e.g., "standard", "detailed")
- **analysis_schema_version**: The schema file version (e.g., "1.0")

This ensures you can always:
1. Know what was extracted from each paper
2. Re-process old papers with new schemas
3. Compare papers processed with different schemas

View schema info in database:

```sql
SELECT title, analysis_schema_name, analysis_schema_version
FROM papers
WHERE analysis_schema_name = 'detailed';
```

## Dynamic Note Templates

Notes automatically adapt to your schema:

### Standard Fields (Always Shown)
If present in your schema, these sections appear in notes:
- Summary, Key Points, Abstract
- Objectives, Methodology, Results, Discussion
- Strengths, Weaknesses, Limitations
- Future Work, Related Work

### Custom Fields (Auto-Generated Section)
Any custom fields you add appear under "Additional Analysis Fields" in notes.

Example note with custom field:
```markdown
# Paper Title

## Summary
...

## Additional Analysis Fields

### Practical Applications
Real-world uses include...

### Domain Specific Metric
Scores 8.7 on the specialized benchmark...
```

## Hot-Reload (Development)

In development mode, schema changes reload automatically (~2s):

1. Edit `analysis_schema.json`
2. Save the file
3. Process next PDF - uses new schema

No need to restart services!

## Example Workflows

### Workflow 1: Literature Review

Use **detailed** preset for 10-20 key papers, **minimal** for initial screening of 100+ papers.

```json
// For initial screening:
{"active_preset": "minimal"}

// Process 100 papers quickly
// Then switch for deep analysis:

{"active_preset": "detailed"}

// Process 15 key papers
```

### Workflow 2: Domain-Specific Research

Create custom preset for your field:

```json
{
  "presets": {
    "neuroscience": {
      "name": "Neuroscience Papers",
      "fields": {
        "title": {"type": "string", "required": true, "description": "Title"},
        "authors": {"type": "array", "items": "string", "required": true, "description": "Authors"},
        "brain_region": {"type": "string", "required": false, "description": "Primary brain region studied"},
        "technique": {"type": "string", "required": false, "description": "Imaging or recording technique used"},
        "sample_size": {"type": "integer", "required": false, "description": "Number of subjects"},
        "findings": {"type": "string", "required": false, "description": "Key neuroscience findings"}
      },
      "instructions": "Focus on brain regions, techniques, and sample sizes. Extract specific neuroscience findings."
    }
  },
  "active_preset": "neuroscience"
}
```

### Workflow 3: Evolving Schema

Start with standard, add fields as you discover patterns:

```json
// Week 1: Standard preset
{"active_preset": "standard"}

// Week 2: Notice many papers discuss datasets - add field
{
  "presets": {
    "standard": {
      "fields": {
        // ... existing fields ...
        "datasets_used": {
          "type": "array",
          "items": "string",
          "required": false,
          "description": "Names of datasets used in this research"
        }
      }
    }
  }
}

// Week 3: Notice need for code availability - add field
// And so on...
```

## Backward Compatibility

Papers processed with old schemas remain accessible:

- **Default schema**: Papers from before this feature use `analysis_schema_name: "default"`
- **Old fields preserved**: All existing analysis data remains intact
- **Notes still work**: Old notes render correctly

## Troubleshooting

### Schema Not Loading

**Problem**: Changes to schema file not taking effect

**Solutions**:
1. Check file location: `<vault>/thoth/_thoth/analysis_schema.json`
2. Validate JSON syntax: Use a JSON validator
3. Check logs for error messages
4. Restart services if not in dev mode

### Validation Errors

**Problem**: Papers fail to process with validation errors

**Solutions**:
1. Check required fields: Ensure LLM can extract them
2. Review field descriptions: Make them clear and specific
3. Mark uncertain fields as `"required": false`
4. Simplify instructions if too complex

### Missing Custom Fields in Notes

**Problem**: Custom fields not appearing in generated notes

**Solutions**:
1. Ensure field has a value (not null or empty)
2. Check field name doesn't conflict with standard fields
3. Verify note template is up to date

### Schema Version Mismatch

**Problem**: Papers show unexpected schema versions

**Solutions**:
1. Schema version comes from JSON file's `"version"` field
2. Update version number when making significant changes
3. Use consistent versioning (e.g., "1.0", "1.1", "2.0")

## CLI Commands

Check schema status:
```bash
python -m thoth system check
```

Validate schema file:
```bash
python -m thoth schema validate
```

List available presets:
```bash
python -m thoth schema list
```

Switch preset:
```bash
python -m thoth schema set detailed
```

## API Endpoints

Get current schema info:
```bash
GET /api/schema
```

List available presets:
```bash
GET /api/schema/presets
```

Switch active preset:
```bash
POST /api/schema/preset
{"preset": "detailed"}
```

## Best Practices

1. **Start with presets**: Use standard/detailed/minimal before customizing
2. **Iterate gradually**: Add custom fields one at a time
3. **Clear descriptions**: Help the LLM understand what to extract
4. **Test on samples**: Process a few papers before batch processing
5. **Version your schema**: Update version number for significant changes
6. **Document your fields**: Add comments explaining custom fields
7. **Keep instructions focused**: Don't overwhelm the LLM with too many instructions

## Schema File Template

Complete template with all 4 presets:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "version": "1.0",
  "lastModified": "2026-01-09T00:00:00Z",
  "active_preset": "standard",

  "presets": {
    "standard": { /* 14 fields */ },
    "detailed": { /* 20 fields */ },
    "minimal": { /* 6 fields */ },
    "custom": { /* User-defined */ }
  }
}
```

See `templates/analysis_schema.json` for the complete default template.

## Support

Issues or questions:
- GitHub: https://github.com/acertainKnight/project-thoth/issues
- Documentation: https://github.com/acertainKnight/project-thoth/docs

## Advanced Topics

### Multiple Named Schemas (Future)

Future support for multiple named schema configurations:

```json
{
  "schemas": {
    "ml_papers": { /* Schema for ML papers */ },
    "bio_papers": { /* Schema for biology papers */ },
    "general": { /* General papers */ }
  },
  "active_schema": "ml_papers"
}
```

This will allow switching entire schema configurations, not just presets.

### Conditional Field Extraction (Future)

Future support for conditional fields:

```json
{
  "fields": {
    "is_survey": {
      "type": "boolean",
      "description": "Is this a survey paper?"
    },
    "survey_coverage": {
      "type": "string",
      "required": false,
      "condition": "is_survey == true",
      "description": "What areas does the survey cover?"
    }
  }
}
```

### Schema Inheritance (Future)

Future support for preset inheritance:

```json
{
  "presets": {
    "my_preset": {
      "extends": "standard",
      "fields": {
        "custom_field": { /* Add to standard fields */ }
      }
    }
  }
}
```
