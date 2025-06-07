# 🚀 Quick Setup - Fix Connection & Chat Icon Issues

## 📋 **Immediate Steps to Fix Your Issues**

### **Step 1: Install the Updated Plugin**
```bash
# Copy the built files to your Obsidian vault's plugins directory
cp -r dist/* /path/to/your/vault/.obsidian/plugins/thoth-research-assistant/
```

### **Step 2: Configure Remote Mode**
1. **Open Obsidian Settings** → Community Plugins → Thoth Research Assistant
2. **Enable Remote Mode**: Toggle ON
3. **Set Remote URL**: `http://localhost:8000`
4. **Add API Keys**:
   - OpenRouter API Key: `your_openrouter_key`
   - Mistral API Key (optional): `your_mistral_key`
   - Serper API Key (optional): `your_serper_key`
   - Web Search Providers: `serper,duckduckgo`
5. **Set Directories**:
   - Workspace Directory: `/home/nick/python/project-thoth`
   - Obsidian Directory: `/path/to/your/vault/thoth`
6. **Click "Test Connection"** - Should show ✅ success

### **Step 3: Test the Connection**
1. **Click "Test Connection"** button in settings
2. Should show: `✅ Connection successful!`
3. If it fails, check:
   - WSL server is running: `curl http://localhost:8000/health`
   - URL format is exact: `http://localhost:8000` (no trailing slash)

### **Step 4: Start the Agent**
1. **Click "Start Agent"** button in settings
2. Should show: `Connected to remote Thoth server successfully!`
3. Status bar should show: `Thoth: Running` (in green)

### **Step 5: Find the Chat Icon**
The chat icon should now appear in the left ribbon (sidebar) as a message circle icon.

If you don't see it:
1. **Reload Obsidian**: `Ctrl+R` or restart completely
2. **Check Plugin is Enabled**: Settings → Community Plugins → Thoth Research Assistant (should be ON)
3. **Look for**: 💬 message-circle icon in the left ribbon

### **Step 6: Test Chat**
1. **Click the chat icon** in the ribbon
2. **Type a message**: "Hello, can you help me research something?"
3. **Press Enter** or click Send
4. Should get a response from the agent

## 🐛 **Debugging**

### **If Connection Still Fails**
1. **Open Developer Console**: `Ctrl+Shift+I` → Console tab
2. **Click "Start Agent"** and look for Thoth debug messages:
   ```
   Thoth: startAgent called
   Remote mode: true
   Remote URL: http://localhost:8000
   Testing connection to: http://localhost:8000
   Health check response status: 200
   ```

### **If Chat Icon Missing**
1. **Check Console** for errors about the ribbon icon
2. **Try Command Palette**: `Ctrl+P` → "Open Research Chat"
3. **Restart Obsidian** completely

### **If Settings Don't Save**
1. **Check file permissions** in your vault directory
2. **Try Manual Config**: Settings → Community Plugins → reload the plugin

## ✅ **Expected Results**

After following these steps:
- ✅ Status bar shows "Thoth: Running" in green
- ✅ Chat icon appears in left ribbon
- ✅ Clicking "Test Connection" shows success
- ✅ Chat modal opens and responds to messages
- ✅ "Start Agent" and "Restart Agent" work correctly

## 🔧 **Troubleshooting Commands**

```bash
# Check WSL server status
curl http://localhost:8000/health

# Check agent status
curl http://localhost:8000/agent/status

# Test chat endpoint
curl -X POST http://localhost:8000/research/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"test","conversation_id":"test"}'
```

If you're still having issues, please:
1. **Copy the debug output** from the browser console
2. **Note exact error messages** from Obsidian notices
3. **Confirm WSL server response**: `curl http://localhost:8000/health`
