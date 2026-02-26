import { App, TFile, Vault, Platform } from 'obsidian';
import { APIUtilities } from '../utils/api';

// Mobile-compatible path utilities
const PathUtil = {
  join: (...parts: string[]): string => {
    return parts.filter(p => p && p.length > 0)
      .join('/')
      .replace(/\/+/g, '/');
  },
  dirname: (filepath: string): string => {
    const lastSlash = filepath.lastIndexOf('/');
    return lastSlash === -1 ? '' : filepath.substring(0, lastSlash);
  },
  basename: (filepath: string): string => {
    const lastSlash = filepath.lastIndexOf('/');
    return lastSlash === -1 ? filepath : filepath.substring(lastSlash + 1);
  },
  resolve: (filepath: string): string => filepath,
  relative: (from: string, to: string): string => {
    const fromParts = from.split('/').filter(Boolean);
    const toParts = to.split('/').filter(Boolean);
    let i = 0;
    while (i < fromParts.length && i < toParts.length && fromParts[i] === toParts[i]) i++;
    const upCount = fromParts.length - i;
    return Array(upCount).fill('..').concat(toParts.slice(i)).join('/');
  }
};

/**
 * Vault detector interface
 */
export interface IVaultDetector {
  getCurrentVaultPath(): string;
  getSettingsFilePath(): string;
  onVaultChange(callback: (newPath: string) => void): void;
  notifyBackendOfVaultPath(): Promise<void>;
  updateBaseUrl(newBaseUrl: string): void;
  stopMonitoring(): void;
}

/**
 * Vault change event
 */
interface VaultChangeEvent {
  oldPath: string;
  newPath: string;
  timestamp: number;
}

/**
 * VaultDetector implementation for managing vault path detection and changes
 */
export class VaultDetector implements IVaultDetector {
  private app: App;
  private baseUrl: string;
  private currentVaultPath: string;
  private changeCallbacks: Array<(newPath: string) => void> = [];
  private settingsFileName = '.thoth.settings.json';
  private isMonitoring = false;

  constructor(app: App, baseUrl: string) {
    this.app = app;
    this.baseUrl = baseUrl;
    this.currentVaultPath = this.detectVaultPath();
    this.startMonitoring();
  }

  /**
   * Get the current vault root path
   */
  getCurrentVaultPath(): string {
    return this.currentVaultPath;
  }

  /**
   * Get the full path to the settings file
   */
  getSettingsFilePath(): string {
    return PathUtil.join(this.currentVaultPath, this.settingsFileName);
  }

  /**
   * Register callback for vault change events
   */
  onVaultChange(callback: (newPath: string) => void): void {
    this.changeCallbacks.push(callback);
  }

