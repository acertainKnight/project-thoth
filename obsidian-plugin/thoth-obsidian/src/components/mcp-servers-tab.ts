import { Setting } from 'obsidian';
import type ThothPlugin from '../../main';

interface MCPServer {
  server_id: string;
  name: string;
  enabled: boolean;
  connected: boolean;
  transport: string;
  auto_attach: boolean;
  tool_count: number;
  tools?: MCPServerTool[];
}

interface MCPServerTool {
  name: string;
  description: string;
  prefixed_name: string;
  attached: boolean;
}

interface MCPServerConfig {
  name: string;
  enabled: boolean;
  transport: 'stdio' | 'http' | 'sse';
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  auto_attach: boolean;
  timeout: number;
}

interface LettaAgent {
  id: string;
  name: string;
}

export class MCPServersTabComponent {
  plugin: ThothPlugin;
  container: HTMLElement;
  servers: MCPServer[] = [];
  expandedServers: Set<string> = new Set();
  selectedTools: Map<string, Set<string>> = new Map();
  selectedAgent: string | null = null;
  agents: LettaAgent[] = [];

  constructor(plugin: ThothPlugin, container: HTMLElement) {
    this.plugin = plugin;
    this.container = container;
  }

  async render(): Promise<void> {
    this.container.empty();

    // Header
    const header = this.container.createDiv({ cls: 'mcp-servers-header' });
    header.createEl('h2', { text: 'MCP Servers' });
    header.createEl('p', {
      text: 'Manage external MCP server connections to extend Thoth capabilities',
      cls: 'mcp-servers-description'
    });

    // Add server button
    const addButton = header.createEl('button', {
      text: '+ Add Server',
      cls: 'mod-cta mcp-add-server-btn'
    });
    addButton.onclick = () => this.showAddServerDialog();

    // Load agents and servers
    await Promise.all([this.loadServers(), this.loadAgents()]);

    // Agent selector (if agents available)
    if (this.agents.length > 0) {
      const agentSelector = this.container.createDiv({ cls: 'mcp-agent-selector' });
      agentSelector.createEl('label', { text: 'Target Agent: ' });
      const select = agentSelector.createEl('select');

      const defaultOption = select.createEl('option', { text: '-- Select Agent --', value: '' });
      for (const agent of this.agents) {
        select.createEl('option', { text: agent.name, value: agent.id });
      }

      if (this.selectedAgent) {
        select.value = this.selectedAgent;
      }

      select.onchange = async () => {
        this.selectedAgent = select.value || null;
        // Refresh tool lists if any servers are expanded
        for (const serverId of this.expandedServers) {
          const server = this.servers.find(s => s.server_id === serverId);
          if (server) {
            server.tools = await this.loadServerTools(serverId);
          }
        }
        await this.render();
      };
    }

    // Server list
    const listContainer = this.container.createDiv({ cls: 'mcp-servers-list' });

    if (this.servers.length === 0) {
      listContainer.createEl('p', {
        text: 'No MCP servers configured. Click "Add Server" to get started.',
        cls: 'mcp-servers-empty'
      });
    } else {
      for (const server of this.servers) {
        await this.renderServerCard(listContainer, server);
      }
    }
  }

  async loadServers(): Promise<void> {
    try {
      const endpoint = `${this.plugin.getEndpointUrl()}/api/mcp-servers`;

      const response = await fetch(endpoint);
      if (response.ok) {
        this.servers = await response.json();
      } else {
        console.error('Failed to load MCP servers:', response.statusText);
        this.servers = [];
      }
    } catch (error) {
      console.error('Error loading MCP servers:', error);
      this.servers = [];
    }
  }

  async loadAgents(): Promise<void> {
    try {
      const lettaEndpoint = this.plugin.getLettaEndpointUrl();
      const response = await fetch(`${lettaEndpoint}/v1/agents/`);
      if (response.ok) {
        this.agents = await response.json();
      } else {
        console.error('Failed to load agents:', response.statusText);
        this.agents = [];
      }
    } catch (error) {
      console.error('Error loading agents:', error);
      this.agents = [];
    }
  }

  async loadServerTools(serverId: string): Promise<MCPServerTool[]> {
    try {
      const endpoint = `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/tools`;

      const url = this.selectedAgent
        ? `${endpoint}?agent_id=${this.selectedAgent}`
        : endpoint;

      const response = await fetch(url);
      if (response.ok) {
        return await response.json();
      } else {
        console.error('Failed to load tools:', response.statusText);
        return [];
      }
    } catch (error) {
      console.error('Error loading tools:', error);
      return [];
    }
  }

