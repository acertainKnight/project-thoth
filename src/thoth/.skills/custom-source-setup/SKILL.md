---
name: Custom Source Setup
description: Set up custom article sources from any website using LLM-powered auto-detection. Use when user asks to add a new source, scrape a website, create a workflow, or wants papers from a site not already supported.
tools:
  - analyze_source_url
  - refine_source_selectors
  - confirm_source_workflow
  - list_available_sources
---

# Custom Source Setup

Automatically configure new article sources from any website. The system uses an LLM to analyze page structure, detect article listings, and propose CSS selectors - no manual scraping configuration needed.

## When to Use This Skill

Load this skill when the user:
- Mentions a URL or website they want to get papers from
- Asks to "add a source" or "scrape a site"
- Wants papers from a journal/conference not in the built-in source list
- Says something like "Can you check Nature papers?" or "Get articles from this site"

## Tools to Use

| Tool | Purpose |
|------|---------|
| `list_available_sources` | Check which sources already exist |
| `analyze_source_url` | Auto-detect article structure on any URL |
| `refine_source_selectors` | Fix detection if results are wrong |
| `confirm_source_workflow` | Save as a permanent discovery source |

## Quick Setup Flow (3-5 min)

For adding a new source:

```
Step 1: Analyze the URL
analyze_source_url(url="https://example.com/papers")

Step 2: Review with user
- Show confidence score (HIGH/MEDIUM/LOW)
- Show number of articles found
- Show 2-3 sample articles (title, authors, URL)
- Ask: "Does this look correct?"

Step 3: Refine if needed (optional)
If user says something is wrong:
refine_source_selectors(
  url="https://example.com/papers",
  current_selectors={...from step 1...},
  user_feedback="The titles are in the abstract section, not the heading"
)

Step 4: Confirm and save
confirm_source_workflow(
  url="https://example.com/papers",
  name="example_papers",  # Use a clear, unique name
  article_container_selector="...",  # From analyze output
  selectors={...},  # From analyze output
  pagination_selector="...",  # If detected
  search_filters=[...],  # If detected
)
```

## Detailed Workflow

### 1. Detect Intent

Watch for these signals:
- User provides a URL: "Can you scrape https://www.nber.org/papers"
- User mentions a website: "I want papers from Nature"
- User asks about adding sources: "How do I add a custom source?"

**Response pattern**:
```
I can set up that website as a source. Let me analyze the page structure...
```

### 2. Analyze the URL

Call `analyze_source_url(url=...)` and parse the results. The tool returns:
- `page_type`: Conference proceedings, journal TOC, search results, etc.
- `confidence`: Score from 0.0-1.0
- `total_articles_found`: Number of article containers detected
- `selectors`: What fields can be extracted (title, authors, abstract, URL, PDF, DOI, etc.)
- `sample_articles`: 3 sample extractions for verification
- `search_filters`: Detected search inputs, date filters, sort dropdowns
- `pagination_selector`: If pagination exists

### 3. Present Results to User

Format a clear summary showing what was detected:

```markdown
## Analysis Results: [Domain]

**Confidence**: [🟢 HIGH / 🟡 MEDIUM / 🔴 LOW] ([score])
**Page Type**: [type]
**Articles Found**: [count]

**Can Extract**:
- Title ✓
- Authors ✓
- Abstract ✓
- URL ✓
- PDF Link ✓
- Publication Date ✓

**Search Filters Detected**: [count]
- Keyword search input: [yes/no]
- Date filter: [yes/no]

**Sample Articles**:
1. [title] by [authors]
2. [title] by [authors]
3. [title] by [authors]

Does this look correct? If not, describe what's wrong and I can refine it.
```

**Confidence Interpretation**:
- **HIGH (≥0.8)**: Very reliable, extracted all key fields correctly
- **MEDIUM (0.6-0.8)**: Good, may be missing some fields like abstracts or dates
- **LOW (<0.6)**: Uncertain, verify samples carefully or try a different page

### 4. Handle User Response

**If correct**: Proceed to Step 5 (confirm)

**If incorrect**: Ask the user to describe what's wrong:
- "The titles are cut off" → selectors are too narrow
- "These aren't articles, they're news posts" → wrong container selector
- "The authors are missing" → author selector needs adjustment
- "The URLs are broken" → relative URL resolution issue

Then call `refine_source_selectors()` with their feedback. The LLM will propose corrected selectors. Show the new results and ask again.

### 5. Confirm and Save

Once the user approves, ask for a name:
```
What should I call this source? (e.g., "nber_working_papers", "nature_neuroscience")
```

Then call `confirm_source_workflow()`:
```python
confirm_source_workflow(
  url="https://...",
  name="[user_provided_name]",
  description="Auto-detected source for [domain]",
  article_container_selector="...",  # From analyze
  selectors={...},  # From analyze
  pagination_selector="...",  # From analyze
  search_filters=[...],  # From analyze
  max_articles_per_run=100,
)
```

### 6. Explain Next Steps

