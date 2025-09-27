import { Setting } from 'obsidian';
import type { UISchema, FieldSchema, GroupSchema, FieldValidationResult } from '../services/schema-service';
import type { ThothSettings } from '../types';
import { getGlobalCacheManager, trackPerformance } from '../services/performance-cache';

/**
 * Field dependency interface
 */
interface FieldDependency {
  field_path: string;
  depends_on: string;
  condition: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains' | 'not_empty';
  value: any;
  action: 'show' | 'hide' | 'enable' | 'disable' | 'require' | 'optional';
}

/**
 * Conditional rule interface
 */
interface ConditionalRule {
  rule_id: string;
  description: string;
  condition_expression: string;
  affected_fields: string[];
  action: 'show' | 'hide' | 'enable' | 'disable' | 'require' | 'optional';
  priority: number;
}

/**
 * Advanced organization interface
 */
export interface AdvancedOrganization {
  evaluateFieldVisibility(fieldName: string, currentConfig: ThothSettings): boolean;
  updateDependentFields(changedField: string, newValue: any): void;
  showConfigurationWizard(category: string): void;
  suggestOptimalConfiguration(useCase: string): ThothSettings;
}

/**
 * Enhanced UI Generator interface with conditional visibility
 */
export interface IUIGenerator extends AdvancedOrganization {
  generateSettingsForm(schema: UISchema, currentConfig: ThothSettings): HTMLElement;
  generateFieldComponent(fieldName: string, fieldSchema: FieldSchema, currentValue: any): HTMLElement;
  generateGroupSection(groupName: string, groupSchema: GroupSchema, fields: FieldSchema[]): HTMLElement;
  updateFieldValue(fieldName: string, value: any): void;
  validateField(fieldName: string): Promise<FieldValidationResult>;
  getFormData(): Partial<ThothSettings>;
  setValidationCallback(callback: (fieldName: string, value: any) => Promise<FieldValidationResult>): void;
  setSaveCallback(callback: (config: Partial<ThothSettings>) => Promise<void>): void;
  cleanup(): void;
}

/**
 * Field component configuration
 */
interface FieldComponentConfig {
  fieldName: string;
  fieldSchema: FieldSchema;
  currentValue: any;
  container: HTMLElement;
  setting: Setting;
  validationEl?: HTMLElement;
}

/**
 * Form state management
 */
interface FormState {
  values: Record<string, any>;
  validationResults: Record<string, FieldValidationResult>;
  isDirty: boolean;
  isValid: boolean;
}

/**
 * UIGenerator implementation for dynamic settings form generation
 */
export class UIGenerator implements IUIGenerator {
  private formState: FormState;
  private fieldComponents: Map<string, FieldComponentConfig> = new Map();
  private validationCallback?: (fieldName: string, value: any) => Promise<FieldValidationResult>;
  private saveCallback?: (config: Partial<ThothSettings>) => Promise<void>;
  private debounceTimers: Map<string, NodeJS.Timeout> = new Map();
  private readonly VALIDATION_DEBOUNCE_MS = 500;

  // Advanced organization features
  private schema?: UISchema;
  private fieldDependencies: FieldDependency[] = [];
  private conditionalRules: ConditionalRule[] = [];
  private visibilityState: Map<string, boolean> = new Map();
  private dependencyGraph: Map<string, string[]> = new Map();
  private cacheManager = getGlobalCacheManager();

  constructor() {
    this.formState = {
      values: {},
      validationResults: {},
      isDirty: false,
      isValid: true
    };
  }

  /**
   * Set validation callback for real-time validation
   */
  setValidationCallback(callback: (fieldName: string, value: any) => Promise<FieldValidationResult>): void {
    this.validationCallback = callback;
  }

  /**
   * Set save callback for form submission
   */
  setSaveCallback(callback: (config: Partial<ThothSettings>) => Promise<void>): void {
    this.saveCallback = callback;
  }

