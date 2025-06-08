# 🚀 Thoth Quick Start - Choose Your Path

## 🎯 **Which Path is Right for You?**

### **📚 Just Want to Process PDFs?** → [PDF Processing Path](#pdf-processing-path)
*Perfect for researchers who want to convert PDFs to structured notes*

### **🔍 Want to Discover New Papers?** → [Research Discovery Path](#research-discovery-path)
*Ideal for staying up-to-date with latest research in your field*

### **💬 Want an AI Research Assistant?** → [AI Agent Path](#ai-agent-path)
*Best for interactive research and knowledge exploration*

### **🔧 Want to Integrate with Obsidian?** → [Obsidian Integration Path](#obsidian-integration-path)
*Perfect for Obsidian users wanting seamless research workflows*

---

## 📚 **PDF Processing Path** *(5 minutes)*

**Goal**: Convert research PDFs into structured Obsidian notes

```bash
# 1. Quick install
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth && uv sync

# 2. Minimal configuration
cp .env.example .env
echo "API_OPENROUTER_KEY=your-key-here" >> .env  # Get from openrouter.ai

# 3. Process your first PDF
uv run python -m thoth process --pdf-path /path/to/your/paper.pdf

# 4. Start monitoring folder
uv run python -m thoth monitor --watch-dir /path/to/your/pdfs
```

**✅ You're Done!** PDFs dropped in the folder will be automatically processed.

---

## 🔍 **Research Discovery Path** *(10 minutes)*

**Goal**: Automatically discover and filter relevant papers from ArXiv/PubMed

```bash
# 1. Complete the PDF Processing Path above, then:

# 2. Start the research agent
uv run python -m thoth agent

# 3. Create a discovery source
Agent> Create an ArXiv source for machine learning papers
Agent> ✅ ArXiv Discovery Source Created Successfully!

# 4. Run discovery
Agent> Run discovery to find new papers
Agent> 🔍 Found 15 relevant papers, downloading 8 after filtering...

# 5. Schedule automatic discovery
Agent> Schedule discovery to run daily at 9 AM
Agent> ⏰ Scheduled daily discovery for 09:00
```

**✅ You're Done!** New relevant papers will be discovered automatically.

---

## 💬 **AI Agent Path** *(3 minutes)*

**Goal**: Chat with your research collection and get intelligent insights

```bash
# 1. Complete the PDF Processing Path above, then:

# 2. Index your knowledge base
uv run python -m thoth rag index

# 3. Start the agent
uv run python -m thoth agent

# 4. Start chatting!
You: What papers do I have on transformer architectures?
Agent: 🔍 I found 12 papers on transformers in your collection...

You: What are the main innovations in attention mechanisms?
Agent: Based on your papers, the key innovations are...

You: Find papers related to "GPT" published after 2020
Agent: 📚 Here are 8 GPT-related papers from 2020 onwards...
```

**✅ You're Done!** You have an AI research assistant for your papers.

---

## 🔧 **Obsidian Integration Path** *(7 minutes)*

**Goal**: Seamless integration with your Obsidian vault

```bash
# 1. Complete the PDF Processing Path above, then:

# 2. Start the API server
uv run python -m thoth api

# 3. Install Obsidian plugin
# Download thoth-obsidian.zip from releases
# Extract to YourVault/.obsidian/plugins/thoth-obsidian/
# Enable in Obsidian Settings > Community Plugins

# 4. Configure plugin
# In Obsidian: Settings > Thoth > Set API URL to http://localhost:8000
# Test connection
```

**✅ You're Done!** Chat with your research directly in Obsidian.

---

## 🎯 **Next Steps by Path**

### **After PDF Processing**
- ✅ [Monitor Additional Folders](INSTALLATION_GUIDE.md#monitoring-setup)
- ✅ [Customize Note Templates](CONFIGURATION_GUIDE.md#note-templates)
- ✅ [Set Up Citation Tracking](COMPLETE_FEATURE_REFERENCE.md#citation-service)

### **After Research Discovery**
- ✅ [Add PubMed Sources](DISCOVERY_SYSTEM_README.md#pubmed-sources)
- ✅ [Configure Custom Filters](DISCOVERY_SYSTEM_README.md#filtering)
- ✅ [Set Up Web Scraping](DISCOVERY_SYSTEM_README.md#web-scraping)

### **After AI Agent**
- ✅ [Customize Agent Tools](DEVELOPMENT_GUIDE.md#adding-agent-tools)
- ✅ [Set Up Advanced RAG](COMPLETE_FEATURE_REFERENCE.md#rag-features)
- ✅ [Configure Tag Management](TAG_CONSOLIDATION_README.md)

### **After Obsidian Integration**
- ✅ [Remote Access Setup](OBSIDIAN_WSL_SETUP.md)
- ✅ [Docker Deployment](OBSIDIAN_DOCKER_SETUP.md)
- ✅ [Advanced Plugin Features](OBSIDIAN_USAGE_GUIDE.md)

---

## 🚨 **Common Issues & Solutions**

### **"Command not found: thoth"**
```bash
# Use full path instead
uv run python -m thoth --help
```

### **"API key error"**
```bash
# Check your .env file
cat .env | grep API_OPENROUTER_KEY
# Get key from: https://openrouter.ai/keys
```

### **"PDF processing failed"**
```bash
# Check logs
tail -f logs/thoth.log
# Most common: large PDF files need Mistral API key
```

### **"Agent not responding"**
```bash
# Restart with debug
LOG_LEVEL=DEBUG uv run python -m thoth agent
```

---

## 📞 **Need Help?**

- 📖 **Full Documentation**: [docs/README.md](README.md)
- 🐛 **Common Issues**: [TROUBLESHOOTING.md](OBSIDIAN_TROUBLESHOOTING.md)
- 💬 **Community**: [GitHub Issues](https://github.com/yourusername/project-thoth/issues)
- 📧 **Support**: Create an issue with logs and system info

---

## 🎉 **Success Metrics**

After following your chosen path, you should have:

- ✅ **PDF Processing**: Papers converted to structured notes
- ✅ **Discovery**: New papers found automatically
- ✅ **AI Agent**: Intelligent research assistant
- ✅ **Obsidian**: Seamless vault integration

**Time to Value**: 3-10 minutes depending on your path!