  async renderServerCard(container: HTMLElement, server: MCPServer): Promise<void> {
    const card = container.createDiv({ cls: 'mcp-server-card' });

    // Status indicator
    const statusClass = server.connected ? 'connected' : server.enabled ? 'disconnected' : 'disabled';
    const statusEl = card.createDiv({ cls: `mcp-server-status ${statusClass}` });
    statusEl.setAttribute('title', server.connected ? 'Connected' : server.enabled ? 'Disconnected' : 'Disabled');

    // Server info
    const info = card.createDiv({ cls: 'mcp-server-info' });
    info.createEl('h3', { text: server.name });
    info.createEl('div', {
      text: `ID: ${server.server_id}`,
      cls: 'mcp-server-id'
    });

    // Details
    const details = card.createDiv({ cls: 'mcp-server-details' });
    details.createEl('span', {
      text: `${server.transport.toUpperCase()}`,
      cls: 'mcp-server-transport'
    });
    details.createEl('span', {
      text: `${server.tool_count} tools`,
      cls: 'mcp-server-tools'
    });
    if (server.auto_attach) {
      details.createEl('span', {
        text: 'Auto-attach',
        cls: 'mcp-server-auto-attach'
      });
    }

    // Actions
    const actions = card.createDiv({ cls: 'mcp-server-actions' });

    // Show/Hide Tools button
    const isExpanded = this.expandedServers.has(server.server_id);
    const toolsBtn = actions.createEl('button', {
      text: isExpanded ? 'Hide Tools' : 'Show Tools',
      cls: 'mcp-btn-secondary'
    });
    toolsBtn.onclick = async () => {
      if (this.expandedServers.has(server.server_id)) {
        this.expandedServers.delete(server.server_id);
      } else {
        this.expandedServers.add(server.server_id);
        // Load tools if not already loaded
        if (!server.tools) {
          server.tools = await this.loadServerTools(server.server_id);
        }
      }
      await this.render();
    };

    // Toggle button
    const toggleBtn = actions.createEl('button', {
      text: server.enabled ? 'Disable' : 'Enable',
      cls: server.enabled ? 'mcp-btn-warning' : 'mcp-btn-success'
    });
    toggleBtn.onclick = () => this.toggleServer(server.server_id, !server.enabled);

    // Test button
    const testBtn = actions.createEl('button', {
      text: 'Test',
      cls: 'mcp-btn-secondary'
    });
    testBtn.onclick = () => this.testServer(server.server_id);

    // Edit button
    const editBtn = actions.createEl('button', {
      text: 'Edit',
      cls: 'mcp-btn-secondary'
    });
    editBtn.onclick = () => this.showEditServerDialog(server.server_id);

    // Remove button
    const removeBtn = actions.createEl('button', {
      text: 'Remove',
      cls: 'mcp-btn-danger'
    });
    removeBtn.onclick = () => this.removeServer(server.server_id);

    // Tools list (if expanded)
    if (isExpanded && server.tools) {
      await this.renderToolsList(card, server);
    }
  }

  async toggleServer(serverId: string, enabled: boolean): Promise<void> {
    try {
      const endpoint = `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/toggle`;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });

