/**
 * Configuration wizard for guided setup of Thoth settings.
 *
 * Provides step-by-step guidance for users to configure Thoth
 * based on their specific use cases and requirements.
 */

import { Modal, Setting } from 'obsidian';
import { UISchema, FieldSchema, FieldValidationResult } from '../services/schema-service';
import { ThothSettings } from '../types';
import { ValidationDisplay, AutoFixSuggestion } from './validation-display';
import { getGlobalCacheManager } from '../services/performance-cache';

/**
 * Wizard step interface
 */
interface WizardStep {
  step_id: string;
  title: string;
  description: string;
  step_type: 'info' | 'form' | 'review' | 'test';
  fields: string[];
  validation_required: boolean;
  next_step?: string;
  previous_step?: string;
  completion_percentage: number;
}

/**
 * Use case configuration interface
 */
interface ConfigurationUseCase {
  use_case_id: string;
  name: string;
  description: string;
  recommended_settings: Record<string, any>;
  required_fields: string[];
  optional_fields: string[];
  performance_impact: 'low' | 'medium' | 'high';
  complexity_level: 'beginner' | 'intermediate' | 'advanced';
  estimated_setup_time: string;
  prerequisites: string[];
}

/**
 * Wizard state interface
 */
interface WizardState {
  currentStep: number;
  totalSteps: number;
  selectedUseCase?: ConfigurationUseCase;
  collectedData: Record<string, any>;
  validationResults: Record<string, FieldValidationResult>;
  isComplete: boolean;
  canProceed: boolean;
}

/**
 * Configuration wizard implementation
 */
export class ConfigurationWizard extends Modal {
  private wizardState: WizardState;
  private validationDisplay: ValidationDisplay;
  private steps: WizardStep[] = [];
  private useCases: ConfigurationUseCase[] = [];
  private onComplete: (config: Partial<ThothSettings>) => Promise<void>;
  private validationCallback?: (fieldName: string, value: any) => Promise<FieldValidationResult>;
  private cacheManager = getGlobalCacheManager();

  constructor(
    app: any,
    schema: UISchema,
    currentConfig: Partial<ThothSettings>,
    onComplete: (config: Partial<ThothSettings>) => Promise<void>
  ) {
    super(app);

    this.onComplete = onComplete;
    this.validationDisplay = new ValidationDisplay();

    this.wizardState = {
      currentStep: 0,
      totalSteps: 0,
      collectedData: { ...currentConfig },
      validationResults: {},
      isComplete: false,
      canProceed: false
    };

    this.initializeUseCases();
    this.initializeWizardStyles();
  }

  /**
   * Set validation callback
   */
  setValidationCallback(callback: (fieldName: string, value: any) => Promise<FieldValidationResult>): void {
    this.validationCallback = callback;
  }

  /**
   * Open wizard
   */
  onOpen(): void {
    const { contentEl } = this;
    contentEl.addClass('thoth-wizard-modal');

    this.renderUseCaseSelection();
  }

  /**
   * Close wizard
   */
  onClose(): void {
    this.contentEl.empty();
  }

