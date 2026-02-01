import { TFile, Vault, App } from 'obsidian';
import { ThothSettings } from '../types';

/**
 * Types of file changes that can be detected
 */
export type ChangeType = 'MODIFIED' | 'CREATED' | 'DELETED' | 'MOVED' | 'RENAMED';

/**
 * File change event interface
 */
export interface FileChangeEvent {
  type: ChangeType;
  filePath: string;
  oldPath?: string;
  content?: string;
  timestamp: number;
  isExternal: boolean;
  metadata?: Record<string, any>;
}

/**
 * File watcher configuration
 */
export interface FileWatcherConfig {
  debounceMs: number;
  enableChangeClassification: boolean;
  monitorVaultMovement: boolean;
  autoSyncOnChange: boolean;
  ignoreTempFiles: boolean;
  maxRetries: number;
}

/**
 * File watcher interface
 */
export interface IFileWatcher {
  watchSettingsFile(path: string): Promise<void>;
  stopWatching(): void;
  onFileChange(callback: (event: FileChangeEvent) => void): void;
  onFileMove(callback: (oldPath: string, newPath: string) => void): void;
  onError(callback: (error: Error) => void): void;
  pauseWatching(): void;
  resumeWatching(): void;
  isWatching(): boolean;
  getCurrentWatchedFile(): string | null;
  destroy(): void;
}

/**
 * Implementation of file watcher for settings file monitoring
 */
export class FileWatcher implements IFileWatcher {
  private app: App;
  private vault: Vault;
  private config: FileWatcherConfig;
  private watchedFilePath: string | null = null;
  private watchedFile: TFile | null = null;
  private isActive: boolean = false;
  private isPaused: boolean = false;

  private changeCallbacks: Array<(event: FileChangeEvent) => void> = [];
  private moveCallbacks: Array<(oldPath: string, newPath: string) => void> = [];
  private errorCallbacks: Array<(error: Error) => void> = [];

  private debounceTimer: NodeJS.Timeout | null = null;
  private lastModificationTime: number = 0;
  private lastKnownContent: string = '';
  private changeBuffer: FileChangeEvent[] = [];

  private vaultListener: (() => void) | null = null;
  private fileListener: (() => void) | null = null;

  constructor(app: App, config: Partial<FileWatcherConfig> = {}) {
    this.app = app;
    this.vault = app.vault;
    this.config = {
      debounceMs: 500,
      enableChangeClassification: true,
      monitorVaultMovement: true,
      autoSyncOnChange: true,
      ignoreTempFiles: true,
      maxRetries: 3,
      ...config
    };
  }

  async watchSettingsFile(path: string): Promise<void> {
    try {
      if (this.isActive) {
        await this.stopWatching();
      }

      this.watchedFilePath = path;
      this.watchedFile = await this.findOrCreateSettingsFile(path);

      if (this.watchedFile) {
        await this.setupFileListeners();
        this.isActive = true;

        // Initialize with current content
        try {
          this.lastKnownContent = await this.vault.read(this.watchedFile);
          this.lastModificationTime = this.watchedFile.stat.mtime;
        } catch (error) {
          console.warn('Could not read initial file content:', error);
        }

        console.log(`FileWatcher: Started monitoring ${path}`);
      } else {
        throw new Error(`Could not find or create settings file at ${path}`);
      }
    } catch (error) {
      this.triggerErrorCallbacks(error as Error);
      throw error;
    }
  }

  stopWatching(): void {
    if (this.vaultListener) {
      this.vault.off('modify' as any, this.vaultListener);
      this.vaultListener = null;
    }

    if (this.fileListener) {
      this.vault.off('rename' as any, this.fileListener);
      this.fileListener = null;
    }

    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }

    this.isActive = false;
    this.isPaused = false;
    this.watchedFile = null;
    this.watchedFilePath = null;
    this.changeBuffer = [];