      if (response.ok) {
        await this.render(); // Refresh
      } else {
        const error = await response.text();
        console.error('Failed to toggle server:', error);
        alert(`Failed to toggle server: ${error}`);
      }
    } catch (error) {
      console.error('Error toggling server:', error);
      alert(`Error: ${error}`);
    }
  }

  async testServer(serverId: string): Promise<void> {
    try {
      const endpoint = `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/test`;

      const response = await fetch(endpoint, { method: 'POST' });

      if (response.ok) {
        const result = await response.json();
        alert(result.success
          ? `✓ ${result.message}`
          : `✗ ${result.message}`
        );
      } else {
        const error = await response.text();
        alert(`Failed to test connection: ${error}`);
      }
    } catch (error) {
      console.error('Error testing server:', error);
      alert(`Error: ${error}`);
    }
  }

  async removeServer(serverId: string): Promise<void> {
    if (!confirm(`Are you sure you want to remove server "${serverId}"?`)) {
      return;
    }

    try {
      const endpoint = `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}`;

      const response = await fetch(endpoint, { method: 'DELETE' });

      if (response.ok) {
        await this.render(); // Refresh
      } else {
        const error = await response.text();
        console.error('Failed to remove server:', error);
        alert(`Failed to remove server: ${error}`);
      }
    } catch (error) {
      console.error('Error removing server:', error);
      alert(`Error: ${error}`);
    }
  }

  showAddServerDialog(): void {
    const dialog = this.container.createDiv({ cls: 'mcp-server-dialog' });
    const overlay = this.container.createDiv({ cls: 'mcp-dialog-overlay' });

    const content = dialog.createDiv({ cls: 'mcp-dialog-content' });
    content.createEl('h2', { text: 'Add MCP Server' });

    const form = content.createDiv({ cls: 'mcp-server-form' });

    // Server ID
    new Setting(form)
      .setName('Server ID')
      .setDesc('Unique identifier (e.g., "my-filesystem")')
      .addText(text => text.setPlaceholder('my-server'));

    // Name
    new Setting(form)
      .setName('Name')
      .setDesc('Human-readable name')
      .addText(text => text.setPlaceholder('My MCP Server'));

    // Transport
    new Setting(form)
      .setName('Transport')
      .setDesc('Connection type')
      .addDropdown(dropdown => {
        dropdown.addOption('stdio', 'stdio (command-line)');
        dropdown.addOption('http', 'HTTP');
        dropdown.addOption('sse', 'SSE (Server-Sent Events)');
        dropdown.onChange(value => {
          // Show/hide relevant fields
          const transport = value as 'stdio' | 'http' | 'sse';
          const stdioFields = form.querySelector('.stdio-fields') as HTMLElement;
          const urlFields = form.querySelector('.url-fields') as HTMLElement;
          if (stdioFields && urlFields) {
            stdioFields.style.display = transport === 'stdio' ? 'block' : 'none';
            urlFields.style.display = transport === 'stdio' ? 'none' : 'block';
          }
        });
      });

    // stdio fields
    const stdioFields = form.createDiv({ cls: 'stdio-fields' });
    new Setting(stdioFields)
      .setName('Command')
      .addText(text => text.setPlaceholder('npx'));
    new Setting(stdioFields)
      .setName('Arguments')
      .setDesc('Comma-separated arguments')
      .addText(text => text.setPlaceholder('-y, @modelcontextprotocol/server-filesystem, /path'));

    // URL fields
    const urlFields = form.createDiv({ cls: 'url-fields' });
    urlFields.style.display = 'none';
    new Setting(urlFields)
      .setName('URL')
      .addText(text => text.setPlaceholder('http://localhost:8080/mcp'));

    // Common settings
    new Setting(form)
      .setName('Enabled')
      .addToggle(toggle => toggle.setValue(true));

    new Setting(form)
      .setName('Auto-attach tools')
      .addToggle(toggle => toggle.setValue(true));

    new Setting(form)
      .setName('Timeout (seconds)')
      .addText(text => text.setValue('30'));

    // Buttons
    const buttons = content.createDiv({ cls: 'mcp-dialog-buttons' });
    const cancelBtn = buttons.createEl('button', { text: 'Cancel' });
    cancelBtn.onclick = () => {
      dialog.remove();
      overlay.remove();
    };

    const saveBtn = buttons.createEl('button', { text: 'Add Server', cls: 'mod-cta' });
    saveBtn.onclick = async () => {
      // Extract form values and call API
      // TODO: Implement form extraction and API call
      dialog.remove();
      overlay.remove();
      await this.render();
    };

    overlay.onclick = () => {
      dialog.remove();
      overlay.remove();
    };
  }

  showEditServerDialog(serverId: string): void {
    // Similar to showAddServerDialog but for editing
    // TODO: Implement edit dialog
    alert('Edit functionality coming soon. For now, please edit mcps.json directly.');
  }

  async renderToolsList(card: HTMLElement, server: MCPServer): Promise<void> {
    if (!server.tools || server.tools.length === 0) {
      const emptyMsg = card.createDiv({ cls: 'mcp-tool-list-empty' });
      emptyMsg.createEl('p', { text: 'No tools available from this server.' });
      return;
    }

    const toolsContainer = card.createDiv({ cls: 'mcp-tool-list' });

    // Action bar at top
    const actionBar = toolsContainer.createDiv({ cls: 'mcp-tool-actions' });

    // Select All / Deselect All buttons
    const selectAllBtn = actionBar.createEl('button', {
      text: 'Select All',
      cls: 'mcp-btn-secondary'
    });
    selectAllBtn.onclick = () => {
      if (!this.selectedTools.has(server.server_id)) {
        this.selectedTools.set(server.server_id, new Set());
      }
      const selected = this.selectedTools.get(server.server_id)!;
      for (const tool of server.tools!) {
        selected.add(tool.name);
      }
      this.render();
    };

    const deselectAllBtn = actionBar.createEl('button', {
      text: 'Deselect All',
      cls: 'mcp-btn-secondary'
    });
    deselectAllBtn.onclick = () => {
      this.selectedTools.set(server.server_id, new Set());
      this.render();
    };

    // Get selected tools for this server
    const selected = this.selectedTools.get(server.server_id) || new Set();

    // Attach/Detach buttons
    if (this.selectedAgent && selected.size > 0) {
      const attachBtn = actionBar.createEl('button', {
        text: `Attach Selected (${selected.size})`,
        cls: 'mcp-btn-success'
      });
      attachBtn.onclick = () => this.attachTools(server.server_id, Array.from(selected));

      const detachBtn = actionBar.createEl('button', {
        text: `Detach Selected (${selected.size})`,
        cls: 'mcp-btn-warning'
      });
      detachBtn.onclick = () => this.detachTools(server.server_id, Array.from(selected));
    } else if (!this.selectedAgent) {
      actionBar.createEl('span', {
        text: 'Select an agent above to attach/detach tools',
        cls: 'mcp-tool-hint'
      });
    }

    // Tools list
    for (const tool of server.tools) {
      const toolItem = toolsContainer.createDiv({ cls: 'mcp-tool-item' });

      // Checkbox
      const checkbox = toolItem.createEl('input', {
        type: 'checkbox',
        cls: 'mcp-tool-checkbox'
      });
      checkbox.checked = selected.has(tool.name);
      checkbox.onchange = () => {
        if (!this.selectedTools.has(server.server_id)) {
          this.selectedTools.set(server.server_id, new Set());
        }
        const toolSet = this.selectedTools.get(server.server_id)!;
        if (checkbox.checked) {
          toolSet.add(tool.name);
        } else {
          toolSet.delete(tool.name);
        }
        this.render();
      };

      // Tool info
      const toolInfo = toolItem.createDiv({ cls: 'mcp-tool-info' });

      const toolHeader = toolInfo.createDiv({ cls: 'mcp-tool-header' });
      toolHeader.createEl('span', { text: tool.name, cls: 'mcp-tool-name' });

      if (tool.attached) {
        toolHeader.createEl('span', { text: '✓ Attached', cls: 'mcp-tool-attached-badge' });
      }

      if (tool.description) {
        toolInfo.createEl('div', { text: tool.description, cls: 'mcp-tool-description' });
      }

      // Prefixed name with copy button
      const prefixedContainer = toolInfo.createDiv({ cls: 'mcp-tool-prefixed-container' });
      prefixedContainer.createEl('code', {
        text: tool.prefixed_name,
        cls: 'mcp-tool-prefixed-name'
      });

      const copyBtn = prefixedContainer.createEl('button', {
        text: '📋',
        cls: 'mcp-tool-copy-btn',
        attr: { 'aria-label': 'Copy tool name' }
      });
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(tool.prefixed_name);
          copyBtn.textContent = '✓';
          setTimeout(() => {
            copyBtn.textContent = '📋';
          }, 2000);
        } catch (error) {
          console.error('Failed to copy:', error);
          alert(`Failed to copy. Tool name: ${tool.prefixed_name}`);
        }
      };
    }
  }

  async attachTools(serverId: string, toolNames: string[]): Promise<void> {
    if (!this.selectedAgent) {
      alert('Please select an agent first.');
      return;
    }

    try {
      const endpoint = `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/tools/attach`;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: this.selectedAgent,
          tool_names: toolNames
        })
      });

      if (response.ok) {
        const result = await response.json();
        const attached = result.attached?.length || 0;
        const alreadyAttached = result.already_attached?.length || 0;
        alert(`✓ Success!\nAttached: ${attached}\nAlready attached: ${alreadyAttached}`);

        // Refresh server tools to update attached status
        const server = this.servers.find(s => s.server_id === serverId);
        if (server) {
          server.tools = await this.loadServerTools(serverId);
        }
        await this.render();
      } else {
        const error = await response.text();
        alert(`Failed to attach tools: ${error}`);
      }
    } catch (error) {
      console.error('Error attaching tools:', error);
      alert(`Error: ${error}`);
    }
  }

  async detachTools(serverId: string, toolNames: string[]): Promise<void> {
    if (!this.selectedAgent) {
      alert('Please select an agent first.');
      return;
    }

    try {
      const endpoint = `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/tools/detach`;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: this.selectedAgent,
          tool_names: toolNames
        })
      });

      if (response.ok) {
        const result = await response.json();
        const detached = result.detached?.length || 0;
        alert(`✓ Detached ${detached} tool(s) successfully!`);

        // Refresh server tools to update attached status
        const server = this.servers.find(s => s.server_id === serverId);
        if (server) {
          server.tools = await this.loadServerTools(serverId);
        }
        await this.render();
      } else {
        const error = await response.text();
        alert(`Failed to detach tools: ${error}`);
      }
    } catch (error) {
      console.error('Error detaching tools:', error);
      alert(`Error: ${error}`);
    }
  }
}
