import { Setting, Platform } from 'obsidian';
import { FieldSchema } from '../services/schema-service';

/**
 * Field component interface
 */
export interface IFieldComponent {
  render(): HTMLElement;
  getValue(): any;
  setValue(value: any): void;
  validate(): boolean;
  setValidationMessage(message: string, isError: boolean): void;
  clearValidation(): void;
  setOnChange(callback: (value: any) => void): void;
}

/**
 * Base field component with common functionality
 */
export abstract class BaseFieldComponent implements IFieldComponent {
  protected setting: Setting;
  protected fieldName: string;
  protected fieldSchema: FieldSchema;
  protected currentValue: any;
  protected onChange?: (value: any) => void;
  protected validationEl?: HTMLElement;
  protected container: HTMLElement;

  constructor(fieldName: string, fieldSchema: FieldSchema, currentValue: any) {
    this.fieldName = fieldName;
    this.fieldSchema = fieldSchema;
    this.currentValue = currentValue;
  }

  abstract render(): HTMLElement;
  abstract getValue(): any;
  abstract setValue(value: any): void;

  /**
   * Set change callback
   */
  setOnChange(callback: (value: any) => void): void {
    this.onChange = callback;
  }

  /**
   * Trigger change event
   */
  protected triggerChange(value: any): void {
    this.currentValue = value;
    if (this.onChange) {
      this.onChange(value);
    }
  }

  /**
   * Basic validation
   */
  validate(): boolean {
    // Required field validation
    if (this.fieldSchema.required && (this.currentValue === undefined || this.currentValue === null || this.currentValue === '')) {
      this.setValidationMessage('This field is required', true);
      return false;
    }

    this.clearValidation();
    return true;
  }

  /**
   * Set validation message
   */
  setValidationMessage(message: string, isError: boolean): void {
    if (!this.validationEl) {
      this.validationEl = this.container.createEl('div', { cls: 'thoth-field-validation' });
    }

    this.validationEl.textContent = message;
    this.validationEl.className = `thoth-field-validation ${isError ? 'error' : 'warning'}`;
    this.validationEl.style.display = 'block';

    // Update container styling
    this.container.classList.toggle('thoth-field-error', isError);
    this.container.classList.toggle('thoth-field-warning', !isError);
  }

  /**
   * Clear validation message
   */
  clearValidation(): void {
    if (this.validationEl) {
      this.validationEl.style.display = 'none';
    }
    this.container.classList.remove('thoth-field-error', 'thoth-field-warning');
  }

  /**
   * Create base field container with setting
   */
  protected createBaseContainer(): HTMLElement {
    this.container = document.createElement('div');
    this.container.className = 'thoth-field-container';
    this.container.dataset.fieldName = this.fieldName;
    this.container.dataset.fieldType = this.fieldSchema.type;

    this.setting = new Setting(this.container);
    this.setting.setName(this.fieldSchema.title);
    this.setting.setDesc(this.fieldSchema.description);

    // Add required indicator
    if (this.fieldSchema.required) {
      const nameEl = this.setting.nameEl;
      nameEl.appendChild(nameEl.createSpan({ text: ' *', cls: 'thoth-required-indicator' }));
    }

    return this.container;
  }
}

/**
 * Text field component
 */
export class TextFieldComponent extends BaseFieldComponent {
  private inputEl?: HTMLInputElement;

  render(): HTMLElement {
    const container = this.createBaseContainer();

    this.setting.addText(text => {
      this.inputEl = text.inputEl;
      text.setPlaceholder(this.fieldSchema.description);
      text.setValue(this.currentValue || this.fieldSchema.default || '');

      // Apply validation pattern if specified
      if (this.fieldSchema.validation?.pattern) {
        text.inputEl.pattern = this.fieldSchema.validation.pattern;
      }

      text.onChange((value) => {
        this.triggerChange(value);
      });
    });

    return container;
  }

  getValue(): any {
    return this.inputEl?.value || '';
  }

