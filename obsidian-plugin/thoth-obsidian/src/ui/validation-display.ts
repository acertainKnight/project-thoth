import { FieldValidationResult, ValidationResult } from '../services/schema-service';

/**
 * Auto-fix suggestion interface
 */
export interface AutoFixSuggestion {
  fix_id: string;
  description: string;
  field_path: string;
  current_value: any;
  suggested_value: any;
  confidence: number;
  risk_level: 'low' | 'medium' | 'high';
  fix_type: 'value_correction' | 'format_fix' | 'default_substitution' | 'type_conversion';
}

/**
 * Contextual help interface
 */
export interface ContextualHelp {
  help_id: string;
  field_path: string;
  title: string;
  content: string;
  examples: string[];
  related_fields: string[];
  documentation_links: string[];
  troubleshooting_steps: string[];
}

/**
 * Enhanced validation result with auto-fix and help
 */
export interface EnhancedValidationResult extends ValidationResult {
  auto_fixes?: AutoFixSuggestion[];
  contextual_help?: ContextualHelp[];
}

/**
 * Validation display interface with enhanced features
 */
export interface IValidationDisplay {
  showFieldError(fieldName: string, error: string, suggestion?: string): void;
  showFieldSuccess(fieldName: string): void;
  showFieldWarning(fieldName: string, warning: string): void;
  clearFieldValidation(fieldName: string): void;
  showFormError(message: string): void;
  showFormSuccess(message: string): void;
  showFormWarning(message: string): void;
  showFormInfo(message: string): void;
  clearFormMessages(): void;
  showSaveProgress(): void;
  hideSaveProgress(): void;
  showLoadingState(fieldName: string): void;
  hideLoadingState(fieldName: string): void;
  updateFormValidityState(isValid: boolean, errorCount: number): void;
  processValidationResult(fieldName: string, result: FieldValidationResult): void;
  processFormValidationResult(result: ValidationResult): void;
  createActionNotification(message: string, actions: Array<{ label: string; action: () => void; style?: 'primary' | 'secondary' }>, type?: ValidationMessageType): HTMLElement;
  // Enhanced features
  showAutoFixSuggestions(fieldName: string, autoFixes: AutoFixSuggestion[]): void;
  showContextualHelp(fieldName: string, help: ContextualHelp): void;
  createSmartErrorMessage(fieldName: string, error: any, autoFixes: AutoFixSuggestion[]): HTMLElement;
  applyAutoFix(autoFix: AutoFixSuggestion): Promise<boolean>;
}

/**
 * Validation message types
 */
export type ValidationMessageType = 'error' | 'warning' | 'success' | 'info';

/**
 * Validation display configuration
 */
interface ValidationDisplayConfig {
  autoHideDelay: number;
  maxErrorLength: number;
  showFieldIcons: boolean;
  animateChanges: boolean;
}

/**
 * ValidationDisplay implementation for comprehensive user feedback
 */
export class ValidationDisplay implements IValidationDisplay {
  private config: ValidationDisplayConfig;
  private fieldValidationElements: Map<string, HTMLElement> = new Map();
  private formMessageElement?: HTMLElement;
  private formStatusElement?: HTMLElement;
  private saveProgressElement?: HTMLElement;
  private autoFixCallbacks: Map<string, (autoFix: AutoFixSuggestion) => Promise<void>> = new Map();

  constructor(config: Partial<ValidationDisplayConfig> = {}) {
    this.config = {
      autoHideDelay: 5000,
      maxErrorLength: 200,
      showFieldIcons: true,
      animateChanges: true,
      ...config
    };

    this.initializeStyles();
  }

  /**
   * Set auto-fix callback for field
   */
  setAutoFixCallback(fieldName: string, callback: (autoFix: AutoFixSuggestion) => Promise<void>): void {
    this.autoFixCallbacks.set(fieldName, callback);
  }

  /**
   * Show field-level error message
   */
  showFieldError(fieldName: string, error: string, suggestion?: string): void {
    const fieldContainer = this.getFieldContainer(fieldName);
    if (!fieldContainer) return;

    const validationEl = this.getOrCreateValidationElement(fieldName, fieldContainer);

    // Clear existing content
    validationEl.innerHTML = '';
    validationEl.className = 'thoth-field-validation thoth-validation-error';

    // Create error content
    const errorContent = validationEl.createEl('div', { cls: 'thoth-validation-content' });

    if (this.config.showFieldIcons) {
      errorContent.createEl('span', { text: '❌', cls: 'thoth-validation-icon' });
    }

    const errorText = this.truncateText(error, this.config.maxErrorLength);
    errorContent.createEl('span', { text: errorText, cls: 'thoth-validation-text' });

    // Add suggestion if provided
    if (suggestion) {
      const suggestionEl = validationEl.createEl('div', { cls: 'thoth-validation-suggestion' });
      suggestionEl.createEl('span', { text: '💡', cls: 'thoth-suggestion-icon' });
      suggestionEl.createEl('span', { text: suggestion, cls: 'thoth-suggestion-text' });
    }

    // Show validation element
    validationEl.style.display = 'block';

    // Update field container state
    this.updateFieldState(fieldContainer, 'error');

    // Animate if enabled
    if (this.config.animateChanges) {
      this.animateValidationChange(validationEl);
    }
  }