  /**
   * Generate complete settings form based on schema with conditional visibility
   */
  @trackPerformance('generate_settings_form')
  generateSettingsForm(schema: UISchema, currentConfig: ThothSettings): HTMLElement {
    const formContainer = document.createElement('div');
    formContainer.className = 'thoth-settings-form';

    // Store schema and initialize advanced features
    this.schema = schema;
    this.initializeAdvancedFeatures(schema);

    // Initialize form state with current config
    this.formState.values = { ...currentConfig };

    // Header section
    const headerEl = formContainer.createEl('div', { cls: 'thoth-settings-header' });
    headerEl.createEl('h1', { text: '🧠 Thoth Research Assistant' });
    headerEl.createEl('p', {
      text: `Configuration v${schema.version}`,
      cls: 'thoth-settings-version'
    });

    // Advanced features toggle
    if (this.hasAdvancedFeatures(schema)) {
      this.createAdvancedFeaturesToggle(headerEl);
    }

    // Form actions bar
    const actionsEl = formContainer.createEl('div', { cls: 'thoth-form-actions' });
    this.createFormActions(actionsEl);

    // Form content container
    const contentEl = formContainer.createEl('div', { cls: 'thoth-form-content' });

    // Sort groups by order with visibility evaluation
    const sortedGroups = Object.entries(schema.groups)
      .sort(([, a], [, b]) => (a.order || 0) - (b.order || 0))
      .filter(([groupName]) => this.evaluateGroupVisibility(groupName, currentConfig));

    // Generate group sections with conditional visibility
    for (const [groupName, groupSchema] of sortedGroups) {
      const groupFields = Object.entries(schema.fields)
        .filter(([, fieldSchema]) => fieldSchema.group === groupName)
        .filter(([fieldName]) => this.evaluateFieldVisibility(fieldName, currentConfig))
        .map(([fieldName, fieldSchema]) => ({ fieldName, fieldSchema }));

      if (groupFields.length > 0) {
        const groupEl = this.generateGroupSection(
          groupName,
          groupSchema,
          groupFields.map(({ fieldSchema }) => fieldSchema)
        );

        // Add fields to the group with conditional visibility
        for (const { fieldName, fieldSchema } of groupFields) {
          const fieldEl = this.generateFieldComponent(fieldName, fieldSchema, currentConfig[fieldName as keyof ThothSettings]);
          groupEl.appendChild(fieldEl);
        }

        contentEl.appendChild(groupEl);
      }
    }

    // Status bar for form state
    const statusEl = formContainer.createEl('div', { cls: 'thoth-form-status' });
    this.createFormStatus(statusEl);

    return formContainer;
  }

  /**
   * Initialize advanced organization features
   */
  private initializeAdvancedFeatures(schema: UISchema): void {
    // Load field dependencies from schema
    if (schema.field_dependencies) {
      this.fieldDependencies = schema.field_dependencies;
    }

    // Load conditional rules from schema
    if (schema.conditional_rules) {
      this.conditionalRules = schema.conditional_rules;
    }

    // Build dependency graph for efficient updates
    this.buildDependencyGraph();

    // Initialize visibility state
    this.initializeVisibilityState();
  }

  /**
   * Build dependency graph for efficient field updates
   */
  private buildDependencyGraph(): void {
    this.dependencyGraph.clear();

    for (const dependency of this.fieldDependencies) {
      if (!this.dependencyGraph.has(dependency.depends_on)) {
        this.dependencyGraph.set(dependency.depends_on, []);
      }
      this.dependencyGraph.get(dependency.depends_on)!.push(dependency.field_path);
    }

    for (const rule of this.conditionalRules) {
      // Parse condition expression to find dependencies
      const dependencies = this.extractDependenciesFromExpression(rule.condition_expression);
      for (const dep of dependencies) {
        if (!this.dependencyGraph.has(dep)) {
          this.dependencyGraph.set(dep, []);
        }
        for (const affectedField of rule.affected_fields) {
          if (!this.dependencyGraph.get(dep)!.includes(affectedField)) {
            this.dependencyGraph.get(dep)!.push(affectedField);
          }
        }
      }
    }
  }

  /**
   * Initialize visibility state for all fields
   */
  private initializeVisibilityState(): void {
    this.visibilityState.clear();

    if (this.schema) {
      for (const fieldName of Object.keys(this.schema.fields)) {
        this.visibilityState.set(fieldName, true); // Default to visible
      }
    }
  }

  /**
   * Evaluate field visibility based on dependencies and conditions
   */
  evaluateFieldVisibility(fieldName: string, currentConfig: ThothSettings): boolean {
    // Check field dependencies
    for (const dependency of this.fieldDependencies) {
      if (dependency.field_path === fieldName) {
        const dependsValue = this.getConfigValue(currentConfig, dependency.depends_on);
        const conditionMet = this.evaluateCondition(dependency.condition, dependsValue, dependency.value);

        if (dependency.action === 'show') {
          return conditionMet;
        } else if (dependency.action === 'hide') {
          return !conditionMet;
        }
      }
    }

    // Check conditional rules
    for (const rule of this.conditionalRules) {
      if (rule.affected_fields.includes(fieldName)) {
        const conditionMet = this.evaluateConditionExpression(rule.condition_expression, currentConfig);

        if (rule.action === 'show') {
          return conditionMet;
        } else if (rule.action === 'hide') {
          return !conditionMet;
        }
      }
    }

    // Default to visible
    return true;
  }

  /**
   * Update dependent fields when a field value changes
   */
  updateDependentFields(changedField: string, newValue: any): void {
    const dependentFields = this.dependencyGraph.get(changedField);
    if (!dependentFields) return;

    // Update form state
    this.formState.values[changedField] = newValue;

    // Evaluate visibility for all dependent fields
    for (const dependentField of dependentFields) {
      const wasVisible = this.visibilityState.get(dependentField);
      const isVisible = this.evaluateFieldVisibility(dependentField, this.formState.values as ThothSettings);

      if (wasVisible !== isVisible) {
        this.visibilityState.set(dependentField, isVisible);
        this.updateFieldVisibility(dependentField, isVisible);
      }

      // Update field requirements
      this.updateFieldRequirements(dependentField, this.formState.values as ThothSettings);
    }

    // Cache the visibility state
    this.cacheManager.cacheUIState(`visibility_${changedField}`, {
      field: changedField,
      value: newValue,
      visibilityState: Object.fromEntries(this.visibilityState)
    });
  }

