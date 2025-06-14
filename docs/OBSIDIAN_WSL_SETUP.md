# WSL + Windows Setup Guide

This guide shows how to run Thoth in WSL (Windows Subsystem for Linux) and connect to it from Obsidian running on Windows.

## 🎯 **Why This Setup?**

**Common Scenario:**
- You prefer running Python development in WSL
- Obsidian runs on Windows (better integration with Windows apps)
- You want to use the Thoth Obsidian plugin without installing Python on Windows

**Benefits:**
- No need to install Python, uv, or Thoth on Windows
- Keep your development environment in WSL
- Full access to Linux tooling for Thoth
- Obsidian gets native Windows integration

## 🚀 **Quick Setup**

### **Step 1: Install Thoth in WSL**
```bash
# In WSL terminal
cd ~
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# Install dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv sync
```

### **Step 2: Configure API Keys in WSL**
```bash
# In project-thoth directory
cp .env.example .env
nano .env

# Add your API keys:
API_MISTRAL_KEY=your_mistral_key_here
API_OPENROUTER_KEY=your_openrouter_key_here
```

### **Step 3: Start Thoth Server in WSL**
```bash
# Important: Use 0.0.0.0 to allow connections from Windows
uv run python -m thoth api --host 0.0.0.0 --port 8000
```

### **Step 4: Configure Obsidian Plugin (Windows)**
1. Open Obsidian on Windows
2. Go to Settings → Community Plugins → Thoth Research Assistant
3. **Enable Remote Mode**: Turn on the toggle
4. **Set Remote URL**: Use one of these options:

#### **Option A: Use localhost (Recommended)**
- URL: `http://localhost:8000`
- WSL automatically forwards port 8000 to Windows

#### **Option B: Use WSL IP Address**
```bash
# In WSL, find your IP:
hostname -I
# Example output: 172.20.10.5
```
- URL: `http://172.20.10.5:8000`

### **Step 5: Test Connection**
1. Click the status bar in Obsidian
2. Should show "Connected to remote Thoth server successfully!"
3. Test chat: Press `Ctrl+P` → "Open Research Chat"
4. Type: "What tools do you have available?"

## 🔧 **Detailed Setup**

### **WSL Configuration**

#### **1. Network Setup**
WSL2 uses a virtual network. You have two options:

**Option 1: Automatic Port Forwarding (Easiest)**
```bash
# Start server with any host
uv run python -m thoth api --host 0.0.0.0 --port 8000
# Windows can access via http://localhost:8000
```

**Option 2: Manual Port Forwarding**
```powershell
# In Windows PowerShell (as Administrator)
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=172.20.10.5
```

#### **2. Firewall Configuration**
```bash
# In WSL, allow port 8000
sudo ufw allow 8000
```

#### **3. Persistent Startup Script**
Create a startup script in WSL:
```bash
# Create script
nano ~/start-thoth.sh

#!/bin/bash
cd ~/project-thoth
uv run python -m thoth api --host 0.0.0.0 --port 8000

# Make executable
chmod +x ~/start-thoth.sh
```

### **Directory Mapping**

#### **Path Configuration**
When using WSL + Windows, you need to handle different path formats:

**WSL Paths (in WSL):**
- Workspace: `/home/username/project-thoth`
- Obsidian: `/mnt/c/Users/Username/Documents/Obsidian Vault`

**Windows Paths (in Obsidian plugin):**
- Workspace: `\\wsl$\Ubuntu\home\username\project-thoth`
- Obsidian: `C:\Users\Username\Documents\Obsidian Vault`

#### **Plugin Configuration**
In Obsidian plugin settings:
- **Remote Mode**: ✅ Enabled
- **Remote URL**: `http://localhost:8000`
- **Workspace Directory**: `\\wsl$\Ubuntu\home\username\project-thoth`
- **Obsidian Directory**: `C:\Users\Username\Documents\Obsidian Vault\thoth`

## 🛠️ **Advanced Configuration**

### **Auto-Start with Windows**

