# Thoth Obsidian Plugin - Troubleshooting Guide

## 🔧 **New Remote Management Features**

The latest version includes comprehensive remote management capabilities to solve connection and configuration sync issues:

### **✅ What's Fixed**
- **Remote Restart**: Restart agent from Obsidian even when running in WSL/Docker
- **Settings Sync**: Automatically sync Obsidian settings to backend
- **Dynamic Configuration**: Update backend config without file editing
- **Better Error Handling**: Specific error messages and recovery suggestions
- **Connection Testing**: Built-in connection test button

## 🚀 **New Remote Restart Feature**

### **How to Restart Agent from Obsidian**

#### **Method 1: Settings Page**
1. Go to Settings → Community Plugins → Thoth Research Assistant
2. Click **"Restart Agent"** button
3. Wait for restart confirmation

#### **Method 2: Command Palette**
1. Press `Ctrl+P` (or `Cmd+P`)
2. Type "Restart Thoth Agent"
3. Press Enter

#### **Method 3: Status Bar**
- Click status bar when agent is running
- Or use right-click menu (coming soon)

### **What Happens During Restart**
1. **Settings Sync**: Current Obsidian settings sent to backend
2. **Graceful Shutdown**: Agent stops safely
3. **Configuration Update**: Backend reloads with new settings
4. **Restart**: Agent restarts with updated configuration
5. **Health Check**: System verifies agent is working

## 🔄 **Automatic Settings Sync**

### **When Settings Sync**
- **On Save**: Every time you change settings in Obsidian
- **On Restart**: Before agent restart
- **On Connect**: When connecting to remote server

### **What Gets Synced**
- **API Keys**: OpenRouter (Mistral optional) keys
- **Directories**: Workspace and Obsidian paths
- **Server Settings**: Host, port configuration
- **Plugin Preferences**: Auto-start, status bar settings

### **Manual Sync**
Force settings sync by clicking **"Test Connection"** button in settings.

## 🐛 **Connection Error Solutions**

### **Error: "Failed to connect to remote server"**

#### **Quick Fixes**
1. **Check Server Status**:
   ```bash
   # In WSL/Docker
   curl http://localhost:8000/health
   # Should return: {"status":"healthy"}
   ```