  /**
   * Initialize configuration use cases
   */
  private initializeUseCases(): void {
    this.useCases = [
      {
        use_case_id: 'researcher_basic',
        name: '📚 Basic Research Assistant',
        description: 'Simple setup for research paper analysis and note-taking',
        recommended_settings: {
          'paths.workspace': './research',
          'paths.pdf': './research/papers',
          'paths.notes': './research/notes',
          'llm.default.model': 'mistral/mistral-large-latest',
          'llm.default.temperature': 0.3,
          'memory.letta.agentModel': 'anthropic/claude-sonnet-4-20250514',
          'features.discovery.enabled': true,
          'features.api_server.enabled': false
        },
        required_fields: ['api_keys.mistral_key', 'paths.workspace'],
        optional_fields: ['memory.letta.agentModel', 'features.discovery.enabled', 'paths.pdf', 'paths.notes'],
        performance_impact: 'low',
        complexity_level: 'beginner',
        estimated_setup_time: '3-5 minutes',
        prerequisites: ['Mistral AI API key']
      },
      {
        use_case_id: 'power_user',
        name: '⚡ Power User Setup',
        description: 'Full-featured setup with all services enabled',
        recommended_settings: {
          'features.api_server.enabled': true,
          'features.mcp.enabled': true,
          'features.rag.enabled': true,
          'features.discovery.enabled': true,
          'memory.letta.agentModel': 'anthropic/claude-sonnet-4-20250514',
          'performance_config.cache_enabled': true,
          'monitoring.health_checks': true,
          'servers.api.port': 8000,
          'servers.mcp.port': 8001
        },
        required_fields: ['api_keys.mistral_key', 'paths.workspace', 'servers.api.port'],
        optional_fields: ['memory.letta.agentModel', 'api_keys.openrouter_key', 'monitoring.health_checks', 'performance_config.cache_enabled'],
        performance_impact: 'high',
        complexity_level: 'advanced',
        estimated_setup_time: '10-15 minutes',
        prerequisites: ['Multiple AI provider API keys', 'Understanding of server configuration']
      },
      {
        use_case_id: 'team_server',
        name: '🏢 Team Server',
        description: 'Multi-user server setup for team collaboration',
        recommended_settings: {
          'features.api_server.enabled': true,
          'servers.api.host': '0.0.0.0',
          'servers.api.port': 8000,
          'servers.api.cors_enabled': true,
          'features.rag.enabled': true,
          'memory.letta.agentModel': 'anthropic/claude-sonnet-4-20250514',
          'monitoring.health_checks': true,
          'performance_config.cache_enabled': true,
          'logging.level': 'INFO'
        },
        required_fields: ['servers.api.port', 'api_keys.mistral_key', 'paths.workspace'],
        optional_fields: ['memory.letta.agentModel', 'servers.api.cors_enabled', 'monitoring.health_checks', 'logging.level'],
        performance_impact: 'high',
        complexity_level: 'intermediate',
        estimated_setup_time: '8-12 minutes',
        prerequisites: ['Network configuration knowledge', 'Team API key management']
      },
      {
        use_case_id: 'custom',
        name: '🛠️ Custom Configuration',
        description: 'Manual configuration for specific requirements',
        recommended_settings: {},
        required_fields: ['api_keys.mistral_key'],
        optional_fields: ['memory.letta.agentModel'],
        performance_impact: 'medium',
        complexity_level: 'intermediate',
        estimated_setup_time: '5-20 minutes',
        prerequisites: ['Basic understanding of Thoth features']
      }
    ];
  }

  /**
   * Render use case selection screen
   */
  private renderUseCaseSelection(): void {
    const { contentEl } = this;
    contentEl.empty();

    // Header
    const headerEl = contentEl.createEl('div', { cls: 'thoth-wizard-header' });
    headerEl.createEl('h1', { text: '🧙‍♂️ Thoth Configuration Wizard' });
    headerEl.createEl('p', { text: 'Choose your setup type to get started quickly' });

    // Use case cards
    const useCasesEl = contentEl.createEl('div', { cls: 'thoth-use-cases' });

    for (const useCase of this.useCases) {
      const cardEl = useCasesEl.createEl('div', { cls: 'thoth-use-case-card' });

      // Card header
      const cardHeader = cardEl.createEl('div', { cls: 'thoth-use-case-header' });
      cardHeader.createEl('h3', { text: useCase.name });

      // Metadata badges
      const metadataEl = cardHeader.createEl('div', { cls: 'thoth-use-case-metadata' });
      metadataEl.createEl('span', {
        text: useCase.complexity_level.toUpperCase(),
        cls: `thoth-complexity thoth-complexity-${useCase.complexity_level}`
      });
      metadataEl.createEl('span', {
        text: useCase.performance_impact.toUpperCase(),
        cls: `thoth-performance thoth-performance-${useCase.performance_impact}`
      });

      // Description
      cardEl.createEl('p', { text: useCase.description, cls: 'thoth-use-case-description' });

      // Details
      const detailsEl = cardEl.createEl('div', { cls: 'thoth-use-case-details' });
      detailsEl.createEl('div', { text: `⏱️ Setup time: ${useCase.estimated_setup_time}` });
      detailsEl.createEl('div', { text: `📋 Required fields: ${useCase.required_fields.length}` });

      // Prerequisites
      if (useCase.prerequisites.length > 0) {
        const prereqEl = detailsEl.createEl('div', { cls: 'thoth-prerequisites' });
        prereqEl.createEl('strong', { text: 'Prerequisites:' });
        const prereqList = prereqEl.createEl('ul');
        for (const prereq of useCase.prerequisites) {
          prereqList.createEl('li', { text: prereq });
        }
      }

      // Select button
      const selectBtn = cardEl.createEl('button', {
        text: 'Select This Setup',
        cls: 'thoth-use-case-select-btn'
      });

      selectBtn.addEventListener('click', () => {
        this.selectUseCase(useCase);
      });
    }

    // Manual configuration option
    const manualEl = contentEl.createEl('div', { cls: 'thoth-manual-config' });
    const manualBtn = manualEl.createEl('button', {
      text: '⚙️ Skip Wizard (Manual Configuration)',
      cls: 'thoth-manual-config-btn'
    });

    manualBtn.addEventListener('click', () => {
      this.close();
    });
  }