  /**
   * Show configuration wizard for a category
   */
  showConfigurationWizard(category: string): void {
    const wizardContainer = document.createElement('div');
    wizardContainer.className = 'thoth-configuration-wizard';

    // This would typically open a modal or dedicated wizard interface
    // For now, we'll create a simple inline wizard
    const wizardHeader = wizardContainer.createEl('div', { cls: 'thoth-wizard-header' });
    wizardHeader.createEl('h3', { text: `Configuration Wizard: ${category}` });
    wizardHeader.createEl('p', { text: 'Follow the steps below to configure this category' });

    // Add wizard content based on category
    const wizardContent = wizardContainer.createEl('div', { cls: 'thoth-wizard-content' });
    this.generateWizardSteps(category, wizardContent);

    // Show wizard (this would typically be in a modal)
    const formContainer = document.querySelector('.thoth-settings-form');
    if (formContainer) {
      formContainer.appendChild(wizardContainer);
    }
  }

  /**
   * Suggest optimal configuration for a use case
   */
  suggestOptimalConfiguration(useCase: string): ThothSettings {
    // This would integrate with the backend schema generator
    // For now, return basic configurations based on common use cases
    const baseConfig = this.formState.values as ThothSettings;

    switch (useCase) {
      case 'researcher_basic':
        return {
          ...baseConfig,
          // Basic research configuration
        };
      case 'power_user':
        return {
          ...baseConfig,
          // Power user configuration
        };
      case 'team_server':
        return {
          ...baseConfig,
          // Team server configuration
        };
      default:
        return baseConfig;
    }
  }

  /**
   * Generate group section with collapsible functionality
   */
  generateGroupSection(groupName: string, groupSchema: GroupSchema, fields: FieldSchema[]): HTMLElement {
    const groupEl = document.createElement('div');
    groupEl.className = 'thoth-settings-group';
    groupEl.dataset.groupName = groupName;

    // Group header
    const headerEl = groupEl.createEl('div', { cls: 'thoth-group-header' });
    headerEl.addEventListener('click', () => this.toggleGroup(groupName));

    const titleEl = headerEl.createEl('h2', { text: groupSchema.title });
    const toggleEl = headerEl.createEl('span', { cls: 'thoth-group-toggle' });
    toggleEl.textContent = groupSchema.collapsed ? '▶' : '▼';

    const descEl = groupEl.createEl('p', {
      text: groupSchema.description,
      cls: 'thoth-group-description'
    });

    // Group content
    const contentEl = groupEl.createEl('div', { cls: 'thoth-group-content' });
    contentEl.style.display = groupSchema.collapsed ? 'none' : 'block';

    return groupEl;
  }

  /**
   * Generate field component based on field type
   */
  generateFieldComponent(fieldName: string, fieldSchema: FieldSchema, currentValue: any): HTMLElement {
    const fieldContainer = document.createElement('div');
    fieldContainer.className = 'thoth-field-container';
    fieldContainer.dataset.fieldName = fieldName;
    fieldContainer.dataset.fieldType = fieldSchema.type;

    // Create Obsidian Setting component
    const setting = new Setting(fieldContainer);
    setting.setName(fieldSchema.title);
    setting.setDesc(fieldSchema.description);

    // Add required indicator
    if (fieldSchema.required) {
      const nameEl = setting.nameEl;
      nameEl.appendChild(nameEl.createSpan({ text: ' *', cls: 'thoth-required-indicator' }));
    }

    // Create validation display element
    const validationEl = fieldContainer.createEl('div', { cls: 'thoth-validation-message' });
    validationEl.style.display = 'none';

    // Configure field component based on type
    this.configureFieldByType(setting, fieldName, fieldSchema, currentValue);

    // Store component configuration
    const componentConfig: FieldComponentConfig = {
      fieldName,
      fieldSchema,
      currentValue,
      container: fieldContainer,
      setting,
      validationEl
    };

    this.fieldComponents.set(fieldName, componentConfig);

    return fieldContainer;
  }

  /**
   * Configure field component based on field type
   */
  private configureFieldByType(setting: Setting, fieldName: string, fieldSchema: FieldSchema, currentValue: any): void {
    switch (fieldSchema.type) {
      case 'text':
        this.createTextField(setting, fieldName, fieldSchema, currentValue);
        break;
      case 'password':
        this.createPasswordField(setting, fieldName, fieldSchema, currentValue);
        break;
      case 'number':
        this.createNumberField(setting, fieldName, fieldSchema, currentValue);
        break;
      case 'boolean':
        this.createBooleanField(setting, fieldName, fieldSchema, currentValue);
        break;
      case 'select':
        this.createSelectField(setting, fieldName, fieldSchema, currentValue);
        break;
      case 'multiselect':
        this.createMultiSelectField(setting, fieldName, fieldSchema, currentValue);
        break;
      case 'file':
        this.createFileField(setting, fieldName, fieldSchema, currentValue);
        break;
      case 'directory':
        this.createDirectoryField(setting, fieldName, fieldSchema, currentValue);
        break;
      default:
        console.warn(`Unknown field type: ${fieldSchema.type}`);
        this.createTextField(setting, fieldName, fieldSchema, currentValue);
    }
  }

