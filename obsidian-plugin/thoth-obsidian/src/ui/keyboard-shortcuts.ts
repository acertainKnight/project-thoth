import { Platform } from 'obsidian';

/**
 * Keyboard shortcut configuration
 */
export interface KeyboardShortcut {
  id: string;
  key: string;
  modifiers: KeyModifier[];
  description: string;
  action: () => void | Promise<void>;
  context?: ShortcutContext[];
  enabled: boolean;
  preventDefault?: boolean;
  stopPropagation?: boolean;
}

/**
 * Key modifiers
 */
export type KeyModifier = 'Ctrl' | 'Shift' | 'Alt' | 'Meta' | 'Cmd';

/**
 * Shortcut contexts
 */
export type ShortcutContext = 'global' | 'json-editor' | 'ui-view' | 'structured-json' | 'search' | 'command-palette';

/**
 * Platform-specific key mapping
 */
interface PlatformKeyMap {
  primary: KeyModifier; // Ctrl on Windows/Linux, Cmd on Mac
  secondary: KeyModifier; // Alt on Windows/Linux, Option on Mac
  tertiary: KeyModifier; // Meta on Windows/Linux, Ctrl on Mac
}

/**
 * Keyboard event information
 */
interface KeyboardEventInfo {
  key: string;
  code: string;
  modifiers: Set<KeyModifier>;
  target: EventTarget | null;
  context: ShortcutContext;
}

/**
 * Shortcut registration options
 */
interface ShortcutOptions {
  global?: boolean;
  context?: ShortcutContext[];
  preventDefault?: boolean;
  stopPropagation?: boolean;
  enabled?: boolean;
}

/**
 * Enhanced keyboard shortcuts system with platform support
 */
export class KeyboardShortcuts {
  private shortcuts = new Map<string, KeyboardShortcut>();
  private contextStack: ShortcutContext[] = ['global'];
  private platformKeys: PlatformKeyMap;
  private isEnabled = true;
  private globalEventListener?: (event: KeyboardEvent) => void;
  private contextEventListeners = new Map<HTMLElement, (event: KeyboardEvent) => void>();

  constructor() {
    this.platformKeys = this.getPlatformKeyMap();
    this.setupGlobalEventListener();
  }

  /**
   * Register a keyboard shortcut
   */
  register(
    id: string,
    key: string,
    modifiers: KeyModifier[],
    description: string,
    action: () => void | Promise<void>,
    options: ShortcutOptions = {}
  ): void {
    const shortcut: KeyboardShortcut = {
      id,
      key: key.toLowerCase(),
      modifiers: this.normalizePlatformModifiers(modifiers),
      description,
      action,
      context: options.context || ['global'],
      enabled: options.enabled !== false,
      preventDefault: options.preventDefault !== false,
      stopPropagation: options.stopPropagation !== false
    };

    this.shortcuts.set(id, shortcut);
  }

  /**
   * Unregister a keyboard shortcut
   */
  unregister(id: string): boolean {
    return this.shortcuts.delete(id);
  }

  /**
   * Enable/disable a specific shortcut
   */
  setEnabled(id: string, enabled: boolean): boolean {
    const shortcut = this.shortcuts.get(id);
    if (shortcut) {
      shortcut.enabled = enabled;
      return true;
    }
    return false;
  }

  /**
   * Enable/disable all shortcuts
   */
  setGlobalEnabled(enabled: boolean): void {
    this.isEnabled = enabled;
  }

  /**
   * Push context onto stack
   */
  pushContext(context: ShortcutContext): void {
    this.contextStack.push(context);
  }

  /**
   * Pop context from stack
   */
  popContext(): ShortcutContext | undefined {
    if (this.contextStack.length > 1) {
      return this.contextStack.pop();
    }
    return undefined;
  }

  /**
   * Get current context
   */
  getCurrentContext(): ShortcutContext {
    return this.contextStack[this.contextStack.length - 1];
  }

