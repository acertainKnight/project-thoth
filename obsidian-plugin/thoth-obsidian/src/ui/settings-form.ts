import { App, Notice } from 'obsidian';
import { UIGenerator, IUIGenerator } from './ui-generator';
import { ValidationDisplay, IValidationDisplay } from './validation-display';
import { ISchemaService, UISchema, FieldValidationResult, ValidationResult } from '../services/schema-service';
import { ThothSettings } from '../types';

/**
 * Settings form interface
 */
export interface ISettingsForm {
  initialize(container: HTMLElement): Promise<void>;
  loadConfiguration(): Promise<void>;
  saveConfiguration(): Promise<boolean>;
  validateForm(): Promise<ValidationResult>;
  resetForm(): void;
  exportConfiguration(): void;
  importConfiguration(config: Partial<ThothSettings>): Promise<boolean>;
  cleanup(): void;
}

/**
 * Form state enum
 */
export enum FormState {
  LOADING = 'loading',
  READY = 'ready',
  VALIDATING = 'validating',
  SAVING = 'saving',
  ERROR = 'error'
}

/**
 * Settings form implementation
 */
export class SettingsForm implements ISettingsForm {
  private app: App;
  private schemaService: ISchemaService;
  private uiGenerator: IUIGenerator;
  private validationDisplay: IValidationDisplay;
  private container?: HTMLElement;
  private currentSchema?: UISchema;
  private currentConfig: ThothSettings;
  private formState: FormState = FormState.LOADING;
  private saveCallback?: (config: Partial<ThothSettings>) => Promise<void>;

  constructor(
    app: App,
    schemaService: ISchemaService,
    currentConfig: ThothSettings,
    saveCallback?: (config: Partial<ThothSettings>) => Promise<void>
  ) {
    this.app = app;
    this.schemaService = schemaService;
    this.currentConfig = { ...currentConfig };
    this.saveCallback = saveCallback;

    // Initialize components
    this.uiGenerator = new UIGenerator();
    this.validationDisplay = new ValidationDisplay();

    // Set up validation and save callbacks
    this.uiGenerator.setValidationCallback(this.handleFieldValidation.bind(this));
    this.uiGenerator.setSaveCallback(this.handleFormSave.bind(this));
  }

  /**
   * Initialize the settings form
   */
  async initialize(container: HTMLElement): Promise<void> {
    this.container = container;

    try {
      this.setFormState(FormState.LOADING);
      this.showLoadingState();

      // Load schema from backend
      this.currentSchema = await this.schemaService.getSchema();

      // Generate form UI
      await this.generateForm();

      this.setFormState(FormState.READY);
      new Notice('Settings form loaded successfully', 2000);

    } catch (error) {
      console.error('Failed to initialize settings form:', error);
      this.setFormState(FormState.ERROR);
      this.showErrorState(error.message);
    }
  }

  /**
   * Load current configuration
   */
  async loadConfiguration(): Promise<void> {
    try {
      this.setFormState(FormState.LOADING);

      // Configuration is already loaded in constructor
      // This method can be used to refresh configuration if needed

      if (this.currentSchema) {
        await this.generateForm();
      }

      this.setFormState(FormState.READY);
    } catch (error) {
      console.error('Failed to load configuration:', error);
      this.setFormState(FormState.ERROR);
      this.validationDisplay.showFormError(`Failed to load configuration: ${error.message}`);
    }
  }

  /**
   * Save configuration
   */
  async saveConfiguration(): Promise<boolean> {
    try {
      this.setFormState(FormState.SAVING);
      this.validationDisplay.showSaveProgress();

      // Get form data
      const formData = this.uiGenerator.getFormData();

      // Validate before saving
      const validationResult = await this.validateForm();
      if (!validationResult.is_valid) {
        this.validationDisplay.processFormValidationResult(validationResult);
        this.validationDisplay.showFormError('Please fix validation errors before saving');
        return false;
      }

      // Save configuration
      if (this.saveCallback) {
        await this.saveCallback(formData);
      }

      // Update current config
      this.currentConfig = { ...this.currentConfig, ...formData };

      this.validationDisplay.showFormSuccess('Configuration saved successfully');
      this.setFormState(FormState.READY);

      return true;

    } catch (error) {
      console.error('Failed to save configuration:', error);
      this.validationDisplay.showFormError(`Save failed: ${error.message}`);
      this.setFormState(FormState.ERROR);
      return false;
    } finally {
      this.validationDisplay.hideSaveProgress();
    }
  }

