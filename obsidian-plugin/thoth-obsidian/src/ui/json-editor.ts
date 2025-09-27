import { ThothSettings } from '../types';
import { ValidationResult, FieldValidationResult } from '../services/schema-service';

/**
 * JSON validation error interface
 */
export interface JSONError {
  line: number;
  column: number;
  message: string;
  type: 'syntax' | 'validation' | 'warning';
  code?: string;
  severity?: 'error' | 'warning' | 'info';
  suggestion?: ValidationSuggestion;
}

/**
 * Validation suggestion interface
 */
export interface ValidationSuggestion {
  description: string;
  action: 'replace' | 'insert' | 'remove' | 'format';
  range?: { start: { line: number; column: number }; end: { line: number; column: number } };
  replacement?: string;
  applicable: boolean;
}

/**
 * Enhanced validation interface
 */
export interface EnhancedValidation {
  validateWithSchema(content: string): Promise<ValidationResult>;
  highlightErrors(errors: JSONError[]): void;
  showSuggestions(suggestions: ValidationSuggestion[]): void;
  applyQuickFix(suggestion: ValidationSuggestion): void;
}

/**
 * JSON editor configuration
 */
export interface JSONEditorConfig {
  readOnly?: boolean;
  showLineNumbers?: boolean;
  autoFormat?: boolean;
  validateOnChange?: boolean;
  theme?: 'light' | 'dark' | 'auto';
  tabSize?: number;
  wordWrap?: boolean;
}

/**
 * JSON editor interface
 */
export interface IJSONEditor extends EnhancedValidation {
  setValue(json: string): void;
  getValue(): string;
  isValid(): boolean;
  getValidationErrors(): JSONError[];
  formatJSON(): void;
  onContentChange(callback: (content: string) => void): void;
  render(container: HTMLElement): void;
  focus(): void;
  setReadOnly(readOnly: boolean): void;
  destroy(): void;

  // Enhanced validation methods
  setValidationEndpoint(endpoint: string): void;
  enableSchemaValidation(schema: any): void;
  getCursorPosition(): { line: number; column: number };
  goToLine(line: number, column?: number): void;
  getSelectedText(): string;
  replaceSelection(text: string): void;
}

/**
 * Textarea-based JSON editor with validation and formatting
 */
export class TextareaJSONEditor implements IJSONEditor {
  private textarea?: HTMLTextAreaElement;
  private container?: HTMLElement;
  private config: JSONEditorConfig;
  private changeCallback?: (content: string) => void;
  private validationErrors: JSONError[] = [];
  private validationEndpoint?: string;
  private schema?: any;
  private suggestions: ValidationSuggestion[] = [];
  private errorHighlights: HTMLElement[] = [];
  private suggestionPanel?: HTMLElement;
  private validationDebounceTimer?: NodeJS.Timeout;

  constructor(config: JSONEditorConfig = {}) {
    this.config = {
      readOnly: false,
      showLineNumbers: true,
      autoFormat: false,
      validateOnChange: true,
      theme: 'auto',
      tabSize: 2,
      wordWrap: true,
      ...config
    };
  }

  /**
   * Render the textarea editor
   */
  render(container: HTMLElement): void {
    this.container = container;
    container.className = 'thoth-json-editor-container thoth-json-editor-textarea';

    // Create wrapper
    const wrapper = container.createEl('div', { cls: 'thoth-textarea-wrapper' });

    // Line numbers (if enabled)
    let lineNumbersEl: HTMLElement | undefined;
    if (this.config.showLineNumbers) {
      lineNumbersEl = wrapper.createEl('div', { cls: 'thoth-line-numbers' });
      this.updateLineNumbers(lineNumbersEl, 1);
    }

    // Textarea
    this.textarea = wrapper.createEl('textarea', { cls: 'thoth-json-textarea' });
    this.setupTextarea();

    // Add toolbar
    this.createToolbar(container);

    // Initial validation
    if (this.config.validateOnChange) {
      this.validateContent();
    }
  }

  /**
   * Set up textarea with proper styling and behavior
   */
  private setupTextarea(): void {
    if (!this.textarea) return;

    // Basic setup
    this.textarea.setAttribute('spellcheck', 'false');
    this.textarea.setAttribute('data-gramm', 'false');
    this.textarea.readOnly = this.config.readOnly || false;

    // Styling
    this.textarea.style.cssText = `
      width: 100%;
      min-height: 300px;
      border: none;
      outline: none;
      resize: vertical;
      font-family: Monaco, Menlo, "Ubuntu Mono", "Cascadia Code", "Source Code Pro", monospace;
      font-size: 13px;
      line-height: 1.5;
      padding: 12px;
      background: var(--background-primary);
      color: var(--text-normal);
      tab-size: ${this.config.tabSize};
      white-space: pre;
      overflow-wrap: normal;
      overflow-x: auto;
    `;

    // Event handlers
    this.textarea.addEventListener('input', () => {
      this.handleContentChange();
    });

    this.textarea.addEventListener('keydown', (e) => {
      this.handleKeyDown(e);
    });

    this.textarea.addEventListener('scroll', () => {
      this.syncLineNumbersScroll();
    });
  }