  /**
   * Register shortcuts for JSON editor context
   */
  registerJSONEditorShortcuts(jsonEditor: any): void {
    // Format JSON
    this.register(
      'json-format',
      'f',
      ['Ctrl', 'Shift'],
      'Format JSON',
      () => jsonEditor.formatJSON(),
      { context: ['json-editor'] }
    );

    // Go to line
    this.register(
      'json-goto-line',
      'g',
      ['Ctrl'],
      'Go to line',
      () => this.showGoToLineDialog(jsonEditor),
      { context: ['json-editor'] }
    );

    // Validate JSON
    this.register(
      'json-validate',
      'v',
      ['Ctrl', 'Shift'],
      'Validate JSON',
      () => jsonEditor.validateContent(),
      { context: ['json-editor'] }
    );

    // Find and replace (future feature)
    this.register(
      'json-find-replace',
      'h',
      ['Ctrl'],
      'Find and replace',
      () => console.log('Find and replace not implemented yet'),
      { context: ['json-editor'], enabled: false }
    );

    // Toggle line numbers
    this.register(
      'json-toggle-line-numbers',
      'l',
      ['Ctrl', 'Shift'],
      'Toggle line numbers',
      () => this.toggleLineNumbers(jsonEditor),
      { context: ['json-editor'] }
    );
  }

  /**
   * Register global application shortcuts
   */
  registerGlobalShortcuts(callbacks: {
    save?: () => void | Promise<void>;
    search?: () => void;
    commandPalette?: () => void;
    switchTab?: (tabIndex: number) => void;
    undo?: () => void;
    redo?: () => void;
    reset?: () => void;
  }): void {
    // Save
    if (callbacks.save) {
      this.register(
        'global-save',
        's',
        ['Ctrl'],
        'Save settings',
        callbacks.save,
        { context: ['global', 'json-editor', 'ui-view', 'structured-json'] }
      );
    }

    // Search
    if (callbacks.search) {
      this.register(
        'global-search',
        'f',
        ['Ctrl'],
        'Open search',
        callbacks.search,
        { context: ['global', 'ui-view', 'structured-json'] }
      );
    }

    // Command palette
    if (callbacks.commandPalette) {
      this.register(
        'global-command-palette',
        'p',
        ['Ctrl', 'Shift'],
        'Open command palette',
        callbacks.commandPalette
      );
    }

    // Tab switching
    if (callbacks.switchTab) {
      for (let i = 1; i <= 3; i++) {
        this.register(
          `global-tab-${i}`,
          i.toString(),
          ['Ctrl'],
          `Switch to tab ${i}`,
          () => callbacks.switchTab!(i - 1)
        );
      }
    }

    // Undo/Redo
    if (callbacks.undo) {
      this.register(
        'global-undo',
        'z',
        ['Ctrl'],
        'Undo',
        callbacks.undo
      );
    }

    if (callbacks.redo) {
      this.register(
        'global-redo',
        'y',
        ['Ctrl'],
        'Redo',
        callbacks.redo
      );

      // Alternative redo shortcut
      this.register(
        'global-redo-alt',
        'z',
        ['Ctrl', 'Shift'],
        'Redo (alternative)',
        callbacks.redo
      );
    }

    // Reset
    if (callbacks.reset) {
      this.register(
        'global-reset',
        'r',
        ['Ctrl', 'Shift'],
        'Reset to defaults',
        callbacks.reset
      );
    }
  }