  /**
   * Show field-level success message
   */
  showFieldSuccess(fieldName: string): void {
    const fieldContainer = this.getFieldContainer(fieldName);
    if (!fieldContainer) return;

    const validationEl = this.getOrCreateValidationElement(fieldName, fieldContainer);

    // Clear existing content
    validationEl.innerHTML = '';
    validationEl.className = 'thoth-field-validation thoth-validation-success';

    // Create success content
    const successContent = validationEl.createEl('div', { cls: 'thoth-validation-content' });

    if (this.config.showFieldIcons) {
      successContent.createEl('span', { text: '✅', cls: 'thoth-validation-icon' });
    }

    successContent.createEl('span', { text: 'Valid', cls: 'thoth-validation-text' });

    // Show validation element briefly
    validationEl.style.display = 'block';

    // Update field container state
    this.updateFieldState(fieldContainer, 'success');

    // Auto-hide success messages after a short delay
    setTimeout(() => {
      this.hideFieldValidation(validationEl, fieldContainer);
    }, 2000);
  }

  /**
   * Show field-level warning message
   */
  showFieldWarning(fieldName: string, warning: string): void {
    const fieldContainer = this.getFieldContainer(fieldName);
    if (!fieldContainer) return;

    const validationEl = this.getOrCreateValidationElement(fieldName, fieldContainer);

    // Clear existing content
    validationEl.innerHTML = '';
    validationEl.className = 'thoth-field-validation thoth-validation-warning';

    // Create warning content
    const warningContent = validationEl.createEl('div', { cls: 'thoth-validation-content' });

    if (this.config.showFieldIcons) {
      warningContent.createEl('span', { text: '⚠️', cls: 'thoth-validation-icon' });
    }

    const warningText = this.truncateText(warning, this.config.maxErrorLength);
    warningContent.createEl('span', { text: warningText, cls: 'thoth-validation-text' });

    // Show validation element
    validationEl.style.display = 'block';

    // Update field container state
    this.updateFieldState(fieldContainer, 'warning');

    // Animate if enabled
    if (this.config.animateChanges) {
      this.animateValidationChange(validationEl);
    }
  }

  /**
   * Clear field validation
   */
  clearFieldValidation(fieldName: string): void {
    const fieldContainer = this.getFieldContainer(fieldName);
    if (!fieldContainer) return;

    const validationEl = this.fieldValidationElements.get(fieldName);
    if (validationEl) {
      this.hideFieldValidation(validationEl, fieldContainer);
    }
  }

  /**
   * Show form-level error message
   */
  showFormError(message: string): void {
    this.showFormMessage(message, 'error');
  }

  /**
   * Show form-level success message
   */
  showFormSuccess(message: string): void {
    this.showFormMessage(message, 'success');
  }

  /**
   * Show form-level warning message
   */
  showFormWarning(message: string): void {
    this.showFormMessage(message, 'warning');
  }

  /**
   * Show form-level info message
   */
  showFormInfo(message: string): void {
    this.showFormMessage(message, 'info');
  }

  /**
   * Clear all form messages
   */
  clearFormMessages(): void {
    if (this.formMessageElement) {
      this.formMessageElement.style.display = 'none';
    }
  }

  /**
   * Show save progress indicator
   */
  showSaveProgress(): void {
    const formContainer = this.getFormContainer();
    if (!formContainer) return;

    if (!this.saveProgressElement) {
      this.saveProgressElement = formContainer.createEl('div', { cls: 'thoth-save-progress' });
    }

    this.saveProgressElement.innerHTML = `
      <div class="thoth-progress-content">
        <div class="thoth-spinner"></div>
        <span>Saving configuration...</span>
      </div>
    `;

    this.saveProgressElement.style.display = 'flex';

    // Disable all form inputs
    this.setFormDisabled(true);
  }

  /**
   * Hide save progress indicator
   */
  hideSaveProgress(): void {
    if (this.saveProgressElement) {
      this.saveProgressElement.style.display = 'none';
    }

    // Re-enable form inputs
    this.setFormDisabled(false);
  }

  /**
   * Show loading state for specific field
   */
  showLoadingState(fieldName: string): void {
    const fieldContainer = this.getFieldContainer(fieldName);
    if (!fieldContainer) return;

    // Add loading indicator to field
    let loadingEl = fieldContainer.querySelector('.thoth-field-loading') as HTMLElement;
    if (!loadingEl) {
      loadingEl = fieldContainer.createEl('div', { cls: 'thoth-field-loading' });
      loadingEl.innerHTML = '<div class="thoth-mini-spinner"></div>';
    }

    loadingEl.style.display = 'inline-block';
  }

  /**
   * Hide loading state for specific field
   */
  hideLoadingState(fieldName: string): void {
    const fieldContainer = this.getFieldContainer(fieldName);
    if (!fieldContainer) return;

    const loadingEl = fieldContainer.querySelector('.thoth-field-loading') as HTMLElement;
    if (loadingEl) {
      loadingEl.style.display = 'none';
    }
  }