  /**
   * Handle content changes
   */
  private handleContentChange(): void {
    if (!this.textarea) return;

    // Update line numbers
    if (this.config.showLineNumbers) {
      const lineNumbers = this.container?.querySelector('.thoth-line-numbers') as HTMLElement;
      if (lineNumbers) {
        const lineCount = this.textarea.value.split('\n').length;
        this.updateLineNumbers(lineNumbers, lineCount);
      }
    }

    // Trigger change callback
    if (this.changeCallback) {
      this.changeCallback(this.textarea.value);
    }

    // Validate if enabled (debounced for performance)
    if (this.config.validateOnChange) {
      this.debouncedValidation();
    }
  }

  /**
   * Handle keyboard shortcuts
   */
  private handleKeyDown(e: KeyboardEvent): void {
    if (!this.textarea) return;

    // Tab handling for indentation
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = this.textarea.selectionStart;
      const end = this.textarea.selectionEnd;
      const spaces = ' '.repeat(this.config.tabSize || 2);

      this.textarea.value = this.textarea.value.substring(0, start) + spaces + this.textarea.value.substring(end);
      this.textarea.selectionStart = this.textarea.selectionEnd = start + spaces.length;
      this.handleContentChange();
    }

    // Format shortcut (Ctrl/Cmd + Shift + F)
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') {
      e.preventDefault();
      this.formatJSON();
    }

    // Auto-close brackets and quotes
    this.handleAutoComplete(e);
  }

  /**
   * Handle auto-completion for brackets and quotes
   */
  private handleAutoComplete(e: KeyboardEvent): void {
    if (!this.textarea || this.config.readOnly) return;

    const pairs: Record<string, string> = {
      '{': '}',
      '[': ']',
      '"': '"'
    };

    if (pairs[e.key]) {
      e.preventDefault();
      const start = this.textarea.selectionStart;
      const end = this.textarea.selectionEnd;
      const selectedText = this.textarea.value.substring(start, end);

      let insertion: string;
      if (e.key === '"' && selectedText) {
        // Wrap selected text in quotes
        insertion = `"${selectedText}"`;
      } else {
        insertion = e.key + (selectedText || '') + pairs[e.key];
      }

      this.textarea.value = this.textarea.value.substring(0, start) + insertion + this.textarea.value.substring(end);

      // Position cursor
      if (selectedText) {
        this.textarea.selectionStart = start + 1;
        this.textarea.selectionEnd = start + 1 + selectedText.length;
      } else {
        this.textarea.selectionStart = this.textarea.selectionEnd = start + 1;
      }

      this.handleContentChange();
    }
  }

  /**
   * Create editor toolbar
   */
  private createToolbar(container: HTMLElement): void {
    const toolbar = container.createEl('div', { cls: 'thoth-json-toolbar' });

    // Format button
    const formatBtn = toolbar.createEl('button', {
      text: '✨ Format',
      cls: 'thoth-toolbar-btn'
    });
    formatBtn.title = 'Format JSON (Ctrl+Shift+F)';
    formatBtn.addEventListener('click', () => this.formatJSON());

    // Validate button
    const validateBtn = toolbar.createEl('button', {
      text: '✓ Validate',
      cls: 'thoth-toolbar-btn'
    });
    validateBtn.title = 'Validate JSON';
    validateBtn.addEventListener('click', () => this.validateContent());

    // Minify button
    const minifyBtn = toolbar.createEl('button', {
      text: '📦 Minify',
      cls: 'thoth-toolbar-btn'
    });
    minifyBtn.title = 'Minify JSON';
    minifyBtn.addEventListener('click', () => this.minifyJSON());

    // Copy button
    const copyBtn = toolbar.createEl('button', {
      text: '📋 Copy',
      cls: 'thoth-toolbar-btn'
    });
    copyBtn.title = 'Copy JSON to clipboard';
    copyBtn.addEventListener('click', () => this.copyToClipboard());

    // Status indicator
    const statusEl = toolbar.createEl('div', { cls: 'thoth-json-status' });
    this.updateStatusIndicator(statusEl);
  }

  /**
   * Update line numbers
   */
  private updateLineNumbers(container: HTMLElement, lineCount: number): void {
    const numbers = Array.from({ length: lineCount }, (_, i) => i + 1);
    container.innerHTML = numbers.map(n => `<div class="thoth-line-number">${n}</div>`).join('');
  }

  /**
   * Sync line numbers scroll with textarea
   */
  private syncLineNumbersScroll(): void {
    if (!this.textarea || !this.config.showLineNumbers) return;

    const lineNumbers = this.container?.querySelector('.thoth-line-numbers') as HTMLElement;
    if (lineNumbers) {
      lineNumbers.scrollTop = this.textarea.scrollTop;
    }
  }

  /**
   * Set JSON content
   */
  setValue(json: string): void {
    if (this.textarea) {
      this.textarea.value = json;
      this.handleContentChange();
    }
  }

  /**
   * Get JSON content
   */
  getValue(): string {
    return this.textarea?.value || '';
  }

  /**
   * Check if JSON is valid
   */
  isValid(): boolean {
    return this.validationErrors.filter(error => error.type === 'syntax').length === 0;
  }

  /**
   * Get validation errors
   */
  getValidationErrors(): JSONError[] {
    return [...this.validationErrors];
  }

  /**
   * Format JSON content
   */
  formatJSON(): void {
    try {
      const content = this.getValue();
      if (!content.trim()) return;

      const parsed = JSON.parse(content);
      const formatted = JSON.stringify(parsed, null, this.config.tabSize || 2);
      this.setValue(formatted);
    } catch (error) {
      console.warn('Cannot format invalid JSON:', error);
    }
  }

  /**
   * Minify JSON content
   */
  private minifyJSON(): void {
    try {
      const content = this.getValue();
      if (!content.trim()) return;

      const parsed = JSON.parse(content);
      const minified = JSON.stringify(parsed);
      this.setValue(minified);
    } catch (error) {
      console.warn('Cannot minify invalid JSON:', error);
    }
  }

  /**
   * Copy content to clipboard
   */
  private async copyToClipboard(): Promise<void> {
    try {
      const content = this.getValue();
      await navigator.clipboard.writeText(content);

      // Show temporary success feedback
      const copyBtn = this.container?.querySelector('.thoth-toolbar-btn:last-of-type') as HTMLButtonElement;
      if (copyBtn) {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = '✅ Copied!';
        copyBtn.disabled = true;

        setTimeout(() => {
          copyBtn.textContent = originalText;
          copyBtn.disabled = false;
        }, 2000);
      }
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  }

  /**
   * Set content change callback
   */
  onContentChange(callback: (content: string) => void): void {
    this.changeCallback = callback;
  }

  /**
   * Focus the editor
   */
  focus(): void {
    if (this.textarea) {
      this.textarea.focus();
    }
  }

  /**
   * Set read-only mode
   */
  setReadOnly(readOnly: boolean): void {
    this.config.readOnly = readOnly;
    if (this.textarea) {
      this.textarea.readOnly = readOnly;
    }
  }

  /**
   * Validate JSON content and update errors
   */
  private validateContent(): void {
    this.validationErrors = [];
    const content = this.getValue();

    if (!content.trim()) {
      this.updateErrorDisplay();
      return;
    }

    try {
      JSON.parse(content);
    } catch (error) {
      const errorMessage = error.message;

      // Try to extract line and column information
      let line = 1;
      let column = 1;

      const lineMatch = errorMessage.match(/line (\d+)/i);
      const columnMatch = errorMessage.match(/column (\d+)/i);
      const positionMatch = errorMessage.match(/position (\d+)/i);

      if (lineMatch) {
        line = parseInt(lineMatch[1]);
      }
      if (columnMatch) {
        column = parseInt(columnMatch[1]);
      } else if (positionMatch) {
        // Calculate line/column from position
        const position = parseInt(positionMatch[1]);
        const beforeError = content.substring(0, position);
        line = beforeError.split('\n').length;
        column = beforeError.split('\n').pop()?.length || 1;
      }

      this.validationErrors.push({
        line,
        column,
        message: errorMessage,
        type: 'syntax'
      });
    }

    this.updateErrorDisplay();
    this.updateStatusIndicator();
  }

  /**
   * Update error display
   */
  private updateErrorDisplay(): void {
    if (!this.container) return;

    // Remove existing error display
    const existingErrors = this.container.querySelector('.thoth-json-errors');
    if (existingErrors) {
      existingErrors.remove();
    }

    // Show errors if any
    if (this.validationErrors.length > 0) {
      const errorsEl = this.container.createEl('div', { cls: 'thoth-json-errors' });

      for (const error of this.validationErrors) {
        const errorEl = errorsEl.createEl('div', { cls: `thoth-json-error thoth-json-error-${error.type}` });

        const iconEl = errorEl.createEl('span', { cls: 'thoth-error-icon' });
        iconEl.textContent = error.type === 'syntax' ? '❌' : '⚠️';

        const locationEl = errorEl.createEl('span', { cls: 'thoth-error-location' });
        locationEl.textContent = `Line ${error.line}, Column ${error.column}`;

        const messageEl = errorEl.createEl('span', { cls: 'thoth-error-message' });
        messageEl.textContent = error.message;
      }
    }
  }

  /**
   * Update status indicator
   */
  private updateStatusIndicator(statusEl?: HTMLElement): void {
    if (!statusEl) {
      statusEl = this.container?.querySelector('.thoth-json-status') as HTMLElement;
    }
    if (!statusEl) return;

    const syntaxErrors = this.validationErrors.filter(e => e.type === 'syntax').length;
    const warnings = this.validationErrors.filter(e => e.type === 'warning').length;

    if (syntaxErrors > 0) {
      statusEl.innerHTML = `<span class="thoth-status-error">❌ ${syntaxErrors} error${syntaxErrors !== 1 ? 's' : ''}</span>`;
    } else if (warnings > 0) {
      statusEl.innerHTML = `<span class="thoth-status-warning">⚠️ ${warnings} warning${warnings !== 1 ? 's' : ''}</span>`;
    } else {
      statusEl.innerHTML = `<span class="thoth-status-valid">✅ Valid JSON</span>`;
    }
  }

  /**
   * Set validation endpoint for schema validation
   */
  setValidationEndpoint(endpoint: string): void {
    this.validationEndpoint = endpoint;
  }

  /**
   * Enable schema validation
   */
  enableSchemaValidation(schema: any): void {
    this.schema = schema;
  }

  /**
   * Validate with schema using backend endpoint
   */
  async validateWithSchema(content: string): Promise<ValidationResult> {
    if (!this.validationEndpoint) {
      return { is_valid: true, errors: [], warnings: [], error_count: 0, warning_count: 0 };
    }

    try {
      const response = await fetch(`${this.validationEndpoint}/config/validate-partial`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content })
      });

      if (!response.ok) {
        throw new Error(`Validation request failed: ${response.statusText}`);
      }

      const result = await response.json();

      // Convert backend validation result to JSONError format
      this.convertValidationResult(result);

      return result;
    } catch (error) {
      console.error('Schema validation failed:', error);
      return {
        is_valid: false,
        errors: [{ field: 'validation', message: `Validation failed: ${error.message}`, code: 'VALIDATION_ERROR' }],
        warnings: [],
        error_count: 1,
        warning_count: 0
      };
    }
  }

  /**
   * Highlight errors in the editor
   */
  highlightErrors(errors: JSONError[]): void {
    if (!this.textarea || !this.container) return;

    // Clear existing highlights
    this.clearErrorHighlights();

    // Add error indicators to line numbers and create hover tooltips
    for (const error of errors) {
      this.addErrorHighlight(error);
    }

    // Update error display panel
    this.updateErrorDisplay();
  }

  /**
   * Show validation suggestions
   */
  showSuggestions(suggestions: ValidationSuggestion[]): void {
    this.suggestions = suggestions;

    if (suggestions.length > 0) {
      this.createSuggestionPanel(suggestions);
    } else {
      this.hideSuggestionPanel();
    }
  }

  /**
   * Apply quick fix suggestion
   */
  applyQuickFix(suggestion: ValidationSuggestion): void {
    if (!this.textarea || !suggestion.applicable) return;

    const content = this.textarea.value;

    switch (suggestion.action) {
      case 'replace':
        if (suggestion.range && suggestion.replacement !== undefined) {
          const before = this.getTextBeforePosition(content, suggestion.range.start);
          const after = this.getTextAfterPosition(content, suggestion.range.end);
          this.setValue(before + suggestion.replacement + after);
        }
        break;

      case 'insert':
        if (suggestion.range && suggestion.replacement !== undefined) {
          const position = this.getPositionOffset(content, suggestion.range.start);
          const newContent = content.slice(0, position) + suggestion.replacement + content.slice(position);
          this.setValue(newContent);
        }
        break;

      case 'remove':
        if (suggestion.range) {
          const before = this.getTextBeforePosition(content, suggestion.range.start);
          const after = this.getTextAfterPosition(content, suggestion.range.end);
          this.setValue(before + after);
        }
        break;

      case 'format':
        this.formatJSON();
        break;
    }

    // Hide suggestion panel after applying fix
    this.hideSuggestionPanel();

    // Re-validate after applying fix
    if (this.config.validateOnChange) {
      this.debouncedValidation();
    }
  }

  /**
   * Get current cursor position
   */
  getCursorPosition(): { line: number; column: number } {
    if (!this.textarea) return { line: 1, column: 1 };

    const selectionStart = this.textarea.selectionStart;
    const textBeforeCursor = this.textarea.value.substring(0, selectionStart);
    const lines = textBeforeCursor.split('\n');

    return {
      line: lines.length,
      column: lines[lines.length - 1].length + 1
    };
  }

  /**
   * Go to specific line and column
   */
  goToLine(line: number, column: number = 1): void {
    if (!this.textarea) return;

    const lines = this.textarea.value.split('\n');
    let position = 0;

    // Calculate position offset
    for (let i = 0; i < Math.min(line - 1, lines.length - 1); i++) {
      position += lines[i].length + 1; // +1 for newline character
    }

    // Add column offset
    position += Math.min(column - 1, lines[line - 1]?.length || 0);

    this.textarea.focus();
    this.textarea.setSelectionRange(position, position);

    // Scroll to make the position visible
    this.scrollToPosition(position);
  }

  /**
   * Get selected text
   */
  getSelectedText(): string {
    if (!this.textarea) return '';

    const start = this.textarea.selectionStart;
    const end = this.textarea.selectionEnd;

    return this.textarea.value.substring(start, end);
  }

  /**
   * Replace selected text
   */
  replaceSelection(text: string): void {
    if (!this.textarea) return;

    const start = this.textarea.selectionStart;
    const end = this.textarea.selectionEnd;
    const value = this.textarea.value;

    this.textarea.value = value.substring(0, start) + text + value.substring(end);
    this.textarea.setSelectionRange(start, start + text.length);

    this.handleContentChange();
  }

  /**
   * Debounced validation to improve performance
   */
  private debouncedValidation(): void {
    if (this.validationDebounceTimer) {
      clearTimeout(this.validationDebounceTimer);
    }

    this.validationDebounceTimer = setTimeout(() => {
      this.performEnhancedValidation();
    }, 500); // 500ms delay
  }

  /**
   * Perform enhanced validation with schema
   */
  private async performEnhancedValidation(): Promise<void> {
    const content = this.getValue();

    // First, do basic JSON syntax validation
    this.validateContent();

    // Then, if we have a validation endpoint, do schema validation
    if (this.validationEndpoint && content.trim()) {
      try {
        const result = await this.validateWithSchema(content);
        this.generateSuggestions(result);
      } catch (error) {
        console.error('Enhanced validation failed:', error);
      }
    }
  }

  /**
   * Convert backend validation result to JSONError format
   */
  private convertValidationResult(result: ValidationResult): void {
    this.validationErrors = [];

    // Add errors
    if (result.errors) {
      for (const error of result.errors) {
        this.validationErrors.push({
          line: this.getLineFromField(error.field),
          column: 1,
          message: error.message,
          type: 'validation',
          code: error.code,
          severity: 'error'
        });
      }
    }

    // Add warnings
    if (result.warnings) {
      for (const warning of result.warnings) {
        this.validationErrors.push({
          line: this.getLineFromField(warning.field),
          column: 1,
          message: warning.message,
          type: 'warning',
          code: warning.code,
          severity: 'warning'
        });
      }
    }

    this.highlightErrors(this.validationErrors);
  }

  /**
   * Get line number from field name (simplified implementation)
   */
  private getLineFromField(fieldName: string): number {
    if (!this.textarea) return 1;

    const content = this.textarea.value;
    const fieldPattern = new RegExp(`["']${fieldName}["']\\s*:`, 'i');
    const match = fieldPattern.exec(content);

    if (match) {
      const beforeMatch = content.substring(0, match.index);
      return beforeMatch.split('\n').length;
    }

    return 1;
  }

  /**
   * Clear existing error highlights
   */
  private clearErrorHighlights(): void {
    this.errorHighlights.forEach(highlight => highlight.remove());
    this.errorHighlights = [];

    // Remove error classes from line numbers
    if (this.container) {
      const lineNumbers = this.container.querySelectorAll('.thoth-line-number');
      lineNumbers.forEach(lineNumber => {
        lineNumber.classList.remove('error', 'warning');
      });
    }
  }

  /**
   * Add error highlight for specific error
   */
  private addErrorHighlight(error: JSONError): void {
    if (!this.container) return;

    // Highlight line number
    const lineNumbers = this.container.querySelectorAll('.thoth-line-number');
    const lineNumberEl = lineNumbers[error.line - 1] as HTMLElement;

    if (lineNumberEl) {
      lineNumberEl.classList.add(error.severity === 'error' ? 'error' : 'warning');
      lineNumberEl.title = `${error.type}: ${error.message}`;
    }
  }

  /**
   * Generate suggestions based on validation results
   */
  private generateSuggestions(result: ValidationResult): void {
    const suggestions: ValidationSuggestion[] = [];

    // Generate format suggestion if JSON is valid but not formatted
    if (result.is_valid) {
      try {
        const content = this.getValue();
        const parsed = JSON.parse(content);
        const formatted = JSON.stringify(parsed, null, 2);

        if (content !== formatted) {
          suggestions.push({
            description: 'Format JSON for better readability',
            action: 'format',
            applicable: true
          });
        }
      } catch (error) {
        // JSON is invalid, skip formatting suggestion
      }
    }

    // Generate field-specific suggestions based on validation errors
    if (result.errors) {
      for (const error of result.errors) {
        if (error.code === 'REQUIRED_FIELD') {
          suggestions.push({
            description: `Add required field "${error.field}"`,
            action: 'insert',
            applicable: true,
            replacement: `"${error.field}": ""`
          });
        }
      }
    }

    this.showSuggestions(suggestions);
  }

  /**
   * Create suggestion panel
   */
  private createSuggestionPanel(suggestions: ValidationSuggestion[]): void {
    this.hideSuggestionPanel();

    if (!this.container) return;

    this.suggestionPanel = this.container.createEl('div', { cls: 'thoth-suggestion-panel' });

    const header = this.suggestionPanel.createEl('div', { cls: 'thoth-suggestion-header' });
    header.createEl('span', { text: '💡 Suggestions', cls: 'thoth-suggestion-title' });

    const closeBtn = header.createEl('button', { cls: 'thoth-suggestion-close' });
    closeBtn.innerHTML = '×';
    closeBtn.addEventListener('click', () => this.hideSuggestionPanel());

    const list = this.suggestionPanel.createEl('div', { cls: 'thoth-suggestion-list' });

    for (const suggestion of suggestions) {
      if (!suggestion.applicable) continue;

      const item = list.createEl('div', { cls: 'thoth-suggestion-item' });

      const description = item.createEl('div', { cls: 'thoth-suggestion-description' });
      description.textContent = suggestion.description;

      const applyBtn = item.createEl('button', { cls: 'thoth-suggestion-apply' });
      applyBtn.textContent = 'Apply';
      applyBtn.addEventListener('click', () => this.applyQuickFix(suggestion));
    }
  }

  /**
   * Hide suggestion panel
   */
  private hideSuggestionPanel(): void {
    if (this.suggestionPanel) {
      this.suggestionPanel.remove();
      this.suggestionPanel = undefined;
    }
  }

  /**
   * Get text before a specific position
   */
  private getTextBeforePosition(content: string, position: { line: number; column: number }): string {
    const lines = content.split('\n');
    const beforeLines = lines.slice(0, position.line - 1);
    const currentLine = lines[position.line - 1] || '';
    const beforeInCurrentLine = currentLine.substring(0, position.column - 1);

    return [...beforeLines, beforeInCurrentLine].join('\n');
  }

  /**
   * Get text after a specific position
   */
  private getTextAfterPosition(content: string, position: { line: number; column: number }): string {
    const lines = content.split('\n');
    const afterLines = lines.slice(position.line);
    const currentLine = lines[position.line - 1] || '';
    const afterInCurrentLine = currentLine.substring(position.column - 1);

    return [afterInCurrentLine, ...afterLines].join('\n');
  }

  /**
   * Get character offset from line/column position
   */
  private getPositionOffset(content: string, position: { line: number; column: number }): number {
    const lines = content.split('\n');
    let offset = 0;

    for (let i = 0; i < position.line - 1 && i < lines.length; i++) {
      offset += lines[i].length + 1; // +1 for newline
    }

    offset += position.column - 1;
    return Math.min(offset, content.length);
  }

  /**
   * Scroll to make a position visible
   */
  private scrollToPosition(position: number): void {
    if (!this.textarea) return;

    const lineHeight = 19.5; // Match CSS line height
    const textBeforePosition = this.textarea.value.substring(0, position);
    const lineNumber = textBeforePosition.split('\n').length;

    const scrollTop = Math.max(0, (lineNumber - 5) * lineHeight);
    this.textarea.scrollTop = scrollTop;

    // Also sync line numbers
    const lineNumbers = this.container?.querySelector('.thoth-line-numbers') as HTMLElement;
    if (lineNumbers) {
      lineNumbers.scrollTop = scrollTop;
    }
  }

  /**
   * Destroy editor and clean up
   */
  destroy(): void {
    // Clear validation timer
    if (this.validationDebounceTimer) {
      clearTimeout(this.validationDebounceTimer);
    }

    // Clear highlights
    this.clearErrorHighlights();

    // Remove suggestion panel
    this.hideSuggestionPanel();

    this.textarea = undefined;
    this.container = undefined;
    this.changeCallback = undefined;
    this.validationErrors = [];
    this.suggestions = [];
  }
}

