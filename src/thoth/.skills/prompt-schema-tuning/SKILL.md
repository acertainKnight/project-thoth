---
name: prompt-schema-tuning
description: Customize what information is extracted from papers (schema) and how it's extracted (prompts). Use when the user wants to change analysis fields, instructions, or prompt templates.
tools:
- get_schema_info
- list_schema_presets
- get_preset_details
- update_schema_field
- update_schema_instructions
- reset_schema_to_default
- list_prompt_templates
- read_prompt_template
- update_prompt_template
- reset_prompt_template
---

# Prompt & Schema Tuning

Customize document analysis by modifying what information is extracted (analysis schema) and how extraction happens (prompt templates). The schema defines fields like "summary" or "methodology". The prompts tell the LLM how to populate those fields.

## Overview

Two configuration layers control analysis:

1. **Analysis Schema** - JSON config defining extractable fields, types, and instructions
   - Location: `_thoth/analysis_schema.json` in vault
   - Four presets: standard, detailed, minimal, custom
   - Hot-reloaded by schema service

2. **Prompt Templates** - Jinja2 templates that guide the LLM
   - Location: `_thoth/prompts/{provider}/` in vault (custom) or `templates/prompts/` (defaults)
   - Provider-specific: google, openai, default, agent
   - Hot-reloaded by file watcher

## Core Tools

### Schema Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `get_schema_info` | View current schema config | Check active preset, fields |
| `list_schema_presets` | List all presets | See available options |
| `get_preset_details` | View fields in a preset | Inspect before editing |
| `update_schema_field` | Add/update/remove field | Change what's extracted |
| `update_schema_instructions` | Change extraction guidance | Adjust how LLM extracts |
| `reset_schema_to_default` | Restore from template | Fix broken config |

### Prompt Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `list_prompt_templates` | List available templates | See what can be edited |
| `read_prompt_template` | View template content | Check current prompts |
| `update_prompt_template` | Modify template | Fix extraction issues |
| `reset_prompt_template` | Delete custom version | Revert to default |

## Understanding the Schema

### Schema Structure

The schema is organized into presets. Each preset has:
- `name` - Display name
- `description` - Purpose description
- `fields` - Dictionary of field definitions
- `instructions` - Natural language guidance for LLM

### Field Specification

Each field has:
```json
{
  "type": "string|integer|array",
  "required": true/false,
  "description": "What this field should contain",
  "items": "string" (for arrays)
}
```

### Example: Standard Preset

```json
{
  "title": {
    "type": "string",
    "required": true,
    "description": "The title of the research paper"
  },
  "summary": {
    "type": "string",
    "required": false,
    "description": "A multi-paragraph summary"
  },
  "tags": {
    "type": "array",
    "items": "string",
    "required": false,
    "description": "Keywords for the article"
  }
}
```

## Understanding Prompts

### Prompt Templates

Jinja2 templates that create the actual LLM prompt. Key variables:
- `{{ content }}` - Document text to analyze
- `{{ analysis_schema }}` - JSON schema for output
- `{{ custom_instructions }}` - Preset-specific instructions
- `{{ chunk }}` - Text chunk for map-reduce processing

### Provider Variations

Different templates per provider optimize for model behavior:
- `google/` - Gemini-specific guidance
- `openai/` - GPT-specific guidance
- `default/` - Generic templates
- `agent/` - Agent-specific prompts

### Key Templates

- `analyze_content.j2` - Direct analysis (short docs)
- `analyze_section.j2` - Map phase (long docs)
- `reduce_sections.j2` - Reduce phase (synthesis)
- `refine_analysis.j2` - Iterative refinement

## Workflow Examples

### Example 1: Summaries Too Short

**User**: "The summaries in my analysis are too short. I need more detail."

```
1. Check current schema
   get_schema_info()
   → Active preset: standard

2. View preset details
   get_preset_details(preset="standard")
   → summary: "A multi-paragraph summary"

3. Update field description to be more specific
   update_schema_field(
     preset="standard",
     field_name="summary",
     field_spec={
       "type": "string",
       "required": false,
       "description": "A comprehensive 5-7 paragraph summary covering objectives, methodology, key results, and implications. Each paragraph should be 4-6 sentences with specific details from the paper."
     }
   )

4. Also update preset instructions for emphasis
   update_schema_instructions(
     preset="standard",
     instructions="Provide comprehensive analysis with detailed multi-paragraph summaries (5-7 paragraphs). Extract 10-15 key points with specific details. Be thorough in describing methodology and results."
   )

5. Response:
   "Updated the summary field to require 5-7 detailed paragraphs and modified preset instructions to emphasize comprehensive analysis. Changes take effect on your next analysis run."
```

### Example 2: Remove Unnecessary Fields

**User**: "I don't need the strengths and weaknesses fields. They're not useful for my research."

```
1. Check which preset is active
   get_schema_info()
   → Active: standard

2. Remove first field
   update_schema_field(
     preset="standard",
     field_name="strengths",
     remove=true
   )

3. Remove second field
   update_schema_field(
     preset="standard",
     field_name="weaknesses",
     remove=true
   )

4. Response:
   "Removed 'strengths' and 'weaknesses' fields from the standard preset. Your analyses will no longer extract these fields."
```

### Example 3: Add Custom Field

**User**: "I want to track which papers mention specific datasets. Add a 'datasets_used' field."