  /**
   * Create text input field
   */
  private createTextField(setting: Setting, fieldName: string, fieldSchema: FieldSchema, currentValue: any): void {
    setting.addText(text => {
      text.setPlaceholder(fieldSchema.description);
      text.setValue(currentValue || fieldSchema.default || '');

      text.onChange(async (value) => {
        this.updateFieldValue(fieldName, value);
        await this.debouncedValidateField(fieldName, value);
      });

      // Apply validation pattern if specified
      if (fieldSchema.validation?.pattern) {
        text.inputEl.pattern = fieldSchema.validation.pattern;
      }
    });
  }

  /**
   * Create password input field with visibility toggle
   */
  private createPasswordField(setting: Setting, fieldName: string, fieldSchema: FieldSchema, currentValue: any): void {
    setting.addText(text => {
      text.inputEl.type = 'password';
      text.setPlaceholder(fieldSchema.description);
      text.setValue(currentValue || fieldSchema.default || '');

      text.onChange(async (value) => {
        this.updateFieldValue(fieldName, value);
        await this.debouncedValidateField(fieldName, value);
      });
    });

    // Add toggle visibility button
    setting.addButton(button => {
      button.setButtonText('👁');
      button.setTooltip('Toggle password visibility');
      button.onClick(() => {
        const input = setting.controlEl.querySelector('input[type="password"], input[type="text"]') as HTMLInputElement;
        if (input) {
          input.type = input.type === 'password' ? 'text' : 'password';
          button.setButtonText(input.type === 'password' ? '👁' : '🙈');
        }
      });
    });
  }

  /**
   * Create number input field
   */
  private createNumberField(setting: Setting, fieldName: string, fieldSchema: FieldSchema, currentValue: any): void {
    setting.addText(text => {
      text.inputEl.type = 'number';
      text.setPlaceholder(fieldSchema.description);
      text.setValue((currentValue || fieldSchema.default || '').toString());

      // Set min/max if specified
      if (fieldSchema.validation?.min !== undefined) {
        text.inputEl.min = fieldSchema.validation.min.toString();
      }
      if (fieldSchema.validation?.max !== undefined) {
        text.inputEl.max = fieldSchema.validation.max.toString();
      }

      text.onChange(async (value) => {
        const numValue = value === '' ? undefined : Number(value);
        this.updateFieldValue(fieldName, numValue);
        await this.debouncedValidateField(fieldName, numValue);
      });
    });
  }

  /**
   * Create boolean toggle field
   */
  private createBooleanField(setting: Setting, fieldName: string, fieldSchema: FieldSchema, currentValue: any): void {
    setting.addToggle(toggle => {
      toggle.setValue(currentValue !== undefined ? currentValue : fieldSchema.default || false);

      toggle.onChange(async (value) => {
        this.updateFieldValue(fieldName, value);
        await this.debouncedValidateField(fieldName, value);
      });
    });
  }

  /**
   * Create select dropdown field
   */
  private createSelectField(setting: Setting, fieldName: string, fieldSchema: FieldSchema, currentValue: any): void {
    setting.addDropdown(dropdown => {
      // Add options
      if (fieldSchema.options) {
        for (const option of fieldSchema.options) {
          dropdown.addOption(option, option);
        }
      }

      dropdown.setValue(currentValue || fieldSchema.default || '');

      dropdown.onChange(async (value) => {
        this.updateFieldValue(fieldName, value);
        await this.debouncedValidateField(fieldName, value);
      });
    });
  }

  /**
   * Create multi-select field with checkboxes
   */
  private createMultiSelectField(setting: Setting, fieldName: string, fieldSchema: FieldSchema, currentValue: any): void {
    const currentValues = Array.isArray(currentValue) ? currentValue : (fieldSchema.default || []);

    if (fieldSchema.options) {
      const optionsContainer = setting.controlEl.createEl('div', { cls: 'thoth-multiselect-container' });

      for (const option of fieldSchema.options) {
        const optionEl = optionsContainer.createEl('label', { cls: 'thoth-multiselect-option' });

        const checkbox = optionEl.createEl('input', { type: 'checkbox' });
        checkbox.checked = currentValues.includes(option);

        optionEl.createEl('span', { text: option });

        checkbox.addEventListener('change', async () => {
          const selectedValues = Array.from(optionsContainer.querySelectorAll('input:checked'))
            .map(input => (input as HTMLInputElement).nextElementSibling?.textContent || '');

          this.updateFieldValue(fieldName, selectedValues);
          await this.debouncedValidateField(fieldName, selectedValues);
        });
      }
    }
  }

