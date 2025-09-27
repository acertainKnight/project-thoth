import { App, Modal, FuzzySuggestModal, FuzzyMatch } from 'obsidian';
import { ThothSettings } from '../types';
import { UISchema, FieldSchema } from '../services/schema-service';
import { KeyboardShortcuts, KeyboardShortcut } from './keyboard-shortcuts';
import { SearchResult } from './search-filter';

/**
 * Command palette item interface
 */
export interface CommandPaletteItem {
  id: string;
  title: string;
  description?: string;
  category: CommandCategory;
  action: () => void | Promise<void>;
  icon?: string;
  keywords?: string[];
  shortcut?: string;
  enabled: boolean;
  context?: string[];
  score?: number;
}

/**
 * Command categories
 */
export type CommandCategory =
  | 'navigation'
  | 'editing'
  | 'validation'
  | 'view'
  | 'search'
  | 'settings'
  | 'tools'
  | 'help';

/**
 * Context action interface
 */
export interface ContextAction {
  id: string;
  title: string;
  description?: string;
  action: (context: ActionContext) => void | Promise<void>;
  icon?: string;
  condition?: (context: ActionContext) => boolean;
  priority: number;
}

/**
 * Action context interface
 */
export interface ActionContext {
  currentTab?: string;
  selectedField?: string;
  selectedText?: string;
  cursorPosition?: { line: number; column: number };
  validationErrors?: Array<{ field: string; message: string }>;
  hasUnsavedChanges?: boolean;
  currentValue?: any;
  fieldSchema?: FieldSchema;
}

/**
 * Command palette configuration
 */
interface CommandPaletteConfig {
  maxResults: number;
  fuzzyThreshold: number;
  showRecentCommands: boolean;
  showKeyboardShortcuts: boolean;
  groupByCategory: boolean;
  enableContextActions: boolean;
}

/**
 * VS Code-style command palette with fuzzy search
 */
export class CommandPalette extends FuzzySuggestModal<CommandPaletteItem> {
  private commands = new Map<string, CommandPaletteItem>();
  private contextActions = new Map<string, ContextAction>();
  private recentCommands: string[] = [];
  private currentContext: ActionContext = {};
  private config: CommandPaletteConfig;
  private keyboardShortcuts?: KeyboardShortcuts;
  private schema?: UISchema;
  private settings?: ThothSettings;

  constructor(app: App, config: Partial<CommandPaletteConfig> = {}) {
    super(app);

    this.config = {
      maxResults: 50,
      fuzzyThreshold: 0.1,
      showRecentCommands: true,
      showKeyboardShortcuts: true,
      groupByCategory: true,
      enableContextActions: true,
      ...config
    };

    this.setPlaceholder('Type a command...');
    this.setInstructions([
      { command: '↑↓', purpose: 'Navigate' },
      { command: '↵', purpose: 'Execute' },
      { command: 'Esc', purpose: 'Cancel' }
    ]);

    this.registerDefaultCommands();
  }

  /**
   * Set keyboard shortcuts reference
   */
  setKeyboardShortcuts(shortcuts: KeyboardShortcuts): void {
    this.keyboardShortcuts = shortcuts;
    this.refreshShortcutCommands();
  }

  /**
   * Set schema for context-aware commands
   */
  setSchema(schema: UISchema): void {
    this.schema = schema;
    this.refreshFieldCommands();
  }

  /**
   * Set current settings for context
   */
  setSettings(settings: ThothSettings): void {
    this.settings = settings;
  }

  /**
   * Update current context
   */
  updateContext(context: Partial<ActionContext>): void {
    this.currentContext = { ...this.currentContext, ...context };
    this.refreshContextActions();
  }

  /**
   * Register a command
   */
  registerCommand(command: CommandPaletteItem): void {
    this.commands.set(command.id, command);
  }

  /**
   * Register multiple commands
   */
  registerCommands(commands: CommandPaletteItem[]): void {
    for (const command of commands) {
      this.registerCommand(command);
    }
  }

  /**
   * Register context action
   */
  registerContextAction(action: ContextAction): void {
    this.contextActions.set(action.id, action);
  }

  /**
   * Unregister command
   */
  unregisterCommand(id: string): boolean {
    return this.commands.delete(id);
  }

