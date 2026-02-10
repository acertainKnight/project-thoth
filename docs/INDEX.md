# Thoth Documentation Index

Complete guide to Thoth's documentation organized by category.

## 🚀 Getting Started

| Document | Description | For Who |
|----------|-------------|---------|
| [README](../README.md) | Project overview, quick start, features | Everyone |
| [Setup Guide](setup.md) | Installation and initial configuration | New users |
| [Quick Reference](quick-reference.md) | Command cheat sheet | Everyone |
| [Usage Guide](usage.md) | Day-to-day usage patterns | Daily users |

## 🏗️ Architecture

| Document | Description | For Who |
|----------|-------------|---------|
| [Architecture](architecture.md) | System overview, all components | Developers, contributors |
| [Design Philosophy](design-philosophy.md) | Core principles, design decisions | Architects, decision makers |
| [MCP Architecture](mcp-architecture.md) | MCP server and 64 tools | Tool developers |
| [Letta Architecture](letta-architecture.md) | Agent system and memory | Agent developers |
| [Skills System](skills-system.md) | Dynamic skill-loading system | Skill authors, power users |

## 🔧 Component Guides

| Document | Description | For Who |
|----------|-------------|---------|
| [Discovery System](discovery-system.md) | Multi-source paper discovery | Source plugin developers |
| [Document Pipeline](document-pipeline.md) | PDF processing and extraction | Pipeline customizers |
| [RAG System](rag-system.md) | Hybrid search, reranking, and retrieval | RAG administrators |
| [Customizable Analysis Schemas](customizable-analysis-schemas.md) | Extraction schema customization | Advanced users |

## ⚙️ Setup & Configuration

| Document | Description | For Who |
|----------|-------------|---------|
| [Letta Setup](letta-setup.md) | Self-hosted Letta configuration | Self-hosters |
| [Letta Cloud Setup](letta-cloud-setup.md) | Cloud Letta configuration | Cloud users |
| [Docker Deployment](docker-deployment.md) | Container deployment guide | DevOps, admins |
| [MCP Configuration](mcp-configuration.md) | Advanced MCP setup | Power users |
| [Mobile Usage](mobile-usage.md) | Using Thoth on mobile devices | Mobile users |

## 🧪 Testing & Quality

| Document | Description | For Who |
|----------|-------------|---------|
| [Testing Strategy](testing-strategy.md) | Testing approach and standards | Developers, QA |

## 🛠️ Advanced Topics

| Document | Description | For Who |
|----------|-------------|---------|
| [Letta Volumes](letta-volumes.md) | Letta data persistence details | Admins, backup |

---

## Documentation by User Journey

### New User Journey
1. Read [README](../README.md) - Understand what Thoth is
2. Follow [Setup Guide](setup.md) - Install and configure
3. Read [Usage Guide](usage.md) - Learn daily workflows
4. Reference [Quick Reference](quick-reference.md) - Commands

### Developer Journey
1. Read [Architecture](architecture.md) - System overview
2. Read [Design Philosophy](design-philosophy.md) - Core principles
3. Read component docs:
   - [MCP Architecture](mcp-architecture.md) - Tool system
   - [Letta Architecture](letta-architecture.md) - Agent system
   - [Skills System](skills-system.md) - Dynamic loading
4. Set up development environment ([Setup Guide](setup.md#development-setup))

### Skill Author Journey
1. Read [Skills System](skills-system.md) - Complete skill guide
2. Read [Usage Guide](usage.md#agent-commands) - Agent usage
3. Reference [MCP Architecture](mcp-architecture.md) - Available tools
4. Create custom skills in vault

### Source Plugin Developer Journey
1. Read [Discovery System](discovery-system.md) - Plugin architecture
2. Read [Architecture](architecture.md#discovery-engine) - Discovery engine
3. Implement plugin interface
4. Test with workflow builder

### Administrator Journey
1. Read [Docker Deployment](docker-deployment.md) - Container setup
2. Read [Letta Setup](letta-setup.md) - Memory system setup
3. Read [Letta Volumes](letta-volumes.md) - Data persistence
4. Configure production deployment

---

## Documentation Status

| Document | Status | Last Updated |
|----------|--------|--------------|
| README.md | ✅ Complete | Feb 2026 |
| setup.md | ✅ Complete | Feb 2026 |
| usage.md | ✅ Complete | Feb 2026 |
| quick-reference.md | ✅ Complete | Feb 2026 |
| architecture.md | ✅ Complete | Feb 2026 |
| design-philosophy.md | ✅ Complete | Feb 2026 |
| mcp-architecture.md | ✅ Complete | Feb 2026 |
| letta-architecture.md | ✅ Complete | Feb 2026 |
| skills-system.md | ✅ Complete | Feb 2026 |
| discovery-system.md | ✅ Complete | Jan 2026 |
| document-pipeline.md | ✅ Complete | Jan 2026 |
| rag-system.md | ✅ Complete | Feb 2026 |
| letta-setup.md | ✅ Complete | Jan 2026 |
| letta-cloud-setup.md | ✅ Complete | Jan 2026 |
| docker-deployment.md | ✅ Complete | Jan 2026 |
| testing-strategy.md | ✅ Complete | Jan 2026 |
| mcp-configuration.md | ✅ Complete | Jan 2026 |
| customizable-analysis-schemas.md | ✅ Complete | Jan 2026 |
| mobile-usage.md | ✅ Complete | Jan 2026 |
| letta-volumes.md | ✅ Complete | Jan 2026 |

---

## Contributing to Documentation

### Documentation Standards

1. **Clear structure**: Use consistent header hierarchy
2. **Code examples**: Include working examples
3. **Cross-references**: Link to related docs
4. **Date stamps**: Include "Last Updated" at bottom
5. **Table of contents**: For docs >200 lines

### Updating Documentation

1. Edit markdown file in `docs/`
2. Update "Last Updated" date
3. Update this index if adding new doc
4. Test all cross-references
5. Submit PR with doc changes

### Documentation Guidelines

- **Audience**: Write for your target audience (beginner, developer, admin)
- **Clarity**: Prefer simple language over jargon
- **Examples**: Include concrete examples
- **Completeness**: Cover happy path and edge cases
- **Maintenance**: Keep in sync with code changes

---

## Getting Help

- **Documentation Issues**: [GitHub Issues](https://github.com/acertainKnight/project-thoth/issues) with `documentation` label
- **Missing Docs**: Request in Issues with `documentation` + `enhancement` labels
- **Doc Errors**: Report in Issues with `documentation` + `bug` labels

---

**Documentation Index Version**: 1.0
**Last Updated**: February 2026