#### **Option 1: Task Scheduler**
1. Open Task Scheduler in Windows
2. Create Basic Task
3. Trigger: When computer starts
4. Action: Start a program
5. Program: `wsl`
6. Arguments: `-e bash -c "cd ~/project-thoth && uv run python -m thoth api --host 0.0.0.0 --port 8000"`

#### **Option 2: Windows Subsystem Startup**
```bash
# In WSL, create systemd service (if supported)
sudo nano /etc/systemd/system/thoth.service

[Unit]
Description=Thoth Research Assistant API
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/home/yourusername/project-thoth
ExecStart=/home/yourusername/.local/bin/uv run python -m thoth api --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target

# Enable service
sudo systemctl enable thoth.service
sudo systemctl start thoth.service
```

### **Multiple Instances**
Run different Thoth instances on different ports:

```bash
# Development instance
uv run python -m thoth api --host 0.0.0.0 --port 8000

# Production instance
uv run python -m thoth api --host 0.0.0.0 --port 8001
```

## 🐛 **Troubleshooting**

### **Connection Issues**

#### **"Failed to connect to remote server"**
1. **Check WSL Server Status**:
   ```bash
   # In WSL
   curl http://localhost:8000/health
   # Should return: {"status":"healthy"}
   ```

2. **Check Windows Port Access**:
   ```powershell
   # In Windows PowerShell
   curl http://localhost:8000/health
   # Should return same result
   ```

3. **Check Firewall**:
   ```bash
   # In WSL
   sudo ufw status
   # Should show: 8000 ALLOW
   ```

#### **"Port already in use"**
```bash
# Find what's using the port
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>

# Or use different port
uv run python -m thoth api --host 0.0.0.0 --port 8001
```

#### **WSL IP Address Changes**
```bash
# Get current WSL IP
hostname -I

# Update Obsidian plugin if needed
# Or use localhost for automatic forwarding
```

### **Performance Issues**

#### **Slow Startup**
- WSL2 can be slow to start
- Consider keeping WSL running in background
- Use SSD for better performance

#### **Network Latency**
- WSL2 adds small network overhead
- Usually negligible for API calls
- Use localhost forwarding for best performance

## 📁 **File Access Patterns**

### **Reading Papers (PDFs)**
```bash
# Option 1: Store PDFs in WSL
mkdir -p ~/project-thoth/data/pdfs

# Option 2: Access Windows folders from WSL
ln -s /mnt/c/Users/Username/Documents/Papers ~/project-thoth/data/pdfs
```

### **Obsidian Notes**
```bash
# Access Obsidian vault from WSL
ln -s "/mnt/c/Users/Username/Documents/Obsidian Vault" ~/obsidian-vault

# Configure paths in .env
OBSIDIAN_DIR=/home/username/obsidian-vault/thoth
```

## ✅ **Verification Checklist**

### **WSL Side**
- [ ] Run comprehensive health check: `uv run python health_check.py`
- [ ] Thoth installed and working: `uv run python -m thoth --help`
- [ ] Server starts: `uv run python -m thoth api --host 0.0.0.0 --port 8000`
- [ ] Health check works: `curl http://localhost:8000/health`
- [ ] API keys configured in `.env`

### **Windows Side**
- [ ] Obsidian plugin installed and enabled
- [ ] Remote mode enabled in settings
- [ ] Remote URL configured: `http://localhost:8000`
- [ ] Connection test works (click status bar)
- [ ] Chat functionality works

### **Integration**
- [ ] File paths accessible from both sides
- [ ] Research queries work end-to-end
- [ ] PDF processing pipeline functional

## 🚀 **Performance Tips**

1. **Use SSD**: Store WSL2 on SSD for better performance
2. **Allocate Memory**: Configure WSL2 memory in `.wslconfig`
3. **Keep WSL Running**: Don't shut down WSL between uses
4. **Use localhost**: Prefer `localhost:8000` over IP addresses
5. **Monitor Resources**: Use `htop` in WSL to monitor resource usage

---

**🎉 You now have a robust WSL + Windows Thoth setup!**

This configuration gives you the best of both worlds - Linux development environment with Windows desktop integration.