  /**
   * Notify backend about current vault path
   */
  async notifyBackendOfVaultPath(): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/config/vault-path`, APIUtilities.withAuthHeaders({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vault_path: this.currentVaultPath,
          settings_file_path: this.getSettingsFilePath(),
          timestamp: Date.now()
        })
      }));

      if (!response.ok) {
        console.warn(`Failed to notify backend of vault path: ${response.statusText}`);
      } else {
        console.log(`Backend notified of vault path: ${this.currentVaultPath}`);
      }
    } catch (error) {
      console.warn('Could not notify backend of vault path:', error);
    }
  }

  /**
   * Detect the current vault path using multiple methods
   */
  private detectVaultPath(): string {
    // Method 1: Try to get from Obsidian app adapter
    try {
      if (this.app.vault.adapter && 'path' in this.app.vault.adapter) {
        const adapterPath = (this.app.vault.adapter as any).path;
        if (adapterPath && typeof adapterPath === 'string') {
          return this.normalizePath(adapterPath);
        }
      }
    } catch (error) {
      console.warn('Could not get vault path from adapter:', error);
    }

    // Method 2: Try to get from vault configuration
    try {
      if (this.app.vault.configDir) {
        const vaultPath = PathUtil.dirname(this.app.vault.configDir);
        return this.normalizePath(vaultPath);
      }
    } catch (error) {
      console.warn('Could not get vault path from config dir:', error);
    }

    // Method 3: Try to infer from file operations
    try {
      // Get any file from the vault and work backwards
      const files = this.app.vault.getAllLoadedFiles();
      if (files.length > 0) {
        const firstFile = files[0];
        if (firstFile instanceof TFile && firstFile.path) {
          // This gives us the relative path, we need to infer the base
          // This is more complex and may not always work
          console.warn('Using file-based vault path detection (may be unreliable)');
        }
      }
    } catch (error) {
      console.warn('Could not infer vault path from files:', error);
    }

    // Method 4: Fallback - try common locations or prompt user
    console.warn('Could not detect vault path automatically');
    return ''; // Empty string indicates detection failed
  }

  /**
   * Normalize path separators and resolve relative paths
   */
  private normalizePath(dirPath: string): string {
    // Handle different path separators and resolve to absolute path
    return PathUtil.resolve(dirPath);
  }

  /**
   * Start monitoring for vault changes
   */
  private startMonitoring(): void {
    if (this.isMonitoring) {
      return;
    }

    this.isMonitoring = true;

    // Monitor for vault changes
    this.app.vault.on('modify', this.handleVaultChange.bind(this));
    this.app.vault.on('create', this.handleVaultChange.bind(this));
    this.app.vault.on('delete', this.handleVaultChange.bind(this));

    // Periodic check for vault path changes (every 30 seconds)
    setInterval(() => {
      this.checkForVaultPathChange();
    }, 30000);
  }

  /**
   * Handle vault change events
   */
  private handleVaultChange(): void {
    // Debounce vault change detection
    setTimeout(() => {
      this.checkForVaultPathChange();
    }, 1000);
  }

  /**
   * Check if vault path has changed
   */
  private checkForVaultPathChange(): void {
    const newVaultPath = this.detectVaultPath();

    if (newVaultPath && newVaultPath !== this.currentVaultPath) {
      const oldPath = this.currentVaultPath;
      this.currentVaultPath = newVaultPath;

      console.log(`Vault path changed from ${oldPath} to ${newVaultPath}`);

      // Notify all registered callbacks
      this.changeCallbacks.forEach(callback => {
        try {
          callback(newVaultPath);
        } catch (error) {
          console.error('Error in vault change callback:', error);
        }
      });

      // Notify backend of the change
      this.notifyBackendOfVaultPath();
    }
  }

  /**
   * Check if settings file exists in the vault
   */
  async settingsFileExists(): Promise<boolean> {
    // Mobile: use Vault API
    if (Platform.isMobile) {
      try {
        const file = this.app.vault.getAbstractFileByPath(this.settingsFileName);
        return file !== null;
      } catch {
        return false;
      }
    }

    // Desktop: use fs if available
    try {
      const settingsPath = this.getSettingsFilePath();
      // Try to check if file exists using Node.js fs (if available)
      if (typeof require !== 'undefined') {
        const fs = require('fs');
        return fs.existsSync(settingsPath);
      }
    } catch (error) {
      console.warn('Could not check settings file existence:', error);
    }
    return false;
  }

  /**
   * Create settings file if it doesn't exist
   */
  async createSettingsFile(initialSettings: any): Promise<boolean> {
    // Mobile: use Vault API
    if (Platform.isMobile) {
      try {
        const settingsContent = JSON.stringify(initialSettings, null, 2);
        await this.app.vault.create(this.settingsFileName, settingsContent);
        console.log(`Created settings file (mobile): ${this.settingsFileName}`);
        return true;
      } catch (error) {
        console.error('Failed to create settings on mobile:', error);
        return false;
      }
    }

    // Desktop: use fs
    try {
      const settingsPath = this.getSettingsFilePath();

      if (typeof require !== 'undefined') {
        const fs = require('fs');
        const settingsContent = JSON.stringify(initialSettings, null, 2);

        await fs.promises.writeFile(settingsPath, settingsContent, 'utf8');
        console.log(`Created settings file at: ${settingsPath}`);
        return true;
      }
    } catch (error) {
      console.error('Failed to create settings file:', error);
    }
    return false;
  }

  /**
   * Read settings from vault settings file
   */
  async readVaultSettings(): Promise<any | null> {
    // Mobile: use Vault API
    if (Platform.isMobile) {
      try {
        const file = this.app.vault.getAbstractFileByPath(this.settingsFileName);
        if (file instanceof TFile) {
          const content = await this.app.vault.read(file);
          return JSON.parse(content);
        }
      } catch (error) {
        console.warn('Could not read settings on mobile:', error);
      }
      return null;
    }

    // Desktop: use fs
    try {
      const settingsPath = this.getSettingsFilePath();

      if (typeof require !== 'undefined') {
        const fs = require('fs');

        if (fs.existsSync(settingsPath)) {
          const content = await fs.promises.readFile(settingsPath, 'utf8');
          return JSON.parse(content);
        }
      }
    } catch (error) {
      console.warn('Could not read vault settings:', error);
    }
    return null;
  }

  /**
   * Write settings to vault settings file
   */
  async writeVaultSettings(settings: any): Promise<boolean> {
    // Mobile: use Vault API
    if (Platform.isMobile) {
      try {
        const settingsContent = JSON.stringify(settings, null, 2);
        const file = this.app.vault.getAbstractFileByPath(this.settingsFileName);
        if (file instanceof TFile) {
          await this.app.vault.modify(file, settingsContent);
        } else {
          await this.app.vault.create(this.settingsFileName, settingsContent);
        }
        console.log(`Updated vault settings file (mobile): ${this.settingsFileName}`);
        return true;
      } catch (error) {
        console.error('Failed to write settings on mobile:', error);
        return false;
      }
    }

    // Desktop: use fs
    try {
      const settingsPath = this.getSettingsFilePath();

      if (typeof require !== 'undefined') {
        const fs = require('fs');
        const settingsContent = JSON.stringify(settings, null, 2);

        await fs.promises.writeFile(settingsPath, settingsContent, 'utf8');
        console.log(`Updated vault settings file: ${settingsPath}`);
        return true;
      }
    } catch (error) {
      console.error('Failed to write vault settings:', error);
    }
    return false;
  }

  /**
   * Get relative path from vault root
   */
  getRelativePathFromVault(absolutePath: string): string {
    return PathUtil.relative(this.currentVaultPath, absolutePath);
  }

  /**
   * Get absolute path from vault-relative path
   */
  getAbsolutePathFromVault(relativePath: string): string {
    return PathUtil.join(this.currentVaultPath, relativePath);
  }

  /**
   * Stop monitoring (cleanup)
   */
  stopMonitoring(): void {
    if (this.isMonitoring) {
      this.app.vault.off('modify', this.handleVaultChange.bind(this));
      this.app.vault.off('create', this.handleVaultChange.bind(this));
      this.app.vault.off('delete', this.handleVaultChange.bind(this));
      this.isMonitoring = false;
    }
  }

  /**
   * Update base URL for backend communication
   */
  updateBaseUrl(newBaseUrl: string): void {
    this.baseUrl = newBaseUrl;
  }

  /**
   * Get vault metadata
   */
  getVaultMetadata(): {
    path: string;
    name: string;
    fileCount: number;
    hasSettings: boolean;
  } {
    const files = this.app.vault.getAllLoadedFiles();
    const vaultName = PathUtil.basename(this.currentVaultPath) || 'Unknown';

    return {
      path: this.currentVaultPath,
      name: vaultName,
      fileCount: files.length,
      hasSettings: false // Will be set asynchronously
    };
  }
}