  /**
   * Get suggestions for fuzzy search
   */
  getItems(): CommandPaletteItem[] {
    const allCommands = Array.from(this.commands.values());
    const enabledCommands = allCommands.filter(cmd => cmd.enabled);

    // Add context actions if enabled
    if (this.config.enableContextActions) {
      const contextCommands = this.getContextualCommands();
      enabledCommands.push(...contextCommands);
    }

    // Sort by recent usage and relevance
    return this.sortCommands(enabledCommands);
  }

  /**
   * Get item text for fuzzy matching
   */
  getItemText(item: CommandPaletteItem): string {
    const parts = [item.title];

    if (item.description) {
      parts.push(item.description);
    }

    if (item.keywords) {
      parts.push(...item.keywords);
    }

    return parts.join(' ');
  }

  /**
   * Render suggestion item
   */
  renderSuggestion(match: FuzzyMatch<CommandPaletteItem>, el: HTMLElement): void {
    const item = match.item;

    el.className = 'thoth-command-item';

    // Icon and title
    const header = el.createEl('div', { cls: 'thoth-command-header' });

    if (item.icon) {
      const icon = header.createEl('span', { cls: 'thoth-command-icon' });
      icon.textContent = item.icon;
    }

    const title = header.createEl('span', { cls: 'thoth-command-title' });
    title.textContent = item.title;

    // Shortcut hint
    if (item.shortcut && this.config.showKeyboardShortcuts) {
      const shortcut = header.createEl('span', { cls: 'thoth-command-shortcut' });
      shortcut.textContent = item.shortcut;
    }

    // Description
    if (item.description) {
      const description = el.createEl('div', { cls: 'thoth-command-description' });
      description.textContent = item.description;
    }

    // Category badge
    const category = el.createEl('div', { cls: 'thoth-command-category' });
    category.textContent = this.formatCategory(item.category);
    category.className += ` thoth-category-${item.category}`;

    // Highlight fuzzy matches
    this.highlightMatches(title, match.match);
  }

  /**
   * Execute selected command
   */
  async onChooseItem(item: CommandPaletteItem): Promise<void> {
    // Add to recent commands
    this.addToRecentCommands(item.id);

    try {
      const result = item.action();
      if (result instanceof Promise) {
        await result;
      }
    } catch (error) {
      console.error(`Command execution failed for ${item.id}:`, error);
      // Could show error notification here
    }
  }