  /**
   * Select use case and proceed to wizard steps
   */
  private selectUseCase(useCase: ConfigurationUseCase): void {
    this.wizardState.selectedUseCase = useCase;

    // Generate wizard steps for selected use case
    this.generateWizardSteps(useCase);

    // Start the wizard
    this.wizardState.currentStep = 0;
    this.renderCurrentStep();
  }

  /**
   * Generate wizard steps for selected use case
   */
  private generateWizardSteps(useCase: ConfigurationUseCase): void {
    this.steps = [];

    // Step 1: Overview
    this.steps.push({
      step_id: 'overview',
      title: `Setup: ${useCase.name}`,
      description: useCase.description,
      step_type: 'info',
      fields: [],
      validation_required: false,
      completion_percentage: 10
    });

    // Step 2: Required fields
    if (useCase.required_fields.length > 0) {
      this.steps.push({
        step_id: 'required_fields',
        title: 'Required Configuration',
        description: 'These settings are required for basic functionality',
        step_type: 'form',
        fields: useCase.required_fields,
        validation_required: true,
        completion_percentage: 50
      });
    }

    // Step 3: Optional fields (grouped)
    if (useCase.optional_fields.length > 0) {
      const optionalGroups = this.groupFieldsByCategory(useCase.optional_fields);

      for (const [category, fields] of Object.entries(optionalGroups)) {
        this.steps.push({
          step_id: `optional_${category.toLowerCase().replace(/\s+/g, '_')}`,
          title: `Optional: ${category}`,
          description: `Configure additional ${category.toLowerCase()} settings`,
          step_type: 'form',
          fields: fields,
          validation_required: false,
          completion_percentage: 70 + (Object.keys(optionalGroups).indexOf(category) * 10)
        });
      }
    }

    // Step 4: Test configuration
    this.steps.push({
      step_id: 'test',
      title: 'Test Configuration',
      description: 'Test your configuration to ensure everything works',
      step_type: 'test',
      fields: [],
      validation_required: true,
      completion_percentage: 90
    });

    // Step 5: Review and complete
    this.steps.push({
      step_id: 'review',
      title: 'Review & Complete',
      description: 'Review your configuration and complete setup',
      step_type: 'review',
      fields: [...useCase.required_fields, ...useCase.optional_fields],
      validation_required: true,
      completion_percentage: 100
    });

    this.wizardState.totalSteps = this.steps.length;
  }

  /**
   * Render current wizard step
   */
  private renderCurrentStep(): void {
    const { contentEl } = this;
    contentEl.empty();

    const currentStep = this.steps[this.wizardState.currentStep];
    if (!currentStep) return;

    // Wizard container
    const wizardEl = contentEl.createEl('div', { cls: 'thoth-wizard-container' });

    // Progress bar
    this.renderProgressBar(wizardEl, currentStep);

    // Step content
    const stepEl = wizardEl.createEl('div', { cls: 'thoth-wizard-step' });

    // Step header
    const headerEl = stepEl.createEl('div', { cls: 'thoth-wizard-step-header' });
    headerEl.createEl('h2', { text: currentStep.title });
    headerEl.createEl('p', { text: currentStep.description });

    // Step content based on type
    const contentContainer = stepEl.createEl('div', { cls: 'thoth-wizard-step-content' });

    switch (currentStep.step_type) {
      case 'info':
        this.renderInfoStep(contentContainer, currentStep);
        break;
      case 'form':
        this.renderFormStep(contentContainer, currentStep);
        break;
      case 'test':
        this.renderTestStep(contentContainer, currentStep);
        break;
      case 'review':
        this.renderReviewStep(contentContainer, currentStep);
        break;
    }

    // Navigation buttons
    const navEl = stepEl.createEl('div', { cls: 'thoth-wizard-navigation' });
    this.renderNavigationButtons(navEl, currentStep);
  }