    console.log('FileWatcher: Stopped monitoring');
  }

  onFileChange(callback: (event: FileChangeEvent) => void): void {
    this.changeCallbacks.push(callback);
  }

  onFileMove(callback: (oldPath: string, newPath: string) => void): void {
    this.moveCallbacks.push(callback);
  }

  onError(callback: (error: Error) => void): void {
    this.errorCallbacks.push(callback);
  }

  pauseWatching(): void {
    this.isPaused = true;
    console.log('FileWatcher: Paused monitoring');
  }

  resumeWatching(): void {
    this.isPaused = false;
    console.log('FileWatcher: Resumed monitoring');

    // Process any buffered changes
    if (this.changeBuffer.length > 0) {
      this.processBufferedChanges();
    }
  }

  isWatching(): boolean {
    return this.isActive && !this.isPaused;
  }

  getCurrentWatchedFile(): string | null {
    return this.watchedFilePath;
  }

  destroy(): void {
    this.stopWatching();
    this.changeCallbacks = [];
    this.moveCallbacks = [];
    this.errorCallbacks = [];
  }

  // Private implementation methods

  private async findOrCreateSettingsFile(path: string): Promise<TFile | null> {
    try {
      // First try to find existing file
      const file = this.vault.getAbstractFileByPath(path);
      if (file instanceof TFile) {
        return file;
      }

      // If not found, try to create it
      // Note: This creates a backend settings file (not plugin settings)
      // Backend manages its own settings in vault/_thoth/settings.json
      const defaultSettings = {
        api_keys: {
          mistral: '',
          openrouter: '',
          openai: '',
          anthropic: '',
          semantic_scholar: ''
        },
        workspace_directory: '',
        obsidian_directory: ''
      };

      const content = JSON.stringify(defaultSettings, null, 2);
      const createdFile = await this.vault.create(path, content);

      if (createdFile instanceof TFile) {
        console.log(`FileWatcher: Created settings file at ${path}`);
        return createdFile;
      }

      return null;
    } catch (error) {
      console.error('Error finding/creating settings file:', error);
      return null;
    }
  }

  private async setupFileListeners(): Promise<void> {
    if (!this.watchedFile) return;

    // Listen for file modifications
    this.vaultListener = () => {
      // Handle file modification logic
      if (this.watchedFile && !this.isPaused) {
        this.handleFileModification(this.watchedFile);
      }
    };

    // Note: Obsidian's vault.on has limited type support, using a more generic approach
    this.vault.on('modify' as any, this.vaultListener);

    // Listen for file moves/renames
    this.fileListener = () => {
      // Handle file move logic - would need to track moves differently
      if (this.watchedFile && !this.isPaused) {
        console.log('File potentially moved, checking...');
      }
    };

    this.vault.on('rename' as any, this.fileListener);

    // Additional listeners for vault changes if enabled
    if (this.config.monitorVaultMovement) {
      this.setupVaultMovementListeners();
    }
  }

  private setupVaultMovementListeners(): void {
    // Monitor for vault-level changes that might affect our watched file
    const vaultChangeListener = () => {
      if (this.watchedFile && !this.isPaused) {
        this.validateFileStillExists();
      }
    };

    // Note: Obsidian's vault events are limited, so we'll use a polling approach
    // for detecting external file system changes
    setInterval(vaultChangeListener, 5000); // Check every 5 seconds
  }

  private async handleFileModification(file: TFile): Promise<void> {
    try {
      const currentTime = Date.now();
      const fileModTime = file.stat.mtime;

      // Check if this is actually a new modification
      if (fileModTime <= this.lastModificationTime) {
        return;
      }

      const content = await this.vault.read(file);
      const isExternal = this.detectExternalChange(content, currentTime);

      const changeEvent: FileChangeEvent = {
        type: 'MODIFIED',
        filePath: file.path,
        content,
        timestamp: currentTime,
        isExternal,
        metadata: {
          fileSize: file.stat.size,
          mtime: fileModTime
        }
      };

      this.lastModificationTime = fileModTime;
      this.lastKnownContent = content;

      if (this.config.debounceMs > 0) {
        this.debounceFileChange(changeEvent);
      } else {
        this.processFileChange(changeEvent);
      }

    } catch (error) {
      this.triggerErrorCallbacks(error as Error);
    }
  }

  private handleFileMove(file: TFile, oldPath: string): void {
    console.log(`FileWatcher: File moved from ${oldPath} to ${file.path}`);

    // Update our internal references
    this.watchedFile = file;
    this.watchedFilePath = file.path;

    // Trigger move callbacks
    this.triggerMoveCallbacks(oldPath, file.path);

    // Also trigger a change event
    const changeEvent: FileChangeEvent = {
      type: 'MOVED',
      filePath: file.path,
      oldPath,
      timestamp: Date.now(),
      isExternal: true,
      metadata: {
        newPath: file.path
      }
    };

    this.processFileChange(changeEvent);
  }

  private detectExternalChange(content: string, timestamp: number): boolean {
    if (!this.config.enableChangeClassification) {
      return false;
    }

    // Simple heuristics to detect if change was external:
    // 1. Content changed but we haven't initiated any changes recently
    // 2. File modification time differs significantly from our last known change
    const timeSinceLastChange = timestamp - this.lastModificationTime;
    const contentChanged = content !== this.lastKnownContent;

    // If content changed and we haven't made changes recently, likely external
    return contentChanged && timeSinceLastChange > 2000; // 2 second threshold
  }

  private debounceFileChange(changeEvent: FileChangeEvent): void {
    // Add to buffer
    this.changeBuffer.push(changeEvent);

    // Clear existing timer
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    // Set new timer
    this.debounceTimer = setTimeout(() => {
      this.processBufferedChanges();
    }, this.config.debounceMs);
  }

  private processBufferedChanges(): void {
    if (this.changeBuffer.length === 0) return;

    // Process the most recent change (in case of multiple rapid changes)
    const latestChange = this.changeBuffer[this.changeBuffer.length - 1];

    // Clear buffer
    this.changeBuffer = [];

    this.processFileChange(latestChange);
  }

  private processFileChange(changeEvent: FileChangeEvent): void {
    try {
      // Validate the change event
      if (this.shouldIgnoreChange(changeEvent)) {
        return;
      }

      // Classify the change if enabled
      if (this.config.enableChangeClassification) {
        this.classifyChange(changeEvent);
      }

      // Trigger callbacks
      this.triggerChangeCallbacks(changeEvent);

      console.log(`FileWatcher: Processed ${changeEvent.type} change at ${changeEvent.filePath}`);
    } catch (error) {
      this.triggerErrorCallbacks(error as Error);
    }
  }

  private shouldIgnoreChange(changeEvent: FileChangeEvent): boolean {
    // Ignore temporary files if configured
    if (this.config.ignoreTempFiles && this.isTempFile(changeEvent.filePath)) {
      return true;
    }

    // Ignore if watching is paused
    if (this.isPaused) {
      return true;
    }

    return false;
  }

  private isTempFile(filePath: string): boolean {
    const tempPatterns = [
      /\.tmp$/,
      /\.temp$/,
      /~$/,
      /\.swp$/,
      /\.bak$/
    ];

    return tempPatterns.some(pattern => pattern.test(filePath));
  }

  private classifyChange(changeEvent: FileChangeEvent): void {
    // Enhanced change classification logic
    if (changeEvent.content) {
      try {
        // Try to parse as JSON to validate structure
        const parsed = JSON.parse(changeEvent.content);
        changeEvent.metadata = {
          ...changeEvent.metadata,
          isValidJSON: true,
          fieldCount: Object.keys(parsed).length
        };
      } catch (error) {
        changeEvent.metadata = {
          ...changeEvent.metadata,
          isValidJSON: false,
          parseError: error.message
        };
      }
    }

    // Determine if this looks like a configuration change
    if (changeEvent.isExternal && changeEvent.content) {
      changeEvent.metadata = {
        ...changeEvent.metadata,
        likelyUserEdit: this.detectUserEditPattern(changeEvent.content)
      };
    }
  }

  private detectUserEditPattern(content: string): boolean {
    // Simple heuristics to detect if this looks like a user edit:
    // 1. Formatted JSON (pretty-printed)
    // 2. Contains comments (though JSON doesn't support them officially)
    // 3. Specific formatting patterns

    try {
      const parsed = JSON.parse(content);
      const formatted = JSON.stringify(parsed, null, 2);

      // If content matches formatted JSON, likely a user edit
      return content.trim() === formatted.trim();
    } catch (error) {
      return false;
    }
  }

  private async validateFileStillExists(): Promise<void> {
    if (!this.watchedFilePath) return;

    try {
      const file = this.vault.getAbstractFileByPath(this.watchedFilePath);
      if (!file || !(file instanceof TFile)) {
        // File was deleted or moved externally
        const changeEvent: FileChangeEvent = {
          type: 'DELETED',
          filePath: this.watchedFilePath,
          timestamp: Date.now(),
          isExternal: true
        };

        this.processFileChange(changeEvent);
        this.stopWatching();
      }
    } catch (error) {
      this.triggerErrorCallbacks(error as Error);
    }
  }

  private triggerChangeCallbacks(event: FileChangeEvent): void {
    for (const callback of this.changeCallbacks) {
      try {
        callback(event);
      } catch (error) {
        console.error('Change callback error:', error);
      }
    }
  }

  private triggerMoveCallbacks(oldPath: string, newPath: string): void {
    for (const callback of this.moveCallbacks) {
      try {
        callback(oldPath, newPath);
      } catch (error) {
        console.error('Move callback error:', error);
      }
    }
  }

  private triggerErrorCallbacks(error: Error): void {
    for (const callback of this.errorCallbacks) {
      try {
        callback(error);
      } catch (error) {
        console.error('Error callback error:', error);
      }
    }
  }
}

/**
 * Factory for creating file watchers with different configurations
 */
export class FileWatcherFactory {
  static createForSettings(app: App): FileWatcher {
    return new FileWatcher(app, {
      debounceMs: 1000,
      enableChangeClassification: true,
      monitorVaultMovement: true,
      autoSyncOnChange: true,
      ignoreTempFiles: true,
      maxRetries: 3
    });
  }

  static createMinimal(app: App): FileWatcher {
    return new FileWatcher(app, {
      debounceMs: 100,
      enableChangeClassification: false,
      monitorVaultMovement: false,
      autoSyncOnChange: false,
      ignoreTempFiles: true,
      maxRetries: 1
    });
  }

  static createHighFrequency(app: App): FileWatcher {
    return new FileWatcher(app, {
      debounceMs: 50,
      enableChangeClassification: true,
      monitorVaultMovement: true,
      autoSyncOnChange: true,
      ignoreTempFiles: true,
      maxRetries: 5
    });
  }
}