  /**
   * Create file picker field
   */
  private createFileField(setting: Setting, fieldName: string, fieldSchema: FieldSchema, currentValue: any): void {
    setting.addText(text => {
      text.setPlaceholder('Click "Browse" to select file');
      text.setValue(currentValue || fieldSchema.default || '');
      text.inputEl.disabled = true;
    });

    setting.addButton(button => {
      button.setButtonText('Browse');
      button.setTooltip('Select file');
      button.onClick(async () => {
        try {
          // Use Electron's file dialog if available
          if (typeof require !== 'undefined') {
            const { remote } = require('electron');
            const { dialog } = remote;

            const result = await dialog.showOpenDialog({
              properties: ['openFile'],
              filters: [
                { name: 'All Files', extensions: ['*'] }
              ]
            });

            if (!result.canceled && result.filePaths.length > 0) {
              const filePath = result.filePaths[0];
              const textComponent = setting.controlEl.querySelector('input[type="text"]') as HTMLInputElement;
              if (textComponent) {
                textComponent.value = filePath;
                this.updateFieldValue(fieldName, filePath);
                await this.debouncedValidateField(fieldName, filePath);
              }
            }
          }
        } catch (error) {
          console.warn('File picker not available:', error);
          // Fallback to text input
          const textComponent = setting.controlEl.querySelector('input[type="text"]') as HTMLInputElement;
          if (textComponent) {
            textComponent.disabled = false;
            textComponent.placeholder = 'Enter file path manually';
          }
        }
      });
    });
  }

  /**
   * Create directory picker field
   */
  private createDirectoryField(setting: Setting, fieldName: string, fieldSchema: FieldSchema, currentValue: any): void {
    setting.addText(text => {
      text.setPlaceholder('Click "Browse" to select directory');
      text.setValue(currentValue || fieldSchema.default || '');
      text.inputEl.disabled = true;
    });

    setting.addButton(button => {
      button.setButtonText('Browse');
      button.setTooltip('Select directory');
      button.onClick(async () => {
        try {
          // Use Electron's directory dialog if available
          if (typeof require !== 'undefined') {
            const { remote } = require('electron');
            const { dialog } = remote;

            const result = await dialog.showOpenDialog({
              properties: ['openDirectory']
            });

            if (!result.canceled && result.filePaths.length > 0) {
              const dirPath = result.filePaths[0];
              const textComponent = setting.controlEl.querySelector('input[type="text"]') as HTMLInputElement;
              if (textComponent) {
                textComponent.value = dirPath;
                this.updateFieldValue(fieldName, dirPath);
                await this.debouncedValidateField(fieldName, dirPath);
              }
            }
          }
        } catch (error) {
          console.warn('Directory picker not available:', error);
          // Fallback to text input
          const textComponent = setting.controlEl.querySelector('input[type="text"]') as HTMLInputElement;
          if (textComponent) {
            textComponent.disabled = false;
            textComponent.placeholder = 'Enter directory path manually';
          }
        }
      });
    });
  }

  /**
   * Create form action buttons
   */
  private createFormActions(container: HTMLElement): void {
    const saveBtn = container.createEl('button', {
      text: 'Save Configuration',
      cls: 'thoth-btn thoth-btn-primary'
    });

    const resetBtn = container.createEl('button', {
      text: 'Reset',
      cls: 'thoth-btn thoth-btn-secondary'
    });

    const exportBtn = container.createEl('button', {
      text: 'Export',
      cls: 'thoth-btn thoth-btn-secondary'
    });

    // Save button handler
    saveBtn.addEventListener('click', async () => {
      if (!this.formState.isValid) {
        this.showFormError('Please fix validation errors before saving');
        return;
      }

      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      try {
        if (this.saveCallback) {
          await this.saveCallback(this.getFormData());
          this.formState.isDirty = false;
          this.updateFormStatus();
          this.showFormSuccess('Configuration saved successfully');
        }
      } catch (error) {
        console.error('Save error:', error);
        this.showFormError(`Save failed: ${error.message}`);
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Configuration';
      }
    });

    // Reset button handler
    resetBtn.addEventListener('click', () => {
      if (this.formState.isDirty) {
        const confirmed = confirm('Are you sure you want to reset all changes?');
        if (!confirmed) return;
      }
      this.resetForm();
    });

    // Export button handler
    exportBtn.addEventListener('click', () => {
      this.exportConfiguration();
    });
  }

  /**
   * Create form status display
   */
  private createFormStatus(container: HTMLElement): void {
    const statusText = container.createEl('span', { cls: 'thoth-status-text' });
    const dirtyIndicator = container.createEl('span', { cls: 'thoth-dirty-indicator' });

    statusText.textContent = 'Ready';
    dirtyIndicator.style.display = 'none';

    this.updateFormStatus();
  }


  /**
   * Debounced field validation
   */
  private async debouncedValidateField(fieldName: string, value: any): Promise<void> {
    // Clear existing timer
    if (this.debounceTimers.has(fieldName)) {
      clearTimeout(this.debounceTimers.get(fieldName)!);
    }

    // Set new timer
    const timer = setTimeout(async () => {
      await this.validateField(fieldName);
      this.debounceTimers.delete(fieldName);
    }, this.VALIDATION_DEBOUNCE_MS);

    this.debounceTimers.set(fieldName, timer);
  }

