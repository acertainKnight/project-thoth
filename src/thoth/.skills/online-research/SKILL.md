---
name: Online Research & PDF Discovery
description: Discover and download academic PDFs using DOIs, arXiv IDs, or paper titles. Downloaded PDFs are automatically processed by the PDF monitor service.
tools:
  - download_pdf
  - locate_pdf
---

# Online Research & PDF Discovery

Discover and download academic PDFs from various sources using DOIs, arXiv IDs, or paper titles.

## Core Capabilities

This skill enables you to:
- **Locate PDFs** from DOIs, arXiv IDs, or paper titles
- **Download PDFs** directly to the vault (auto-processed by monitor service)

**Note**: For web search, use Letta's built-in `web_search` tool instead of Thoth's deprecated web search. Downloaded PDFs are automatically processed by the PDF monitor service - no manual processing needed.

## Reading External Content

For reading web articles, blog posts, and documentation **outside** your knowledge base:

| Tool | Use For |
|------|---------|
| Letta's `fetch_webpage` | Read external web content (blogs, docs, articles) |
| `read_full_article` | Read papers in your knowledge base |
| `download_pdf` | Save papers for later processing |

**Iterative Learning with External Sources**:
1. Use `web_search` to find relevant web content
2. Use `fetch_webpage` to read articles fully
3. Learn from the content, identify knowledge gaps
4. Keep reading more sources until you understand the topic
5. For academic papers, use `download_pdf` to add them to your knowledge base

## Tools Overview

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `locate_pdf` | Find PDF URLs from identifiers | Have DOI/arXiv ID, need download link |
| `download_pdf` | Download PDF to vault | Found a paper URL, want to save it |

## When to Use This Skill

Use online research when user asks for:
- "Download this paper from arXiv"
- "Get the PDF for DOI: 10.xxxx/xxxxx"
- "Find and download this paper"
- "Add this paper to my knowledge base"

**For web search**: Use Letta's built-in `web_search` tool to find papers online. Then use this skill to download them.

**Don't use** when:
- User asks about papers already in knowledge base (use `knowledge-base-qa` or `deep-research` skills)
- Simple citation lookup (use citation tools)

## Standard Research Workflow

### 1. Discover Papers Online (Use Letta web_search)

Use Letta's built-in `web_search` tool to find papers:
- Add year filters: "reinforcement learning 2024 2025"
- Use specific venues: "NeurIPS 2024 attention mechanisms"
- Include file type: "transformers architecture filetype:pdf"
- Target preprint servers: "site:arxiv.org memory augmented"

### 2. Locate PDF Sources

```
# If you have a DOI
locate_pdf(
  doi="10.1145/3534678.3539147",
  title="[Paper Title]"
)

# If you have an arXiv ID
locate_pdf(
  arxiv_id="2401.12345",
  title="[Paper Title]"
)

# If you only have a title
locate_pdf(
  title="Attention Is All You Need"
)
```

**Returns:**
- Direct PDF URL
- Source (arXiv, ACM, IEEE, DOI resolver, etc.)
- Accessibility status
- Alternative links if primary fails

### 3. Validate Before Downloading

```
# For multiple papers, validate sources first
validate_pdf_sources(
  sources=[
    {"url": "https://arxiv.org/pdf/2401.12345.pdf"},
    {"doi": "10.xxxx/xxxxx"},
    {"arxiv_id": "2402.56789"}
  ]
)
```

**Validation checks:**
- URL accessibility
- Content-Type verification
- File size reasonableness
- Redirect handling

### 4. Download PDFs

```
# Download single PDF
download_pdf(
  source="https://arxiv.org/pdf/2401.12345.pdf"
)

# Or use DOI
download_pdf(
  source="10.1145/3534678.3539147"
)

# Or use arXiv ID
download_pdf(
  source="2401.12345"
)

# Custom filename (optional)
download_pdf(
  source="https://example.com/paper.pdf",
  filename="My Custom Paper Name.pdf"
)
```

**Download features:**
- Auto-saves to configured vault PDF directory
- Auto-generates filenames from titles
- Supports direct URLs, DOIs, and arXiv IDs
- Progress tracking for large files
- Duplicate detection

### 5. Automatic Processing

Downloaded PDFs are automatically picked up by the PDF monitor service, which:
- Extracts text and metadata
- Generates embeddings
- Adds papers to the knowledge base
- Integrates with citation network
- Auto-generates tags

**No manual processing needed!** Just download the PDF and the monitor service handles the rest.

## Workflow Examples

### Example 1: Find and Download Papers

**User**: "Find and download the latest papers on memory-augmented transformers"

```
Step 1: Use Letta's web_search to find papers
web_search(query="memory-augmented transformers 2024 2025 arxiv")
→ Found papers with arXiv links

Step 2: Extract arXiv IDs or DOIs from results

Step 3: Download papers
For each paper:
  download_pdf(source="2401.12345")  # arXiv ID
→ Downloaded and auto-processed

Response: "Downloaded 5 papers on memory-augmented transformers.
They will be automatically processed and added to your knowledge base."
```

### Example 2: Download Specific Paper

**User**: "Download the paper 'Attention Is All You Need'"