  setValue(value: any): void {
    if (this.inputEl) {
      this.inputEl.value = value?.toString() || '';
      this.currentValue = value;
    }
  }

  validate(): boolean {
    const baseValid = super.validate();
    if (!baseValid) return false;

    const value = this.getValue();

    // Pattern validation
    if (this.fieldSchema.validation?.pattern && value) {
      const regex = new RegExp(this.fieldSchema.validation.pattern);
      if (!regex.test(value)) {
        this.setValidationMessage(
          this.fieldSchema.validation.message || 'Invalid format',
          true
        );
        return false;
      }
    }

    return true;
  }
}

/**
 * Password field component with visibility toggle
 */
export class PasswordFieldComponent extends BaseFieldComponent {
  private inputEl?: HTMLInputElement;
  private toggleBtn?: HTMLButtonElement;

  render(): HTMLElement {
    const container = this.createBaseContainer();

    this.setting.addText(text => {
      this.inputEl = text.inputEl;
      text.inputEl.type = 'password';
      text.setPlaceholder(this.fieldSchema.description);
      text.setValue(this.currentValue || this.fieldSchema.default || '');

      text.onChange((value) => {
        this.triggerChange(value);
      });
    });

    // Add visibility toggle button
    this.setting.addButton(button => {
      this.toggleBtn = button.buttonEl;
      button.setButtonText('👁');
      button.setTooltip('Toggle password visibility');
      button.onClick(() => {
        if (this.inputEl) {
          const isPassword = this.inputEl.type === 'password';
          this.inputEl.type = isPassword ? 'text' : 'password';
          if (this.toggleBtn) {
            this.toggleBtn.textContent = isPassword ? '🙈' : '👁';
          }
        }
      });
    });

    return container;
  }

  getValue(): any {
    return this.inputEl?.value || '';
  }

  setValue(value: any): void {
    if (this.inputEl) {
      this.inputEl.value = value?.toString() || '';
      this.currentValue = value;
    }
  }
}

/**
 * Number field component with range validation
 */
export class NumberFieldComponent extends BaseFieldComponent {
  private inputEl?: HTMLInputElement;

  render(): HTMLElement {
    const container = this.createBaseContainer();

    this.setting.addText(text => {
      this.inputEl = text.inputEl;
      text.inputEl.type = 'number';
      text.setPlaceholder(this.fieldSchema.description);
      text.setValue((this.currentValue || this.fieldSchema.default || '').toString());

      // Set min/max if specified
      if (this.fieldSchema.validation?.min !== undefined) {
        text.inputEl.min = this.fieldSchema.validation.min.toString();
      }
      if (this.fieldSchema.validation?.max !== undefined) {
        text.inputEl.max = this.fieldSchema.validation.max.toString();
      }

      text.onChange((value) => {
        const numValue = value === '' ? undefined : Number(value);
        this.triggerChange(numValue);
      });
    });

    return container;
  }

  getValue(): any {
    const value = this.inputEl?.value;
    return value === '' ? undefined : Number(value);
  }

  setValue(value: any): void {
    if (this.inputEl) {
      this.inputEl.value = value?.toString() || '';
      this.currentValue = value;
    }
  }

  validate(): boolean {
    const baseValid = super.validate();
    if (!baseValid) return false;

    const value = this.getValue();

    if (value !== undefined && value !== null) {
      if (isNaN(value)) {
        this.setValidationMessage('Must be a valid number', true);
        return false;
      }

      if (this.fieldSchema.validation?.min !== undefined && value < this.fieldSchema.validation.min) {
        this.setValidationMessage(`Must be at least ${this.fieldSchema.validation.min}`, true);
        return false;
      }

      if (this.fieldSchema.validation?.max !== undefined && value > this.fieldSchema.validation.max) {
        this.setValidationMessage(`Must be at most ${this.fieldSchema.validation.max}`, true);
        return false;
      }
    }

    return true;
  }
}

/**
 * Boolean toggle field component
 */
export class BooleanFieldComponent extends BaseFieldComponent {
  private toggleEl?: HTMLElement;