  /**
   * Register default commands
   */
  private registerDefaultCommands(): void {
    // Navigation commands
    this.registerCommand({
      id: 'nav-switch-ui-view',
      title: 'Switch to UI View',
      description: 'Switch to the form-based settings view',
      category: 'navigation',
      action: () => console.log('Switch to UI view'),
      icon: '🎨',
      keywords: ['tab', 'form', 'ui'],
      enabled: true
    });

    this.registerCommand({
      id: 'nav-switch-structured-json',
      title: 'Switch to Structured JSON',
      description: 'Switch to the organized JSON view',
      category: 'navigation',
      action: () => console.log('Switch to structured JSON'),
      icon: '📋',
      keywords: ['tab', 'json', 'structured'],
      enabled: true
    });

    this.registerCommand({
      id: 'nav-switch-raw-json',
      title: 'Switch to Raw JSON',
      description: 'Switch to the raw JSON editor',
      category: 'navigation',
      action: () => console.log('Switch to raw JSON'),
      icon: '📝',
      keywords: ['tab', 'json', 'raw', 'editor'],
      enabled: true
    });

    // Editing commands
    this.registerCommand({
      id: 'edit-format-json',
      title: 'Format JSON',
      description: 'Format JSON with proper indentation',
      category: 'editing',
      action: () => console.log('Format JSON'),
      icon: '✨',
      keywords: ['format', 'indent', 'beautify'],
      enabled: true
    });

    this.registerCommand({
      id: 'edit-validate-all',
      title: 'Validate All Settings',
      description: 'Run validation on all configuration fields',
      category: 'validation',
      action: () => console.log('Validate all'),
      icon: '✓',
      keywords: ['validate', 'check', 'verify'],
      enabled: true
    });

    this.registerCommand({
      id: 'edit-reset-field',
      title: 'Reset Field to Default',
      description: 'Reset the current field to its default value',
      category: 'editing',
      action: () => console.log('Reset field'),
      icon: '↶',
      keywords: ['reset', 'default', 'revert'],
      enabled: true
    });

    // View commands
    this.registerCommand({
      id: 'view-expand-all',
      title: 'Expand All Groups',
      description: 'Expand all collapsible setting groups',
      category: 'view',
      action: () => console.log('Expand all'),
      icon: '⤵',
      keywords: ['expand', 'open', 'show'],
      enabled: true
    });

    this.registerCommand({
      id: 'view-collapse-all',
      title: 'Collapse All Groups',
      description: 'Collapse all setting groups',
      category: 'view',
      action: () => console.log('Collapse all'),
      icon: '⤴',
      keywords: ['collapse', 'close', 'hide'],
      enabled: true
    });

    // Search commands
    this.registerCommand({
      id: 'search-open',
      title: 'Open Search',
      description: 'Open the settings search interface',
      category: 'search',
      action: () => console.log('Open search'),
      icon: '🔍',
      keywords: ['find', 'search', 'filter'],
      enabled: true
    });

    this.registerCommand({
      id: 'search-clear',
      title: 'Clear Search',
      description: 'Clear current search and filters',
      category: 'search',
      action: () => console.log('Clear search'),
      icon: '🗑',
      keywords: ['clear', 'reset', 'remove'],
      enabled: true
    });

    // Settings commands
    this.registerCommand({
      id: 'settings-export',
      title: 'Export Configuration',
      description: 'Export current settings to JSON file',
      category: 'settings',
      action: () => console.log('Export config'),
      icon: '📤',
      keywords: ['export', 'save', 'backup'],
      enabled: true
    });

    this.registerCommand({
      id: 'settings-import',
      title: 'Import Configuration',
      description: 'Import settings from JSON file',
      category: 'settings',
      action: () => console.log('Import config'),
      icon: '📥',
      keywords: ['import', 'load', 'restore'],
      enabled: true
    });

    // Tools commands
    this.registerCommand({
      id: 'tools-show-shortcuts',
      title: 'Show Keyboard Shortcuts',
      description: 'Display all available keyboard shortcuts',
      category: 'help',
      action: () => this.showShortcutsHelp(),
      icon: '⌨',
      keywords: ['keyboard', 'shortcuts', 'help', 'keys'],
      enabled: true
    });

    this.registerCommand({
      id: 'tools-performance-info',
      title: 'Show Performance Info',
      description: 'Display synchronization performance metrics',
      category: 'tools',
      action: () => console.log('Show performance info'),
      icon: '📊',
      keywords: ['performance', 'metrics', 'stats'],
      enabled: true
    });
  }

  /**
   * Refresh shortcut-based commands
   */
  private refreshShortcutCommands(): void {
    if (!this.keyboardShortcuts) return;

    const shortcuts = this.keyboardShortcuts.getAllShortcuts();

    for (const shortcut of shortcuts) {
      // Skip if command already exists
      if (this.commands.has(`shortcut-${shortcut.id}`)) continue;

      this.registerCommand({
        id: `shortcut-${shortcut.id}`,
        title: shortcut.description,
        description: `Execute: ${shortcut.description}`,
        category: 'editing',
        action: shortcut.action,
        shortcut: this.keyboardShortcuts!.formatShortcut(shortcut),
        keywords: [shortcut.id, ...shortcut.description.toLowerCase().split(' ')],
        enabled: shortcut.enabled
      });
    }
  }

  /**
   * Refresh field-specific commands
   */
  private refreshFieldCommands(): void {
    if (!this.schema) return;

    // Clear existing field commands
    const fieldCommandIds = Array.from(this.commands.keys())
      .filter(id => id.startsWith('field-'));

    for (const id of fieldCommandIds) {
      this.commands.delete(id);
    }

    // Add commands for each field
    for (const [fieldName, fieldSchema] of Object.entries(this.schema.fields)) {
      this.registerCommand({
        id: `field-${fieldName}`,
        title: `Go to ${fieldName}`,
        description: fieldSchema.description || `Navigate to ${fieldName} field`,
        category: 'navigation',
        action: () => this.navigateToField(fieldName),
        icon: '📍',
        keywords: [fieldName, fieldSchema.description || '', 'goto', 'navigate'],
        enabled: true
      });

      // Add edit command for each field
      this.registerCommand({
        id: `edit-${fieldName}`,
        title: `Edit ${fieldName}`,
        description: `Edit the ${fieldName} setting`,
        category: 'editing',
        action: () => this.editField(fieldName),
        icon: '✏',
        keywords: [fieldName, 'edit', 'modify', 'change'],
        enabled: true
      });
    }
  }