```
Step 1: Locate the paper
locate_pdf(title="Attention Is All You Need")
→ Found: https://arxiv.org/pdf/1706.03762.pdf

Step 2: Download
download_pdf(source="https://arxiv.org/pdf/1706.03762.pdf")
→ Downloaded to: vault/thoth/papers/pdfs/Attention-Is-All-You-Need.pdf
→ Auto-processing will add it to knowledge base

Response: "Successfully downloaded 'Attention Is All You Need'.
The paper will be automatically processed and added to your knowledge base."
```

### Example 3: Download from DOI

**User**: "Get me the PDF for DOI: 10.1145/3534678.3539147"

```
Step 1: Download directly using DOI
download_pdf(source="10.1145/3534678.3539147")
→ Downloaded and auto-processed

Response: "Downloaded paper from DOI 10.1145/3534678.3539147.
The paper will be automatically processed and added to your knowledge base."
```

### Example 4: Research Topic Discovery

**User**: "What's the latest research on efficient attention mechanisms? Download the top 5 papers."

```
Step 1: Use Letta's web_search
web_search(query="efficient attention mechanisms 2024 2025 arxiv")
→ Found papers with arXiv links

Step 2: Extract arXiv IDs from results

Step 3: Download top 5 papers
For each arXiv ID:
  download_pdf(source="[arxiv_id]")
→ All downloaded and auto-processed

Response: "Downloaded 5 papers on efficient attention mechanisms.
All papers will be automatically processed and added to your knowledge base."
```

## Advanced Techniques

### Smart Filename Generation

```
# The download_pdf tool auto-generates filenames from:
# 1. Article title (if found in metadata)
# 2. URL path (if title unavailable)
# 3. Hash-based unique name (as fallback)

# You can override with custom filename:
download_pdf(
  source="https://arxiv.org/pdf/2401.12345.pdf",
  filename="MyResearch_ReinforcementLearning_2024.pdf"
)
```

### Error Handling

```
# If direct download fails, try locating the PDF first
# Attempt primary source
pdf = locate_pdf(doi="10.xxxx/xxxxx")
download_pdf(source=pdf.url)
# If locate fails, try Letta's web_search to find alternative URLs
```

## Source Priority

When locating PDFs, the system tries sources in this order:

1. **arXiv** - Fast, reliable, open access
2. **DOI resolver** - Authoritative, may require access
3. **Semantic Scholar** - Good metadata, open access tracking
4. **PubMed Central** - Life sciences, open access
5. **ACM/IEEE** - Conference papers (may require access)

## Best Practices

### Download Strategy
1. **Handle errors**: Not all papers are openly accessible
2. **Respect limits**: Don't overwhelm servers with requests
3. **Check duplicates**: Tool detects existing files automatically
4. **Use arXiv/DOI when available**: Most reliable sources

### Search Strategy (using Letta web_search)
1. **Be specific**: Include domain terms, years, venues
2. **Use filters**: Add "filetype:pdf" or "site:arxiv.org"
3. **Iterate**: Refine search based on initial results

## Common Pitfalls

### ❌ Don't:
- Search for papers already in knowledge base (use existing tools)
- Use overly broad search queries
- Download papers without checking for duplicates

### ✅ Do:
- Check knowledge base first with `search_articles`
- Use specific, targeted search queries with Letta web_search
- Let the download tool handle duplicate detection
- Trust the PDF monitor service for processing

## Integration with Other Skills

### Online Research → Deep Research
```
1. Use Letta web_search to find papers
2. Use download_pdf to save them
3. Wait for auto-processing
4. Use read_full_article to deeply read the papers
5. Keep reading related papers to fill knowledge gaps
6. Use deep-research tools to analyze and synthesize
```

### Online Research → Knowledge Base
```
1. web_search (Letta) → find papers
2. download_pdf → save to vault
3. (auto-processing by monitor service)
4. read_full_article → deeply read the processed papers
5. Now accessible via all knowledge base tools
```

### Learning from External Web Content
```
1. web_search (Letta) → find web articles, blogs, documentation
2. fetch_webpage (Letta) → read the full content
3. Learn from the article, take notes
4. Identify gaps in understanding
5. Keep reading more sources until you understand
```

## Quick Reference

### Fastest Path: arXiv Paper
```
download_pdf(source="2401.12345")  # Just the arXiv ID
→ Auto-processed by monitor service
```

### Fastest Path: DOI
```
download_pdf(source="10.1145/xxxxx")
→ Auto-processed by monitor service
```

### Fastest Path: Direct URL
```
download_pdf(source="https://arxiv.org/pdf/2401.12345.pdf")
→ Auto-processed by monitor service
```

### Discovery Workflow
```
web_search (Letta) → locate_pdf → download_pdf → (auto-processing)
```

## Summary

This skill empowers you to:
1. **Locate** PDFs from DOIs, arXiv IDs, or titles
2. **Download** papers directly to the vault
3. **Auto-process** via the PDF monitor service

Use this skill as the **first step** in any research workflow that requires accessing papers not yet in the knowledge base. Once papers are downloaded and processed, switch to `deep-research` or `knowledge-base-qa` skills for analysis.