  render(): HTMLElement {
    const container = this.createBaseContainer();

    this.setting.addToggle(toggle => {
      this.toggleEl = toggle.toggleEl;
      toggle.setValue(this.currentValue !== undefined ? this.currentValue : this.fieldSchema.default || false);

      toggle.onChange((value) => {
        this.triggerChange(value);
      });
    });

    return container;
  }

  getValue(): any {
    const inputEl = this.toggleEl?.querySelector('input[type="checkbox"]') as HTMLInputElement;
    return inputEl?.checked || false;
  }

  setValue(value: any): void {
    const inputEl = this.toggleEl?.querySelector('input[type="checkbox"]') as HTMLInputElement;
    if (inputEl) {
      inputEl.checked = Boolean(value);
      this.currentValue = value;
    }
  }
}

/**
 * Select dropdown field component
 */
export class SelectFieldComponent extends BaseFieldComponent {
  private selectEl?: HTMLSelectElement;

  render(): HTMLElement {
    const container = this.createBaseContainer();

    this.setting.addDropdown(dropdown => {
      this.selectEl = dropdown.selectEl;

      // Add options
      if (this.fieldSchema.options) {
        for (const option of this.fieldSchema.options) {
          dropdown.addOption(option, option);
        }
      }

      dropdown.setValue(this.currentValue || this.fieldSchema.default || '');

      dropdown.onChange((value) => {
        this.triggerChange(value);
      });
    });

    return container;
  }

  getValue(): any {
    return this.selectEl?.value || '';
  }

  setValue(value: any): void {
    if (this.selectEl) {
      this.selectEl.value = value?.toString() || '';
      this.currentValue = value;
    }
  }
}

/**
 * Multi-select field component with checkboxes
 */
export class MultiSelectFieldComponent extends BaseFieldComponent {
  private checkboxContainer?: HTMLElement;

  render(): HTMLElement {
    const container = this.createBaseContainer();
    const currentValues = Array.isArray(this.currentValue) ? this.currentValue : (this.fieldSchema.default || []);

    if (this.fieldSchema.options) {
      this.checkboxContainer = this.setting.controlEl.createEl('div', { cls: 'thoth-multiselect-container' });

      for (const option of this.fieldSchema.options) {
        const optionEl = this.checkboxContainer.createEl('label', { cls: 'thoth-multiselect-option' });

        const checkbox = optionEl.createEl('input', { type: 'checkbox' }) as HTMLInputElement;
        checkbox.checked = currentValues.includes(option);
        checkbox.value = option;

        optionEl.createEl('span', { text: option });

        checkbox.addEventListener('change', () => {
          const selectedValues = this.getSelectedValues();
          this.triggerChange(selectedValues);
        });
      }
    }

    return container;
  }

  getValue(): any {
    return this.getSelectedValues();
  }

  setValue(value: any): void {
    const values = Array.isArray(value) ? value : [];
    this.currentValue = values;

    if (this.checkboxContainer) {
      const checkboxes = this.checkboxContainer.querySelectorAll('input[type="checkbox"]') as NodeListOf<HTMLInputElement>;
      checkboxes.forEach(checkbox => {
        checkbox.checked = values.includes(checkbox.value);
      });
    }
  }

  private getSelectedValues(): string[] {
    if (!this.checkboxContainer) return [];

    const checkboxes = this.checkboxContainer.querySelectorAll('input[type="checkbox"]:checked') as NodeListOf<HTMLInputElement>;
    return Array.from(checkboxes).map(cb => cb.value);
  }
}

/**
 * File picker field component
 */
export class FileFieldComponent extends BaseFieldComponent {
  private inputEl?: HTMLInputElement;
  private browseBtn?: HTMLButtonElement;