  /**
   * Register navigation shortcuts
   */
  registerNavigationShortcuts(callbacks: {
    goToSymbol?: () => void;
    quickOpen?: () => void;
    nextField?: () => void;
    previousField?: () => void;
    expandAll?: () => void;
    collapseAll?: () => void;
  }): void {
    // Go to symbol (field)
    if (callbacks.goToSymbol) {
      this.register(
        'nav-goto-symbol',
        'o',
        ['Ctrl', 'Shift'],
        'Go to symbol (field)',
        callbacks.goToSymbol
      );
    }

    // Quick open
    if (callbacks.quickOpen) {
      this.register(
        'nav-quick-open',
        'p',
        ['Ctrl'],
        'Quick open (go to setting)',
        callbacks.quickOpen
      );
    }

    // Field navigation
    if (callbacks.nextField) {
      this.register(
        'nav-next-field',
        'ArrowDown',
        ['Ctrl'],
        'Next field',
        callbacks.nextField,
        { context: ['ui-view', 'structured-json'] }
      );
    }

    if (callbacks.previousField) {
      this.register(
        'nav-previous-field',
        'ArrowUp',
        ['Ctrl'],
        'Previous field',
        callbacks.previousField,
        { context: ['ui-view', 'structured-json'] }
      );
    }

    // Expand/collapse
    if (callbacks.expandAll) {
      this.register(
        'nav-expand-all',
        'e',
        ['Ctrl', 'Shift'],
        'Expand all groups',
        callbacks.expandAll,
        { context: ['structured-json'] }
      );
    }

    if (callbacks.collapseAll) {
      this.register(
        'nav-collapse-all',
        'c',
        ['Ctrl', 'Shift'],
        'Collapse all groups',
        callbacks.collapseAll,
        { context: ['structured-json'] }
      );
    }
  }

  /**
   * Bind shortcuts to a specific element
   */
  bindToElement(element: HTMLElement, context: ShortcutContext): void {
    const eventListener = (event: KeyboardEvent) => {
      this.handleKeyboardEvent(event, context);
    };

    element.addEventListener('keydown', eventListener);
    this.contextEventListeners.set(element, eventListener);
  }

  /**
   * Unbind shortcuts from element
   */
  unbindFromElement(element: HTMLElement): void {
    const eventListener = this.contextEventListeners.get(element);
    if (eventListener) {
      element.removeEventListener('keydown', eventListener);
      this.contextEventListeners.delete(element);
    }
  }

  /**
   * Get all registered shortcuts
   */
  getAllShortcuts(): KeyboardShortcut[] {
    return Array.from(this.shortcuts.values());
  }

  /**
   * Get shortcuts for specific context
   */
  getShortcutsForContext(context: ShortcutContext): KeyboardShortcut[] {
    return Array.from(this.shortcuts.values()).filter(shortcut =>
      shortcut.context?.includes(context) || shortcut.context?.includes('global')
    );
  }

  /**
   * Format shortcut for display
   */
  formatShortcut(shortcut: KeyboardShortcut): string {
    const modifiers = shortcut.modifiers.map(mod => this.formatModifier(mod));
    const key = this.formatKey(shortcut.key);

    return [...modifiers, key].join(' + ');
  }

  /**
   * Check if shortcut conflicts with existing ones
   */
  hasConflict(key: string, modifiers: KeyModifier[], context: ShortcutContext[]): KeyboardShortcut | null {
    const normalizedKey = key.toLowerCase();
    const normalizedModifiers = this.normalizePlatformModifiers(modifiers);

    for (const shortcut of this.shortcuts.values()) {
      if (shortcut.key === normalizedKey &&
          this.modifiersEqual(shortcut.modifiers, normalizedModifiers) &&
          this.contextsOverlap(shortcut.context || ['global'], context)) {
        return shortcut;
      }
    }

    return null;
  }

  /**
   * Destroy keyboard shortcuts and clean up
   */
  destroy(): void {
    // Remove global event listener
    if (this.globalEventListener) {
      document.removeEventListener('keydown', this.globalEventListener);
    }

    // Remove context event listeners
    for (const [element, listener] of this.contextEventListeners) {
      element.removeEventListener('keydown', listener);
    }

    this.shortcuts.clear();
    this.contextEventListeners.clear();
    this.contextStack = ['global'];
  }

  /**
   * Get platform-specific key mapping
   */
  private getPlatformKeyMap(): PlatformKeyMap {
    const isMac = Platform.isMacOS;

    return {
      primary: isMac ? 'Cmd' : 'Ctrl',
      secondary: 'Alt',
      tertiary: isMac ? 'Ctrl' : 'Meta'
    };
  }