/**
 * JSON editor factory
 */
export class JSONEditorFactory {
  /**
   * Create textarea-based JSON editor
   */
  static async create(config: JSONEditorConfig = {}): Promise<IJSONEditor> {
    return new TextareaJSONEditor(config);
  }

  /**
   * Create read-only JSON viewer
   */
  static async createViewer(config: JSONEditorConfig = {}): Promise<IJSONEditor> {
    const viewerConfig = { ...config, readOnly: true };
    return new TextareaJSONEditor(viewerConfig);
  }

  /**
   * Create JSON editor with specific theme
   */
  static async createWithTheme(theme: 'light' | 'dark' | 'auto', config: JSONEditorConfig = {}): Promise<IJSONEditor> {
    const themedConfig = { ...config, theme };
    return new TextareaJSONEditor(themedConfig);
  }
}

/**
 * JSON utilities for editor operations
 */
export class JSONEditorUtils {
  /**
   * Validate JSON and return detailed error information
   */
  static validateJSON(jsonString: string): { isValid: boolean; errors: JSONError[] } {
    const errors: JSONError[] = [];

    if (!jsonString.trim()) {
      return { isValid: true, errors };
    }

    try {
      JSON.parse(jsonString);
      return { isValid: true, errors };
    } catch (error) {
      const errorMessage = error.message;

      // Extract position information
      let line = 1;
      let column = 1;

      const lineMatch = errorMessage.match(/line (\d+)/i);
      const columnMatch = errorMessage.match(/column (\d+)/i);

      if (lineMatch) line = parseInt(lineMatch[1]);
      if (columnMatch) column = parseInt(columnMatch[1]);

      errors.push({
        line,
        column,
        message: errorMessage,
        type: 'syntax'
      });

      return { isValid: false, errors };
    }
  }