  /**
   * Update form validity state
   */
  updateFormValidityState(isValid: boolean, errorCount: number): void {
    const formContainer = this.getFormContainer();
    if (!formContainer) return;

    // Update form status element
    if (!this.formStatusElement) {
      this.formStatusElement = formContainer.createEl('div', { cls: 'thoth-form-status' });
    }

    this.formStatusElement.className = `thoth-form-status ${isValid ? 'valid' : 'invalid'}`;

    if (isValid) {
      this.formStatusElement.innerHTML = `
        <span class="thoth-status-icon">✅</span>
        <span>Configuration is valid</span>
      `;
    } else {
      this.formStatusElement.innerHTML = `
        <span class="thoth-status-icon">❌</span>
        <span>${errorCount} validation error${errorCount !== 1 ? 's' : ''}</span>
      `;
    }

    this.formStatusElement.style.display = 'flex';
  }

  /**
   * Process validation result and update display
   */
  processValidationResult(fieldName: string, result: FieldValidationResult): void {
    if (result.is_valid) {
      this.showFieldSuccess(fieldName);
    } else if (result.error) {
      this.showFieldError(fieldName, result.error);
    } else if (result.warning) {
      this.showFieldWarning(fieldName, result.warning);
    }
  }

  /**
   * Process full form validation result
   */
  processFormValidationResult(result: ValidationResult): void {
    this.clearFormMessages();

    if (result.is_valid) {
      this.showFormSuccess('All configuration is valid');
    } else {
      // Show errors
      if (result.errors && result.errors.length > 0) {
        for (const error of result.errors) {
          this.showFieldError(error.field, error.message);
        }
        this.showFormError(`Found ${result.error_count} configuration error${result.error_count !== 1 ? 's' : ''}`);
      }

      // Show warnings
      if (result.warnings && result.warnings.length > 0) {
        for (const warning of result.warnings) {
          this.showFieldWarning(warning.field, warning.message);
        }
      }
    }

    this.updateFormValidityState(result.is_valid, result.error_count);
  }

  /**
   * Show auto-fix suggestions for a field
   */
  showAutoFixSuggestions(fieldName: string, autoFixes: AutoFixSuggestion[]): void {
    const fieldContainer = this.getFieldContainer(fieldName);
    if (!fieldContainer || autoFixes.length === 0) return;

    const validationEl = this.getOrCreateValidationElement(fieldName, fieldContainer);

    // Create auto-fix container
    const autoFixContainer = validationEl.createEl('div', { cls: 'thoth-auto-fix-container' });
    autoFixContainer.createEl('div', { text: '🔧 Auto-fix suggestions:', cls: 'thoth-auto-fix-header' });

    const fixesList = autoFixContainer.createEl('div', { cls: 'thoth-auto-fix-list' });

    for (const autoFix of autoFixes) {
      const fixEl = fixesList.createEl('div', { cls: 'thoth-auto-fix-item' });

      // Fix description with confidence indicator
      const descEl = fixEl.createEl('div', { cls: 'thoth-auto-fix-description' });
      descEl.createEl('span', { text: autoFix.description });
      descEl.createEl('span', {
        text: ` (${Math.round(autoFix.confidence * 100)}% confidence)`,
        cls: 'thoth-auto-fix-confidence'
      });

      // Risk level indicator
      const riskEl = fixEl.createEl('span', {
        text: autoFix.risk_level.toUpperCase(),
        cls: `thoth-risk-level thoth-risk-${autoFix.risk_level}`
      });

      // Apply button
      const applyBtn = fixEl.createEl('button', {
        text: 'Apply Fix',
        cls: 'thoth-auto-fix-apply-btn'
      });

      applyBtn.addEventListener('click', async () => {
        applyBtn.disabled = true;
        applyBtn.textContent = 'Applying...';

        try {
          const success = await this.applyAutoFix(autoFix);
          if (success) {
            fixEl.classList.add('thoth-auto-fix-applied');
            applyBtn.textContent = 'Applied ✓';
            applyBtn.classList.add('applied');
          } else {
            applyBtn.textContent = 'Failed ✗';
            applyBtn.classList.add('failed');
          }
        } catch (error) {
          console.error('Auto-fix application failed:', error);
          applyBtn.textContent = 'Error ✗';
          applyBtn.classList.add('failed');
        }
      });
    }

    validationEl.style.display = 'block';
  }