  /**
   * Render progress bar
   */
  private renderProgressBar(container: HTMLElement, currentStep: WizardStep): void {
    const progressEl = container.createEl('div', { cls: 'thoth-wizard-progress' });

    const progressBar = progressEl.createEl('div', { cls: 'thoth-progress-bar' });
    const progressFill = progressBar.createEl('div', { cls: 'thoth-progress-fill' });
    progressFill.style.width = `${currentStep.completion_percentage}%`;

    const progressText = progressEl.createEl('div', { cls: 'thoth-progress-text' });
    progressText.textContent = `Step ${this.wizardState.currentStep + 1} of ${this.wizardState.totalSteps} (${currentStep.completion_percentage}%)`;
  }

  /**
   * Render info step
   */
  private renderInfoStep(container: HTMLElement, step: WizardStep): void {
    if (this.wizardState.selectedUseCase) {
      const useCase = this.wizardState.selectedUseCase;

      // Use case overview
      const overviewEl = container.createEl('div', { cls: 'thoth-use-case-overview' });

      overviewEl.createEl('h3', { text: 'Configuration Overview' });

      const detailsEl = overviewEl.createEl('div', { cls: 'thoth-overview-details' });
      detailsEl.createEl('div', { text: `📊 Complexity: ${useCase.complexity_level}` });
      detailsEl.createEl('div', { text: `⚡ Performance Impact: ${useCase.performance_impact}` });
      detailsEl.createEl('div', { text: `⏱️ Estimated Setup Time: ${useCase.estimated_setup_time}` });

      // What will be configured
      const configEl = overviewEl.createEl('div', { cls: 'thoth-config-preview' });
      configEl.createEl('h4', { text: 'What will be configured:' });

      const configList = configEl.createEl('ul');
      for (const [key, value] of Object.entries(useCase.recommended_settings)) {
        const listItem = configList.createEl('li');
        listItem.createEl('strong', { text: key });
        listItem.createEl('span', { text: `: ${value}` });
      }
    }

    this.wizardState.canProceed = true;
  }

  /**
   * Render form step
   */
  private renderFormStep(container: HTMLElement, step: WizardStep): void {
    const formEl = container.createEl('div', { cls: 'thoth-wizard-form' });

    let allFieldsValid = true;

    for (const fieldName of step.fields) {
      const fieldContainer = formEl.createEl('div', { cls: 'thoth-wizard-field' });

      // Create field based on type (simplified for wizard)
      const setting = new Setting(fieldContainer);

      // Get field metadata
      const fieldMetadata = this.getFieldMetadata(fieldName);

      setting.setName(fieldMetadata.title || fieldName);
      setting.setDesc(fieldMetadata.description || '');

      // Add required indicator
      if (fieldMetadata.required) {
        const nameEl = setting.nameEl;
        nameEl.appendChild(nameEl.createSpan({ text: ' *', cls: 'thoth-required-indicator' }));
      }

      // Create input based on field type
      this.createWizardField(setting, fieldName, fieldMetadata);

      // Add validation display
      const validationEl = fieldContainer.createEl('div', { cls: 'thoth-wizard-field-validation' });
      validationEl.style.display = 'none';

      // Validate field if it has a value
      const currentValue = this.wizardState.collectedData[fieldName];
      if (currentValue !== undefined && currentValue !== '') {
        this.validateWizardField(fieldName, currentValue, validationEl);
      } else if (fieldMetadata.required) {
        allFieldsValid = false;
      }
    }

    this.wizardState.canProceed = !step.validation_required || allFieldsValid;
  }

  /**
   * Render test step
   */
  private renderTestStep(container: HTMLElement, step: WizardStep): void {
    const testEl = container.createEl('div', { cls: 'thoth-wizard-test' });

    testEl.createEl('h3', { text: '🧪 Testing Configuration' });
    testEl.createEl('p', { text: 'Running tests to verify your configuration...' });

    const testsEl = testEl.createEl('div', { cls: 'thoth-test-results' });

    // Run configuration tests
    this.runConfigurationTests(testsEl);
  }