  /**
   * Get contextual commands based on current state
   */
  private getContextualCommands(): CommandPaletteItem[] {
    const contextCommands: CommandPaletteItem[] = [];

    // Add context actions as commands
    for (const action of this.contextActions.values()) {
      if (!action.condition || action.condition(this.currentContext)) {
        contextCommands.push({
          id: `context-${action.id}`,
          title: action.title,
          description: action.description,
          category: 'tools',
          action: () => action.action(this.currentContext),
          icon: action.icon,
          enabled: true
        });
      }
    }

    // Add recent commands if enabled
    if (this.config.showRecentCommands && this.recentCommands.length > 0) {
      const recentSection: CommandPaletteItem = {
        id: 'recent-separator',
        title: '--- Recent Commands ---',
        description: '',
        category: 'tools',
        action: () => {},
        enabled: false
      };
      contextCommands.unshift(recentSection);

      for (const commandId of this.recentCommands.slice(0, 5)) {
        const command = this.commands.get(commandId);
        if (command) {
          const recentCommand = { ...command };
          recentCommand.id = `recent-${command.id}`;
          recentCommand.title = `🕒 ${command.title}`;
          contextCommands.unshift(recentCommand);
        }
      }
    }

    return contextCommands;
  }

  /**
   * Sort commands by relevance and usage
   */
  private sortCommands(commands: CommandPaletteItem[]): CommandPaletteItem[] {
    return commands.sort((a, b) => {
      // Recent commands first
      const aIsRecent = this.recentCommands.includes(a.id);
      const bIsRecent = this.recentCommands.includes(b.id);

      if (aIsRecent && !bIsRecent) return -1;
      if (!aIsRecent && bIsRecent) return 1;

      // Then by score if available
      if (a.score !== undefined && b.score !== undefined) {
        return b.score - a.score;
      }

      // Then by category priority
      const categoryPriority: Record<CommandCategory, number> = {
        navigation: 1,
        editing: 2,
        search: 3,
        validation: 4,
        view: 5,
        settings: 6,
        tools: 7,
        help: 8
      };

      const aPriority = categoryPriority[a.category] || 9;
      const bPriority = categoryPriority[b.category] || 9;

      if (aPriority !== bPriority) {
        return aPriority - bPriority;
      }

      // Finally by alphabetical order
      return a.title.localeCompare(b.title);
    });
  }

  /**
   * Add command to recent list
   */
  private addToRecentCommands(commandId: string): void {
    // Remove if already exists
    const existingIndex = this.recentCommands.indexOf(commandId);
    if (existingIndex >= 0) {
      this.recentCommands.splice(existingIndex, 1);
    }

    // Add to beginning
    this.recentCommands.unshift(commandId);

    // Limit size
    if (this.recentCommands.length > 10) {
      this.recentCommands = this.recentCommands.slice(0, 10);
    }
  }

  /**
   * Navigate to specific field
   */
  private navigateToField(fieldName: string): void {
    // This would trigger navigation to the field in the active view
    console.log(`Navigate to field: ${fieldName}`);

    // Emit custom event that can be caught by the UI components
    const event = new CustomEvent('thoth-navigate-to-field', {
      detail: { fieldName, context: this.currentContext }
    });
    document.dispatchEvent(event);
  }

  /**
   * Edit specific field
   */
  private editField(fieldName: string): void {
    console.log(`Edit field: ${fieldName}`);

    const event = new CustomEvent('thoth-edit-field', {
      detail: { fieldName, context: this.currentContext }
    });
    document.dispatchEvent(event);
  }

  /**
   * Show keyboard shortcuts help
   */
  private showShortcutsHelp(): void {
    if (this.keyboardShortcuts) {
      const shortcuts = this.keyboardShortcuts.getAllShortcuts();
      this.displayShortcutsModal(shortcuts);
    }
  }