  /**
   * Format JSON with error handling
   */
  static formatJSON(jsonString: string, tabSize: number = 2): string {
    try {
      if (!jsonString.trim()) return jsonString;

      const parsed = JSON.parse(jsonString);
      return JSON.stringify(parsed, null, tabSize);
    } catch (error) {
      console.warn('Cannot format invalid JSON:', error);
      return jsonString; // Return original if invalid
    }
  }

  /**
   * Minify JSON string
   */
  static minifyJSON(jsonString: string): string {
    try {
      if (!jsonString.trim()) return jsonString;

      const parsed = JSON.parse(jsonString);
      return JSON.stringify(parsed);
    } catch (error) {
      console.warn('Cannot minify invalid JSON:', error);
      return jsonString;
    }
  }

  /**
   * Convert settings object to formatted JSON string
   */
  static settingsToJSON(settings: ThothSettings, tabSize: number = 2): string {
    try {
      return JSON.stringify(settings, null, tabSize);
    } catch (error) {
      console.error('Failed to serialize settings:', error);
      return '{}';
    }
  }

  /**
   * Parse JSON string to settings object
   */
  static parseSettingsJSON(jsonString: string): Partial<ThothSettings> {
    try {
      return JSON.parse(jsonString);
    } catch (error) {
      console.error('Failed to parse settings JSON:', error);
      return {};
    }
  }

