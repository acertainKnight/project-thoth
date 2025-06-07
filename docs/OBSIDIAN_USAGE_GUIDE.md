# Thoth Obsidian Plugin - Complete Usage Guide

## 🎯 **How It Works: Complete Architecture**

The Thoth Obsidian plugin creates a seamless bridge between Obsidian and the powerful Thoth research system:

```
Obsidian Plugin → FastAPI Server → LangGraph Agent → Research Tools
      ↓              ↓               ↓              ↓
   UI Controls  ← HTTP API   ← Agent Core   ← Tool Execution
```

### **🔧 System Components**

1. **Obsidian Plugin** - Your control center in Obsidian
2. **FastAPI Server** - HTTP bridge (`thoth api`)
3. **LangGraph Agent** - AI research assistant with 20+ tools
4. **Tool Ecosystem** - Discovery, RAG, queries, analysis, etc.

## 🚀 **Getting Started**

### **1. Prerequisites (CRITICAL!)**

Before using the plugin, ensure you have:

1. **Thoth Installed**:
   ```bash
   # Test that thoth is available
   uv run python -m thoth --help
   ```

2. **API Keys Configured**:
   - At minimum: **OpenRouter API Key**
   - **Mistral API Key** is optional for remote OCR

3. **Directory Structure**:
   - Set correct workspace directory (where project-thoth is located)
   - Set correct Obsidian directory (your vault location)

### **2. First Time Setup**

1. **Configure Plugin**: Go to Settings → Community Plugins → Thoth Research Assistant
2. **Set API Keys**: Enter your OpenRouter API key (Mistral key optional)
3. **Set Directories**:
   - **Workspace Directory**: `/home/nick/python/project-thoth`
   - **Obsidian Directory**: `/path/to/your/obsidian/vault/thoth`
4. **Test Agent**: Click status bar or use "Start Thoth Agent" command

### **3. Essential Configuration**

Go to **Settings → Community plugins → Thoth Research Assistant**:

#### **🔑 API Keys (Required)**
 - **Mistral API Key** (optional): For remote OCR
 - **OpenRouter API Key**: For AI research capabilities

#### **📁 Directory Settings (Critical)**
- **Workspace Directory**: `/home/nick/python/project-thoth` (where you cloned the repo)
- **Obsidian Directory**: `/path/to/your/obsidian/vault/thoth` (your notes folder)

#### **🌐 Connection Settings**
- **Host**: `127.0.0.1` (default - change if port is busy)
- **Port**: `8000` (default)
- **Base URL**: `http://127.0.0.1:8000`

## 🔧 **Starting the Agent - Step by Step**

### **Method 1: From Obsidian (Recommended)**

1. **Check Status Bar**: Look for "Thoth: Stopped" at bottom of Obsidian
2. **Click Status Bar**: Should show "Starting Thoth agent... This may take a moment."
3. **Wait for Startup**: Takes 10-30 seconds for full initialization
4. **Success**: Status bar shows "Thoth: Running" in green

### **Method 2: Manual CLI (For Troubleshooting)**

1. **Open Terminal** in your workspace directory
2. **Start Manually**:
   ```bash
   cd /home/nick/python/project-thoth
   uv run python -m thoth api --host 127.0.0.1 --port 8000
   ```
3. **Leave Running**: Keep terminal open
4. **Use Plugin**: Now plugin can connect to running server

### **Method 3: Remote Mode (WSL/Docker/Remote Server)**

If Thoth runs on a different machine or in WSL:

1. **Enable Remote Mode** in plugin settings
2. **Set Remote URL**: e.g., `http://localhost:8000` (for WSL)
3. **Start Server**: On the remote machine with `--host 0.0.0.0`
4. **Connect**: Click status bar to connect

📖 **[WSL Setup Guide](OBSIDIAN_WSL_SETUP.md)** - Complete guide for WSL + Windows setup

### **Status Indicators Explained**

- **🟢 "Thoth: Running"**: Everything working perfectly
- **🟡 "Thoth: Checking..."**: Plugin testing connection
- **🔴 "Thoth: Stopped"**: Agent not running - click to start
- **🟠 "Thoth: Error"**: Process running but API not responding

## 💬 **How to Chat with Your Research Agent**

### **Opening the Chat Interface**

1. **Command Palette**: Press `Ctrl+P` (or `Cmd+P` on Mac)
2. **Search**: Type "Open Research Chat"
3. **Enter**: Press Enter to open chat modal

### **Using the Chat Interface**

The chat modal provides a full conversational interface:

#### **Basic Chat Features**
- **Type messages** in the text area at bottom
- **Send messages** by pressing Enter (Shift+Enter for new lines)
- **View history** - conversations are saved between sessions
- **Copy responses** - click and drag to select text

#### **How to Ask Questions**

The agent understands natural language. Here are effective patterns:

**📚 Discovery & Sources**
```
You: Show me my discovery sources
You: Create an ArXiv source for machine learning papers
You: What sources are currently active?
```

**🔍 Research Questions**
```
You: What papers do I have on transformers?
You: Explain the connection between BERT and GPT
You: Search my knowledge base for attention mechanisms
```

**📊 Analysis & Stats**
```
You: What are the main themes in my research?
You: Show me statistics about my knowledge base
You: List my research queries
```

**🛠️ System Management**
```
You: What tools do you have available?
You: Index my knowledge base
You: Check system status
```

#### **Expected Response Time**
- **Simple queries**: 2-5 seconds
- **Complex research**: 10-30 seconds
- **Tool-heavy operations**: 30-60 seconds

### **Quick Research Workflow**

#### **Text Selection Research**
1. **Select text** in any Obsidian note
2. **Command Palette**: Press `Ctrl+P`
3. **Run**: "Insert Research Query"
4. **Wait**: Results appear directly in your note