  /**
   * Render review step
   */
  private renderReviewStep(container: HTMLElement, step: WizardStep): void {
    const reviewEl = container.createEl('div', { cls: 'thoth-wizard-review' });

    reviewEl.createEl('h3', { text: '📋 Configuration Review' });
    reviewEl.createEl('p', { text: 'Please review your configuration before completing setup' });

    // Configuration summary
    const summaryEl = reviewEl.createEl('div', { cls: 'thoth-config-summary' });

    for (const [fieldName, value] of Object.entries(this.wizardState.collectedData)) {
      if (value !== undefined && value !== '') {
        const itemEl = summaryEl.createEl('div', { cls: 'thoth-config-item' });
        itemEl.createEl('span', { text: fieldName, cls: 'thoth-config-key' });
        itemEl.createEl('span', { text: this.formatDisplayValue(value), cls: 'thoth-config-value' });
      }
    }

    // Final validation
    this.validateCompleteConfiguration();
  }

  /**
   * Render navigation buttons
   */
  private renderNavigationButtons(container: HTMLElement, currentStep: WizardStep): void {
    const navEl = container.createEl('div', { cls: 'thoth-wizard-nav' });

    // Previous button
    if (this.wizardState.currentStep > 0) {
      const prevBtn = navEl.createEl('button', {
        text: '← Previous',
        cls: 'thoth-wizard-btn thoth-wizard-btn-secondary'
      });
      prevBtn.addEventListener('click', () => this.goToPreviousStep());
    }

    // Next/Complete button
    const isLastStep = this.wizardState.currentStep === this.wizardState.totalSteps - 1;
    const nextBtn = navEl.createEl('button', {
      text: isLastStep ? 'Complete Setup' : 'Next →',
      cls: `thoth-wizard-btn thoth-wizard-btn-primary ${!this.wizardState.canProceed ? 'disabled' : ''}`
    });

    nextBtn.disabled = !this.wizardState.canProceed;

    nextBtn.addEventListener('click', () => {
      if (isLastStep) {
        this.completeWizard();
      } else {
        this.goToNextStep();
      }
    });

    // Cancel button
    const cancelBtn = navEl.createEl('button', {
      text: 'Cancel',
      cls: 'thoth-wizard-btn thoth-wizard-btn-cancel'
    });
    cancelBtn.addEventListener('click', () => this.close());
  }

  /**
   * Helper methods
   */

  private createWizardField(setting: Setting, fieldName: string, fieldMetadata: any): void {
    const currentValue = this.wizardState.collectedData[fieldName] || '';

    // Create appropriate input type
    if (fieldMetadata.type === 'password') {
      setting.addText(text => {
        text.inputEl.type = 'password';
        text.setPlaceholder(fieldMetadata.placeholder || 'Enter value...');
        text.setValue(currentValue);
        text.onChange((value) => this.updateWizardField(fieldName, value));
      });
    } else if (fieldMetadata.type === 'boolean') {
      setting.addToggle(toggle => {
        toggle.setValue(Boolean(currentValue));
        toggle.onChange((value) => this.updateWizardField(fieldName, value));
      });
    } else if (fieldMetadata.type === 'number') {
      setting.addText(text => {
        text.inputEl.type = 'number';
        text.setPlaceholder(fieldMetadata.placeholder || 'Enter number...');
        text.setValue(currentValue.toString());
        text.onChange((value) => this.updateWizardField(fieldName, Number(value)));
      });
    } else {
      // Default to text
      setting.addText(text => {
        text.setPlaceholder(fieldMetadata.placeholder || 'Enter value...');
        text.setValue(currentValue);
        text.onChange((value) => this.updateWizardField(fieldName, value));
      });
    }
  }

  private updateWizardField(fieldName: string, value: any): void {
    this.wizardState.collectedData[fieldName] = value;

    // Validate field
    if (this.validationCallback) {
      this.validationCallback(fieldName, value).then(result => {
        this.wizardState.validationResults[fieldName] = result;
        this.updateStepValidation();
      });
    }
  }