  /**
   * Display shortcuts in a modal
   */
  private displayShortcutsModal(shortcuts: KeyboardShortcut[]): void {
    const modal = new Modal(this.app);

    modal.titleEl.textContent = 'Keyboard Shortcuts';

    const content = modal.contentEl;
    content.addClass('thoth-shortcuts-modal');

    // Group shortcuts by context
    const groupedShortcuts = this.groupShortcutsByContext(shortcuts);

    for (const [context, contextShortcuts] of groupedShortcuts) {
      if (contextShortcuts.length === 0) continue;

      const section = content.createEl('div', { cls: 'thoth-shortcuts-section' });
      section.createEl('h3', { text: this.formatContext(context), cls: 'thoth-shortcuts-section-title' });

      const list = section.createEl('div', { cls: 'thoth-shortcuts-list' });

      for (const shortcut of contextShortcuts) {
        const item = list.createEl('div', { cls: 'thoth-shortcut-item' });

        const description = item.createEl('span', { cls: 'thoth-shortcut-description' });
        description.textContent = shortcut.description;

        const keys = item.createEl('span', { cls: 'thoth-shortcut-keys' });
        keys.textContent = this.keyboardShortcuts!.formatShortcut(shortcut);
      }
    }

    modal.open();
  }

  /**
   * Group shortcuts by context
   */
  private groupShortcutsByContext(shortcuts: KeyboardShortcut[]): Map<string, KeyboardShortcut[]> {
    const grouped = new Map<string, KeyboardShortcut[]>();

    for (const shortcut of shortcuts) {
      const contexts = shortcut.context || ['global'];

      for (const context of contexts) {
        if (!grouped.has(context)) {
          grouped.set(context, []);
        }
        grouped.get(context)!.push(shortcut);
      }
    }

    return grouped;
  }

  /**
   * Refresh context actions based on current state
   */
  private refreshContextActions(): void {
    // Register context-specific actions
    this.registerContextAction({
      id: 'fix-validation-errors',
      title: 'Fix Validation Errors',
      description: 'Automatically fix common validation issues',
      action: (context) => this.autoFixValidationErrors(context),
      icon: '🔧',
      condition: (context) => !!context.validationErrors && context.validationErrors.length > 0,
      priority: 1
    });

    this.registerContextAction({
      id: 'copy-field-value',
      title: 'Copy Field Value',
      description: 'Copy the current field value to clipboard',
      action: (context) => this.copyFieldValue(context),
      icon: '📋',
      condition: (context) => !!context.currentValue,
      priority: 2
    });

    this.registerContextAction({
      id: 'show-field-info',
      title: 'Show Field Information',
      description: 'Display detailed information about this field',
      action: (context) => this.showFieldInfo(context),
      icon: 'ℹ',
      condition: (context) => !!context.selectedField,
      priority: 3
    });
  }

  /**
   * Auto-fix validation errors
   */
  private async autoFixValidationErrors(context: ActionContext): Promise<void> {
    if (!context.validationErrors) return;

    console.log('Auto-fixing validation errors:', context.validationErrors);

    const event = new CustomEvent('thoth-auto-fix-errors', {
      detail: { errors: context.validationErrors, context }
    });
    document.dispatchEvent(event);
  }

  /**
   * Copy field value to clipboard
   */
  private async copyFieldValue(context: ActionContext): Promise<void> {
    if (context.currentValue === undefined) return;

    try {
      const valueStr = typeof context.currentValue === 'string'
        ? context.currentValue
        : JSON.stringify(context.currentValue, null, 2);

      await navigator.clipboard.writeText(valueStr);
      console.log('Field value copied to clipboard');
    } catch (error) {
      console.error('Failed to copy field value:', error);
    }
  }

  /**
   * Show field information
   */
  private showFieldInfo(context: ActionContext): void {
    if (!context.selectedField || !context.fieldSchema) return;

    const modal = new Modal(this.app);
    modal.titleEl.textContent = `Field: ${context.selectedField}`;

    const content = modal.contentEl;
    content.addClass('thoth-field-info-modal');

    // Field details
    if (context.fieldSchema.description) {
      content.createEl('p', { text: context.fieldSchema.description });
    }

    content.createEl('p', { text: `Type: ${context.fieldSchema.type}` });

    if (context.fieldSchema.required) {
      content.createEl('p', { text: 'Required field', cls: 'thoth-field-required' });
    }

    if (context.currentValue !== undefined) {
      content.createEl('p', { text: `Current value: ${JSON.stringify(context.currentValue)}` });
    }

    modal.open();
  }

