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

export class MCPServersTabComponent {
  plugin: ThothPlugin;
  container: HTMLElement;
  servers: MCPServer[] = [];

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

    // Load and display servers
    await this.loadServers();

    // Server list
    const listContainer = this.container.createDiv({ cls: 'mcp-servers-list' });

    if (this.servers.length === 0) {
      listContainer.createEl('p', {
        text: 'No MCP servers configured. Click "Add Server" to get started.',
        cls: 'mcp-servers-empty'
      });
    } else {
      for (const server of this.servers) {
        this.renderServerCard(listContainer, server);
      }
    }
  }

  async loadServers(): Promise<void> {
    try {
      const endpoint = this.plugin.settings.remoteMode
        ? `${this.plugin.settings.remoteEndpointUrl}/api/mcp-servers`
        : `http://localhost:8282/api/mcp-servers`;

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

  renderServerCard(container: HTMLElement, server: MCPServer): void {
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
  }

  async toggleServer(serverId: string, enabled: boolean): Promise<void> {
    try {
      const endpoint = this.plugin.settings.remoteMode
        ? `${this.plugin.settings.remoteEndpointUrl}/api/mcp-servers/${serverId}/toggle`
        : `http://localhost:8282/api/mcp-servers/${serverId}/toggle`;

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
      const endpoint = this.plugin.settings.remoteMode
        ? `${this.plugin.settings.remoteEndpointUrl}/api/mcp-servers/${serverId}/test`
        : `http://localhost:8282/api/mcp-servers/${serverId}/test`;

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
      const endpoint = this.plugin.settings.remoteMode
        ? `${this.plugin.settings.remoteEndpointUrl}/api/mcp-servers/${serverId}`
        : `http://localhost:8282/api/mcp-servers/${serverId}`;

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
}