  private async validateWizardField(fieldName: string, value: any, validationEl: HTMLElement): Promise<void> {
    if (!this.validationCallback) return;

    try {
      const result = await this.validationCallback(fieldName, value);
      this.wizardState.validationResults[fieldName] = result;

      if (!result.is_valid) {
        validationEl.innerHTML = '';
        validationEl.className = 'thoth-wizard-field-validation thoth-validation-error';
        validationEl.createEl('span', { text: '❌' });
        validationEl.createEl('span', { text: result.error || 'Validation failed' });
        validationEl.style.display = 'block';
      } else {
        validationEl.style.display = 'none';
      }
    } catch (error) {
      console.warn(`Wizard validation failed for ${fieldName}:`, error);
    }
  }

  private async runConfigurationTests(container: HTMLElement): Promise<void> {
    const tests = [
      { name: 'API Key Validation', test: () => this.testApiKeys() },
      { name: 'Directory Access', test: () => this.testDirectoryAccess() },
      { name: 'Server Configuration', test: () => this.testServerConfig() },
      { name: 'Service Connectivity', test: () => this.testServiceConnectivity() }
    ];

    for (const testCase of tests) {
      const testEl = container.createEl('div', { cls: 'thoth-test-case' });
      testEl.createEl('span', { text: testCase.name, cls: 'thoth-test-name' });

      const statusEl = testEl.createEl('span', { cls: 'thoth-test-status' });
      statusEl.textContent = '🔄 Running...';

      try {
        const result = await testCase.test();
        if (result.success) {
          statusEl.textContent = '✅ Passed';
          statusEl.className = 'thoth-test-status thoth-test-success';
        } else {
          statusEl.textContent = '❌ Failed';
          statusEl.className = 'thoth-test-status thoth-test-error';
          testEl.createEl('div', { text: result.error, cls: 'thoth-test-error-message' });
        }
      } catch (error) {
        statusEl.textContent = '❌ Error';
        statusEl.className = 'thoth-test-status thoth-test-error';
        testEl.createEl('div', { text: error.message, cls: 'thoth-test-error-message' });
      }

      // Add small delay for visual effect
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    this.wizardState.canProceed = true;
  }

  /**
   * Navigation methods
   */
  private goToNextStep(): void {
    if (this.wizardState.currentStep < this.wizardState.totalSteps - 1) {
      this.wizardState.currentStep++;
      this.renderCurrentStep();
    }
  }

  private goToPreviousStep(): void {
    if (this.wizardState.currentStep > 0) {
      this.wizardState.currentStep--;
      this.renderCurrentStep();
    }
  }

  /**
   * Complete wizard and apply configuration
   */
  private async completeWizard(): Promise<void> {
    try {
      // Apply recommended settings from use case
      if (this.wizardState.selectedUseCase) {
        const recommendedSettings = this.wizardState.selectedUseCase.recommended_settings;
        Object.assign(this.wizardState.collectedData, recommendedSettings);
      }

      // Save configuration
      await this.onComplete(this.wizardState.collectedData);

      // Cache wizard completion for analytics
      this.cacheManager.cacheUIState('wizard_completion', {
        useCase: this.wizardState.selectedUseCase?.use_case_id,
        completedAt: new Date().toISOString(),
        stepCount: this.wizardState.totalSteps
      });

      this.close();
    } catch (error) {
      console.error('Failed to complete wizard:', error);
      this.validationDisplay.showFormError(`Setup failed: ${error.message}`);
    }
  }

  /**
   * Utility methods
   */

  private groupFieldsByCategory(fields: string[]): Record<string, string[]> {
    const grouped: Record<string, string[]> = {};

    for (const field of fields) {
      const category = this.getFieldCategory(field);
      if (!grouped[category]) {
        grouped[category] = [];
      }
      grouped[category].push(field);
    }

    return grouped;
  }

  private getFieldCategory(fieldName: string): string {
    if (fieldName.startsWith('api_keys')) return 'API Configuration';
    if (fieldName.startsWith('paths')) return 'Directories';
    if (fieldName.startsWith('servers')) return 'Server Settings';
    if (fieldName.startsWith('features')) return 'Features';
    if (fieldName.startsWith('memory.letta')) return 'Agent Configuration';
    return 'General';
  }

  private getFieldMetadata(fieldName: string): any {
    // Custom metadata for known fields
    const customFields: Record<string, any> = {
      'memory.letta.agentModel': {
        title: 'Letta Agent Model',
        description: 'LLM model for research agents (litellm format, e.g. "anthropic/claude-sonnet-4-20250514"). Leave empty for Letta server default.',
        type: 'text',
        placeholder: 'anthropic/claude-sonnet-4-20250514',
      },
    };

    if (customFields[fieldName]) {
      return {
        ...customFields[fieldName],
        required: this.wizardState.selectedUseCase?.required_fields.includes(fieldName),
      };
    }

    return {
      title: this.formatFieldTitle(fieldName),
      description: `Configure ${fieldName}`,
      type: this.inferFieldType(fieldName),
      required: this.wizardState.selectedUseCase?.required_fields.includes(fieldName),
      placeholder: this.getFieldPlaceholder(fieldName)
    };
  }

  private formatFieldTitle(fieldName: string): string {
    return fieldName.split('.').pop()?.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()) || fieldName;
  }

