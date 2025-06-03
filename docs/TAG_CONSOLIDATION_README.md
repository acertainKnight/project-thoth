# Tag Consolidation and Re-tagging System

This document describes the new tag consolidation and re-tagging functionality in Thoth, which helps organize and streamline tags across your academic article collection.

## Overview

The tag consolidation system performs two main functions:

1. **Tag Consolidation**: Analyzes all existing tags in your citation graph and consolidates similar or duplicate tags into canonical forms
2. **Tag Re-tagging**: Suggests additional relevant tags for articles based on their abstracts using the consolidated tag vocabulary

## Features

### 🏷️ Tag Consolidation
- Extracts all unique tags from articles in the citation graph
- Uses LLM analysis to identify similar tags (e.g., `#ml`, `#machine_learning`, `#machine-learning`)
- Creates canonical tag mappings with clear reasoning
- Updates existing articles with consolidated tags

### 🎯 Intelligent Tag Suggestion
- Analyzes article abstracts to suggest additional relevant tags
- Only suggests tags from the existing consolidated vocabulary
- Provides reasoning for each suggested tag
- Avoids over-tagging by limiting suggestions to highly relevant tags

### 📊 Comprehensive Reporting
- Detailed statistics on the consolidation process
- Before/after tag counts
- Tag mapping information
- Per-article update summaries

## Usage

### Command Line Interface

Run the complete tag consolidation and re-tagging process:

```bash
python -m thoth.main consolidate-tags
```

This command will:
1. Load your citation graph
2. Extract all existing tags
3. Consolidate similar tags using LLM analysis
4. Update articles with consolidated tags
5. Suggest additional relevant tags for each article
6. Save the updated graph with enhanced tags
7. Display comprehensive statistics

### Example Output

```
[INFO] Starting complete tag consolidation and re-tagging process...
[INFO] Extracted 45 unique tags from 23 articles
[INFO] Tag consolidation completed. Mapped 12 tags, resulting in 38 canonical tags
[INFO] Updated tags for "Deep Learning Approaches to Computer Vision": 3 -> 6 tags
[INFO] Updated tags for "Natural Language Processing with Transformers": 2 -> 5 tags
[INFO] Tag consolidation and re-tagging completed. Processed 23 articles, updated 18 articles, consolidated 12 tags, added 34 new tags

Summary statistics:
  - Articles processed: 23
  - Articles updated: 18
  - Tags consolidated: 12
  - Tags added: 34
  - Original tag count: 45
  - Final tag count: 38

Tag consolidation mappings:
  #ml -> #machine_learning
  #ai -> #artificial_intelligence
  #nlp -> #natural_language_processing
  #cv -> #computer_vision
```

## How It Works

### 1. Tag Extraction
The system scans all articles in the citation graph and extracts their existing tags from the analysis data.

### 2. Tag Consolidation
Using the `consolidate_tags.j2` prompt template, the LLM:
- Analyzes all existing tags for similarities
- Groups related tags together
- Selects canonical tag names based on clarity and common usage
- Creates mappings from old tags to canonical tags
- Provides reasoning for consolidation decisions

### 3. Tag Application
For each article, the system:
- Applies consolidation mappings to existing tags
- Updates the article's tag list with canonical equivalents

### 4. Tag Suggestion
Using the `suggest_additional_tags.j2` prompt template, the LLM:
- Analyzes each article's title and abstract
- Compares against the consolidated tag vocabulary
- Suggests 3-8 highly relevant additional tags
- Provides reasoning for each suggestion

### 5. Graph Update
The updated tags are saved back to the citation graph, ensuring persistence across sessions.

## Configuration

The tag consolidation system uses the same LLM configuration as the main analysis pipeline:

- **Model**: Configured via `llm_config.model` in your config
- **API Key**: Uses `api_keys.openrouter_key` from your config
- **Prompts**: Located in `templates/prompts/` directory

## Integration with Existing Workflow

The tag consolidation system is designed to complement your existing Thoth workflow:

1. **Process PDFs** as usual using `python -m thoth.main process`
2. **Regenerate notes** if needed using `python -m thoth.main regenerate-all-notes`
3. **Consolidate tags** periodically using `python -m thoth.main consolidate-tags`
4. **Generate updated notes** again if you want the new tags reflected

## Advanced Usage

### Programmatic Access

You can also use the tag consolidation functionality programmatically:

```python
from thoth.pipeline import ThothPipeline

# Initialize pipeline
pipeline = ThothPipeline()

# Run tag consolidation
stats = pipeline.consolidate_and_retag_all_articles()

# Access results
print(f"Processed {stats['articles_processed']} articles")
print(f"Consolidated {stats['tags_consolidated']} tags")
print(f"Added {stats['tags_added']} new tags")
```

### Individual Components

You can also use individual components:

```python
from thoth.analyze.tag_consolidator import TagConsolidator

# Initialize consolidator
consolidator = TagConsolidator()

# Extract tags
tags = consolidator.extract_all_tags_from_graph(citation_tracker)

# Consolidate tags
consolidation = consolidator.consolidate_tags(tags)

# Suggest tags for an article
suggestions = consolidator.suggest_additional_tags(
    title="Article Title",
    abstract="Article abstract...",
    current_tags=["#existing_tag"],
    available_tags=consolidation.consolidated_tags
)
```

## Best Practices

### When to Run Tag Consolidation

- **After adding many new articles** to your collection
- **Before major research projects** to ensure consistent organization
- **Periodically** (e.g., monthly) to maintain tag quality
- **When you notice tag inconsistencies** in your collection

### Tag Quality Guidelines

The system follows these principles for high-quality tags:

1. **Descriptive over abbreviative**: Prefers `#machine_learning` over `#ml`
2. **Consistent formatting**: Uses underscores, lowercase, `#` prefix
3. **Academic standards**: Follows common field naming conventions
4. **Balanced specificity**: Specific enough to be useful, general enough to apply broadly
5. **Preservation of distinctions**: Won't merge fundamentally different concepts

### Reviewing Results

After running tag consolidation:

1. **Review the mappings** to ensure they make sense
2. **Check updated articles** to verify tag quality
3. **Regenerate notes** if you want the new tags reflected in Obsidian
4. **Monitor tag usage** over time for further refinements

## Troubleshooting

### Common Issues

**No tags found in citation graph**
- Ensure you have processed articles with tag generation enabled
- Check that your analysis results include tag data

**Tag consolidation fails**
- Verify your OpenRouter API key is configured
- Check internet connectivity
- Review logs for specific error messages

**Unexpected tag mappings**
- The LLM makes decisions based on semantic similarity
- Review the reasoning provided in the output
- Consider the context of your specific research domain

**Performance with large collections**
- The process may take time for large article collections
- LLM calls are made for each article during re-tagging
- Consider running during off-peak hours

### Getting Help

If you encounter issues:

1. Check the logs for detailed error messages
2. Verify your configuration settings
3. Ensure all dependencies are properly installed
4. Review this documentation for usage guidelines

## Future Enhancements

Potential future improvements:

- **Manual tag management**: Interface for reviewing and editing tag mappings
- **Tag hierarchies**: Support for hierarchical tag structures
- **Batch processing**: Optimize for very large collections
- **Export/import**: Share tag vocabularies across installations
- **Tag analytics**: Insights into tag usage patterns

## File Structure

The tag consolidation system adds these new files:

```
project-thoth/
├── src/thoth/analyze/
│   └── tag_consolidator.py          # Main consolidation logic
├── src/thoth/utilities/
│   └── models.py                    # Added TagConsolidationResponse, TagSuggestionResponse
├── templates/prompts/
│   ├── consolidate_tags.j2          # Tag consolidation prompt
│   └── suggest_additional_tags.j2   # Tag suggestion prompt
└── TAG_CONSOLIDATION_README.md      # This documentation
```

## API Reference

### TagConsolidator Class

**Methods:**
- `extract_all_tags_from_graph(citation_tracker)`: Extract unique tags from graph
- `consolidate_tags(existing_tags)`: Create tag consolidation mappings
- `suggest_additional_tags(title, abstract, current_tags, available_tags)`: Suggest relevant tags
- `consolidate_and_retag_all_articles(citation_tracker)`: Complete consolidation process

### Pipeline Integration

**ThothPipeline Methods:**
- `consolidate_and_retag_all_articles()`: Run complete tag consolidation

**CLI Commands:**
- `python -m thoth.main consolidate-tags`: Run tag consolidation from command line

---

This tag consolidation system provides a powerful way to maintain organized, consistent, and comprehensive tagging across your academic article collection, making it easier to discover and organize related research.