  /**
   * Validate field with backend
   */
  async validateField(fieldName: string): Promise<FieldValidationResult> {
    const value = this.formState.values[fieldName];
    const component = this.fieldComponents.get(fieldName);

    if (!component) {
      return { is_valid: true };
    }

    let validationResult: FieldValidationResult = { is_valid: true };

    try {
      // Use backend validation if available
      if (this.validationCallback) {
        validationResult = await this.validationCallback(fieldName, value);
      } else {
        // Fallback to client-side validation
        validationResult = this.clientSideValidation(fieldName, value, component.fieldSchema);
      }
    } catch (error) {
      console.warn(`Validation failed for ${fieldName}:`, error);
      validationResult = { is_valid: true }; // Don't block user on validation errors
    }

    // Store validation result
    this.formState.validationResults[fieldName] = validationResult;

    // Update UI
    this.displayValidationResult(fieldName, validationResult);
    this.updateFormValidityState();

    return validationResult;
  }

  /**
   * Client-side validation fallback
   */
  private clientSideValidation(fieldName: string, value: any, fieldSchema: FieldSchema): FieldValidationResult {
    // Required field validation
    if (fieldSchema.required && (value === undefined || value === null || value === '')) {
      return {
        is_valid: false,
        error: 'This field is required'
      };
    }

    // Pattern validation for text fields
    if (fieldSchema.validation?.pattern && value) {
      const regex = new RegExp(fieldSchema.validation.pattern);
      if (!regex.test(value)) {
        return {
          is_valid: false,
          error: fieldSchema.validation.message || 'Invalid format'
        };
      }
    }

    // Number range validation
    if (fieldSchema.type === 'number' && value !== undefined && value !== null) {
      const numValue = Number(value);
      if (isNaN(numValue)) {
        return {
          is_valid: false,
          error: 'Must be a valid number'
        };
      }

      if (fieldSchema.validation?.min !== undefined && numValue < fieldSchema.validation.min) {
        return {
          is_valid: false,
          error: `Must be at least ${fieldSchema.validation.min}`
        };
      }

      if (fieldSchema.validation?.max !== undefined && numValue > fieldSchema.validation.max) {
        return {
          is_valid: false,
          error: `Must be at most ${fieldSchema.validation.max}`
        };
      }
    }

    return { is_valid: true };
  }

  /**
   * Display validation result for a field
   */
  private displayValidationResult(fieldName: string, result: FieldValidationResult): void {
    const component = this.fieldComponents.get(fieldName);
    if (!component || !component.validationEl) return;

    const validationEl = component.validationEl;

    if (result.is_valid) {
      validationEl.style.display = 'none';
      component.container.classList.remove('thoth-field-error');
      component.container.classList.add('thoth-field-valid');
    } else {
      validationEl.style.display = 'block';
      validationEl.textContent = result.error || 'Validation error';
      validationEl.className = 'thoth-validation-message thoth-validation-error';
      component.container.classList.remove('thoth-field-valid');
      component.container.classList.add('thoth-field-error');
    }
  }

  /**
   * Update overall form validity state
   */
  private updateFormValidityState(): void {
    const hasErrors = Object.values(this.formState.validationResults)
      .some(result => !result.is_valid);

    this.formState.isValid = !hasErrors;
    this.updateFormStatus();
  }

  /**
   * Update form status display
   */
  private updateFormStatus(): void {
    const statusEl = document.querySelector('.thoth-status-text') as HTMLElement;
    const dirtyEl = document.querySelector('.thoth-dirty-indicator') as HTMLElement;

    if (statusEl) {
      if (!this.formState.isValid) {
        statusEl.textContent = 'Validation errors';
        statusEl.className = 'thoth-status-text thoth-status-error';
      } else if (this.formState.isDirty) {
        statusEl.textContent = 'Unsaved changes';
        statusEl.className = 'thoth-status-text thoth-status-warning';
      } else {
        statusEl.textContent = 'Saved';
        statusEl.className = 'thoth-status-text thoth-status-success';
      }
    }

    if (dirtyEl) {
      dirtyEl.style.display = this.formState.isDirty ? 'inline' : 'none';
      dirtyEl.textContent = '●';
    }
  }

  /**
   * Toggle group collapsed/expanded state
   */
  private toggleGroup(groupName: string): void {
    const groupEl = document.querySelector(`[data-group-name="${groupName}"]`) as HTMLElement;
    if (!groupEl) return;

    const contentEl = groupEl.querySelector('.thoth-group-content') as HTMLElement;
    const toggleEl = groupEl.querySelector('.thoth-group-toggle') as HTMLElement;

    if (contentEl && toggleEl) {
      const isCollapsed = contentEl.style.display === 'none';
      contentEl.style.display = isCollapsed ? 'block' : 'none';
      toggleEl.textContent = isCollapsed ? '▼' : '▶';
    }
  }

  /**
   * Get current form data
   */
  getFormData(): Partial<ThothSettings> {
    return { ...this.formState.values };
  }

  /**
   * Reset form to original state
   */
  private resetForm(): void {
    // Reset form state
    this.formState.isDirty = false;
    this.formState.validationResults = {};
    this.formState.isValid = true;

    // Reset field components
    for (const [fieldName, component] of this.fieldComponents) {
      const originalValue = component.currentValue;
      this.formState.values[fieldName] = originalValue;

      // Update UI component
      this.updateFieldUI(fieldName, originalValue);

      // Clear validation display
      if (component.validationEl) {
        component.validationEl.style.display = 'none';
      }
      component.container.classList.remove('thoth-field-error', 'thoth-field-valid');
    }

    this.updateFormStatus();
  }