```
1. Check active preset
   get_schema_info()
   → Active: standard

2. Add new field
   update_schema_field(
     preset="standard",
     field_name="datasets_used",
     field_spec={
       "type": "array",
       "items": "string",
       "required": false,
       "description": "List of datasets mentioned in the paper, including their names and brief descriptions of how they were used"
     }
   )

3. Update instructions to emphasize this
   get_preset_details(preset="standard")
   # Read current instructions

   update_schema_instructions(
     preset="standard",
     instructions="[existing instructions] Pay special attention to identifying and listing all datasets mentioned in the paper, including dataset names, sources, and usage context."
   )

4. Response:
   "Added 'datasets_used' field to extract dataset information as an array of strings. Updated instructions to emphasize dataset extraction."
```

### Example 4: Fix Prompt Issues

**User**: "The analysis keeps missing the methodology section. Can you check the prompt?"

```
1. List available templates
   list_prompt_templates(provider="google")
   → Shows analyze_content.j2, analyze_section.j2, etc.

2. Read current prompt
   read_prompt_template(
     template_name="analyze_content.j2",
     provider="google"
   )
   → Shows full Jinja2 template

3. Identify issue: prompt doesn't explicitly mention methodology

4. Update template to emphasize methodology
   update_prompt_template(
     template_name="analyze_content.j2",
     provider="google",
     content="[Updated Jinja2 template with added emphasis:
     'Pay special attention to the methodology section. Extract detailed information about study design, methods, procedures, and analytical approaches. If methodology is split across multiple sections, synthesize information from all locations.']"
   )

5. Response:
   "Updated the analyze_content.j2 prompt for Google provider to emphasize methodology extraction. The change is hot-reloaded and will affect your next analysis."
```

### Example 5: Reset After Bad Edit

**User**: "I messed up the schema. Can you restore it?"

```
1. Check what's wrong
   get_schema_info()
   → Might show validation errors

2. Reset to defaults
   reset_schema_to_default(confirm=true)
   → Resets entire file

   # OR reset just one preset:
   reset_schema_to_default(preset="custom", confirm=true)

3. Response:
   "Reset schema to repository defaults. Your custom changes have been removed but saved in a .bak file if you need to recover anything."
```

## Schema vs Prompts: When to Edit What

### Edit the Schema When:
- User wants different fields extracted ("add funding info")
- Fields are wrong type ("tags should be an array")
- Too many/too few fields ("I don't need all this detail")
- Field descriptions are unclear to the LLM

### Edit the Prompts When:
- LLM consistently misses information ("not finding methods")
- Output format is wrong ("summaries are too technical")
- Need provider-specific adjustments ("works with GPT but not Gemini")
- Want to add examples or constraints to guidance

### Edit Both When:
- Major change to analysis approach ("focus on reproducibility")
- Field exists but LLM populates it poorly ("methodology" field needs better extraction)

## Best Practices

### Before Editing
1. Always read current config first (`get_schema_info`, `get_preset_details`, `read_prompt_template`)
2. Understand what's currently configured
3. Identify the specific problem (wrong field vs wrong extraction)

### When Editing Schema
- Make field descriptions detailed and specific
- Use `instructions` for general guidance, field `description` for specifics
- Test with one paper before bulk reprocessing
- Keep backups (tools create `.bak` files automatically)

### When Editing Prompts
- Keep required Jinja2 variables (`{{ content }}`, `{{ analysis_schema }}`)
- Test with both short and long documents
- Consider provider differences (Gemini vs GPT behavior)
- Document why you made changes (comment in prompt)

### After Editing
- Changes take effect immediately (hot-reloaded)
- No service restart needed
- Test with a single paper first
- If extraction fails, check validation warnings

## Troubleshooting

### Schema Validation Fails
```
Problem: "Schema validation failed: missing required key"
Solution:
1. validate_schema_file() to see specific error
2. Fix the issue or reset_schema_to_default()
3. Backup is saved automatically
```

### Prompt Not Loading
```
Problem: "Template not found for provider"
Solution:
1. list_prompt_templates() to verify name and provider
2. Check spelling of template_name (must include .j2)
3. Provider must be 'google', 'openai', 'default', or 'agent'
```

### LLM Returns Wrong Format
```
Problem: "LLM output doesn't match schema"
Solution:
1. read_prompt_template() to check if schema is passed
2. Verify {{ analysis_schema }} appears in template
3. Check field types are valid (string, integer, array)
```

### Custom Prompt Not Used
```
Problem: "My changes aren't affecting analysis"
Solution:
1. Verify file saved to _thoth/prompts/{provider}/
2. Check provider name matches model (google for gemini, openai for gpt)
3. Hot-reload may take a few seconds
```

## Schema Reference

### Standard Preset (15 fields)
Balanced analysis: title, authors, year, doi, journal, abstract, key_points, summary, objectives, methodology, results, discussion, strengths, weaknesses, tags

### Detailed Preset (20 fields)
Exhaustive extraction: adds data, experimental_setup, evaluation_metrics, limitations, future_work, related_work

### Minimal Preset (6 fields)
Quick screening: title, authors, year, abstract, key_points (3-5), tags (3-5)

### Custom Preset
User-defined template for specialized needs

## Prompt Reference

### Analysis Prompts
- `analyze_content.j2` - Single-pass analysis for short docs
- `analyze_section.j2` - Map phase for chunked docs
- `reduce_sections.j2` - Combine section analyses
- `refine_analysis.j2` - Iterative improvement

### Other Prompts
- `extract_citations*.j2` - Citation extraction
- `evaluate_*.j2` - Relevance evaluation
- `consolidate_tags.j2` - Tag management
- `research_agent_chat.j2` - Agent conversations

## Notes

- Schema changes require valid JSON structure
- Prompt changes should preserve Jinja2 syntax
- All edits create `.bak` backups automatically
- Changes apply to new analyses, not retroactively
- Custom configs survive system updates (vault-based)