  /**
   * Show contextual help for a field
   */
  showContextualHelp(fieldName: string, help: ContextualHelp): void {
    const fieldContainer = this.getFieldContainer(fieldName);
    if (!fieldContainer) return;

    // Create help toggle button
    let helpBtn = fieldContainer.querySelector('.thoth-help-toggle') as HTMLButtonElement;
    if (!helpBtn) {
      helpBtn = fieldContainer.createEl('button', {
        text: '?',
        cls: 'thoth-help-toggle',
        title: 'Show help'
      });
    }

    // Create help panel
    let helpPanel = fieldContainer.querySelector('.thoth-help-panel') as HTMLElement;
    if (!helpPanel) {
      helpPanel = fieldContainer.createEl('div', { cls: 'thoth-help-panel' });
      helpPanel.style.display = 'none';
    }

    // Populate help content
    helpPanel.innerHTML = '';

    const helpHeader = helpPanel.createEl('div', { cls: 'thoth-help-header' });
    helpHeader.createEl('h4', { text: help.title });
    helpHeader.createEl('button', { text: '×', cls: 'thoth-help-close' });

    helpPanel.createEl('p', { text: help.content, cls: 'thoth-help-content' });

    // Examples
    if (help.examples.length > 0) {
      const examplesEl = helpPanel.createEl('div', { cls: 'thoth-help-examples' });
      examplesEl.createEl('h5', { text: 'Examples:' });
      const examplesList = examplesEl.createEl('ul');
      for (const example of help.examples) {
        examplesList.createEl('li', { text: example });
      }
    }

    // Troubleshooting steps
    if (help.troubleshooting_steps.length > 0) {
      const stepsEl = helpPanel.createEl('div', { cls: 'thoth-help-troubleshooting' });
      stepsEl.createEl('h5', { text: 'Troubleshooting:' });
      const stepsList = stepsEl.createEl('ol');
      for (const step of help.troubleshooting_steps) {
        stepsList.createEl('li', { text: step });
      }
    }

    // Documentation links
    if (help.documentation_links.length > 0) {
      const linksEl = helpPanel.createEl('div', { cls: 'thoth-help-links' });
      linksEl.createEl('h5', { text: 'Documentation:' });
      for (const link of help.documentation_links) {
        const linkEl = linksEl.createEl('a', {
          text: link,
          href: link,
          cls: 'thoth-help-link'
        });
        linkEl.target = '_blank';
      }
    }

    // Toggle functionality
    helpBtn.addEventListener('click', () => {
      const isVisible = helpPanel.style.display !== 'none';
      helpPanel.style.display = isVisible ? 'none' : 'block';
      helpBtn.textContent = isVisible ? '?' : '×';
    });

    // Close functionality
    const closeBtn = helpPanel.querySelector('.thoth-help-close') as HTMLButtonElement;
    closeBtn?.addEventListener('click', () => {
      helpPanel.style.display = 'none';
      helpBtn.textContent = '?';
    });
  }

  /**
   * Create smart error message with auto-fix integration
   */
  createSmartErrorMessage(fieldName: string, error: any, autoFixes: AutoFixSuggestion[]): HTMLElement {
    const errorContainer = document.createElement('div');
    errorContainer.className = 'thoth-smart-error-message';

    // Main error message
    const errorHeader = errorContainer.createEl('div', { cls: 'thoth-error-header' });
    errorHeader.createEl('span', { text: '❌', cls: 'thoth-error-icon' });
    errorHeader.createEl('span', { text: error.message || error, cls: 'thoth-error-text' });

    // Severity indicator
    if (error.severity) {
      const severityEl = errorContainer.createEl('span', {
        text: error.severity.toUpperCase(),
        cls: `thoth-severity thoth-severity-${error.severity}`
      });
    }

    // Context-aware help
    if (error.contextual_help) {
      const helpBtn = errorContainer.createEl('button', {
        text: 'Get Help',
        cls: 'thoth-error-help-btn'
      });
      helpBtn.addEventListener('click', () => {
        this.showContextualHelp(fieldName, error.contextual_help);
      });
    }

    // Auto-fix suggestions
    if (autoFixes.length > 0) {
      this.showAutoFixSuggestions(fieldName, autoFixes);
    }

    return errorContainer;
  }