  /**
   * Validate entire form
   */
  async validateForm(): Promise<ValidationResult> {
    try {
      this.setFormState(FormState.VALIDATING);

      const formData = this.uiGenerator.getFormData();
      const result = await this.schemaService.validateConfig(formData);

      this.validationDisplay.processFormValidationResult(result);
      this.setFormState(FormState.READY);

      return result;
    } catch (error) {
      console.error('Form validation failed:', error);
      this.setFormState(FormState.ERROR);

      // Return error result
      return {
        is_valid: false,
        errors: [{ field: 'form', message: error.message, code: 'VALIDATION_ERROR' }],
        warnings: [],
        error_count: 1,
        warning_count: 0
      };
    }
  }

  /**
   * Reset form to original state
   */
  resetForm(): void {
    try {
      // Reset UI generator
      this.uiGenerator.cleanup();

      // Clear validation display
      this.validationDisplay.clearFormMessages();

      // Regenerate form with original config
      if (this.currentSchema) {
        this.generateForm();
      }

      this.validationDisplay.showFormSuccess('Form reset to original values');
      this.setFormState(FormState.READY);

    } catch (error) {
      console.error('Failed to reset form:', error);
      this.validationDisplay.showFormError(`Reset failed: ${error.message}`);
    }
  }

  /**
   * Export configuration as JSON
   */
  exportConfiguration(): void {
    try {
      const formData = this.uiGenerator.getFormData();
      const exportData = {
        version: this.currentSchema?.version || '1.0.0',
        exported_at: new Date().toISOString(),
        configuration: formData
      };

      const dataStr = JSON.stringify(exportData, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });

      const link = document.createElement('a');
      link.href = URL.createObjectURL(dataBlob);
      link.download = `thoth-config-${new Date().toISOString().split('T')[0]}.json`;
      link.click();

      URL.revokeObjectURL(link.href);

      this.validationDisplay.showFormSuccess('Configuration exported successfully');
    } catch (error) {
      console.error('Export failed:', error);
      this.validationDisplay.showFormError(`Export failed: ${error.message}`);
    }
  }

  /**
   * Import configuration from JSON
   */
  async importConfiguration(config: Partial<ThothSettings>): Promise<boolean> {
    try {
      this.setFormState(FormState.LOADING);

      // Validate imported configuration
      const validationResult = await this.schemaService.validateConfig(config);

      if (!validationResult.is_valid) {
        this.validationDisplay.processFormValidationResult(validationResult);
        this.validationDisplay.showFormError('Imported configuration has validation errors');
        return false;
      }

      // Update current configuration
      this.currentConfig = { ...this.currentConfig, ...config };

      // Regenerate form with imported data
      if (this.currentSchema) {
        await this.generateForm();
      }

      this.validationDisplay.showFormSuccess('Configuration imported successfully');
      this.setFormState(FormState.READY);

      return true;
    } catch (error) {
      console.error('Import failed:', error);
      this.validationDisplay.showFormError(`Import failed: ${error.message}`);
      this.setFormState(FormState.ERROR);
      return false;
    }
  }

  /**
   * Clean up resources
   */
  cleanup(): void {
    this.uiGenerator.cleanup();
    this.setFormState(FormState.LOADING);
  }

  /**
   * Generate form UI
   */
  private async generateForm(): Promise<void> {
    if (!this.container || !this.currentSchema) {
      throw new Error('Form container or schema not available');
    }

    // Clear existing content
    this.container.empty();

    // Generate form using UI generator
    const formEl = this.uiGenerator.generateSettingsForm(this.currentSchema, this.currentConfig);
    this.container.appendChild(formEl);

    // Add import/export functionality
    this.addImportExportButtons();
  }

  /**
   * Add import/export buttons to form
   */
  private addImportExportButtons(): void {
    if (!this.container) return;

    const actionsEl = this.container.querySelector('.thoth-form-actions');
    if (!actionsEl) return;

    // Import button
    const importBtn = actionsEl.createEl('button', {
      text: 'Import',
      cls: 'thoth-btn thoth-btn-secondary'
    });

    importBtn.addEventListener('click', () => {
      this.showImportDialog();
    });

    // Add divider
    actionsEl.createEl('span', { text: '|', cls: 'thoth-actions-divider' });

    // Validate button
    const validateBtn = actionsEl.createEl('button', {
      text: 'Validate',
      cls: 'thoth-btn thoth-btn-secondary'
    });

    validateBtn.addEventListener('click', async () => {
      const result = await this.validateForm();
      if (result.is_valid) {
        this.validationDisplay.showFormSuccess('Configuration is valid');
      } else {
        this.validationDisplay.showFormError(`Found ${result.error_count} validation error${result.error_count !== 1 ? 's' : ''}`);
      }
    });
  }

  /**
   * Show import dialog
   */
  private showImportDialog(): void {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';

    input.addEventListener('change', async (event) => {
      const file = (event.target as HTMLInputElement).files?.[0];
      if (!file) return;

      try {
        const content = await file.text();
        const importData = JSON.parse(content);

        // Extract configuration from import data
        const config = importData.configuration || importData;

        await this.importConfiguration(config);
      } catch (error) {
        console.error('Import error:', error);
        this.validationDisplay.showFormError(`Import failed: Invalid JSON file`);
      }
    });

    input.click();
  }

  /**
   * Handle field validation
   */
  private async handleFieldValidation(fieldName: string, value: any): Promise<FieldValidationResult> {
    try {
      this.validationDisplay.showLoadingState(fieldName);

      const result = await this.schemaService.validatePartialConfig(fieldName, value);

      this.validationDisplay.hideLoadingState(fieldName);
      this.validationDisplay.processValidationResult(fieldName, result);

      return result;
    } catch (error) {
      console.warn(`Validation failed for ${fieldName}:`, error);
      this.validationDisplay.hideLoadingState(fieldName);

      // Return success to not block user interaction on validation errors
      return { is_valid: true };
    }
  }

  /**
   * Handle form save
   */
  private async handleFormSave(config: Partial<ThothSettings>): Promise<void> {
    if (this.saveCallback) {
      await this.saveCallback(config);
    }
  }

  /**
   * Set form state
   */
  private setFormState(state: FormState): void {
    this.formState = state;

    if (this.container) {
      this.container.dataset.formState = state;
    }
  }

  /**
   * Show loading state
   */
  private showLoadingState(): void {
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="thoth-loading-state">
        <div class="thoth-loading-content">
          <div class="thoth-spinner-large"></div>
          <h2>Loading Settings Schema...</h2>
          <p>Fetching configuration schema from backend...</p>
        </div>
      </div>
    `;
  }

  /**
   * Show error state
   */
  private showErrorState(errorMessage: string): void {
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="thoth-error-state">
        <div class="thoth-error-content">
          <div class="thoth-error-icon">❌</div>
          <h2>Failed to Load Settings</h2>
          <p class="thoth-error-message">${errorMessage}</p>
          <div class="thoth-error-actions">
            <button class="thoth-btn thoth-btn-primary" id="retry-load">Retry</button>
            <button class="thoth-btn thoth-btn-secondary" id="use-fallback">Use Offline Mode</button>
          </div>
        </div>
      </div>
    `;

    // Add retry functionality
    const retryBtn = this.container.querySelector('#retry-load') as HTMLButtonElement;
    if (retryBtn) {
      retryBtn.addEventListener('click', () => {
        this.initialize(this.container!);
      });
    }

    // Add fallback functionality
    const fallbackBtn = this.container.querySelector('#use-fallback') as HTMLButtonElement;
    if (fallbackBtn) {
      fallbackBtn.addEventListener('click', async () => {
        try {
          // Try to use fallback schema
          this.currentSchema = await this.schemaService.getSchema(); // This should return fallback
          await this.generateForm();
          this.setFormState(FormState.READY);
          this.validationDisplay.showFormWarning('Using offline configuration (limited functionality)');
        } catch (error) {
          this.validationDisplay.showFormError('Failed to load offline configuration');
        }
      });
    }
  }

  /**
   * Create comprehensive form footer with actions and status
   */
  private createFormFooter(): HTMLElement {
    const footerEl = document.createElement('div');
    footerEl.className = 'thoth-form-footer';

    // Connection status
    const statusEl = footerEl.createEl('div', { cls: 'thoth-connection-status' });
    this.updateConnectionStatus(statusEl);

    // Schema info
    const schemaInfoEl = footerEl.createEl('div', { cls: 'thoth-schema-info' });
    if (this.currentSchema) {
      schemaInfoEl.innerHTML = `
        <span class="thoth-schema-version">Schema v${this.currentSchema.version}</span>
        <span class="thoth-field-count">${Object.keys(this.currentSchema.fields).length} fields</span>
        <span class="thoth-group-count">${Object.keys(this.currentSchema.groups).length} groups</span>
      `;
    }

    // Advanced actions
    const advancedEl = footerEl.createEl('div', { cls: 'thoth-advanced-actions' });

    const refreshBtn = advancedEl.createEl('button', {
      text: '🔄 Refresh Schema',
      cls: 'thoth-btn thoth-btn-small'
    });

    refreshBtn.addEventListener('click', async () => {
      await this.refreshSchema();
    });

    const validateAllBtn = advancedEl.createEl('button', {
      text: '✓ Validate All',
      cls: 'thoth-btn thoth-btn-small'
    });

    validateAllBtn.addEventListener('click', async () => {
      await this.validateForm();
    });

    return footerEl;
  }

  /**
   * Update connection status display
   */
  private async updateConnectionStatus(statusEl: HTMLElement): Promise<void> {
    try {
      const isOnline = await this.schemaService.isBackendReachable();

      statusEl.innerHTML = `
        <span class="thoth-status-indicator ${isOnline ? 'online' : 'offline'}"></span>
        <span class="thoth-status-text">${isOnline ? 'Connected' : 'Offline'}</span>
      `;
    } catch (error) {
      statusEl.innerHTML = `
        <span class="thoth-status-indicator offline"></span>
        <span class="thoth-status-text">Connection Error</span>
      `;
    }
  }

  /**
   * Refresh schema from backend
   */
  private async refreshSchema(): Promise<void> {
    try {
      this.setFormState(FormState.LOADING);
      this.validationDisplay.showFormInfo('Refreshing schema...');

      await this.schemaService.refreshSchema();
      this.currentSchema = await this.schemaService.getSchema();

      await this.generateForm();

      this.validationDisplay.showFormSuccess('Schema refreshed successfully');
      this.setFormState(FormState.READY);
    } catch (error) {
      console.error('Schema refresh failed:', error);
      this.validationDisplay.showFormError(`Schema refresh failed: ${error.message}`);
      this.setFormState(FormState.ERROR);
    }
  }

  /**
   * Handle schema updates
   */
  async handleSchemaUpdate(): Promise<void> {
    try {
      const isOutdated = await this.schemaService.isSchemaOutdated();

      if (isOutdated) {
        const shouldUpdate = await this.showSchemaUpdateDialog();
        if (shouldUpdate) {
          await this.refreshSchema();
        }
      }
    } catch (error) {
      console.warn('Schema update check failed:', error);
    }
  }

  /**
   * Show schema update dialog
   */
  private async showSchemaUpdateDialog(): Promise<boolean> {
    return new Promise((resolve) => {
      const notification = this.validationDisplay.createActionNotification(
        'A newer configuration schema is available. Update now?',
        [
          {
            label: 'Update',
            action: () => resolve(true),
            style: 'primary'
          },
          {
            label: 'Later',
            action: () => resolve(false),
            style: 'secondary'
          }
        ],
        'info'
      );

      const formContainer = this.getFormContainer();
      if (formContainer) {
        formContainer.insertBefore(notification, formContainer.firstChild);
      }
    });
  }

  /**
   * Get form container
   */
  private getFormContainer(): HTMLElement | null {
    return this.container || document.querySelector('.thoth-settings-form');
  }

  /**
   * Monitor form for changes
   */
  private setupFormMonitoring(): void {
    // Check for schema updates periodically
    setInterval(async () => {
      if (this.formState === FormState.READY) {
        await this.handleSchemaUpdate();
      }
    }, 30000); // Check every 30 seconds
  }

  /**
   * Create form help section
   */
  private createFormHelp(): HTMLElement {
    const helpEl = document.createElement('div');
    helpEl.className = 'thoth-form-help';

    helpEl.innerHTML = `
      <details class="thoth-help-section">
        <summary>Configuration Help</summary>
        <div class="thoth-help-content">
          <h4>Getting Started</h4>
          <ul>
            <li><strong>Required fields</strong> are marked with a red asterisk (*)</li>
            <li><strong>API Keys</strong> are essential for the system to function</li>
            <li><strong>Directories</strong> should point to valid paths on your system</li>
            <li>Use <strong>Remote Mode</strong> to connect to a running Thoth server</li>
          </ul>

          <h4>Validation</h4>
          <ul>
            <li>Fields are validated in real-time as you type</li>
            <li>Red indicators show errors that must be fixed</li>
            <li>Orange indicators show warnings (non-blocking)</li>
            <li>Green indicators show valid fields</li>
          </ul>

          <h4>Troubleshooting</h4>
          <ul>
            <li>If connection fails, check your endpoint URL and network</li>
            <li>Use "Validate All" to check all fields at once</li>
            <li>Export your config to backup your settings</li>
            <li>Use offline mode if the backend is unavailable</li>
          </ul>
        </div>
      </details>
    `;

    return helpEl;
  }

  /**
   * Initialize form styles
   */
  private initializeFormStyles(): void {
    if (document.getElementById('thoth-form-styles')) {
      return; // Styles already loaded
    }

    const style = document.createElement('style');
    style.id = 'thoth-form-styles';
    style.textContent = `
      /* Main form styles */
      .thoth-settings-form {
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
      }

      .thoth-settings-header h1 {
        margin: 0 0 8px 0;
        color: var(--text-normal);
      }

      .thoth-settings-version {
        color: var(--text-muted);
        font-size: 0.9em;
        margin-bottom: 20px;
      }

      /* Form actions */
      .thoth-form-actions {
        display: flex;
        gap: 12px;
        align-items: center;
        margin: 20px 0;
        padding: 16px;
        background: var(--background-secondary);
        border-radius: 8px;
        border: 1px solid var(--background-modifier-border);
      }

      .thoth-btn {
        padding: 8px 16px;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s ease;
        font-size: 0.9em;
      }

      .thoth-btn-primary {
        background: var(--interactive-accent);
        color: var(--text-on-accent);
      }

      .thoth-btn-primary:hover:not(:disabled) {
        background: var(--interactive-accent-hover);
        transform: translateY(-1px);
      }

      .thoth-btn-secondary {
        background: var(--background-modifier-form-field);
        color: var(--text-normal);
        border: 1px solid var(--background-modifier-border);
      }

      .thoth-btn-secondary:hover:not(:disabled) {
        background: var(--background-modifier-hover);
      }

      .thoth-btn-small {
        padding: 4px 8px;
        font-size: 0.8em;
      }

      .thoth-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        transform: none;
      }

      .thoth-actions-divider {
        color: var(--text-muted);
        margin: 0 4px;
      }

      /* Form content */
      .thoth-form-content {
        margin: 20px 0;
      }

      /* Group styles */
      .thoth-settings-group {
        margin: 24px 0;
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
        overflow: hidden;
      }

      .thoth-group-header {
        padding: 12px 16px;
        background: var(--background-secondary);
        cursor: pointer;
        user-select: none;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid var(--background-modifier-border);
      }

      .thoth-group-header:hover {
        background: var(--background-modifier-hover);
      }

      .thoth-group-header h2 {
        margin: 0;
        font-size: 1.1em;
        color: var(--text-normal);
      }

      .thoth-group-toggle {
        font-size: 1.2em;
        color: var(--text-muted);
        transition: transform 0.2s ease;
      }

      .thoth-group-description {
        margin: 0;
        padding: 0 16px 12px;
        color: var(--text-muted);
        font-size: 0.9em;
        background: var(--background-secondary);
      }

      .thoth-group-content {
        padding: 16px;
        background: var(--background-primary);
      }

      /* Loading and error states */
      .thoth-loading-state,
      .thoth-error-state {
        text-align: center;
        padding: 60px 20px;
      }

      .thoth-loading-content,
      .thoth-error-content {
        max-width: 400px;
        margin: 0 auto;
      }

      .thoth-spinner-large {
        width: 40px;
        height: 40px;
        border: 4px solid var(--background-modifier-border);
        border-top: 4px solid var(--interactive-accent);
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 20px;
      }

      .thoth-error-icon {
        font-size: 3em;
        margin-bottom: 16px;
      }

      .thoth-error-message {
        color: var(--text-muted);
        margin: 16px 0;
        line-height: 1.5;
      }

      .thoth-error-actions {
        display: flex;
        gap: 12px;
        justify-content: center;
        margin-top: 20px;
      }

      /* Form footer */
      .thoth-form-footer {
        margin-top: 32px;
        padding: 16px;
        background: var(--background-secondary);
        border-radius: 8px;
        border: 1px solid var(--background-modifier-border);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 16px;
      }

      .thoth-connection-status {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.9em;
      }

      .thoth-status-indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
      }

      .thoth-status-indicator.online {
        background: var(--color-green);
      }

      .thoth-status-indicator.offline {
        background: var(--color-red);
      }

      .thoth-schema-info {
        display: flex;
        gap: 16px;
        font-size: 0.85em;
        color: var(--text-muted);
      }

      .thoth-advanced-actions {
        display: flex;
        gap: 8px;
      }

      /* Form help */
      .thoth-form-help {
        margin: 20px 0;
      }

      .thoth-help-section {
        border: 1px solid var(--background-modifier-border);
        border-radius: 6px;
        overflow: hidden;
      }

      .thoth-help-section summary {
        padding: 12px 16px;
        background: var(--background-secondary);
        cursor: pointer;
        font-weight: 500;
        border-bottom: 1px solid var(--background-modifier-border);
      }

      .thoth-help-content {
        padding: 16px;
        background: var(--background-primary);
      }

      .thoth-help-content h4 {
        margin: 0 0 8px 0;
        color: var(--text-normal);
      }

      .thoth-help-content ul {
        margin: 0 0 16px 0;
        padding-left: 20px;
      }

      .thoth-help-content li {
        margin: 4px 0;
        line-height: 1.4;
      }

      /* Form state classes */
      .thoth-settings-form[data-form-state="loading"] {
        pointer-events: none;
        opacity: 0.7;
      }

      .thoth-settings-form[data-form-state="saving"] .thoth-form-content {
        pointer-events: none;
        opacity: 0.8;
      }

      /* Responsive design */
      @media (max-width: 600px) {
        .thoth-form-actions,
        .thoth-form-footer {
          flex-direction: column;
          align-items: stretch;
        }

        .thoth-form-actions .thoth-btn {
          flex: 1;
        }

        .thoth-schema-info {
          justify-content: center;
        }
      }
    `;

    document.head.appendChild(style);
  }
}

/**
 * Settings form factory
 */
export class SettingsFormFactory {
  /**
   * Create settings form instance
   */
  static create(
    app: App,
    schemaService: ISchemaService,
    currentConfig: ThothSettings,
    saveCallback?: (config: Partial<ThothSettings>) => Promise<void>
  ): ISettingsForm {
    return new SettingsForm(app, schemaService, currentConfig, saveCallback);
  }

  /**
   * Create settings form with default configuration
   */
  static createDefault(
    app: App,
    schemaService: ISchemaService,
    saveCallback?: (config: Partial<ThothSettings>) => Promise<void>
  ): ISettingsForm {
    // Use default settings from types
    const { DEFAULT_SETTINGS } = require('../types');
    return new SettingsForm(app, schemaService, DEFAULT_SETTINGS, saveCallback);
  }
}