  /**
   * Normalize modifiers for current platform
   */
  private normalizePlatformModifiers(modifiers: KeyModifier[]): KeyModifier[] {
    return modifiers.map(modifier => {
      switch (modifier) {
        case 'Ctrl':
          return Platform.isMacOS ? 'Cmd' : 'Ctrl';
        case 'Cmd':
          return Platform.isMacOS ? 'Cmd' : 'Ctrl';
        case 'Meta':
          return Platform.isMacOS ? 'Cmd' : 'Meta';
        default:
          return modifier;
      }
    });
  }

  /**
   * Setup global event listener
   */
  private setupGlobalEventListener(): void {
    this.globalEventListener = (event: KeyboardEvent) => {
      if (!this.isEnabled) return;

      this.handleKeyboardEvent(event, 'global');
    };

    document.addEventListener('keydown', this.globalEventListener);
  }

  /**
   * Handle keyboard events
   */
  private handleKeyboardEvent(event: KeyboardEvent, context: ShortcutContext): void {
    if (!this.isEnabled) return;

    const eventInfo = this.parseKeyboardEvent(event, context);
    const matchingShortcut = this.findMatchingShortcut(eventInfo);

    if (matchingShortcut && matchingShortcut.enabled) {
      if (matchingShortcut.preventDefault) {
        event.preventDefault();
      }

      if (matchingShortcut.stopPropagation) {
        event.stopPropagation();
      }

      try {
        const result = matchingShortcut.action();
        if (result instanceof Promise) {
          result.catch(error => {
            console.error(`Shortcut action failed for ${matchingShortcut.id}:`, error);
          });
        }
      } catch (error) {
        console.error(`Shortcut action failed for ${matchingShortcut.id}:`, error);
      }
    }
  }

  /**
   * Parse keyboard event into structured information
   */
  private parseKeyboardEvent(event: KeyboardEvent, context: ShortcutContext): KeyboardEventInfo {
    const modifiers = new Set<KeyModifier>();

    if (event.ctrlKey) modifiers.add('Ctrl');
    if (event.shiftKey) modifiers.add('Shift');
    if (event.altKey) modifiers.add('Alt');
    if (event.metaKey) modifiers.add('Meta');

    // Normalize for platform
    const normalizedModifiers = new Set(
      this.normalizePlatformModifiers(Array.from(modifiers))
    );

    return {
      key: event.key.toLowerCase(),
      code: event.code,
      modifiers: normalizedModifiers,
      target: event.target,
      context
    };
  }

  /**
   * Find matching shortcut for event
   */
  private findMatchingShortcut(eventInfo: KeyboardEventInfo): KeyboardShortcut | null {
    const currentContext = this.getCurrentContext();

    for (const shortcut of this.shortcuts.values()) {
      if (!shortcut.enabled) continue;

      // Check if shortcut applies to current context
      const appliesToContext = shortcut.context?.includes(currentContext) ||
                              shortcut.context?.includes('global') ||
                              shortcut.context?.includes(eventInfo.context);

      if (!appliesToContext) continue;

      // Check key match
      if (shortcut.key !== eventInfo.key) continue;

      // Check modifier match
      if (!this.modifiersMatch(shortcut.modifiers, eventInfo.modifiers)) continue;

      return shortcut;
    }

    return null;
  }

  /**
   * Check if modifiers match
   */
  private modifiersMatch(required: KeyModifier[], pressed: Set<KeyModifier>): boolean {
    const requiredSet = new Set(required);

    // All required modifiers must be pressed
    for (const modifier of requiredSet) {
      if (!pressed.has(modifier)) return false;
    }

    // No extra modifiers should be pressed
    for (const modifier of pressed) {
      if (!requiredSet.has(modifier)) return false;
    }

    return true;
  }