After confirmation, explain to the user:
```markdown
✓ Source "[name]" has been added!

**What this means**:
- When you run discovery for a research question, your keywords will be typed into the search box on this site (if detected)
- The system will extract articles from the listing, follow pagination, and stop when it hits papers it already found
- Articles from this source are automatically deduplicated with other sources

**To use this source**:
Add it to a research question's `selected_sources` list, or use `["*"]` to query all sources including this one.
```

## Error Handling

| Issue | Solution |
|-------|----------|
| Confidence < 0.5 | Suggest trying a different page (e.g., search results vs main listing) |
| 0 articles found | Page may not have article listings; verify URL |
| Only title detected | Acceptable for basic sources; abstract/authors may be on detail pages |
| LLM analysis failed | Fallback heuristics are used; results may be less accurate |
| User feedback doesn't help | Ask user to describe the HTML structure or provide example article manually |

## Example Conversations

### Example 1: Simple Success Case

**User**: "Can you get papers from NBER working papers?"

**Agent**:
```
I'll set up NBER as a source. Let me analyze their papers page...

[calls analyze_source_url("https://www.nber.org/papers")]

## Analysis Results: NBER Working Papers

**Confidence**: 🟢 HIGH (1.00)
**Page Type**: article_listing
**Articles Found**: 34

**Can Extract**:
- Title ✓
- Authors ✓
- Abstract ✓
- URL ✓
- Publication Date ✓

**Search Filters Detected**: 2
- Keyword search input: Yes
- Sort dropdown: Yes

**Sample Articles**:
1. "Creating High-Opportunity Neighborhoods: Evidence from the HOPE VI Program" by Raj Chetty, Rebecca Diamond, et al.
2. "Is the Environmental Exposure Gap Shrinking?" by Glenn Sheriff, Danae Hernandez-Cortes, et al.

Does this look correct?
```

**User**: "Yes that looks perfect"

**Agent**:
```
Great! What should I call this source? (e.g., "nber_working_papers")
```

**User**: "nber_working_papers"

**Agent**:
```
[calls confirm_source_workflow(...)]

✓ Source "nber_working_papers" has been added!

This source is now active and will be included when you run discovery with selected_sources=["*"] or when you explicitly add "nber_working_papers" to your research question's source list. Your keywords will be typed into the search box, and the system will extract articles across multiple pages until it hits papers it already found.
```

### Example 2: Refinement Needed

**User**: "Add papers from https://jmlr.org/papers/"

**Agent**:
```
[calls analyze_source_url("https://jmlr.org/papers/")]

## Analysis Results: JMLR

**Confidence**: 🟡 MEDIUM (0.65)
**Articles Found**: 124

**Sample Articles**:
1. "Volume 25" by Unknown
2. "Papers" by Unknown
3. "Proceedings" by Unknown

This confidence is medium. The titles look like volume/section headers instead of actual paper titles. This might not be the right page - could you try a specific volume page instead?
```

**User**: "Try https://jmlr.org/papers/v25/"

**Agent**: [repeats analysis on better URL with correct results]

### Example 3: User Feedback Refinement

**User**: "The authors field is empty on these samples"

**Agent**:
```
Let me refine the author selector...

[calls refine_source_selectors(
  url="...",
  current_selectors={...},
  user_feedback="The authors field is empty, please find the correct author elements"
)]

## Refined Results

**Articles Found**: 87
**Confidence**: 🟢 HIGH (0.90)

**Sample Articles**:
1. "Paper Title" by John Smith, Jane Doe
2. "Another Paper" by Alice Johnson, Bob Wilson

Is this better?
```

## Best Practices

1. **Always check existing sources first**: Call `list_available_sources()` before setting up a new one to avoid duplicates
2. **Use specific listing pages**: Conference proceedings pages, journal table of contents, or search result pages work best
3. **Verify samples carefully**: The 2-3 sample articles show what will be extracted - make sure they're actual papers, not navigation elements
4. **Good naming**: Use lowercase with underscores (e.g., `acm_dl`, `ieee_xplore`, `plos_one`)
5. **Note authentication**: If the site requires login, set `requires_authentication=true` (authentication setup is separate)

## Limitations

- Works best on article listing pages (not single article detail pages)
- Cannot handle sites that require JavaScript interaction beyond search forms
- Cannot solve CAPTCHAs or complex authentication flows
- Some sites may block automated access (respect robots.txt)
- For sites with unusual structures, manual configuration may be needed

## Response Template

After successful setup:

```
✓ Custom source "[name]" is now active!

**Source Details**:
- Domain: [domain]
- Fields extracted: [title, authors, abstract, etc.]
- Search support: [Yes/No]
- Pagination: [Yes/No]

**Usage**:
When you create or update a research question, add `"[name]"` to the `selected_sources` list. The system will:
1. Type your research keywords into the site's search box (if detected)
2. Extract articles across multiple pages
3. Stop when it encounters papers already in your collection
4. Deduplicate with articles from other sources

Want to test it? Create a research question with this source, or add it to an existing one!
```