  /**
   * Apply auto-fix suggestion
   */
  async applyAutoFix(autoFix: AutoFixSuggestion): Promise<boolean> {
    try {
      const callback = this.autoFixCallbacks.get(autoFix.field_path);
      if (!callback) {
        console.warn(`No auto-fix callback registered for field: ${autoFix.field_path}`);
        return false;
      }

      await callback(autoFix);

      // Show success notification
      this.showFormSuccess(`Auto-fix applied: ${autoFix.description}`);

      // Clear field validation after successful fix
      this.clearFieldValidation(autoFix.field_path);

      return true;
    } catch (error) {
      console.error('Failed to apply auto-fix:', error);
      this.showFormError(`Auto-fix failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Create notification with action buttons
   */
  createActionNotification(
    message: string,
    actions: Array<{ label: string; action: () => void; style?: 'primary' | 'secondary' }>,
    type: ValidationMessageType = 'info'
  ): HTMLElement {
    const container = document.createElement('div');
    container.className = `thoth-action-notification thoth-notification-${type}`;

    // Message content
    const contentEl = container.createEl('div', { cls: 'thoth-notification-content' });
    contentEl.createEl('span', { text: this.getIconForType(type), cls: 'thoth-notification-icon' });
    contentEl.createEl('span', { text: message, cls: 'thoth-notification-text' });

    // Actions
    if (actions.length > 0) {
      const actionsEl = container.createEl('div', { cls: 'thoth-notification-actions' });

      for (const action of actions) {
        const btnEl = actionsEl.createEl('button', {
          text: action.label,
          cls: `thoth-notification-btn ${action.style === 'primary' ? 'primary' : 'secondary'}`
        });

        btnEl.addEventListener('click', () => {
          action.action();
          container.remove(); // Remove notification after action
        });
      }
    }

    return container;
  }

  /**
   * Show validation summary
   */
  showValidationSummary(validFields: number, totalFields: number, errors: string[]): void {
    const formContainer = this.getFormContainer();
    if (!formContainer) return;

    // Remove existing summary
    const existingSummary = formContainer.querySelector('.thoth-validation-summary');
    if (existingSummary) {
      existingSummary.remove();
    }

    // Create new summary
    const summaryEl = formContainer.createEl('div', { cls: 'thoth-validation-summary' });

    const progressBar = summaryEl.createEl('div', { cls: 'thoth-validation-progress' });
    const progressFill = progressBar.createEl('div', { cls: 'thoth-validation-progress-fill' });
    progressFill.style.width = `${(validFields / totalFields) * 100}%`;

    const summaryText = summaryEl.createEl('div', { cls: 'thoth-validation-summary-text' });
    summaryText.textContent = `${validFields}/${totalFields} fields valid`;

    // Show errors if any
    if (errors.length > 0) {
      const errorsEl = summaryEl.createEl('div', { cls: 'thoth-validation-errors' });
      errorsEl.createEl('h4', { text: 'Validation Errors:' });

      const errorsList = errorsEl.createEl('ul');
      for (const error of errors.slice(0, 5)) { // Show max 5 errors
        errorsList.createEl('li', { text: error });
      }

      if (errors.length > 5) {
        errorsList.createEl('li', { text: `... and ${errors.length - 5} more` });
      }
    }
  }

  /**
   * Get or create validation element for field
   */
  private getOrCreateValidationElement(fieldName: string, fieldContainer: HTMLElement): HTMLElement {
    let validationEl = this.fieldValidationElements.get(fieldName);

    if (!validationEl) {
      validationEl = fieldContainer.createEl('div', { cls: 'thoth-field-validation' });
      validationEl.style.display = 'none';
      this.fieldValidationElements.set(fieldName, validationEl);
    }

    return validationEl;
  }

  /**
   * Get field container element
   */
  private getFieldContainer(fieldName: string): HTMLElement | null {
    return document.querySelector(`[data-field-name="${fieldName}"]`) as HTMLElement;
  }

  /**
   * Get form container element
   */
  private getFormContainer(): HTMLElement | null {
    return document.querySelector('.thoth-settings-form') as HTMLElement;
  }

  /**
   * Show form-level message
   */
  private showFormMessage(message: string, type: ValidationMessageType): void {
    const formContainer = this.getFormContainer();
    if (!formContainer) return;

    if (!this.formMessageElement) {
      this.formMessageElement = formContainer.createEl('div', { cls: 'thoth-form-message' });
    }

    this.formMessageElement.className = `thoth-form-message thoth-message-${type}`;
    this.formMessageElement.innerHTML = `
      <div class="thoth-message-content">
        <span class="thoth-message-icon">${this.getIconForType(type)}</span>
        <span class="thoth-message-text">${message}</span>
        <button class="thoth-message-close" title="Close">×</button>
      </div>
    `;

    this.formMessageElement.style.display = 'block';

    // Add close functionality
    const closeBtn = this.formMessageElement.querySelector('.thoth-message-close') as HTMLButtonElement;
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        this.clearFormMessages();
      });
    }

    // Auto-hide non-error messages
    if (type !== 'error') {
      setTimeout(() => {
        this.clearFormMessages();
      }, this.config.autoHideDelay);
    }

    // Animate if enabled
    if (this.config.animateChanges) {
      this.animateFormMessage(this.formMessageElement);
    }
  }

  /**
   * Update field state styling
   */
  private updateFieldState(fieldContainer: HTMLElement, state: 'error' | 'warning' | 'success' | 'normal'): void {
    // Remove all state classes
    fieldContainer.classList.remove(
      'thoth-field-error',
      'thoth-field-warning',
      'thoth-field-success',
      'thoth-field-normal'
    );

    // Add new state class
    fieldContainer.classList.add(`thoth-field-${state}`);
  }

  /**
   * Hide field validation element
   */
  private hideFieldValidation(validationEl: HTMLElement, fieldContainer: HTMLElement): void {
    validationEl.style.display = 'none';
    this.updateFieldState(fieldContainer, 'normal');
  }

  /**
   * Set form disabled state
   */
  private setFormDisabled(disabled: boolean): void {
    const formContainer = this.getFormContainer();
    if (!formContainer) return;

    const inputs = formContainer.querySelectorAll('input, select, textarea, button');
    inputs.forEach(input => {
      if (input instanceof HTMLInputElement || input instanceof HTMLSelectElement ||
          input instanceof HTMLTextAreaElement || input instanceof HTMLButtonElement) {
        // Don't disable the close button for messages
        if (!input.classList.contains('thoth-message-close')) {
          input.disabled = disabled;
        }
      }
    });
  }

  /**
   * Get icon for validation type
   */
  private getIconForType(type: ValidationMessageType): string {
    const iconMap = {
      error: '❌',
      warning: '⚠️',
      success: '✅',
      info: 'ℹ️'
    };
    return iconMap[type] || 'ℹ️';
  }

  /**
   * Truncate text if too long
   */
  private truncateText(text: string, maxLength: number): string {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - 3) + '...';
  }

  /**
   * Animate validation change
   */
  private animateValidationChange(element: HTMLElement): void {
    element.style.opacity = '0';
    element.style.transform = 'translateY(-10px)';

    // Force reflow
    element.offsetHeight;

    element.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    element.style.opacity = '1';
    element.style.transform = 'translateY(0)';
  }

  /**
   * Animate form message
   */
  private animateFormMessage(element: HTMLElement): void {
    element.style.opacity = '0';
    element.style.transform = 'scale(0.95)';

    // Force reflow
    element.offsetHeight;

    element.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
    element.style.opacity = '1';
    element.style.transform = 'scale(1)';
  }

  /**
   * Initialize validation display styles
   */
  private initializeStyles(): void {
    if (document.getElementById('thoth-validation-styles')) {
      return; // Styles already loaded
    }

    const style = document.createElement('style');
    style.id = 'thoth-validation-styles';
    style.textContent = `
      /* Field validation styles */
      .thoth-field-validation {
        margin-top: 6px;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 0.85em;
        line-height: 1.4;
        border-left: 4px solid;
      }

      .thoth-validation-error {
        background: rgba(255, 0, 0, 0.1);
        border-left-color: var(--color-red);
        color: var(--color-red);
      }

      .thoth-validation-warning {
        background: rgba(255, 165, 0, 0.1);
        border-left-color: var(--color-orange);
        color: var(--color-orange);
      }

      .thoth-validation-success {
        background: rgba(0, 255, 0, 0.1);
        border-left-color: var(--color-green);
        color: var(--color-green);
      }

      .thoth-validation-content {
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .thoth-validation-icon {
        font-size: 1em;
        flex-shrink: 0;
      }

      .thoth-validation-text {
        flex: 1;
      }

      .thoth-validation-suggestion {
        margin-top: 6px;
        padding: 6px;
        background: rgba(0, 0, 0, 0.05);
        border-radius: 3px;
        display: flex;
        align-items: center;
        gap: 6px;
        font-style: italic;
      }

      .thoth-suggestion-icon {
        font-size: 0.9em;
      }

      /* Field state styles */
      .thoth-field-error {
        border-left: 3px solid var(--color-red);
        padding-left: 8px;
      }

      .thoth-field-warning {
        border-left: 3px solid var(--color-orange);
        padding-left: 8px;
      }

      .thoth-field-success {
        border-left: 3px solid var(--color-green);
        padding-left: 8px;
      }

      /* Form message styles */
      .thoth-form-message {
        margin: 16px 0;
        padding: 12px 16px;
        border-radius: 6px;
        border-left: 4px solid;
      }

      .thoth-message-error {
        background: rgba(255, 0, 0, 0.1);
        border-left-color: var(--color-red);
      }

      .thoth-message-warning {
        background: rgba(255, 165, 0, 0.1);
        border-left-color: var(--color-orange);
      }

      .thoth-message-success {
        background: rgba(0, 255, 0, 0.1);
        border-left-color: var(--color-green);
      }

      .thoth-message-info {
        background: rgba(0, 123, 255, 0.1);
        border-left-color: var(--interactive-accent);
      }

      .thoth-message-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }

      .thoth-message-icon {
        font-size: 1.1em;
        flex-shrink: 0;
      }

      .thoth-message-text {
        flex: 1;
        font-weight: 500;
      }

      .thoth-message-close {
        background: none;
        border: none;
        font-size: 1.2em;
        cursor: pointer;
        opacity: 0.7;
        padding: 0;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .thoth-message-close:hover {
        opacity: 1;
      }

      /* Progress and loading styles */
      .thoth-save-progress {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: var(--background-primary);
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
        padding: 20px 30px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        z-index: 1000;
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .thoth-progress-content {
        display: flex;
        align-items: center;
        gap: 12px;
        font-weight: 500;
      }

      .thoth-spinner {
        width: 20px;
        height: 20px;
        border: 2px solid var(--background-modifier-border);
        border-top: 2px solid var(--interactive-accent);
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }

      .thoth-mini-spinner {
        width: 12px;
        height: 12px;
        border: 1px solid var(--background-modifier-border);
        border-top: 1px solid var(--interactive-accent);
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }

      .thoth-field-loading {
        margin-left: 8px;
        display: inline-flex;
        align-items: center;
      }

      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }

      /* Form status styles */
      .thoth-form-status {
        margin: 16px 0;
        padding: 10px 16px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 500;
      }

      .thoth-form-status.valid {
        background: rgba(0, 255, 0, 0.1);
        color: var(--color-green);
      }

      .thoth-form-status.invalid {
        background: rgba(255, 0, 0, 0.1);
        color: var(--color-red);
      }

      .thoth-status-icon {
        font-size: 1.1em;
      }

      /* Validation summary styles */
      .thoth-validation-summary {
        margin: 16px 0;
        padding: 12px;
        background: var(--background-secondary);
        border-radius: 6px;
        border: 1px solid var(--background-modifier-border);
      }

      .thoth-validation-progress {
        height: 6px;
        background: var(--background-modifier-border);
        border-radius: 3px;
        overflow: hidden;
        margin-bottom: 8px;
      }

      .thoth-validation-progress-fill {
        height: 100%;
        background: var(--interactive-accent);
        transition: width 0.3s ease;
      }

      .thoth-validation-summary-text {
        font-weight: 500;
        margin-bottom: 8px;
      }

      .thoth-validation-errors h4 {
        margin: 0 0 6px 0;
        font-size: 0.9em;
        color: var(--color-red);
      }

      .thoth-validation-errors ul {
        margin: 0;
        padding-left: 16px;
      }

      .thoth-validation-errors li {
        margin: 2px 0;
        font-size: 0.85em;
        color: var(--text-muted);
      }

      /* Action notification styles */
      .thoth-action-notification {
        margin: 12px 0;
        padding: 12px 16px;
        border-radius: 6px;
        border-left: 4px solid;
      }

      .thoth-notification-error {
        background: rgba(255, 0, 0, 0.1);
        border-left-color: var(--color-red);
      }

      .thoth-notification-warning {
        background: rgba(255, 165, 0, 0.1);
        border-left-color: var(--color-orange);
      }

      .thoth-notification-success {
        background: rgba(0, 255, 0, 0.1);
        border-left-color: var(--color-green);
      }

      .thoth-notification-info {
        background: rgba(0, 123, 255, 0.1);
        border-left-color: var(--interactive-accent);
      }

      .thoth-notification-content {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
      }

      .thoth-notification-actions {
        display: flex;
        gap: 8px;
        margin-top: 8px;
      }

      .thoth-notification-btn {
        padding: 6px 12px;
        border-radius: 4px;
        border: 1px solid var(--background-modifier-border);
        background: var(--background-secondary);
        cursor: pointer;
        font-size: 0.85em;
        transition: all 0.2s ease;
      }

      .thoth-notification-btn:hover {
        background: var(--background-modifier-hover);
      }

      .thoth-notification-btn.primary {
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        border-color: var(--interactive-accent);
      }

      .thoth-notification-btn.primary:hover {
        background: var(--interactive-accent-hover);
      }

      /* Required field indicator */
      .thoth-required-indicator {
        color: var(--color-red);
        font-weight: bold;
      }

      /* Auto-fix styles */
      .thoth-auto-fix-container {
        margin-top: 8px;
        padding: 10px;
        background: rgba(0, 123, 255, 0.05);
        border: 1px solid var(--interactive-accent);
        border-radius: 6px;
      }

      .thoth-auto-fix-header {
        font-weight: 600;
        margin-bottom: 8px;
        color: var(--interactive-accent);
      }

      .thoth-auto-fix-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      .thoth-auto-fix-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 8px;
        background: var(--background-secondary);
        border-radius: 4px;
        gap: 8px;
      }

      .thoth-auto-fix-description {
        flex: 1;
        font-size: 0.9em;
      }

      .thoth-auto-fix-confidence {
        font-size: 0.8em;
        color: var(--text-muted);
      }

      .thoth-risk-level {
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 0.7em;
        font-weight: 600;
        text-transform: uppercase;
      }

      .thoth-risk-low {
        background: rgba(0, 255, 0, 0.2);
        color: var(--color-green);
      }

      .thoth-risk-medium {
        background: rgba(255, 165, 0, 0.2);
        color: var(--color-orange);
      }

      .thoth-risk-high {
        background: rgba(255, 0, 0, 0.2);
        color: var(--color-red);
      }

      .thoth-auto-fix-apply-btn {
        padding: 4px 8px;
        border-radius: 3px;
        border: 1px solid var(--interactive-accent);
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        cursor: pointer;
        font-size: 0.8em;
        transition: all 0.2s ease;
      }

      .thoth-auto-fix-apply-btn:hover {
        background: var(--interactive-accent-hover);
      }

      .thoth-auto-fix-apply-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }

      .thoth-auto-fix-apply-btn.applied {
        background: var(--color-green);
        border-color: var(--color-green);
      }

      .thoth-auto-fix-apply-btn.failed {
        background: var(--color-red);
        border-color: var(--color-red);
      }

      .thoth-auto-fix-applied {
        opacity: 0.7;
        background: rgba(0, 255, 0, 0.1);
      }

      /* Help panel styles */
      .thoth-help-toggle {
        width: 20px;
        height: 20px;
        border-radius: 50%;
        border: 1px solid var(--text-muted);
        background: var(--background-secondary);
        color: var(--text-muted);
        cursor: pointer;
        font-size: 0.8em;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-left: 8px;
      }

      .thoth-help-toggle:hover {
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        border-color: var(--interactive-accent);
      }

      .thoth-help-panel {
        position: absolute;
        top: 100%;
        right: 0;
        width: 300px;
        max-height: 400px;
        overflow-y: auto;
        background: var(--background-primary);
        border: 1px solid var(--background-modifier-border);
        border-radius: 6px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        z-index: 1000;
        padding: 12px;
      }

      .thoth-help-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        padding-bottom: 6px;
        border-bottom: 1px solid var(--background-modifier-border);
      }

      .thoth-help-header h4 {
        margin: 0;
        font-size: 1em;
        color: var(--text-normal);
      }

      .thoth-help-close {
        background: none;
        border: none;
        font-size: 1.2em;
        cursor: pointer;
        color: var(--text-muted);
        padding: 0;
        width: 20px;
        height: 20px;
      }

      .thoth-help-close:hover {
        color: var(--text-normal);
      }

      .thoth-help-content {
        margin: 8px 0;
        line-height: 1.4;
        color: var(--text-normal);
      }

      .thoth-help-examples h5,
      .thoth-help-troubleshooting h5 {
        margin: 10px 0 4px 0;
        font-size: 0.9em;
        color: var(--interactive-accent);
      }

      .thoth-help-examples ul,
      .thoth-help-troubleshooting ol {
        margin: 4px 0;
        padding-left: 16px;
      }

      .thoth-help-examples li,
      .thoth-help-troubleshooting li {
        margin: 2px 0;
        font-size: 0.85em;
        color: var(--text-muted);
      }

      .thoth-help-links {
        margin-top: 10px;
        padding-top: 6px;
        border-top: 1px solid var(--background-modifier-border);
      }

      .thoth-help-links h5 {
        margin: 0 0 4px 0;
        font-size: 0.9em;
        color: var(--interactive-accent);
      }

      .thoth-help-link {
        display: block;
        margin: 2px 0;
        font-size: 0.85em;
        color: var(--interactive-accent);
        text-decoration: none;
      }

      .thoth-help-link:hover {
        text-decoration: underline;
      }

      /* Smart error message styles */
      .thoth-smart-error-message {
        margin-top: 6px;
        padding: 10px;
        background: rgba(255, 0, 0, 0.08);
        border: 1px solid rgba(255, 0, 0, 0.2);
        border-radius: 6px;
      }

      .thoth-error-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
      }