  /**
   * Update field UI with new value
   */
  private updateFieldUI(fieldName: string, value: any): void {
    const component = this.fieldComponents.get(fieldName);
    if (!component) return;

    const inputEl = component.setting.controlEl.querySelector('input, select, textarea') as HTMLInputElement;
    if (inputEl) {
      if (component.fieldSchema.type === 'boolean') {
        (inputEl as HTMLInputElement).checked = Boolean(value);
      } else {
        inputEl.value = value?.toString() || '';
      }
    }
  }

  /**
   * Export configuration to JSON file
   */
  private exportConfiguration(): void {
    const config = this.getFormData();
    const dataStr = JSON.stringify(config, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });

    const link = document.createElement('a');
    link.href = URL.createObjectURL(dataBlob);
    link.download = `thoth-config-${new Date().toISOString().split('T')[0]}.json`;
    link.click();

    URL.revokeObjectURL(link.href);
  }

  /**
   * Show form error message
   */
  private showFormError(message: string): void {
    // Create or update error display
    let errorEl = document.querySelector('.thoth-form-error') as HTMLElement;
    if (!errorEl) {
      const formEl = document.querySelector('.thoth-settings-form');
      if (formEl) {
        errorEl = formEl.createEl('div', { cls: 'thoth-form-error' });
      }
    }

    if (errorEl) {
      errorEl.textContent = message;
      errorEl.style.display = 'block';

      // Auto-hide after 5 seconds
      setTimeout(() => {
        errorEl.style.display = 'none';
      }, 5000);
    }
  }

  /**
   * Show form success message
   */
  private showFormSuccess(message: string): void {
    // Create or update success display
    let successEl = document.querySelector('.thoth-form-success') as HTMLElement;
    if (!successEl) {
      const formEl = document.querySelector('.thoth-settings-form');
      if (formEl) {
        successEl = formEl.createEl('div', { cls: 'thoth-form-success' });
      }
    }

    if (successEl) {
      successEl.textContent = message;
      successEl.style.display = 'block';

      // Auto-hide after 3 seconds
      setTimeout(() => {
        successEl.style.display = 'none';
      }, 3000);
    }
  }

  /**
   * Advanced organization helper methods
   */

  private hasAdvancedFeatures(schema: UISchema): boolean {
    return !!(schema.field_dependencies || schema.conditional_rules || schema.advanced_categories);
  }

  private createAdvancedFeaturesToggle(container: HTMLElement): void {
    const toggleContainer = container.createEl('div', { cls: 'thoth-advanced-toggle' });

    const toggle = toggleContainer.createEl('label', { cls: 'thoth-toggle-label' });
    const checkbox = toggle.createEl('input', { type: 'checkbox' });
    toggle.createEl('span', { text: 'Show Advanced Settings' });

    checkbox.addEventListener('change', () => {
      this.formState.values['ui_preferences.show_advanced'] = checkbox.checked;
      this.updateDependentFields('ui_preferences.show_advanced', checkbox.checked);
    });
  }

  private evaluateGroupVisibility(groupName: string, currentConfig: ThothSettings): boolean {
    // Check if any fields in the group are visible
    if (!this.schema) return true;

    const groupFields = Object.entries(this.schema.fields)
      .filter(([, fieldSchema]) => fieldSchema.group === groupName)
      .map(([fieldName]) => fieldName);

    return groupFields.some(fieldName => this.evaluateFieldVisibility(fieldName, currentConfig));
  }

  private evaluateCondition(condition: string, value: any, targetValue: any): boolean {
    switch (condition) {
      case 'equals':
        return value === targetValue;
      case 'not_equals':
        return value !== targetValue;
      case 'greater_than':
        return Number(value) > Number(targetValue);
      case 'less_than':
        return Number(value) < Number(targetValue);
      case 'contains':
        return String(value).includes(String(targetValue));
      case 'not_empty':
        return value !== null && value !== undefined && value !== '';
      default:
        return true;
    }
  }

  private evaluateConditionExpression(expression: string, config: ThothSettings): boolean {
    try {
      // Simple expression parser for basic conditions
      // Replace field references with actual values
      let evaluatedExpression = expression;

      // Find field references (format: field.path)
      const fieldRefs = expression.match(/[\w.]+(?=\s*[!=<>])/g) || [];

      for (const fieldRef of fieldRefs) {
        if (fieldRef.includes('.')) {
          const fieldValue = this.getConfigValue(config, fieldRef);

          // Convert to string representation for expression
          let valueRepr: string;
          if (typeof fieldValue === 'string') {
            valueRepr = `'${fieldValue}'`;
          } else if (fieldValue === null || fieldValue === undefined) {
            valueRepr = "''";
          } else {
            valueRepr = String(fieldValue).toLowerCase();
          }

          evaluatedExpression = evaluatedExpression.replace(new RegExp(fieldRef, 'g'), valueRepr);
        }
      }

      // Note: In production, use a safe expression evaluator
      return new Function('return ' + evaluatedExpression)();
    } catch (error) {
      console.warn(`Failed to evaluate condition expression "${expression}":`, error);
      return true; // Default to showing field if evaluation fails
    }
  }

  private getConfigValue(config: ThothSettings, fieldPath: string): any {
    const keys = fieldPath.split('.');
    let current: any = config;

    for (const key of keys) {
      if (current && typeof current === 'object' && key in current) {
        current = current[key];
      } else {
        return undefined;
      }
    }

    return current;
  }

  private extractDependenciesFromExpression(expression: string): string[] {
    const fieldRefs = expression.match(/[\w.]+(?=\s*[!=<>])/g) || [];
    return fieldRefs.filter(ref => ref.includes('.'));
  }

  private updateFieldVisibility(fieldName: string, isVisible: boolean): void {
    const component = this.fieldComponents.get(fieldName);
    if (component) {
      component.container.style.display = isVisible ? 'block' : 'none';

      // Add/remove visibility class for CSS transitions
      if (isVisible) {
        component.container.classList.remove('thoth-field-hidden');
        component.container.classList.add('thoth-field-visible');
      } else {
        component.container.classList.remove('thoth-field-visible');
        component.container.classList.add('thoth-field-hidden');
      }
    }
  }

  private updateFieldRequirements(fieldName: string, currentConfig: ThothSettings): void {
    const component = this.fieldComponents.get(fieldName);
    if (!component) return;

    // Check if field should be required based on dependencies
    let isRequired = component.fieldSchema.required;

    for (const dependency of this.fieldDependencies) {
      if (dependency.field_path === fieldName && dependency.action === 'require') {
        const dependsValue = this.getConfigValue(currentConfig, dependency.depends_on);
        const conditionMet = this.evaluateCondition(dependency.condition, dependsValue, dependency.value);
        isRequired = isRequired || conditionMet;
      }
    }

    // Update UI to reflect requirement changes
    const nameEl = component.container.querySelector('.setting-item-name');
    if (nameEl) {
      const indicator = nameEl.querySelector('.thoth-required-indicator');
      if (isRequired && !indicator) {
        nameEl.createEl('span', { text: ' *', cls: 'thoth-required-indicator' });
      } else if (!isRequired && indicator) {
        indicator.remove();
      }
    }
  }

  private generateWizardSteps(category: string, container: HTMLElement): void {
    // Generate wizard steps based on category
    const steps = this.getWizardStepsForCategory(category);

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      const stepEl = container.createEl('div', { cls: 'thoth-wizard-step' });

      const stepHeader = stepEl.createEl('div', { cls: 'thoth-wizard-step-header' });
      stepHeader.createEl('span', { text: `${i + 1}.`, cls: 'thoth-wizard-step-number' });
      stepHeader.createEl('span', { text: step.title, cls: 'thoth-wizard-step-title' });

      stepEl.createEl('p', { text: step.description, cls: 'thoth-wizard-step-description' });

      // Add fields for this step
      if (step.fields) {
        const fieldsContainer = stepEl.createEl('div', { cls: 'thoth-wizard-step-fields' });
        for (const fieldName of step.fields) {
          const fieldSchema = this.schema?.fields[fieldName];
          if (fieldSchema) {
            const fieldEl = this.generateFieldComponent(fieldName, fieldSchema, this.formState.values[fieldName]);
            fieldsContainer.appendChild(fieldEl);
          }
        }
      }
    }
  }

  private getWizardStepsForCategory(category: string): Array<{title: string, description: string, fields?: string[]}> {
    const stepDefinitions: Record<string, Array<{title: string, description: string, fields?: string[]}>> = {
      'API Keys': [
        {
          title: 'Choose AI Provider',
          description: 'Select your preferred AI provider and enter the API key',
          fields: ['api_keys.mistral_key', 'api_keys.openrouter_key']
        },
        {
          title: 'Test Connection',
          description: 'Verify your API key works correctly'
        }
      ],
      'LLM Configuration': [
        {
          title: 'Select Model',
          description: 'Choose the AI model that best fits your needs',
          fields: ['llm.default.model']
        },
        {
          title: 'Configure Behavior',
          description: 'Adjust model parameters for your use case',
          fields: ['llm.default.temperature', 'llm.default.max_tokens']
        }
      ]
    };

    return stepDefinitions[category] || [];
  }

  /**
   * Update field value with dependency handling (enhanced version)
   */
  updateFieldValue(fieldName: string, value: any): void {
    const oldValue = this.formState.values[fieldName];
    this.formState.values[fieldName] = value;

    // Mark form as dirty if value changed
    if (oldValue !== value) {
      this.formState.isDirty = true;
      this.updateFormStatus();

      // Update dependent fields with advanced organization features
      this.updateDependentFields(fieldName, value);
    }
  }

  /**
   * Clean up resources
   */
  cleanup(): void {
    // Clear debounce timers
    for (const timer of this.debounceTimers.values()) {
      clearTimeout(timer);
    }
    this.debounceTimers.clear();

    // Clear component references
    this.fieldComponents.clear();

    // Clear advanced organization state
    this.fieldDependencies = [];
    this.conditionalRules = [];
    this.visibilityState.clear();
    this.dependencyGraph.clear();
  }
}

/**
 * Validation result interface for internal use
 */
interface ValidationResult {
  isValid: boolean;
  error?: string;
  warning?: string;
}