  render(): HTMLElement {
    const container = this.createBaseContainer();

    this.setting.addText(text => {
      this.inputEl = text.inputEl;
      text.setPlaceholder('Click "Browse" to select file');
      text.setValue(this.currentValue || this.fieldSchema.default || '');
      text.inputEl.disabled = true;

      // Allow manual input as fallback
      text.onChange((value) => {
        this.triggerChange(value);
      });
    });

    this.setting.addButton(button => {
      this.browseBtn = button.buttonEl;
      button.setButtonText('Browse');
      button.setTooltip('Select file');
      button.onClick(async () => {
        await this.openFilePicker();
      });
    });

    // Add enable manual input button
    this.setting.addButton(button => {
      button.setButtonText('✏️');
      button.setTooltip('Enable manual input');
      button.onClick(() => {
        if (this.inputEl) {
          this.inputEl.disabled = !this.inputEl.disabled;
          this.inputEl.placeholder = this.inputEl.disabled ?
            'Click "Browse" to select file' :
            'Enter file path manually';
        }
      });
    });

    return container;
  }

  getValue(): any {
    return this.inputEl?.value || '';
  }

  setValue(value: any): void {
    if (this.inputEl) {
      this.inputEl.value = value?.toString() || '';
      this.currentValue = value;
    }
  }

  private async openFilePicker(): Promise<void> {
    // Mobile: skip Electron, enable manual input
    if (Platform.isMobile) {
      if (this.inputEl) {
        this.inputEl.disabled = false;
        this.inputEl.placeholder = 'Enter file path (file picker not available on mobile)';
        this.inputEl.focus();
      }
      return;
    }

    // Desktop: try Electron file picker
    try {
      // Try to use Electron's file dialog
      if (typeof require !== 'undefined') {
        const { remote } = require('electron');
        if (remote && remote.dialog) {
          const { dialog } = remote;

          const result = await dialog.showOpenDialog({
            properties: ['openFile'],
            filters: [
              { name: 'All Files', extensions: ['*'] }
            ]
          });

          if (!result.canceled && result.filePaths.length > 0) {
            const filePath = result.filePaths[0];
            this.setValue(filePath);
            this.triggerChange(filePath);
            return;
          }
        }
      }

      // Fallback: enable manual input
      if (this.inputEl) {
        this.inputEl.disabled = false;
        this.inputEl.placeholder = 'Enter file path manually';
        this.inputEl.focus();
      }
    } catch (error) {
      console.warn('File picker error:', error);
      // Enable manual input as fallback
      if (this.inputEl) {
        this.inputEl.disabled = false;
        this.inputEl.placeholder = 'Enter file path manually (file picker unavailable)';
      }
    }
  }
}

/**
 * Directory picker field component
 */
export class DirectoryFieldComponent extends BaseFieldComponent {
  private inputEl?: HTMLInputElement;
  private browseBtn?: HTMLButtonElement;

  render(): HTMLElement {
    const container = this.createBaseContainer();

    this.setting.addText(text => {
      this.inputEl = text.inputEl;
      text.setPlaceholder('Click "Browse" to select directory');
      text.setValue(this.currentValue || this.fieldSchema.default || '');
      text.inputEl.disabled = true;

      // Allow manual input as fallback
      text.onChange((value) => {
        this.triggerChange(value);
      });
    });

    this.setting.addButton(button => {
      this.browseBtn = button.buttonEl;
      button.setButtonText('Browse');
      button.setTooltip('Select directory');
      button.onClick(async () => {
        await this.openDirectoryPicker();
      });
    });

    // Add enable manual input button
    this.setting.addButton(button => {
      button.setButtonText('✏️');
      button.setTooltip('Enable manual input');
      button.onClick(() => {
        if (this.inputEl) {
          this.inputEl.disabled = !this.inputEl.disabled;
          this.inputEl.placeholder = this.inputEl.disabled ?
            'Click "Browse" to select directory' :
            'Enter directory path manually';
        }
      });
    });

    return container;
  }

  getValue(): any {
    return this.inputEl?.value || '';
  }

  setValue(value: any): void {
    if (this.inputEl) {
      this.inputEl.value = value?.toString() || '';
      this.currentValue = value;
    }
  }