      .thoth-error-icon {
        font-size: 1em;
        flex-shrink: 0;
      }

      .thoth-error-text {
        flex: 1;
        font-weight: 500;
        color: var(--color-red);
      }

      .thoth-severity {
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 0.7em;
        font-weight: 600;
      }

      .thoth-severity-error {
        background: rgba(255, 0, 0, 0.2);
        color: var(--color-red);
      }

      .thoth-severity-warning {
        background: rgba(255, 165, 0, 0.2);
        color: var(--color-orange);
      }

      .thoth-error-help-btn {
        padding: 4px 8px;
        border-radius: 3px;
        border: 1px solid var(--interactive-accent);
        background: transparent;
        color: var(--interactive-accent);
        cursor: pointer;
        font-size: 0.8em;
        margin-left: auto;
      }

      .thoth-error-help-btn:hover {
        background: var(--interactive-accent);
        color: var(--text-on-accent);
      }
    `;

    document.head.appendChild(style);
  }
}

/**
 * Validation display utilities
 */
export class ValidationDisplayUtils {
  /**
   * Create field validation element
   */
  static createValidationElement(container: HTMLElement, type: ValidationMessageType): HTMLElement {
    const validationEl = container.createEl('div', { cls: `thoth-field-validation thoth-validation-${type}` });
    validationEl.style.display = 'none';
    return validationEl;
  }

  /**
   * Format validation error for display
   */
  static formatValidationError(error: string, suggestion?: string): string {
    let formatted = error;
    if (suggestion) {
      formatted += ` Suggestion: ${suggestion}`;
    }
    return formatted;
  }

  /**
   * Extract field name from validation error
   */
  static extractFieldFromError(error: any): string | null {
    if (error && typeof error === 'object' && error.field) {
      return error.field;
    }
    return null;
  }

  /**
   * Group validation errors by field
   */
  static groupErrorsByField(errors: any[]): Map<string, string[]> {
    const grouped = new Map<string, string[]>();

    for (const error of errors) {
      const field = this.extractFieldFromError(error);
      if (field) {
        if (!grouped.has(field)) {
          grouped.set(field, []);
        }
        grouped.get(field)!.push(error.message || error.toString());
      }
    }

    return grouped;
  }

  /**
   * Create validation summary text
   */
  static createValidationSummary(validCount: number, totalCount: number, errorCount: number): string {
    if (errorCount === 0) {
      return `All ${totalCount} fields are valid`;
    } else {
      return `${validCount}/${totalCount} fields valid, ${errorCount} error${errorCount !== 1 ? 's' : ''}`;
    }
  }
}
