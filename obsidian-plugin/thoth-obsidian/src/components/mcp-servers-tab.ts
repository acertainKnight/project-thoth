import { Notice, Setting } from 'obsidian';
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

      select.createEl('option', { text: '-- Select Agent --', value: '' });
      for (const agent of this.agents) {
        select.createEl('option', { text: agent.name, value: agent.id });
      }

      if (this.selectedAgent) {
        select.value = this.selectedAgent;
      }

      select.onchange = async () => {
        this.selectedAgent = select.value || null;
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
      const response = await this.plugin.authFetch(
        `${this.plugin.getEndpointUrl()}/api/mcp-servers`
      );
      this.servers = response.ok ? await response.json() : [];
    } catch (error) {
      console.error('Error loading MCP servers:', error);
      this.servers = [];
    }
  }

  async loadAgents(): Promise<void> {
    try {
      const response = await this.plugin.authFetch(
        `${this.plugin.getLettaEndpointUrl()}/v1/agents/`
      );
      this.agents = response.ok ? await response.json() : [];
    } catch (error) {
      console.error('Error loading agents:', error);
      this.agents = [];
    }
  }

  async loadServerTools(serverId: string): Promise<MCPServerTool[]> {
    try {
      const base = `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/tools`;
      const url = this.selectedAgent ? `${base}?agent_id=${this.selectedAgent}` : base;
      const response = await this.plugin.authFetch(url);
      return response.ok ? await response.json() : [];
    } catch (error) {
      console.error('Error loading tools:', error);
      return [];
    }
  }

  async renderServerCard(container: HTMLElement, server: MCPServer): Promise<void> {
    const card = container.createDiv({ cls: 'mcp-server-card' });

    const statusClass = server.connected ? 'connected' : server.enabled ? 'disconnected' : 'disabled';
    const statusEl = card.createDiv({ cls: `mcp-server-status ${statusClass}` });
    statusEl.setAttribute('title', server.connected ? 'Connected' : server.enabled ? 'Disconnected' : 'Disabled');

    const info = card.createDiv({ cls: 'mcp-server-info' });
    info.createEl('h3', { text: server.name });
    info.createEl('div', { text: `ID: ${server.server_id}`, cls: 'mcp-server-id' });

    const details = card.createDiv({ cls: 'mcp-server-details' });
    details.createEl('span', { text: server.transport.toUpperCase(), cls: 'mcp-server-transport' });
    details.createEl('span', { text: `${server.tool_count} tools`, cls: 'mcp-server-tools' });
    if (server.auto_attach) {
      details.createEl('span', { text: 'Auto-attach', cls: 'mcp-server-auto-attach' });
    }

    const actions = card.createDiv({ cls: 'mcp-server-actions' });

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
        if (!server.tools) {
          server.tools = await this.loadServerTools(server.server_id);
        }
      }
      await this.render();
    };

    const toggleBtn = actions.createEl('button', {
      text: server.enabled ? 'Disable' : 'Enable',
      cls: server.enabled ? 'mcp-btn-warning' : 'mcp-btn-success'
    });
    toggleBtn.onclick = () => this.toggleServer(server.server_id, !server.enabled);

    const testBtn = actions.createEl('button', { text: 'Test', cls: 'mcp-btn-secondary' });
    testBtn.onclick = () => this.testServer(server.server_id);

    const editBtn = actions.createEl('button', { text: 'Edit', cls: 'mcp-btn-secondary' });
    editBtn.onclick = () => this.showEditServerDialog(server);

    const removeBtn = actions.createEl('button', { text: 'Remove', cls: 'mcp-btn-danger' });
    removeBtn.onclick = () => this.removeServer(server.server_id, server.name);

    if (isExpanded && server.tools) {
      await this.renderToolsList(card, server);
    }
  }

  async toggleServer(serverId: string, enabled: boolean): Promise<void> {
    try {
      const response = await this.plugin.authFetch(
        `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/toggle`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled })
        }
      );

      if (response.ok) {
        new Notice(`Server ${enabled ? 'enabled' : 'disabled'}`);
        await this.render();
      } else {
        const error = await response.text();
        new Notice(`Failed to toggle server: ${error}`, 5000);
      }
    } catch (error) {
      new Notice(`Error: ${error.message}`, 5000);
    }
  }

  async testServer(serverId: string): Promise<void> {
    try {
      const response = await this.plugin.authFetch(
        `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/test`,
        { method: 'POST' }
      );

      if (response.ok) {
        const result = await response.json();
        new Notice(result.success ? `Connection OK: ${result.message}` : `Test failed: ${result.message}`, 5000);
      } else {
        const error = await response.text();
        new Notice(`Failed to test connection: ${error}`, 5000);
      }
    } catch (error) {
      new Notice(`Error: ${error.message}`, 5000);
    }
  }

  async removeServer(serverId: string, serverName: string): Promise<void> {
    const confirmed = await this.plugin.showConfirm(
      `Remove server "${serverName}"? This cannot be undone.`
    );
    if (!confirmed) return;

    try {
      const response = await this.plugin.authFetch(
        `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}`,
        { method: 'DELETE' }
      );

      if (response.ok) {
        new Notice(`Server "${serverName}" removed`);
        await this.render();
      } else {
        const error = await response.text();
        new Notice(`Failed to remove server: ${error}`, 5000);
      }
    } catch (error) {
      new Notice(`Error: ${error.message}`, 5000);
    }
  }

  showAddServerDialog(): void {
    this.showServerDialog(null);
  }

  showEditServerDialog(server: MCPServer): void {
    this.showServerDialog(server);
  }

  private showServerDialog(existing: MCPServer | null): void {
    const isEdit = existing !== null;
    const overlay = document.body.createDiv({ cls: 'mcp-dialog-overlay' });
    const dialog = overlay.createDiv({ cls: 'mcp-dialog-content' });

    dialog.createEl('h2', { text: isEdit ? 'Edit MCP Server' : 'Add MCP Server' });

    const form = dialog.createDiv({ cls: 'mcp-server-form' });

    // Capture component refs for reading values later
    let serverId = existing?.server_id ?? '';
    let serverName = existing?.name ?? '';
    let transport: 'stdio' | 'http' | 'sse' = (existing?.transport as any) ?? 'stdio';
    let command = '';
    let args = '';
    let url = '';
    let enabled = existing?.enabled ?? true;
    let autoAttach = existing?.auto_attach ?? true;
    let timeout = '30';

    if (!isEdit) {
      new Setting(form)
        .setName('Server ID')
        .setDesc('Unique identifier (e.g., "my-filesystem")')
        .addText(text => {
          text.setPlaceholder('my-server').setValue(serverId);
          text.onChange(v => { serverId = v; });
        });
    }

    new Setting(form)
      .setName('Name')
      .setDesc('Human-readable name')
      .addText(text => {
        text.setPlaceholder('My MCP Server').setValue(serverName);
        text.onChange(v => { serverName = v; });
      });

    // Transport selector + conditional fields
    const stdioFields = form.createDiv({ cls: 'stdio-fields' });
    const urlFields = form.createDiv({ cls: 'url-fields' });

    const updateFieldVisibility = () => {
      stdioFields.style.display = transport === 'stdio' ? '' : 'none';
      urlFields.style.display = transport === 'stdio' ? 'none' : '';
    };

    new Setting(form)
      .setName('Transport')
      .setDesc('Connection type')
      .addDropdown(dd => {
        dd.addOption('stdio', 'stdio (command-line)');
        dd.addOption('http', 'HTTP');
        dd.addOption('sse', 'SSE (Server-Sent Events)');
        dd.setValue(transport);
        dd.onChange(v => {
          transport = v as 'stdio' | 'http' | 'sse';
          updateFieldVisibility();
        });
      });

    new Setting(stdioFields)
      .setName('Command')
      .addText(text => {
        text.setPlaceholder('npx').setValue(command);
        text.onChange(v => { command = v; });
      });
    new Setting(stdioFields)
      .setName('Arguments')
      .setDesc('Comma-separated arguments')
      .addText(text => {
        text.setPlaceholder('-y, @modelcontextprotocol/server-filesystem, /path').setValue(args);
        text.onChange(v => { args = v; });
      });

    new Setting(urlFields)
      .setName('URL')
      .addText(text => {
        text.setPlaceholder('http://localhost:8080/mcp').setValue(url);
        text.onChange(v => { url = v; });
      });

    updateFieldVisibility();

    new Setting(form)
      .setName('Enabled')
      .addToggle(toggle => {
        toggle.setValue(enabled);
        toggle.onChange(v => { enabled = v; });
      });

    new Setting(form)
      .setName('Auto-attach tools')
      .addToggle(toggle => {
        toggle.setValue(autoAttach);
        toggle.onChange(v => { autoAttach = v; });
      });

    new Setting(form)
      .setName('Timeout (seconds)')
      .addText(text => {
        text.setValue(timeout);
        text.onChange(v => { timeout = v; });
      });

    const buttons = dialog.createDiv({ cls: 'mcp-dialog-buttons' });

    const cancelBtn = buttons.createEl('button', { text: 'Cancel' });
    cancelBtn.onclick = () => overlay.remove();

    const saveBtn = buttons.createEl('button', {
      text: isEdit ? 'Save Changes' : 'Add Server',
      cls: 'mod-cta'
    });
    saveBtn.onclick = async () => {
      if (!isEdit && !serverId.trim()) {
        new Notice('Server ID is required');
        return;
      }
      if (!serverName.trim()) {
        new Notice('Server name is required');
        return;
      }

      const config: MCPServerConfig = {
        name: serverName.trim(),
        enabled,
        transport,
        auto_attach: autoAttach,
        timeout: parseInt(timeout, 10) || 30,
        ...(transport === 'stdio'
          ? {
              command: command.trim() || undefined,
              args: args.split(',').map(a => a.trim()).filter(Boolean)
            }
          : { url: url.trim() || undefined })
      };

      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      try {
        const endpoint = this.plugin.getEndpointUrl();
        const response = isEdit
          ? await this.plugin.authFetch(
              `${endpoint}/api/mcp-servers/${existing!.server_id}`,
              {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
              }
            )
          : await this.plugin.authFetch(
              `${endpoint}/api/mcp-servers`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ server_id: serverId.trim(), ...config })
              }
            );

        if (response.ok) {
          new Notice(isEdit ? `Server "${serverName}" updated` : `Server "${serverName}" added`);
          overlay.remove();
          await this.render();
        } else {
          const err = await response.json().catch(() => ({ detail: response.statusText }));
          new Notice(`Failed to ${isEdit ? 'update' : 'add'} server: ${err.detail || err}`, 5000);
          saveBtn.disabled = false;
          saveBtn.textContent = isEdit ? 'Save Changes' : 'Add Server';
        }
      } catch (error) {
        new Notice(`Error: ${error.message}`, 5000);
        saveBtn.disabled = false;
        saveBtn.textContent = isEdit ? 'Save Changes' : 'Add Server';
      }
    };

    overlay.onclick = (e) => {
      if (e.target === overlay) overlay.remove();
    };
  }

  async renderToolsList(card: HTMLElement, server: MCPServer): Promise<void> {
    if (!server.tools || server.tools.length === 0) {
      card.createDiv({ cls: 'mcp-tool-list-empty' }).createEl('p', {
        text: 'No tools available from this server.'
      });
      return;
    }

    const toolsContainer = card.createDiv({ cls: 'mcp-tool-list' });
    const actionBar = toolsContainer.createDiv({ cls: 'mcp-tool-actions' });

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

    const selected = this.selectedTools.get(server.server_id) || new Set();

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

    for (const tool of server.tools) {
      const toolItem = toolsContainer.createDiv({ cls: 'mcp-tool-item' });

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
        // Update action bar without full re-render to preserve expanded state
        this.render();
      };

      const toolInfo = toolItem.createDiv({ cls: 'mcp-tool-info' });
      const toolHeader = toolInfo.createDiv({ cls: 'mcp-tool-header' });
      toolHeader.createEl('span', { text: tool.name, cls: 'mcp-tool-name' });

      if (tool.attached) {
        toolHeader.createEl('span', { text: 'Attached', cls: 'mcp-tool-attached-badge' });
      }

      if (tool.description) {
        toolInfo.createEl('div', { text: tool.description, cls: 'mcp-tool-description' });
      }

      const prefixedContainer = toolInfo.createDiv({ cls: 'mcp-tool-prefixed-container' });
      prefixedContainer.createEl('code', {
        text: tool.prefixed_name,
        cls: 'mcp-tool-prefixed-name'
      });

      const copyBtn = prefixedContainer.createEl('button', {
        text: 'Copy',
        cls: 'mcp-tool-copy-btn',
        attr: { 'aria-label': 'Copy tool name' }
      });
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(tool.prefixed_name);
          copyBtn.textContent = 'Copied';
          setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
        } catch (error) {
          new Notice(`Failed to copy: ${tool.prefixed_name}`, 3000);
        }
      };
    }
  }

  async attachTools(serverId: string, toolNames: string[]): Promise<void> {
    if (!this.selectedAgent) {
      new Notice('Please select an agent first');
      return;
    }

    try {
      const response = await this.plugin.authFetch(
        `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/tools/attach`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_id: this.selectedAgent, tool_names: toolNames })
        }
      );

      if (response.ok) {
        const result = await response.json();
        const attached = result.attached?.length || 0;
        const already = result.already_attached?.length || 0;
        new Notice(`Attached ${attached} tool(s)${already ? `, ${already} already attached` : ''}`);
        const server = this.servers.find(s => s.server_id === serverId);
        if (server) {
          server.tools = await this.loadServerTools(serverId);
        }
        await this.render();
      } else {
        const error = await response.text();
        new Notice(`Failed to attach tools: ${error}`, 5000);
      }
    } catch (error) {
      new Notice(`Error: ${error.message}`, 5000);
    }
  }

  async detachTools(serverId: string, toolNames: string[]): Promise<void> {
    if (!this.selectedAgent) {
      new Notice('Please select an agent first');
      return;
    }

    try {
      const response = await this.plugin.authFetch(
        `${this.plugin.getEndpointUrl()}/api/mcp-servers/${serverId}/tools/detach`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_id: this.selectedAgent, tool_names: toolNames })
        }
      );

      if (response.ok) {
        const result = await response.json();
        const detached = result.detached?.length || 0;
        new Notice(`Detached ${detached} tool(s) successfully`);
        const server = this.servers.find(s => s.server_id === serverId);
        if (server) {
          server.tools = await this.loadServerTools(serverId);
        }
        await this.render();
      } else {
        const error = await response.text();
        new Notice(`Failed to detach tools: ${error}`, 5000);
      }
    } catch (error) {
      new Notice(`Error: ${error.message}`, 5000);
    }
  }
}
