# Thoth Research Assistant - Documentation

Welcome to the complete documentation for the Thoth Research Assistant system. This documentation covers all aspects of installation, configuration, usage, and development for the Thoth ecosystem.

## 📚 **Documentation Index**

### **🚀 Getting Started**

- **[Main README](../README.md)** - Project overview and quick start
- **[Installation Guide](INSTALLATION.md)** - Complete installation instructions
- **[Configuration Guide](CONFIGURATION.md)** - System configuration and setup

### **🔧 Core System**

- **[Modern Agent Framework](MODERN_AGENT_README.md)** - LangGraph-based agent architecture
- **[MCP Framework](MCP_FRAMEWORK_README.md)** - Model Context Protocol implementation
- **[Research Assistant](RESEARCH_ASSISTANT_README.md)** - Core research assistant functionality
- **[Research Assistant Integration](RESEARCH_ASSISTANT_INTEGRATION.md)** - Pipeline integration guide

### **🔍 Discovery & Analysis**

- **[Discovery System](DISCOVERY_SYSTEM_README.md)** - Automated article discovery
- **[Scrape Filter Integration](SCRAPE_FILTER_INTEGRATION.md)** - Article filtering system
- **[Tag Consolidation](TAG_CONSOLIDATION_README.md)** - Tag management and consolidation

### **🎯 Obsidian Integration**

- **[Obsidian Plugin](OBSIDIAN_PLUGIN_README.md)** - Plugin overview and installation
- **[Usage Guide](OBSIDIAN_USAGE_GUIDE.md)** - Complete usage instructions
- **[WSL Setup](OBSIDIAN_WSL_SETUP.md)** - Windows Subsystem for Linux configuration
- **[Docker Setup](OBSIDIAN_DOCKER_SETUP.md)** - Containerized deployment
- **[Troubleshooting](OBSIDIAN_TROUBLESHOOTING.md)** - Remote management and error solutions

### **🐳 Deployment**

- **[Docker Configuration](../docker-compose.yml)** - Container orchestration
- **[Production Deployment](../docker-compose.prod.yml)** - Production-ready setup
- **[Development Environment](../docker-compose.dev.yml)** - Development configuration

---

## 🎯 **Quick Navigation**

### **For New Users**
1. Start with [Obsidian Plugin README](OBSIDIAN_PLUGIN_README.md) for quick setup
2. Follow [Usage Guide](OBSIDIAN_USAGE_GUIDE.md) for step-by-step instructions
3. Check [WSL Setup](OBSIDIAN_WSL_SETUP.md) if using Windows + WSL

### **For Developers**
1. Review [Modern Agent Framework](MODERN_AGENT_README.md) for architecture
2. Study [MCP Framework](MCP_FRAMEWORK_README.md) for integration patterns
3. Explore [Discovery System](DISCOVERY_SYSTEM_README.md) for extensibility

### **For System Administrators**
1. Use [Docker Setup](OBSIDIAN_DOCKER_SETUP.md) for containerized deployment
2. Configure production with [docker-compose.prod.yml](../docker-compose.prod.yml)
3. Monitor with built-in health checks and logging

---

## 🏗️ **Architecture Overview**

Thoth is a modular research assistant system with the following components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Obsidian       │    │  FastAPI        │    │  LangGraph      │
│  Plugin         │◄──►│  Server         │◄──►│  Agent          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  User           │    │  HTTP API       │    │  Research       │
│  Interface      │    │  Layer          │    │  Tools          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Key Components**

1. **Obsidian Plugin** - User interface and Obsidian integration
2. **FastAPI Server** - HTTP API bridge between UI and agent
3. **LangGraph Agent** - AI-powered research assistant with tools
4. **Discovery System** - Automated paper discovery and filtering
5. **Knowledge Base** - RAG system for research query and analysis
6. **Tag System** - Intelligent tagging and organization

---

## 🛠️ **Development Workflow**

### **Setting Up Development Environment**

```bash
# Clone repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# Install dependencies
uv sync --dev

# Start development server
uv run python -m thoth api --reload

# Or use Docker for development
docker-compose -f docker-compose.dev.yml up -d
```

### **Testing**

```bash
# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/thoth

# Run specific test categories
uv run pytest tests/test_agent/
```

### **Documentation Updates**

When updating documentation:

1. Keep this index updated with new files
2. Follow the established naming conventions
3. Include cross-references between related docs
4. Update any relevant setup guides

---

## 📖 **Documentation Standards**

### **File Naming Convention**
- **System Components**: `COMPONENT_NAME_README.md`
- **Setup Guides**: `SETUP_TYPE_SETUP.md`
- **Integration Guides**: `INTEGRATION_TYPE_INTEGRATION.md`

### **Content Structure**
- Start with clear overview and purpose
- Include quick start sections
- Provide comprehensive examples
- Add troubleshooting sections
- Include cross-references to related docs

### **Cross-References**
- Link to related documentation
- Reference specific sections where helpful
- Maintain bidirectional links when relevant

---

## 🔗 **External Resources**

### **Dependencies**
- **[LangChain](https://python.langchain.com/)** - Agent framework
- **[LangGraph](https://langchain-ai.github.io/langgraph/)** - Graph-based agents
- **[FastAPI](https://fastapi.tiangolo.com/)** - API framework
- **[Obsidian](https://obsidian.md/)** - Knowledge management platform

### **API Services**
- **[Mistral AI](https://mistral.ai/)** - Language models
- **[OpenRouter](https://openrouter.ai/)** - Multi-model API access
- **[ArXiv API](https://arxiv.org/help/api/)** - Academic paper access
- **[PubMed API](https://www.ncbi.nlm.nih.gov/books/NBK25501/)** - Medical literature

---

## 🤝 **Contributing**

### **Documentation Contributions**
1. Follow the file naming conventions
2. Include comprehensive examples
3. Test all instructions before submitting
4. Update this index with new documentation

### **Code Contributions**
1. Follow established patterns in existing code
2. Include comprehensive tests
3. Update relevant documentation
4. Ensure Docker builds work

### **Bug Reports**
When reporting bugs:
1. Include system information
2. Provide reproduction steps
3. Reference relevant documentation
4. Include log outputs when applicable

---

## 📄 **License**

This documentation is part of the Thoth project and follows the same licensing terms as the main project.

---

**📝 Last Updated**: December 2024
**🔄 Update Frequency**: As needed for major changes
**📧 Contact**: Create an issue for documentation improvements