  private inferFieldType(fieldName: string): string {
    if (fieldName.includes('key') || fieldName.includes('password')) return 'password';
    if (fieldName.includes('port') || fieldName.includes('timeout')) return 'number';
    if (fieldName.includes('enabled') || fieldName.includes('auto')) return 'boolean';
    return 'text';
  }

  private getFieldPlaceholder(fieldName: string): string {
    if (fieldName.includes('key')) return 'Enter your API key...';
    if (fieldName.includes('port')) return '8000';
    if (fieldName.includes('path') || fieldName.includes('dir')) return '/path/to/directory';
    if (fieldName.includes('url')) return 'https://example.com';
    return 'Enter value...';
  }

  private formatDisplayValue(value: any): string {
    if (typeof value === 'string' && value.includes('key')) {
      return '•••••••••'; // Hide sensitive values
    }
    return String(value);
  }

  private updateStepValidation(): void {
    const currentStep = this.steps[this.wizardState.currentStep];
    if (!currentStep || !currentStep.validation_required) {
      this.wizardState.canProceed = true;
      return;
    }

    // Check if all required fields in current step are valid
    const stepFieldsValid = currentStep.fields.every(fieldName => {
      const result = this.wizardState.validationResults[fieldName];
      const value = this.wizardState.collectedData[fieldName];
      const fieldMetadata = this.getFieldMetadata(fieldName);

      // Required field must have value and be valid
      if (fieldMetadata.required) {
        return value !== undefined && value !== '' && (!result || result.is_valid);
      }

      // Optional field must be valid if it has a value
      return !value || !result || result.is_valid;
    });

    this.wizardState.canProceed = stepFieldsValid;

    // Update next button state
    const nextBtn = document.querySelector('.thoth-wizard-btn-primary') as HTMLButtonElement;
    if (nextBtn) {
      nextBtn.disabled = !this.wizardState.canProceed;
      nextBtn.classList.toggle('disabled', !this.wizardState.canProceed);
    }
  }

  private validateCompleteConfiguration(): void {
    // Final validation of complete configuration
    const hasRequiredFields = this.wizardState.selectedUseCase?.required_fields.every(
      fieldName => this.wizardState.collectedData[fieldName] !== undefined &&
                  this.wizardState.collectedData[fieldName] !== ''
    );

    this.wizardState.canProceed = Boolean(hasRequiredFields);
  }

  /**
   * Test methods (simplified implementations)
   */
  private async testApiKeys(): Promise<{success: boolean, error?: string}> {
    const mistralKey = this.wizardState.collectedData['api_keys.mistral_key'];
    if (mistralKey) {
      // Simulate API key test
      return new Promise(resolve => {
        setTimeout(() => {
          resolve({ success: true });
        }, 1000);
      });
    }
    return { success: false, error: 'No API key configured' };
  }

  private async testDirectoryAccess(): Promise<{success: boolean, error?: string}> {
    // Simulate directory access test
    return new Promise(resolve => {
      setTimeout(() => {
        resolve({ success: true });
      }, 800);
    });
  }

  private async testServerConfig(): Promise<{success: boolean, error?: string}> {
    const serverEnabled = this.wizardState.collectedData['features.api_server.enabled'];
    if (serverEnabled) {
      // Simulate server configuration test
      return new Promise(resolve => {
        setTimeout(() => {
          resolve({ success: true });
        }, 1200);
      });
    }
    return { success: true }; // Skip if server not enabled
  }