#### **Example Output**
```markdown
## 🔍 Research: machine learning in healthcare
*Generated on 12/3/2024 8:30 PM by Thoth Research Assistant*

Based on your research collection, machine learning in healthcare
shows significant applications in:

1. **Diagnostic Imaging**: CNN models achieving 94% accuracy...
2. **Drug Discovery**: Transformer models predicting molecular...

**Key Papers:**
- [Deep Learning for Medical Image Analysis](paper1.md)
---
```

## 🐛 **Troubleshooting Guide**

### **Agent Won't Start**

#### **Check 1: Installation**
```bash
# Test if uv is installed
uv --version

# Test if thoth is available
uv run python -m thoth --help
```

#### **Check 2: API Keys**
- Go to plugin settings
- Verify Mistral API key is set (optional)
- Verify OpenRouter API key is set
- Test keys at their respective websites

#### **Check 3: Directory Configuration**
- Workspace Directory must point to where you cloned project-thoth
- Directory must exist and contain pyproject.toml file
- Check that uv can run from that directory

#### **Check 4: Port Conflicts**
```bash
# Check if port 8000 is in use
netstat -an | grep 8000

# Try different port in plugin settings
```

### **Common Error Messages**

#### **"uv command not found"**
**Solution**: Install uv package manager
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### **"API key error"**
**Solution**: Check API keys in plugin settings
- Visit [console.mistral.ai](https://console.mistral.ai) for a Mistral key (optional)
- Visit [openrouter.ai](https://openrouter.ai) for OpenRouter key

#### **"Address already in use"**
**Solution**: Change port number
1. Go to plugin settings
2. Change "Endpoint Port" from 8000 to 8001 (or 8002, etc.)
3. Restart agent

#### **"Permission denied"**
**Solution**: Check file permissions
```bash
chmod +x /path/to/project-thoth
cd /path/to/project-thoth
uv sync
```

### **Chat Not Working**

#### **Check Agent Status**
1. Look at status bar - should be green "Thoth: Running"
2. If red, click to start agent
3. If orange, restart agent from command palette

#### **Test API Connection**
1. Open browser to `http://127.0.0.1:8000/health`
2. Should see: `{"status":"healthy","service":"thoth-obsidian-api"}`
3. If not, agent isn't running properly

#### **Check Console Errors**
1. Press `Ctrl+Shift+I` (or `Cmd+Shift+I`)
2. Go to Console tab
3. Look for red error messages
4. Report errors if you can't resolve them

### **Research Results Empty**

#### **Knowledge Base Not Indexed**
```bash
# From terminal in workspace directory
uv run python -m thoth rag index
```

#### **No Papers Processed**
```bash
# Check RAG statistics
uv run python -m thoth rag stats
```

#### **No Research Queries**
Ask agent: "List my research queries" - create some if empty

## 📋 **Command Reference**

### **Available Commands in Obsidian**

Access via Command Palette (`Ctrl+P`):

#### **Agent Control**
- **Start Thoth Agent** - Launches the API server with agent
- **Stop Thoth Agent** - Gracefully shuts down
- **Restart Thoth Agent** - Stops and restarts

#### **Research Commands**
- **Open Research Chat** - Interactive AI assistant
- **Insert Research Query** - Research selected text

### **Agent Capabilities**

Your agent has access to 20+ research tools:

#### **📚 Discovery Management**
- `Create ArXiv Source` - Monitor ArXiv for papers
- `Create PubMed Source` - Monitor medical literature
- `Run Discovery` - Execute discovery searches
- `List Sources` - Show all configured sources

#### **🔍 Knowledge Base (RAG)**
- `Search Knowledge` - Find papers by topic
- `Ask Questions` - Query your research collection
- `Explain Connections` - Find relationships between papers
- `Index Knowledge` - Update search index

#### **📋 Query Management**
- `Create Query` - Define research interests
- `List Queries` - Show active queries
- `Edit Query` - Modify research criteria

## 💡 **Best Practices**

### **Daily Workflow**
1. **Start Obsidian**: Agent auto-starts if enabled
2. **Check Status**: Green status bar means ready
3. **Research While Writing**: Select text → Insert Research Query
4. **Use Chat**: For complex questions and system management

### **First Week Setup**
1. **Day 1**: Configure plugin, test basic functionality
2. **Day 2**: Set up 2-3 discovery sources
3. **Day 3**: Create 5-10 research queries
4. **Day 4**: Index existing knowledge base
5. **Day 5**: Practice chat workflows

### **Maintenance**
- **Weekly**: Restart agent for optimal performance
- **Monthly**: Re-index knowledge base after adding papers
- **As needed**: Update research queries as interests evolve

## 🆘 **Getting Help**

### **Debug Information**
When reporting issues, please provide:

1. **Plugin Console Logs**: `Ctrl+Shift+I` → Console tab
2. **Agent Logs**: Check `logs/thoth.log` in workspace
3. **API Status**: Test `http://127.0.0.1:8000/health`
4. **Configuration**: Settings values (remove API keys!)

### **Self-Help Checklist**
- [ ] Thoth installed and accessible via `uv run python -m thoth --help`
- [ ] API keys configured in plugin settings
- [ ] Workspace directory points to project-thoth location
- [ ] Port 8000 is available (or different port configured)
- [ ] Agent status shows green "Running"
- [ ] `/health` endpoint returns success

---

**🎉 You're now ready to revolutionize your research workflow with Thoth!**

The agent learns your research patterns and becomes more helpful over time. Start with simple questions and gradually explore advanced features as you become comfortable with the system.

**Happy researching! 🔬✨**