  /**
   * Get JSON schema for settings validation
   */
  static getSettingsJSONSchema(): any {
    // Return a basic JSON schema for ThothSettings
    // This could be expanded to provide full schema validation
    return {
      type: 'object',
      properties: {
        // Would include all ThothSettings properties
        // For now, we'll keep it simple
      }
    };
  }
}

/**
 * Initialize JSON editor styles
 */
export function initializeJSONEditorStyles(): void {
  if (document.getElementById('thoth-json-editor-styles')) {
    return; // Styles already loaded
  }

  const style = document.createElement('style');
  style.id = 'thoth-json-editor-styles';
  style.textContent = `
    /* JSON Editor Container */
    .thoth-json-editor-container {
      height: 100%;
      display: flex;
      flex-direction: column;
      border: 1px solid var(--background-modifier-border);
      border-radius: 6px;
      overflow: hidden;
      background: var(--background-primary);
    }

    /* Textarea wrapper */
    .thoth-textarea-wrapper {
      flex: 1;
      display: flex;
      position: relative;
      overflow: hidden;
    }

    /* Line numbers */
    .thoth-line-numbers {
      background: var(--background-secondary);
      border-right: 1px solid var(--background-modifier-border);
      padding: 12px 8px;
      min-width: 40px;
      font-family: Monaco, Menlo, "Ubuntu Mono", monospace;
      font-size: 13px;
      line-height: 1.5;
      color: var(--text-muted);
      text-align: right;
      user-select: none;
      overflow: hidden;
    }

    .thoth-line-number {
      height: 19.5px; /* Match line height */
    }

    /* JSON textarea */
    .thoth-json-textarea {
      flex: 1;
      border: none;
      outline: none;
      resize: none;
      font-family: Monaco, Menlo, "Ubuntu Mono", "Cascadia Code", monospace;
      font-size: 13px;
      line-height: 1.5;
      padding: 12px;
      background: var(--background-primary);
      color: var(--text-normal);
      white-space: pre;
      overflow-wrap: normal;
      overflow-x: auto;
    }

    .thoth-json-textarea:focus {
      background: var(--background-primary);
    }

    /* Toolbar */
    .thoth-json-toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      background: var(--background-secondary);
      border-top: 1px solid var(--background-modifier-border);
      flex-shrink: 0;
    }

    .thoth-toolbar-btn {
      padding: 4px 8px;
      background: var(--background-modifier-form-field);
      border: 1px solid var(--background-modifier-border);
      border-radius: 4px;
      cursor: pointer;
      font-size: 11px;
      color: var(--text-normal);
      transition: all 0.2s ease;
    }

    .thoth-toolbar-btn:hover {
      background: var(--background-modifier-hover);
    }

    .thoth-toolbar-btn:active {
      transform: translateY(1px);
    }

    .thoth-toolbar-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      transform: none;
    }

    /* JSON status indicator */
    .thoth-json-status {
      margin-left: auto;
      font-size: 11px;
      font-weight: 500;
    }

    .thoth-status-valid {
      color: var(--color-green);
    }

    .thoth-status-error {
      color: var(--color-red);
    }

    .thoth-status-warning {
      color: var(--color-orange);
    }

    /* JSON validation errors */
    .thoth-json-errors {
      background: var(--background-secondary);
      border-top: 1px solid var(--background-modifier-border);
      max-height: 120px;
      overflow-y: auto;
      flex-shrink: 0;
    }

    .thoth-json-error {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-bottom: 1px solid var(--background-modifier-border);
      font-size: 12px;
    }

    .thoth-json-error:last-child {
      border-bottom: none;
    }

    .thoth-json-error-syntax {
      background: rgba(255, 0, 0, 0.05);
    }

    .thoth-json-error-warning {
      background: rgba(255, 165, 0, 0.05);
    }

    .thoth-error-icon {
      flex-shrink: 0;
      font-size: 14px;
    }

    .thoth-error-location {
      flex-shrink: 0;
      font-weight: 500;
      color: var(--text-accent);
      min-width: 80px;
    }

    .thoth-error-message {
      flex: 1;
      color: var(--text-muted);
    }

    /* Focus styles */
    .thoth-json-editor-container:focus-within {
      border-color: var(--interactive-accent);
      box-shadow: 0 0 0 2px rgba(var(--interactive-accent-rgb), 0.2);
    }

    /* High contrast mode */
    @media (prefers-contrast: high) {
      .thoth-json-editor-container {
        border-width: 2px;
      }

      .thoth-json-error {
        border-left: 3px solid var(--color-red);
      }
    }

    /* Enhanced error highlighting */
    .thoth-line-number.error {
      background: rgba(255, 0, 0, 0.1);
      color: var(--color-red);
      font-weight: bold;
      border-left: 3px solid var(--color-red);
    }

    .thoth-line-number.warning {
      background: rgba(255, 165, 0, 0.1);
      color: var(--color-orange);
      font-weight: bold;
      border-left: 3px solid var(--color-orange);
    }

    /* Suggestion panel */
    .thoth-suggestion-panel {
      position: absolute;
      top: 50%;
      right: 12px;
      transform: translateY(-50%);
      background: var(--background-primary);
      border: 1px solid var(--background-modifier-border);
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      min-width: 250px;
      max-width: 300px;
      z-index: 1000;
      animation: fadeInSuggestion 0.2s ease;
    }

    @keyframes fadeInSuggestion {
      from {
        opacity: 0;
        transform: translateY(-50%) scale(0.95);
      }
      to {
        opacity: 1;
        transform: translateY(-50%) scale(1);
      }
    }

    .thoth-suggestion-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      background: var(--background-secondary);
      border-bottom: 1px solid var(--background-modifier-border);
      border-radius: 6px 6px 0 0;
    }

    .thoth-suggestion-title {
      font-weight: 500;
      font-size: 12px;
      color: var(--text-normal);
    }

    .thoth-suggestion-close {
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 16px;
      padding: 0;
      width: 20px;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 2px;
    }

    .thoth-suggestion-close:hover {
      background: var(--background-modifier-hover);
      color: var(--text-normal);
    }

    .thoth-suggestion-list {
      padding: 4px;
      max-height: 200px;
      overflow-y: auto;
    }

    .thoth-suggestion-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px;
      border-radius: 4px;
      margin-bottom: 2px;
      transition: background 0.1s ease;
    }

    .thoth-suggestion-item:hover {
      background: var(--background-modifier-hover);
    }

    .thoth-suggestion-description {
      flex: 1;
      font-size: 12px;
      color: var(--text-normal);
      margin-right: 8px;
    }

    .thoth-suggestion-apply {
      background: var(--interactive-accent);
      color: white;
      border: none;
      border-radius: 3px;
      padding: 4px 8px;
      font-size: 11px;
      cursor: pointer;
      transition: all 0.1s ease;
    }

    .thoth-suggestion-apply:hover {
      background: var(--interactive-accent-hover);
      transform: translateY(-1px);
    }

    .thoth-suggestion-apply:active {
      transform: translateY(0);
    }

    /* Enhanced error display */
    .thoth-json-error {
      cursor: pointer;
      transition: background 0.1s ease;
    }

    .thoth-json-error:hover {
      background: rgba(var(--interactive-accent-rgb), 0.1);
    }

    .thoth-json-error-validation {
      background: rgba(255, 0, 0, 0.08);
      border-left: 3px solid var(--color-red);
    }

    .thoth-json-error-validation .thoth-error-icon {
      color: var(--color-red);
    }

    /* Responsive design */
    @media (max-width: 600px) {
      .thoth-json-toolbar {
        flex-wrap: wrap;
        gap: 4px;
      }

      .thoth-toolbar-btn {
        font-size: 10px;
        padding: 3px 6px;
      }

      .thoth-line-numbers {
        min-width: 30px;
        padding: 12px 4px;
      }

      .thoth-suggestion-panel {
        position: fixed;
        top: 50%;
        left: 50%;
        right: auto;
        transform: translate(-50%, -50%);
        min-width: 280px;
        max-width: 90vw;
      }

      .thoth-line-number.error,
      .thoth-line-number.warning {
        border-left-width: 2px;
      }
    }

    /* Dark theme adjustments */
    .theme-dark .thoth-suggestion-panel {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .theme-dark .thoth-line-number.error {
      background: rgba(255, 100, 100, 0.15);
    }

    .theme-dark .thoth-line-number.warning {
      background: rgba(255, 200, 100, 0.15);
    }

    /* Accessibility improvements */
    .thoth-suggestion-apply:focus,
    .thoth-suggestion-close:focus {
      outline: 2px solid var(--interactive-accent);
      outline-offset: 1px;
    }

    .thoth-json-error:focus {
      outline: 2px solid var(--interactive-accent);
      outline-offset: -2px;
    }

    /* Animation for error highlighting */
    .thoth-line-number.error,
    .thoth-line-number.warning {
      animation: highlightError 0.3s ease;
    }

    @keyframes highlightError {
      0% {
        transform: translateX(0);
      }
      25% {
        transform: translateX(2px);
      }
      75% {
        transform: translateX(-2px);
      }
      100% {
        transform: translateX(0);
      }
    }
  `;

  document.head.appendChild(style);
}