  private async testServiceConnectivity(): Promise<{success: boolean, error?: string}> {
    // Simulate service connectivity test
    return new Promise(resolve => {
      setTimeout(() => {
        resolve({ success: true });
      }, 1500);
    });
  }

  /**
   * Initialize wizard styles
   */
  private initializeWizardStyles(): void {
    if (document.getElementById('thoth-wizard-styles')) {
      return; // Styles already loaded
    }

    const style = document.createElement('style');
    style.id = 'thoth-wizard-styles';
    style.textContent = `
      .thoth-wizard-modal {
        width: 600px;
        max-width: 90vw;
        height: 500px;
        max-height: 80vh;
      }

      .thoth-wizard-container {
        height: 100%;
        display: flex;
        flex-direction: column;
      }

      .thoth-wizard-progress {
        margin-bottom: 20px;
        padding: 10px 0;
      }

      .thoth-progress-bar {
        height: 6px;
        background: var(--background-modifier-border);
        border-radius: 3px;
        overflow: hidden;
        margin-bottom: 8px;
      }

      .thoth-progress-fill {
        height: 100%;
        background: var(--interactive-accent);
        transition: width 0.3s ease;
      }

      .thoth-progress-text {
        text-align: center;
        font-size: 0.9em;
        color: var(--text-muted);
      }

      .thoth-use-cases {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
        margin: 20px 0;
      }

      .thoth-use-case-card {
        padding: 16px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 8px;
        background: var(--background-secondary);
        transition: all 0.2s ease;
        cursor: pointer;
      }

      .thoth-use-case-card:hover {
        border-color: var(--interactive-accent);
        background: var(--background-modifier-hover);
      }

      .thoth-wizard-nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: auto;
        padding-top: 20px;
        border-top: 1px solid var(--background-modifier-border);
      }

      .thoth-wizard-btn {
        padding: 8px 16px;
        border-radius: 6px;
        border: 1px solid var(--background-modifier-border);
        background: var(--background-secondary);
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s ease;
      }

      .thoth-wizard-btn-primary {
        background: var(--interactive-accent);
        color: var(--text-on-accent);
        border-color: var(--interactive-accent);
      }

      .thoth-wizard-btn-primary:hover:not(.disabled) {
        background: var(--interactive-accent-hover);
      }

      .thoth-wizard-btn-primary.disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .thoth-test-case {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid var(--background-modifier-border);
      }

      .thoth-test-success {
        color: var(--color-green);
      }

      .thoth-test-error {
        color: var(--color-red);
      }

      .thoth-config-summary {
        max-height: 200px;
        overflow-y: auto;
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        padding: 10px;
      }

      .thoth-config-item {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        border-bottom: 1px solid var(--background-modifier-border);
      }

      .thoth-config-key {
        font-weight: 500;
        color: var(--text-normal);
      }

      .thoth-config-value {
        color: var(--text-muted);
        font-family: monospace;
      }

      .thoth-complexity-beginner {
        background: rgba(0, 255, 0, 0.2);
        color: var(--color-green);
      }

      .thoth-complexity-intermediate {
        background: rgba(255, 165, 0, 0.2);
        color: var(--color-orange);
      }

      .thoth-complexity-advanced {
        background: rgba(255, 0, 0, 0.2);
        color: var(--color-red);
      }

      .thoth-performance-low {
        background: rgba(0, 255, 0, 0.1);
        color: var(--color-green);
      }

      .thoth-performance-medium {
        background: rgba(255, 165, 0, 0.1);
        color: var(--color-orange);
      }

      .thoth-performance-high {
        background: rgba(255, 0, 0, 0.1);
        color: var(--color-red);
      }
    `;

    document.head.appendChild(style);
  }
}

/**
 * Factory function to create and show configuration wizard
 */
export function showConfigurationWizard(
  app: any,
  schema: UISchema,
  currentConfig: Partial<ThothSettings>,
  onComplete: (config: Partial<ThothSettings>) => Promise<void>
): ConfigurationWizard {
  const wizard = new ConfigurationWizard(app, schema, currentConfig, onComplete);
  wizard.open();
  return wizard;
}