  private async openDirectoryPicker(): Promise<void> {
    // Mobile: skip Electron, enable manual input
    if (Platform.isMobile) {
      if (this.inputEl) {
        this.inputEl.disabled = false;
        this.inputEl.placeholder = 'Enter directory path (directory picker not available on mobile)';
        this.inputEl.focus();
      }
      return;
    }

    // Desktop: try Electron directory picker
    try {
      // Try to use Electron's directory dialog
      if (typeof require !== 'undefined') {
        const { remote } = require('electron');
        if (remote && remote.dialog) {
          const { dialog } = remote;

          const result = await dialog.showOpenDialog({
            properties: ['openDirectory']
          });

          if (!result.canceled && result.filePaths.length > 0) {
            const dirPath = result.filePaths[0];
            this.setValue(dirPath);
            this.triggerChange(dirPath);
            return;
          }
        }
      }

      // Fallback: enable manual input
      if (this.inputEl) {
        this.inputEl.disabled = false;
        this.inputEl.placeholder = 'Enter directory path manually';
        this.inputEl.focus();
      }
    } catch (error) {
      console.warn('Directory picker error:', error);
      // Enable manual input as fallback
      if (this.inputEl) {
        this.inputEl.disabled = false;
        this.inputEl.placeholder = 'Enter directory path manually (directory picker unavailable)';
      }
    }
  }
}

/**
 * Field component factory
 */
export class FieldComponentFactory {
  /**
   * Create field component based on field type
   */
  static createComponent(fieldName: string, fieldSchema: FieldSchema, currentValue: any): IFieldComponent {
    switch (fieldSchema.type) {
      case 'text':
        return new TextFieldComponent(fieldName, fieldSchema, currentValue);
      case 'password':
        return new PasswordFieldComponent(fieldName, fieldSchema, currentValue);
      case 'number':
        return new NumberFieldComponent(fieldName, fieldSchema, currentValue);
      case 'boolean':
        return new BooleanFieldComponent(fieldName, fieldSchema, currentValue);
      case 'select':
        return new SelectFieldComponent(fieldName, fieldSchema, currentValue);
      case 'multiselect':
        return new MultiSelectFieldComponent(fieldName, fieldSchema, currentValue);
      case 'file':
        return new FileFieldComponent(fieldName, fieldSchema, currentValue);
      case 'directory':
        return new DirectoryFieldComponent(fieldName, fieldSchema, currentValue);
      default:
        console.warn(`Unknown field type: ${fieldSchema.type}, using text field`);
        return new TextFieldComponent(fieldName, fieldSchema, currentValue);
    }
  }

  /**
   * Get supported field types
   */
  static getSupportedTypes(): string[] {
    return ['text', 'password', 'number', 'boolean', 'select', 'multiselect', 'file', 'directory'];
  }

  /**
   * Check if field type is supported
   */
  static isTypeSupported(type: string): boolean {
    return this.getSupportedTypes().includes(type);
  }
}

/**
 * Field validation utilities
 */
export class FieldValidationUtils {
  /**
   * Validate field value against schema
   */
  static validateFieldValue(fieldSchema: FieldSchema, value: any): { isValid: boolean; error?: string } {
    // Required field validation
    if (fieldSchema.required && (value === undefined || value === null || value === '')) {
      return { isValid: false, error: 'This field is required' };
    }

    // Type-specific validation
    switch (fieldSchema.type) {
      case 'text':
      case 'password':
        return this.validateTextValue(fieldSchema, value);
      case 'number':
        return this.validateNumberValue(fieldSchema, value);
      case 'boolean':
        return this.validateBooleanValue(fieldSchema, value);
      case 'select':
        return this.validateSelectValue(fieldSchema, value);
      case 'multiselect':
        return this.validateMultiSelectValue(fieldSchema, value);
      case 'file':
      case 'directory':
        return this.validatePathValue(fieldSchema, value);
      default:
        return { isValid: true };
    }
  }

