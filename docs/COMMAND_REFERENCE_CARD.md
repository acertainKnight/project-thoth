# 📋 Thoth Command Reference Card

**Quick reference for the most commonly used Thoth commands**

---

## 🚀 **Essential Commands**

### **PDF Processing**
```bash
# Process single PDF
thoth process --pdf-path /path/to/paper.pdf

# Monitor folder for new PDFs
thoth monitor --watch-dir /path/to/pdfs --api-server

# Regenerate specific note
thoth reprocess-note --article-id "10.1234/doi"

# Regenerate all notes
thoth regenerate-all-notes
```

### **API Server**
```bash
# Start API server
thoth api --host 127.0.0.1 --port 8000

# Development server (auto-reload)
thoth api --reload
```

### **Research Agent**
```bash
# Start interactive agent
thoth agent
```

---

## 🔍 **Discovery Commands**

### **Source Management**
```bash
# List all sources
thoth discovery list

# Create ArXiv source
thoth discovery create --name "ml_papers" --type api --config-file arxiv_config.json

# Run discovery
thoth discovery run --source "ml_papers" --max-articles 50

# Delete source
thoth discovery delete --name "old_source" --confirm
```

### **Scheduler**
```bash
# Start scheduler
thoth discovery scheduler start

# Check status
thoth discovery scheduler status
```

---

## 🧠 **Knowledge Base (RAG)**

### **Index Management**
```bash
# Index all documents
thoth rag index

# Clear index
thoth rag clear --confirm

# Show statistics
thoth rag stats
```

### **Search & Query**
```bash
# Search knowledge base
thoth rag search --query "transformer architecture" --k 5

# Ask questions
thoth rag ask --question "What are the main contributions?" --k 4

# Filter by type
thoth rag search --query "attention" --filter-type note
```

---

## 🏷️ **Tag Management**

```bash
# Full tag consolidation + suggestion
thoth consolidate-tags

# Only consolidate existing tags
thoth consolidate-tags-only

# Only suggest new tags
thoth suggest-tags
```

---

## 🔧 **Configuration Examples**

### **Basic .env Setup**
```bash
# Required (minimum)
API_OPENROUTER_KEY="your-openrouter-key"

# Optional (recommended)
API_MISTRAL_KEY="your-mistral-key"
LLM_MODEL="openai/gpt-4o-mini"
PDF_DIR="data/pdf"
NOTES_DIR="data/notes"
```

### **Agent Conversation Examples**
```
# Create discovery source
You: Create an ArXiv source for machine learning papers
Agent: ✅ ArXiv Discovery Source Created Successfully!

# Search knowledge
You: What papers do I have on transformers?
Agent: 🔍 I found 12 papers on transformers...

# Run discovery
You: Find new papers on attention mechanisms
Agent: 🔍 Searching ArXiv for attention mechanisms...
```

---

## 🚨 **Quick Troubleshooting**

### **Common Issues**
```bash
# Command not found
uv run python -m thoth --help

# Check API key
cat .env | grep API_OPENROUTER_KEY

# Debug mode
LOG_LEVEL=DEBUG thoth process --pdf-path paper.pdf

# Check logs
tail -f logs/thoth.log
```

### **Test Commands**
```bash
# Test configuration
thoth filter-test --create-sample-queries

# Test API connectivity
curl http://localhost:8000/health

# Test agent tools
thoth rag stats
```

---

## 📁 **File Structure**

```
project-thoth/
├── data/
│   ├── pdf/              # Original PDFs
│   ├── notes/            # Generated notes
│   ├── discovery/        # Discovery configs
│   └── knowledge/        # Citation graph
├── logs/                 # System logs
└── .env                  # Configuration
```

---

## 🔗 **Quick Links**

- **[Full Documentation](README.md)** - Complete documentation index
- **[Installation Guide](INSTALLATION_GUIDE.md)** - Setup instructions
- **[Configuration Guide](CONFIGURATION_GUIDE.md)** - All configuration options
- **[Troubleshooting](OBSIDIAN_TROUBLESHOOTING.md)** - Common issues & solutions

---

## 💡 **Pro Tips**

1. **Start with agent**: Use `thoth agent` for guided setup
2. **Use aliases**: Create shell aliases for common commands
3. **Monitor logs**: Keep `tail -f logs/thoth.log` running
4. **API server**: Always run with `--api-server` for Obsidian integration
5. **Regular indexing**: Run `thoth rag index` after processing new papers

---

**📌 Pin this reference card for quick access to Thoth commands!**