  /**
   * Check if modifiers are equal
   */
  private modifiersEqual(modifiers1: KeyModifier[], modifiers2: KeyModifier[]): boolean {
    const set1 = new Set(modifiers1);
    const set2 = new Set(modifiers2);

    if (set1.size !== set2.size) return false;

    for (const modifier of set1) {
      if (!set2.has(modifier)) return false;
    }

    return true;
  }

  /**
   * Check if contexts overlap
   */
  private contextsOverlap(contexts1: ShortcutContext[], contexts2: ShortcutContext[]): boolean {
    return contexts1.some(context => contexts2.includes(context) || context === 'global');
  }

  /**
   * Format modifier for display
   */
  private formatModifier(modifier: KeyModifier): string {
    if (Platform.isMacOS) {
      switch (modifier) {
        case 'Cmd': return '⌘';
        case 'Ctrl': return '⌃';
        case 'Alt': return '⌥';
        case 'Shift': return '⇧';
        case 'Meta': return '⌘';
        default: return modifier;
      }
    } else {
      return modifier;
    }
  }

  /**
   * Format key for display
   */
  private formatKey(key: string): string {
    const keyMap: Record<string, string> = {
      ' ': 'Space',
      'arrowup': '↑',
      'arrowdown': '↓',
      'arrowleft': '←',
      'arrowright': '→',
      'enter': 'Enter',
      'escape': 'Esc',
      'backspace': '⌫',
      'delete': 'Del',
      'tab': 'Tab'
    };

    return keyMap[key.toLowerCase()] || key.toUpperCase();
  }

  /**
   * Show go to line dialog for JSON editor
   */
  private async showGoToLineDialog(jsonEditor: any): Promise<void> {
    const input = prompt('Go to line:');
    if (input && jsonEditor.goToLine) {
      const lineNumber = parseInt(input);
      if (!isNaN(lineNumber)) {
        jsonEditor.goToLine(lineNumber);
      }
    }
  }

  /**
   * Toggle line numbers in JSON editor
   */
  private toggleLineNumbers(jsonEditor: any): void {
    // This would need to be implemented in the JSON editor
    console.log('Toggle line numbers:', jsonEditor);
  }
}

/**
 * Keyboard shortcuts factory for creating configured instances
 */
export class KeyboardShortcutsFactory {
  /**
   * Create keyboard shortcuts with default configuration
   */
  static create(): KeyboardShortcuts {
    return new KeyboardShortcuts();
  }

  /**
   * Create keyboard shortcuts with JSON editor bindings
   */
  static createWithJSONEditor(jsonEditor: any): KeyboardShortcuts {
    const shortcuts = new KeyboardShortcuts();
    shortcuts.registerJSONEditorShortcuts(jsonEditor);
    return shortcuts;
  }

  /**
   * Create keyboard shortcuts with global bindings
   */
  static createWithGlobalShortcuts(callbacks: {
    save?: () => void | Promise<void>;
    search?: () => void;
    commandPalette?: () => void;
    switchTab?: (tabIndex: number) => void;
    undo?: () => void;
    redo?: () => void;
    reset?: () => void;
  }): KeyboardShortcuts {
    const shortcuts = new KeyboardShortcuts();
    shortcuts.registerGlobalShortcuts(callbacks);
    return shortcuts;
  }

  /**
   * Create comprehensive keyboard shortcuts for settings interface
   */
  static createForSettingsInterface(
    jsonEditor: any,
    globalCallbacks: {
      save?: () => void | Promise<void>;
      search?: () => void;
      commandPalette?: () => void;
      switchTab?: (tabIndex: number) => void;
      undo?: () => void;
      redo?: () => void;
      reset?: () => void;
    },
    navigationCallbacks: {
      goToSymbol?: () => void;
      quickOpen?: () => void;
      nextField?: () => void;
      previousField?: () => void;
      expandAll?: () => void;
      collapseAll?: () => void;
    }
  ): KeyboardShortcuts {
    const shortcuts = new KeyboardShortcuts();

    shortcuts.registerGlobalShortcuts(globalCallbacks);
    shortcuts.registerNavigationShortcuts(navigationCallbacks);

    if (jsonEditor) {
      shortcuts.registerJSONEditorShortcuts(jsonEditor);
    }

    return shortcuts;
  }
}