  /**
   * Format category name for display
   */
  private formatCategory(category: CommandCategory): string {
    const categoryNames: Record<CommandCategory, string> = {
      navigation: 'Navigation',
      editing: 'Editing',
      validation: 'Validation',
      view: 'View',
      search: 'Search',
      settings: 'Settings',
      tools: 'Tools',
      help: 'Help'
    };

    return categoryNames[category] || category;
  }

  /**
   * Format context name for display
   */
  private formatContext(context: string): string {
    const contextNames: Record<string, string> = {
      global: 'Global',
      'json-editor': 'JSON Editor',
      'ui-view': 'UI View',
      'structured-json': 'Structured JSON',
      search: 'Search',
      'command-palette': 'Command Palette'
    };

    return contextNames[context] || context;
  }

  /**
   * Highlight fuzzy matches in text
   */
  private highlightMatches(element: HTMLElement, match: any): void {
    if (!match || !match.matches) return;

    // This is a simplified implementation
    // In a real scenario, you'd properly highlight the matched characters
    const text = element.textContent || '';
    const highlightedText = this.addHighlightSpans(text, match.matches);
    element.innerHTML = highlightedText;
  }

  /**
   * Add highlight spans to text
   */
  private addHighlightSpans(text: string, matches: number[][]): string {
    if (!matches || matches.length === 0) return text;

    let result = '';
    let lastIndex = 0;

    // Sort matches by start position
    const sortedMatches = matches.sort((a, b) => a[0] - b[0]);

    for (const [start, end] of sortedMatches) {
      // Add text before match
      result += text.substring(lastIndex, start);

      // Add highlighted match
      const matchText = text.substring(start, end + 1);
      result += `<span class="thoth-command-highlight">${matchText}</span>`;

      lastIndex = end + 1;
    }

    // Add remaining text
    result += text.substring(lastIndex);

    return result;
  }
}

/**
 * Command palette factory
 */
export class CommandPaletteFactory {
  /**
   * Create command palette with default configuration
   */
  static create(app: App): CommandPalette {
    return new CommandPalette(app);
  }

  /**
   * Create command palette with keyboard shortcuts integration
   */
  static createWithShortcuts(app: App, shortcuts: KeyboardShortcuts): CommandPalette {
    const palette = new CommandPalette(app);
    palette.setKeyboardShortcuts(shortcuts);
    return palette;
  }

  /**
   * Create command palette with full integration
   */
  static createForSettingsInterface(
    app: App,
    shortcuts: KeyboardShortcuts,
    schema: UISchema,
    settings: ThothSettings
  ): CommandPalette {
    const palette = new CommandPalette(app, {
      maxResults: 50,
      showRecentCommands: true,
      showKeyboardShortcuts: true,
      groupByCategory: true,
      enableContextActions: true
    });

    palette.setKeyboardShortcuts(shortcuts);
    palette.setSchema(schema);
    palette.setSettings(settings);

    return palette;
  }
}

/**
 * Context action manager for dynamic action registration
 */
export class ContextActionManager {
  private actions = new Map<string, ContextAction>();
  private currentContext: ActionContext = {};

  /**
   * Register context action
   */
  register(action: ContextAction): void {
    this.actions.set(action.id, action);
  }

  /**
   * Unregister context action
   */
  unregister(id: string): boolean {
    return this.actions.delete(id);
  }

  /**
   * Update current context
   */
  updateContext(context: Partial<ActionContext>): void {
    this.currentContext = { ...this.currentContext, ...context };
  }

  /**
   * Get applicable actions for current context
   */
  getApplicableActions(): ContextAction[] {
    return Array.from(this.actions.values())
      .filter(action => !action.condition || action.condition(this.currentContext))
      .sort((a, b) => a.priority - b.priority);
  }

  /**
   * Execute action by ID
   */
  async executeAction(id: string): Promise<boolean> {
    const action = this.actions.get(id);
    if (!action) return false;

    if (action.condition && !action.condition(this.currentContext)) {
      return false;
    }

    try {
      const result = action.action(this.currentContext);
      if (result instanceof Promise) {
        await result;
      }
      return true;
    } catch (error) {
      console.error(`Context action failed for ${id}:`, error);
      return false;
    }
  }

  /**
   * Get action by ID
   */
  getAction(id: string): ContextAction | undefined {
    return this.actions.get(id);
  }

