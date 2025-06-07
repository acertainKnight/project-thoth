# Thoth Obsidian Plugin

An intelligent research assistant plugin that brings AI-powered research capabilities directly into your Obsidian vault. Thoth helps you discover, analyze, and cite research while you write.

## 🚀 **Quick Start Checklist**

Before you begin, make sure you have:

- [ ] **Thoth installed**: Test with `uv run python -m thoth --help` in terminal
- [ ] **API Keys**: Get [OpenRouter API](https://openrouter.ai) key (Mistral key optional)
- [ ] **Plugin installed**: Enable in Obsidian Settings → Community Plugins

### **Essential Setup (5 minutes)**

1. **Configure API Keys** (Settings → Community Plugins → Thoth Research Assistant):
   - Enter your OpenRouter API Key
   - Enter your Mistral API Key if available

2. **Set Directories**:
   - **Workspace Directory**: `/home/nick/python/project-thoth` (where you cloned the repo)
   - **Obsidian Directory**: `/path/to/your/vault/thoth` (your notes folder)

3. **Start Agent**:
   - Click the status bar at bottom of Obsidian (should say "Thoth: Stopped")
   - Wait for "Thoth: Running" in green

4. **Test Chat**:
   - Press `Ctrl+P` → "Open Research Chat"
   - Type: "What tools do you have available?"

**🎉 If the agent responds, you're ready to go!**

### **🖥️ WSL + Windows Setup**

If you're running Thoth in WSL and Obsidian on Windows:

1. **Enable Remote Mode** in plugin settings
2. **Start Thoth in WSL**: `uv run python -m thoth api --host 0.0.0.0 --port 8000`
3. **Set Remote URL**: `http://localhost:8000`
4. **Connect**: Click status bar in Obsidian

📖 **[Full WSL Setup Guide](OBSIDIAN_WSL_SETUP.md)** - Detailed instructions for WSL + Windows configuration

### **🐳 Docker Setup**

Run Thoth in Docker and connect from any Obsidian:

1. **Build and run**: `docker-compose up -d`
2. **Enable Remote Mode** in plugin settings
3. **Set Remote URL**: `http://localhost:8000`
4. **Connect**: Click status bar in Obsidian

📖 **[Full Docker Setup Guide](OBSIDIAN_DOCKER_SETUP.md)** - Complete containerization guide

---

## ✨ Features

- **🤖 AI-Powered Research**: Get intelligent answers to research questions using advanced AI models
- **📚 Smart Citations**: Automatically generate and manage citations for your research
- **💬 Interactive Chat**: Engage in research conversations directly within Obsidian
- **🔍 Context-Aware Queries**: Research selected text with a single command
- **⚡ Real-Time Integration**: Connect with the Thoth research backend for live data
- **📊 Status Monitoring**: Visual indicators for agent status and connection health
- **🎨 Modern UI**: Clean, responsive interface that matches Obsidian's design language

## 🚀 Installation

### Prerequisites

- Obsidian v0.15.0 or higher
- Thoth research system installed and configured
- API keys for Mistral AI and/or OpenRouter

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/yourusername/thoth-obsidian/releases)
2. Extract the files to your vault's `.obsidian/plugins/thoth-obsidian/` directory
3. Reload Obsidian or enable the plugin in Settings → Community Plugins

### Development Installation

1. Clone this repository into your vault's plugins directory:
   ```bash
   cd /path/to/your/vault/.obsidian/plugins/
   git clone https://github.com/yourusername/thoth-obsidian.git
   ```
2. Install dependencies:
   ```bash
   cd thoth-obsidian
   npm install
   ```
3. Build the plugin:
   ```bash
   npm run build
   ```
4. Enable the plugin in Obsidian Settings → Community Plugins

## ⚙️ Configuration

### Initial Setup

1. Open Obsidian Settings → Community Plugins → Thoth Research Assistant
2. Configure your API keys:
   - **Mistral API Key** (optional): Your API key for Mistral AI services
   - **OpenRouter API Key**: Your API key for OpenRouter (multiple model access)
3. Set connection details:
   - **Endpoint Host**: Usually `localhost` for local installations
   - **Endpoint Port**: Default is `8000`
4. Adjust behavior settings:
   - **Auto-start Agent**: Automatically start Thoth when Obsidian opens
   - **Show Status Bar**: Display connection status in the status bar

### API Keys

To get your API keys:
- **Mistral AI**: Visit [console.mistral.ai](https://console.mistral.ai)
- **OpenRouter**: Visit [openrouter.ai](https://openrouter.ai)

## 🎯 Usage

### Basic Commands

The plugin adds several commands to Obsidian's command palette (Ctrl/Cmd + P):

- **Start Thoth Agent**: Initialize the research backend
- **Stop Thoth Agent**: Shut down the research backend
- **Restart Thoth Agent**: Restart the backend service
- **Open Research Chat**: Launch the interactive chat interface
- **Insert Research Query**: Research selected text (available in editor)

### Research Workflow

1. **Start the Agent**: Use the command palette or click the status bar
2. **Select Text**: Highlight any text in your notes
3. **Research**: Run "Insert Research Query" command
4. **Chat**: Use the chat interface for follow-up questions
5. **Integrate**: Copy insights directly into your notes

### Chat Interface

The chat modal provides:
- **Persistent History**: Conversations are saved across sessions
- **Rich Formatting**: Support for markdown in responses
- **Quick Actions**: Easy copy/paste of research results
- **Context Awareness**: Understands your current document context

### Status Indicators

- **🟢 Green "Thoth: Running"**: Agent is active and ready
- **🔴 Red "Thoth: Stopped"**: Agent is not running
- **Click Status**: Quick start/stop functionality

## 🛠️ Development

### Building from Source

```bash
# Install dependencies
npm install

# Development build with file watching
npm run dev

# Production build
npm run build

# Lint code
npm run lint

# Clean build artifacts
npm run clean
```

### Project Structure

```
thoth-obsidian/
├── main.ts           # Main plugin logic
├── styles.css        # UI styling
├── manifest.json     # Plugin metadata
├── package.json      # Dependencies and scripts
├── tsconfig.json     # TypeScript configuration
├── .eslintrc.json    # Linting rules
└── README.md         # This file
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Lint your code: `npm run lint`
5. Submit a pull request

## 🐛 Troubleshooting

### Common Issues

**Agent Won't Start**
- Verify Thoth is installed and in your PATH
- Check that API keys are configured correctly
- Ensure no other process is using the endpoint port

**Connection Errors**
- Confirm endpoint host/port settings
- Check firewall settings
- Verify the Thoth backend is running

**Chat Not Responding**
- Ensure the agent is running (check status bar)
- Verify API keys have sufficient credits
- Check the developer console for error messages

### Debug Mode

Enable debug logging by:
1. Open Developer Tools (Ctrl/Cmd + Shift + I)
2. Go to Console tab
3. Look for messages prefixed with "Thoth Agent:"

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/yourusername/thoth-obsidian/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/thoth-obsidian/discussions)
- **Documentation**: [Full Documentation](https://yoursite.com/docs)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for the [Obsidian](https://obsidian.md) knowledge management platform
- Powered by [OpenRouter](https://openrouter.ai) with optional OCR from [Mistral AI](https://mistral.ai)
- Inspired by the need for seamless research integration

## 🔮 Roadmap

- [ ] PDF annotation integration
- [ ] Zotero synchronization
- [ ] Custom research templates
- [ ] Collaborative research features
- [ ] Advanced citation formatting
- [ ] Research dashboard and analytics

---

**Made with ❤️ for researchers and knowledge workers**