/**
 * Shortcut configuration presets
 */
export class ShortcutPresets {
  /**
   * VS Code-like shortcuts
   */
  static getVSCodePreset(): Array<{
    id: string;
    key: string;
    modifiers: KeyModifier[];
    description: string;
    context?: ShortcutContext[];
  }> {
    return [
      { id: 'save', key: 's', modifiers: ['Ctrl'], description: 'Save' },
      { id: 'find', key: 'f', modifiers: ['Ctrl'], description: 'Find' },
      { id: 'replace', key: 'h', modifiers: ['Ctrl'], description: 'Replace' },
      { id: 'goto-line', key: 'g', modifiers: ['Ctrl'], description: 'Go to Line' },
      { id: 'command-palette', key: 'p', modifiers: ['Ctrl', 'Shift'], description: 'Command Palette' },
      { id: 'quick-open', key: 'p', modifiers: ['Ctrl'], description: 'Quick Open' },
      { id: 'undo', key: 'z', modifiers: ['Ctrl'], description: 'Undo' },
      { id: 'redo', key: 'y', modifiers: ['Ctrl'], description: 'Redo' },
      { id: 'format', key: 'f', modifiers: ['Ctrl', 'Shift'], description: 'Format Document' },
      { id: 'toggle-comment', key: '/', modifiers: ['Ctrl'], description: 'Toggle Comment' },
      { id: 'tab-1', key: '1', modifiers: ['Ctrl'], description: 'Tab 1' },
      { id: 'tab-2', key: '2', modifiers: ['Ctrl'], description: 'Tab 2' },
      { id: 'tab-3', key: '3', modifiers: ['Ctrl'], description: 'Tab 3' }
    ];
  }

  /**
   * JSON editor specific shortcuts
   */
  static getJSONEditorPreset(): Array<{
    id: string;
    key: string;
    modifiers: KeyModifier[];
    description: string;
    context?: ShortcutContext[];
  }> {
    return [
      { id: 'format-json', key: 'f', modifiers: ['Ctrl', 'Shift'], description: 'Format JSON', context: ['json-editor'] },
      { id: 'validate-json', key: 'v', modifiers: ['Ctrl', 'Shift'], description: 'Validate JSON', context: ['json-editor'] },
      { id: 'minify-json', key: 'm', modifiers: ['Ctrl', 'Shift'], description: 'Minify JSON', context: ['json-editor'] },
      { id: 'goto-line', key: 'g', modifiers: ['Ctrl'], description: 'Go to Line', context: ['json-editor'] },
      { id: 'find-replace', key: 'h', modifiers: ['Ctrl'], description: 'Find and Replace', context: ['json-editor'] },
      { id: 'select-all', key: 'a', modifiers: ['Ctrl'], description: 'Select All', context: ['json-editor'] },
      { id: 'copy', key: 'c', modifiers: ['Ctrl'], description: 'Copy', context: ['json-editor'] },
      { id: 'paste', key: 'v', modifiers: ['Ctrl'], description: 'Paste', context: ['json-editor'] },
      { id: 'cut', key: 'x', modifiers: ['Ctrl'], description: 'Cut', context: ['json-editor'] }
    ];
  }

  /**
   * Accessibility shortcuts
   */
  static getAccessibilityPreset(): Array<{
    id: string;
    key: string;
    modifiers: KeyModifier[];
    description: string;
    context?: ShortcutContext[];
  }> {
    return [
      { id: 'focus-search', key: 'f', modifiers: ['Alt'], description: 'Focus Search' },
      { id: 'focus-content', key: 'c', modifiers: ['Alt'], description: 'Focus Content' },
      { id: 'next-tab', key: 'Tab', modifiers: ['Ctrl'], description: 'Next Tab' },
      { id: 'previous-tab', key: 'Tab', modifiers: ['Ctrl', 'Shift'], description: 'Previous Tab' },
      { id: 'announce-context', key: 'a', modifiers: ['Alt', 'Shift'], description: 'Announce Context' },
      { id: 'read-errors', key: 'e', modifiers: ['Alt'], description: 'Read Validation Errors' }
    ];
  }
}