  /**
   * Clear all actions
   */
  clear(): void {
    this.actions.clear();
  }

  /**
   * Destroy and clean up
   */
  destroy(): void {
    this.clear();
    this.currentContext = {};
  }
}

/**
 * Initialize command palette styles
 */
export function initializeCommandPaletteStyles(): void {
  if (document.getElementById('thoth-command-palette-styles')) {
    return; // Styles already loaded
  }

  const style = document.createElement('style');
  style.id = 'thoth-command-palette-styles';
  style.textContent = `
    /* Command palette modal */
    .thoth-command-item {
      padding: 8px 12px;
      border-radius: 4px;
      margin-bottom: 1px;
      cursor: pointer;
      transition: background 0.1s ease;
    }

    .thoth-command-item:hover {
      background: var(--background-modifier-hover);
    }

    .thoth-command-item.is-selected {
      background: var(--background-modifier-active-hover);
    }

    .thoth-command-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 2px;
    }

    .thoth-command-icon {
      font-size: 14px;
      margin-right: 8px;
      opacity: 0.8;
    }

    .thoth-command-title {
      flex: 1;
      font-weight: 500;
      color: var(--text-normal);
    }

    .thoth-command-shortcut {
      font-size: 10px;
      background: var(--background-modifier-form-field);
      padding: 2px 6px;
      border-radius: 3px;
      font-family: monospace;
      color: var(--text-muted);
      margin-left: 8px;
    }

    .thoth-command-description {
      font-size: 11px;
      color: var(--text-muted);
      margin-left: 22px;
      line-height: 1.3;
    }

    .thoth-command-category {
      position: absolute;
      right: 8px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 9px;
      background: var(--interactive-accent);
      color: white;
      padding: 1px 4px;
      border-radius: 2px;
      opacity: 0.7;
    }

    /* Category colors */
    .thoth-category-navigation { background: var(--color-blue); }
    .thoth-category-editing { background: var(--color-green); }
    .thoth-category-validation { background: var(--color-orange); }
    .thoth-category-view { background: var(--color-purple); }
    .thoth-category-search { background: var(--color-cyan); }
    .thoth-category-settings { background: var(--color-yellow); }
    .thoth-category-tools { background: var(--color-gray); }
    .thoth-category-help { background: var(--color-pink); }

    /* Command highlighting */
    .thoth-command-highlight {
      background: var(--text-highlight-bg);
      color: var(--text-normal);
      font-weight: 600;
      border-radius: 2px;
      padding: 0 1px;
    }

    /* Shortcuts modal */
    .thoth-shortcuts-modal {
      max-height: 70vh;
      overflow-y: auto;
    }

    .thoth-shortcuts-section {
      margin-bottom: 20px;
    }

    .thoth-shortcuts-section-title {
      font-size: 14px;
      color: var(--text-normal);
      margin: 0 0 8px 0;
      padding-bottom: 4px;
      border-bottom: 1px solid var(--background-modifier-border);
    }

    .thoth-shortcuts-list {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .thoth-shortcut-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 4px 0;
    }

    .thoth-shortcut-description {
      font-size: 12px;
      color: var(--text-normal);
    }

    .thoth-shortcut-keys {
      font-size: 11px;
      color: var(--text-muted);
      font-family: monospace;
      background: var(--background-modifier-form-field);
      padding: 2px 6px;
      border-radius: 3px;
      border: 1px solid var(--background-modifier-border);
    }

    /* Field info modal */
    .thoth-field-info-modal p {
      margin: 8px 0;
      line-height: 1.4;
    }

    .thoth-field-required {
      color: var(--color-red);
      font-weight: 500;
    }

    /* Responsive design */
    @media (max-width: 600px) {
      .thoth-command-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 4px;
      }

      .thoth-command-shortcut {
        margin-left: 0;
      }

      .thoth-shortcuts-modal {
        padding: 12px;
      }

      .thoth-shortcut-item {
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
      }
    }

    /* Dark theme adjustments */
    .theme-dark .thoth-command-highlight {
      background: rgba(255, 255, 0, 0.3);
    }

    /* Animation for command palette */
    .thoth-command-item {
      animation: fadeInCommand 0.1s ease;
    }

    @keyframes fadeInCommand {
      from {
        opacity: 0;
        transform: translateY(2px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
  `;

  document.head.appendChild(style);
}