  private static validateTextValue(fieldSchema: FieldSchema, value: any): { isValid: boolean; error?: string } {
    if (value && fieldSchema.validation?.pattern) {
      const regex = new RegExp(fieldSchema.validation.pattern);
      if (!regex.test(value)) {
        return {
          isValid: false,
          error: fieldSchema.validation.message || 'Invalid format'
        };
      }
    }
    return { isValid: true };
  }

  private static validateNumberValue(fieldSchema: FieldSchema, value: any): { isValid: boolean; error?: string } {
    if (value !== undefined && value !== null && value !== '') {
      const numValue = Number(value);
      if (isNaN(numValue)) {
        return { isValid: false, error: 'Must be a valid number' };
      }

      if (fieldSchema.validation?.min !== undefined && numValue < fieldSchema.validation.min) {
        return { isValid: false, error: `Must be at least ${fieldSchema.validation.min}` };
      }

      if (fieldSchema.validation?.max !== undefined && numValue > fieldSchema.validation.max) {
        return { isValid: false, error: `Must be at most ${fieldSchema.validation.max}` };
      }
    }
    return { isValid: true };
  }

  private static validateBooleanValue(fieldSchema: FieldSchema, value: any): { isValid: boolean; error?: string } {
    // Boolean values are always valid
    return { isValid: true };
  }

  private static validateSelectValue(fieldSchema: FieldSchema, value: any): { isValid: boolean; error?: string } {
    if (value && fieldSchema.options && !fieldSchema.options.includes(value)) {
      return { isValid: false, error: 'Invalid option selected' };
    }
    return { isValid: true };
  }

  private static validateMultiSelectValue(fieldSchema: FieldSchema, value: any): { isValid: boolean; error?: string } {
    if (Array.isArray(value) && fieldSchema.options) {
      for (const item of value) {
        if (!fieldSchema.options.includes(item)) {
          return { isValid: false, error: `Invalid option: ${item}` };
        }
      }
    }
    return { isValid: true };
  }

  private static validatePathValue(fieldSchema: FieldSchema, value: any): { isValid: boolean; error?: string } {
    if (value && typeof value === 'string') {
      // Basic path validation - check for invalid characters
      const invalidChars = /[<>:"|?*]/;
      if (invalidChars.test(value)) {
        return { isValid: false, error: 'Path contains invalid characters' };
      }
    }
    return { isValid: true };
  }
}

/**
 * Field styling utilities
 */
export class FieldStylingUtils {
  /**
   * Apply field styling based on state
   */
  static applyFieldState(container: HTMLElement, state: 'normal' | 'error' | 'warning' | 'success'): void {
    // Remove all state classes
    container.classList.remove('thoth-field-error', 'thoth-field-warning', 'thoth-field-success');

    // Apply new state class
    if (state !== 'normal') {
      container.classList.add(`thoth-field-${state}`);
    }
  }

  /**
   * Create field help text element
   */
  static createHelpText(container: HTMLElement, text: string): HTMLElement {
    const helpEl = container.createEl('div', { cls: 'thoth-field-help' });
    helpEl.textContent = text;
    return helpEl;
  }

  /**
   * Create field status indicator
   */
  static createStatusIndicator(container: HTMLElement): HTMLElement {
    const statusEl = container.createEl('div', { cls: 'thoth-field-status' });
    statusEl.style.display = 'none';
    return statusEl;
  }

  /**
   * Update status indicator
   */
  static updateStatusIndicator(statusEl: HTMLElement, type: 'loading' | 'success' | 'error' | 'warning'): void {
    const iconMap = {
      loading: '⏳',
      success: '✅',
      error: '❌',
      warning: '⚠️'
    };

    statusEl.textContent = iconMap[type];
    statusEl.className = `thoth-field-status thoth-status-${type}`;
    statusEl.style.display = 'inline-block';
  }

  /**
   * Hide status indicator
   */
  static hideStatusIndicator(statusEl: HTMLElement): void {
    statusEl.style.display = 'none';
  }
}