/**
 * Initialize keyboard shortcuts styles
 */
export function initializeKeyboardShortcutsStyles(): void {
  if (document.getElementById('thoth-keyboard-shortcuts-styles')) {
    return; // Styles already loaded
  }

  const style = document.createElement('style');
  style.id = 'thoth-keyboard-shortcuts-styles';
  style.textContent = `
    /* Keyboard shortcut indicators */
    .thoth-shortcut-hint {
      font-size: 10px;
      color: var(--text-muted);
      background: var(--background-modifier-form-field);
      padding: 1px 4px;
      border-radius: 2px;
      margin-left: 4px;
      font-family: monospace;
      opacity: 0.7;
    }

    .thoth-shortcut-hint:hover {
      opacity: 1;
    }

    /* Shortcut overlay for help */
    .thoth-shortcuts-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      z-index: 10000;
      display: flex;
      align-items: center;
      justify-content: center;
      animation: fadeIn 0.2s ease;
    }

    .thoth-shortcuts-panel {
      background: var(--background-primary);
      border: 1px solid var(--background-modifier-border);
      border-radius: 8px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
      max-width: 600px;
      max-height: 80vh;
      overflow-y: auto;
      animation: slideIn 0.2s ease;
    }

    .thoth-shortcuts-header {
      padding: 16px 20px;
      border-bottom: 1px solid var(--background-modifier-border);
      background: var(--background-secondary);
    }

    .thoth-shortcuts-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-normal);
      margin: 0;
    }

    .thoth-shortcuts-subtitle {
      font-size: 12px;
      color: var(--text-muted);
      margin: 4px 0 0 0;
    }

    .thoth-shortcuts-content {
      padding: 16px 20px;
    }

    .thoth-shortcuts-group {
      margin-bottom: 20px;
    }

    .thoth-shortcuts-group:last-child {
      margin-bottom: 0;
    }

    .thoth-shortcuts-group-title {
      font-size: 14px;
      font-weight: 500;
      color: var(--text-normal);
      margin: 0 0 8px 0;
      padding-bottom: 4px;
      border-bottom: 1px solid var(--background-modifier-border);
    }

    .thoth-shortcuts-list {
      display: flex;
      flex-direction: column;
      gap: 4px;
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

    /* Animations */
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    @keyframes slideIn {
      from {
        opacity: 0;
        transform: scale(0.95) translateY(-20px);
      }
      to {
        opacity: 1;
        transform: scale(1) translateY(0);
      }
    }

    /* Context indicators */
    .thoth-context-indicator {
      position: fixed;
      top: 10px;
      right: 10px;
      background: var(--interactive-accent);
      color: white;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 500;
      opacity: 0.8;
      pointer-events: none;
      z-index: 1000;
      transition: opacity 0.2s ease;
    }

    .thoth-context-indicator.hidden {
      opacity: 0;
    }

    /* Responsive design */
    @media (max-width: 600px) {
      .thoth-shortcuts-panel {
        max-width: 90vw;
        margin: 20px;
      }

      .thoth-shortcut-item {
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
      }
    }

    /* High contrast mode */
    @media (prefers-contrast: high) {
      .thoth-shortcuts-overlay {
        background: rgba(0, 0, 0, 0.8);
      }

      .thoth-shortcuts-panel {
        border-width: 2px;
      }

      .thoth-shortcut-keys {
        border-width: 2px;
      }
    }

    /* Focus management */
    .thoth-shortcuts-panel {
      outline: none;
    }

    .thoth-shortcuts-panel:focus-within {
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2),
                  0 0 0 2px var(--interactive-accent);
    }
  `;

  document.head.appendChild(style);
}
