---
name: external-knowledge
description: Manage external knowledge collections (textbooks, lecture notes, background material) and search them to support research. Use when user wants to upload reference material or query foundational knowledge.
tools:
- create_knowledge_collection
- list_knowledge_collections
- delete_knowledge_collection
- upload_external_knowledge
- search_external_knowledge
---

# External Knowledge Management

Manage collections of external reference material like textbooks, lecture notes, tutorials, and background documents. These supplement your research paper collection with foundational knowledge.

## What is External Knowledge?

External knowledge is any reference material that supports your research but isn't a research paper:
- Textbooks (RL textbooks, statistics books, ML theory)
- Lecture notes and course materials
- Technical documentation
- Tutorial articles and blog posts
- Background reading on methods and theory

This material is organized into **collections** by topic, making it easy to find relevant background information.

## Tools Available

| Tool | Purpose |
|------|---------|
| `create_knowledge_collection` | Create a new collection for organizing documents |
| `list_knowledge_collections` | Show all collections with document counts |
| `delete_knowledge_collection` | Remove a collection (optionally keep documents) |
| `upload_external_knowledge` | Upload a single file to a collection |
| `search_external_knowledge` | Search within external knowledge (all or specific collection) |

## Supported File Formats

The system converts these formats to markdown automatically:
- PDF (.pdf) - via Mistral OCR
- Markdown (.md) - pass-through
- Plain text (.txt) - wrapped with title
- HTML (.html, .htm) - converted via markdownify
- EPUB (.epub) - chapters extracted and converted
- DOCX (.docx) - converted via mammoth

## Creating Collections

Organize external knowledge by topic:

```
create_knowledge_collection(
  name="Reinforcement Learning Textbooks",
  description="Core RL textbooks including Sutton & Barto, Silver lectures"
)

create_knowledge_collection(
  name="Statistical Methods",
  description="Statistics and hypothesis testing background"
)
```

**Collection naming tips**:
- Use clear, descriptive names
- Group by subject area or course
- Keep it simple (avoid deeply nested hierarchies)

## Uploading Documents

Upload files from the user's vault:

```
upload_external_knowledge(
  file_path="/path/to/vault/references/sutton_barto_rl_book.pdf",
  collection_name="Reinforcement Learning Textbooks",
  title="Reinforcement Learning: An Introduction"
)
```

**Important**: The file path must be accessible from the vault. Ask the user for the full path if they mention a document.

For bulk uploads, recommend the CLI:
```bash
thoth knowledge upload /path/to/folder --collection "Collection Name" --recursive
```

## Searching External Knowledge

Search across all external knowledge or within a specific collection:

```
# Search all external knowledge
search_external_knowledge(
  query="policy gradient methods",
  max_results=5
)

# Search specific collection
search_external_knowledge(
  query="hypothesis testing procedures",
  collection_name="Statistical Methods",
  max_results=5
)
```

**When to search external knowledge**:
- User asks about foundational concepts not in papers
- You need background understanding before analyzing papers
- User references a textbook or course material
- Question requires theoretical foundation

## Integrating with Research Q&A

The standard Q&A tools now support scoping:

```
# Search everything (papers + external knowledge)
answer_research_question(
  question="What are policy gradient methods?",
  scope="all"
)

# Search only research papers
answer_research_question(
  question="Recent advances in policy gradients",
  scope="papers_only"
)

# Search only external knowledge
answer_research_question(
  question="Basic definition of policy gradients",
  scope="external"
)

# Search specific collection
answer_research_question(
  question="Policy gradients chapter content",
  scope="collection:Reinforcement Learning Textbooks"
)
```

## Workflow Examples

### Example 1: User Uploads Textbook

**User**: "I have the Sutton & Barto RL textbook. Can you add it to Thoth?"

```
1. list_knowledge_collections()
   → Check if "RL Textbooks" collection exists

2. If not: create_knowledge_collection(
     name="RL Textbooks",
     description="Core reinforcement learning textbooks"
   )

3. Ask user: "Please provide the full path to the textbook PDF in your vault"

4. upload_external_knowledge(
     file_path="[user's path]",
     collection_name="RL Textbooks",
     title="Reinforcement Learning: An Introduction"
   )

5. Confirm: "I've added the Sutton & Barto textbook. You can now ask me
   questions about RL theory and I'll reference both the textbook and
   your research papers."
```

### Example 2: Background Research

**User**: "What are actor-critic methods?"

```
1. search_external_knowledge(
     query="actor-critic methods definition",
     max_results=3
   )
   → Get textbook explanation

2. answer_research_question(
     question="actor-critic methods applications",
     scope="papers_only",
     max_sources=5
   )
   → Get recent research usage

3. Synthesize:
   "Actor-critic methods combine policy gradients with value functions
   [from textbook excerpt]. Recent applications include [paper findings]..."
```

### Example 3: Deep Learning with Background

**User**: "Explain the paper 'PPO Algorithm' in detail"

```
1. read_full_article(
     article_identifier="PPO Algorithm",
     agent_id="your_id"
   )
   → Load the research paper

2. search_external_knowledge(
     query="proximal policy optimization background trust region",
     collection_name="RL Textbooks"
   )
   → Get foundational context

3. Synthesize explanation using both sources:
   - Paper's novel contributions
   - Textbook's foundational concepts
   - How the paper builds on theory
```

## Managing Collections

### Listing Collections

```
list_knowledge_collections()
```

Shows all collections with document counts. Use this to:
- See what external knowledge is available
- Check collection names for upload
- Find collections before searching

### Deleting Collections

```
# Keep documents but remove collection
delete_knowledge_collection(
  collection_name="Old Collection"
)

# Delete collection and all documents
delete_knowledge_collection(
  collection_name="Outdated Material",
  delete_documents=true
)
```

**Warning**: Deleting documents also removes them from the RAG index. This is permanent.

## Best Practices

1. **Organize by topic**: Create collections for distinct subject areas
2. **Search before reading**: Use search to find relevant sections, then read full articles if needed
3. **Combine sources**: Reference both external knowledge and research papers in answers
4. **Ask for paths**: Users need to provide file paths from their vault
5. **Scope appropriately**: Use scope parameters to search the right knowledge source

## Common Patterns

### Pattern: Foundation First
When user asks about advanced research topic:
1. Search external knowledge for foundational concepts
2. Search research papers for cutting-edge findings
3. Explain progression from basics to state-of-art

### Pattern: Gap Filling
When research papers lack background:
1. Identify missing foundational knowledge
2. Search external collections for that background
3. Provide comprehensive answer with both sources

### Pattern: Verification
When unsure about basic concepts:
1. Search external knowledge to verify understanding
2. Use verified understanding to interpret research papers
3. Ensure accurate explanations

## Response Template with External Knowledge

```
## Answer: [Question]

[Direct answer with inline citations from both papers and external sources]

**From research papers**:
- [Author et al., Year]: [Finding from paper]

**From reference material**:
- [Textbook/Source name]: [Background concept or definition]

**How they connect**:
[Explain how the foundational knowledge relates to the research findings]

**Want more?**
- I can search for more background material
- I can find additional papers on this topic
- I can explain specific concepts in more depth
```