2. **Verify URL Format**:
   - ✅ Correct: `http://localhost:8000`
   - ❌ Wrong: `localhost:8000` (missing http://)
   - ❌ Wrong: `http://localhost:8000/` (trailing slash)

3. **Test Different URLs**:
   - WSL: `http://localhost:8000`
   - WSL (alternative): `http://127.0.0.1:8000`
   - Docker: `http://localhost:8000`
   - Remote: `http://YOUR_SERVER_IP:8000`

#### **Advanced Troubleshooting**
```bash
# Check if port is listening
netstat -an | grep 8000

# Check WSL IP address
hostname -I

# Test from Windows command prompt
curl http://localhost:8000/health
```

### **Error: "Agent restart failed"**

#### **For WSL/Docker**
1. **Check Process**: Make sure Thoth is running
   ```bash
   ps aux | grep thoth
   ```

2. **Check Logs**: Look for error messages
   ```bash
   tail -f logs/thoth.log
   ```

3. **Manual Restart**:
   ```bash
   # Stop current process
   pkill -f "thoth api"

   # Start new process
   uv run python -m thoth api --host 0.0.0.0 --port 8000
   ```

#### **For Local Mode**
1. **Check uv Installation**:
   ```bash
   uv --version
   ```

2. **Check Permissions**:
   ```bash
   chmod +x /path/to/project-thoth
   ```

3. **Check API Keys**: Ensure keys are configured in plugin settings

### **Error: "Settings sync failed"**

#### **Troubleshooting Steps**
1. **Verify Connection**: Use "Test Connection" button
2. **Check Agent Status**: Visit `/agent/status` endpoint
3. **Manual Sync**: Try restarting agent

#### **Force Configuration Reset**
If settings get corrupted:
1. Stop agent
2. Delete `.env` file in workspace
3. Restart agent (will regenerate from Obsidian settings)

## 🔧 **New Troubleshooting Tools**

### **Built-in Diagnostics**

#### **Test Connection Button**
- **Location**: Settings → Thoth Research Assistant
- **What it checks**: Health endpoint connectivity
- **Results**: Shows success/failure with specific error

#### **Agent Status Display**
- **Location**: Settings page, status bar
- **Statuses**:
  - 🟢 **Running**: Everything working
  - 🟡 **Restarting**: Restart in progress
  - 🔴 **Stopped**: Not running
  - 🟠 **Error**: Process running but not responding

#### **Enhanced Error Messages**
- **Specific errors**: Instead of "connection failed"
- **Recovery suggestions**: What to try next
- **Context information**: Which component failed

### **Debug Mode**

#### **Enable Detailed Logging**
1. Open Obsidian Developer Tools (`Ctrl+Shift+I`)
2. Go to Console tab
3. Look for "Thoth:" messages

#### **Backend Logs**
```bash
# View live logs
tail -f logs/thoth.log

# View API logs
tail -f logs/thoth.log | grep "obsidian.py"
```

## 📋 **Configuration Validation**

### **Settings Checklist**

#### **Required Settings**
- [ ] **Mistral API Key** (optional): Provide if using remote OCR
- [ ] **OpenRouter API Key**: Must be valid
- [ ] **Workspace Directory**: Must exist and contain `pyproject.toml`
- [ ] **Remote URL**: Must be reachable (if using remote mode)

#### **Common Configuration Issues**

**Workspace Directory Problems**
```bash
# Check directory exists
ls -la /path/to/workspace/pyproject.toml

# Check permissions
ls -ld /path/to/workspace
```

**API Key Issues**
- Keys must be active and have credits
- Check at [console.mistral.ai](https://console.mistral.ai) and [openrouter.ai](https://openrouter.ai)

**Network Issues**
```bash
# Test WSL networking
ping -c 1 localhost
curl http://localhost:8000/health
```

## 🚨 **Emergency Recovery**

### **Complete Reset Procedure**

If everything fails:

1. **Stop All Processes**
   ```bash
   pkill -f "thoth"
   pkill -f "python -m thoth"
   ```

2. **Reset Configuration**
   ```bash
   cd /path/to/project-thoth
   rm -f .env
   ```

3. **Restart Obsidian**
   - Close completely
   - Reopen
   - Go to plugin settings

4. **Reconfigure from Scratch**
   - Enter API keys
   - Set directories
   - Test connection
   - Start agent

### **WSL-Specific Recovery**

```bash
# Restart WSL networking
wsl --shutdown
# Wait 10 seconds, then reopen WSL

# Check WSL status
wsl --status

# Restart Thoth
cd ~/project-thoth
uv run python -m thoth api --host 0.0.0.0 --port 8000
```

## 🔍 **Advanced Diagnostics**

### **API Endpoint Testing**

Test individual endpoints:

```bash
# Health check
curl http://localhost:8000/health

# Agent status
curl http://localhost:8000/agent/status

# Agent configuration
curl http://localhost:8000/agent/config

# Test chat (requires agent running)
curl -X POST http://localhost:8000/research/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"test","conversation_id":"test"}'
```

### **Network Diagnostics**

```bash
# Check port accessibility from Windows
telnet localhost 8000

# Check WSL port forwarding
netsh interface portproxy show all

# Check Windows firewall
netsh advfirewall firewall show rule name="WSL"
```

### **Process Diagnostics**

```bash
# Check running processes
ps aux | grep -i thoth

# Check network connections
netstat -tulpn | grep 8000

# Check system resources
top -p $(pgrep -f thoth)
```

## 📞 **Getting Help**

### **Before Reporting Issues**

1. **Try Connection Test**: Use built-in test button
2. **Check Status**: Note exact status/error messages
3. **Test Manual Start**: Try starting from command line
4. **Check Logs**: Look at both Obsidian console and backend logs

### **Information to Include**

When reporting issues:
- **Operating System**: Windows version, WSL version
- **Thoth Version**: `uv run python -m thoth --version`
- **Error Messages**: Exact text from both UI and logs
- **Configuration**: Remote mode? API keys set?
- **Steps to Reproduce**: What you did before the error

### **Common Solutions Summary**

| Error | Quick Fix |
|-------|-----------|
| Connection failed | Check URL format and server status |
| Agent won't start | Verify API keys and workspace directory |
| Settings not applying | Use restart agent feature |
| WSL connection issues | Use `http://localhost:8000` URL |
| Port conflicts | Change port to 8001 or 8002 |
| Permission errors | Check file/directory permissions |

---

**💡 Pro Tip**: The new remote restart feature solves most configuration issues automatically. When in doubt, try restarting the agent first!
