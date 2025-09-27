import { ThothSettings } from '../types';
import { Modal, App, Setting } from 'obsidian';

/**
 * Types of conflicts that can occur during synchronization
 */
export type ConflictType = 'FIELD_CONFLICT' | 'TYPE_CONFLICT' | 'VALIDATION_CONFLICT' | 'TIMESTAMP_CONFLICT';

/**
 * Resolution strategies for conflicts
 */
export type ResolutionStrategy = 'KEEP_LOCAL' | 'KEEP_REMOTE' | 'MERGE' | 'MANUAL' | 'TIMESTAMP_PRIORITY';

/**
 * Conflict information interface
 */
export interface Conflict {
  id: string;
  fieldPath: string;
  conflictType: ConflictType;
  localValue: any;
  remoteValue: any;
  localTimestamp?: number;
  remoteTimestamp?: number;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  description: string;
  suggestedResolution?: ResolutionStrategy;
  metadata?: Record<string, any>;
}

/**
 * Resolved conflict interface
 */
export interface ResolvedConflict {
  conflictId: string;
  strategy: ResolutionStrategy;
  resolvedValue: any;
  resolvedAt: number;
  resolvedBy: 'USER' | 'AUTOMATIC';
  rationale?: string;
}

/**
 * Conflict resolution result
 */
export interface ConflictResolution {
  conflicts: Conflict[];
  resolutions: ResolvedConflict[];
  resolvedCount: number;
  unresolvedCount: number;
  autoResolvedCount: number;
  manualResolvedCount: number;
}

/**
 * Resolution preferences for future automation
 */
export interface ResolutionPreferences {
  defaultStrategy: ResolutionStrategy;
  fieldSpecificStrategies: Map<string, ResolutionStrategy>;
  autoResolveThreshold: number;
  alwaysPromptForCritical: boolean;
  rememberChoices: boolean;
}

/**
 * Conflict resolver interface
 */
export interface IConflictResolver {
  detectConflicts(local: ThothSettings, remote: ThothSettings): Promise<Conflict[]>;
  resolveConflict(conflict: Conflict, strategy: ResolutionStrategy, customValue?: any): Promise<ResolvedConflict>;
  showConflictDialog(conflicts: Conflict[]): Promise<ConflictResolution>;
  mergeConfigurations(local: ThothSettings, remote: ThothSettings, resolutions: ResolvedConflict[]): Promise<ThothSettings>;
  saveResolutionPreferences(preferences: ResolutionPreferences): void;
  getResolutionPreferences(): ResolutionPreferences;
  canAutoResolve(conflict: Conflict): boolean;
  autoResolveConflicts(conflicts: Conflict[]): Promise<ResolvedConflict[]>;
}

/**
 * Implementation of conflict resolver with user interaction
 */
export class ConflictResolver implements IConflictResolver {
  private app: App;
  private preferences: ResolutionPreferences;
  private conflictHistory: Map<string, ResolvedConflict[]> = new Map();

  constructor(app: App) {
    this.app = app;
    this.preferences = this.loadDefaultPreferences();
  }

  async detectConflicts(local: ThothSettings, remote: ThothSettings): Promise<Conflict[]> {
    const conflicts: Conflict[] = [];
    const localKeys = new Set(Object.keys(local));
    const remoteKeys = new Set(Object.keys(remote));
    const allKeys = new Set([...localKeys, ...remoteKeys]);

    for (const key of allKeys) {
      const conflict = await this.detectFieldConflict(key, local, remote);
      if (conflict) {
        conflicts.push(conflict);
      }
    }

    // Sort conflicts by severity
    return conflicts.sort((a, b) => this.getSeverityWeight(b.severity) - this.getSeverityWeight(a.severity));
  }

  async resolveConflict(conflict: Conflict, strategy: ResolutionStrategy, customValue?: any): Promise<ResolvedConflict> {
    let resolvedValue: any;
    let rationale: string;

    switch (strategy) {
      case 'KEEP_LOCAL':
        resolvedValue = conflict.localValue;
        rationale = 'Kept local value to preserve user changes';
        break;

      case 'KEEP_REMOTE':
        resolvedValue = conflict.remoteValue;
        rationale = 'Accepted remote value as authoritative';
        break;

      case 'MERGE':
        resolvedValue = await this.performMerge(conflict);
        rationale = 'Merged local and remote values intelligently';
        break;

      case 'MANUAL':
        resolvedValue = customValue !== undefined ? customValue : conflict.localValue;
        rationale = 'User provided custom resolution';
        break;

      case 'TIMESTAMP_PRIORITY':
        resolvedValue = this.resolveByTimestamp(conflict);
        rationale = 'Resolved based on modification timestamp';
        break;

      default:
        resolvedValue = conflict.localValue;
        rationale = 'Fallback to local value';
    }

    const resolution: ResolvedConflict = {
      conflictId: conflict.id,
      strategy,
      resolvedValue,
      resolvedAt: Date.now(),
      resolvedBy: strategy === 'MANUAL' ? 'USER' : 'AUTOMATIC',
      rationale
    };

    // Store in history
    const history = this.conflictHistory.get(conflict.fieldPath) || [];
    history.push(resolution);
    this.conflictHistory.set(conflict.fieldPath, history);

    return resolution;
  }

  async showConflictDialog(conflicts: Conflict[]): Promise<ConflictResolution> {
    return new Promise((resolve) => {
      new ConflictResolutionModal(this.app, conflicts, resolve).open();
    });
  }

  async mergeConfigurations(
    local: ThothSettings,
    remote: ThothSettings,
    resolutions: ResolvedConflict[]
  ): Promise<ThothSettings> {
    const merged: ThothSettings = { ...local };

    for (const resolution of resolutions) {
      const fieldPath = this.getFieldPathFromConflictId(resolution.conflictId);
      if (fieldPath) {
        this.setNestedValue(merged, fieldPath, resolution.resolvedValue);
      }
    }

    return merged;
  }

  saveResolutionPreferences(preferences: ResolutionPreferences): void {
    this.preferences = { ...preferences };
    // In a real implementation, this would persist to storage
    localStorage.setItem('thoth-conflict-preferences', JSON.stringify(preferences));
  }

  getResolutionPreferences(): ResolutionPreferences {
    return { ...this.preferences };
  }

  canAutoResolve(conflict: Conflict): boolean {
    if (conflict.severity === 'CRITICAL' && this.preferences.alwaysPromptForCritical) {
      return false;
    }

    // Check field-specific preferences
    const fieldStrategy = this.preferences.fieldSpecificStrategies.get(conflict.fieldPath);
    if (fieldStrategy && fieldStrategy !== 'MANUAL') {
      return true;
    }

    // Check if conflict is low severity and below auto-resolve threshold
    return conflict.severity === 'LOW' && this.getSeverityWeight(conflict.severity) <= this.preferences.autoResolveThreshold;
  }

  async autoResolveConflicts(conflicts: Conflict[]): Promise<ResolvedConflict[]> {
    const resolutions: ResolvedConflict[] = [];

    for (const conflict of conflicts) {
      if (this.canAutoResolve(conflict)) {
        const strategy = this.preferences.fieldSpecificStrategies.get(conflict.fieldPath)
          || conflict.suggestedResolution
          || this.preferences.defaultStrategy;

        const resolution = await this.resolveConflict(conflict, strategy);
        resolutions.push(resolution);
      }
    }

    return resolutions;
  }

  // Private helper methods

  private async detectFieldConflict(key: string, local: ThothSettings, remote: ThothSettings): Promise<Conflict | null> {
    const localValue = local[key as keyof ThothSettings];
    const remoteValue = remote[key as keyof ThothSettings];

    // No conflict if values are identical
    if (JSON.stringify(localValue) === JSON.stringify(remoteValue)) {
      return null;
    }

    // Determine conflict type and severity
    let conflictType: ConflictType = 'FIELD_CONFLICT';
    let severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' = 'LOW';

    if (typeof localValue !== typeof remoteValue) {
      conflictType = 'TYPE_CONFLICT';
      severity = 'HIGH';
    } else if (this.isCriticalField(key)) {
      severity = 'CRITICAL';
    } else if (this.isImportantField(key)) {
      severity = 'MEDIUM';
    }

    return {
      id: crypto.randomUUID(),
      fieldPath: key,
      conflictType,
      localValue,
      remoteValue,
      severity,
      description: this.generateConflictDescription(key, localValue, remoteValue, conflictType),
      suggestedResolution: this.suggestResolution(key, localValue, remoteValue, conflictType)
    };
  }

  private async performMerge(conflict: Conflict): Promise<any> {
    const { localValue, remoteValue } = conflict;

    // Simple merge strategies based on value types
    if (Array.isArray(localValue) && Array.isArray(remoteValue)) {
      // Merge arrays by combining unique elements
      return [...new Set([...localValue, ...remoteValue])];
    }

    if (typeof localValue === 'object' && typeof remoteValue === 'object' && localValue && remoteValue) {
      // Merge objects by combining properties
      return { ...localValue, ...remoteValue };
    }

    if (typeof localValue === 'string' && typeof remoteValue === 'string') {
      // For strings, prefer the longer one (assuming more information)
      return localValue.length >= remoteValue.length ? localValue : remoteValue;
    }

    if (typeof localValue === 'number' && typeof remoteValue === 'number') {
      // For numbers, use the larger value
      return Math.max(localValue, remoteValue);
    }

    // Fallback to local value
    return localValue;
  }

  private resolveByTimestamp(conflict: Conflict): any {
    if (conflict.localTimestamp && conflict.remoteTimestamp) {
      return conflict.localTimestamp > conflict.remoteTimestamp ? conflict.localValue : conflict.remoteValue;
    }
    return conflict.localValue;
  }

  private generateConflictDescription(key: string, localValue: any, remoteValue: any, type: ConflictType): string {
    switch (type) {
      case 'TYPE_CONFLICT':
        return `Field '${key}' has different types: local (${typeof localValue}) vs remote (${typeof remoteValue})`;
      case 'FIELD_CONFLICT':
        return `Field '${key}' has different values: '${JSON.stringify(localValue)}' vs '${JSON.stringify(remoteValue)}'`;
      default:
        return `Conflict detected in field '${key}'`;
    }
  }

  private suggestResolution(key: string, localValue: any, remoteValue: any, type: ConflictType): ResolutionStrategy {
    if (this.isCriticalField(key)) {
      return 'MANUAL';
    }

    if (type === 'TYPE_CONFLICT') {
      return 'MANUAL';
    }

    if (this.isConfigurationField(key)) {
      return 'KEEP_LOCAL';
    }

    return 'MERGE';
  }

  private isCriticalField(key: string): boolean {
    const criticalFields = ['mistralKey', 'openrouterKey', 'workspaceDirectory', 'endpointHost', 'endpointPort'];
    return criticalFields.includes(key);
  }

  private isImportantField(key: string): boolean {
    const importantFields = ['primaryLlmModel', 'analysisLlmModel', 'obsidianDirectory', 'dataDirectory'];
    return importantFields.includes(key);
  }

  private isConfigurationField(key: string): boolean {
    const configFields = ['theme', 'compactMode', 'showAdvancedSettings', 'enableNotifications'];
    return configFields.includes(key);
  }

  private getSeverityWeight(severity: string): number {
    switch (severity) {
      case 'LOW': return 1;
      case 'MEDIUM': return 2;
      case 'HIGH': return 3;
      case 'CRITICAL': return 4;
      default: return 1;
    }
  }

  private loadDefaultPreferences(): ResolutionPreferences {
    try {
      const stored = localStorage.getItem('thoth-conflict-preferences');
      if (stored) {
        const parsed = JSON.parse(stored);
        return {
          ...parsed,
          fieldSpecificStrategies: new Map(Object.entries(parsed.fieldSpecificStrategies || {}))
        };
      }
    } catch (error) {
      console.warn('Failed to load conflict preferences:', error);
    }

    return {
      defaultStrategy: 'MERGE',
      fieldSpecificStrategies: new Map(),
      autoResolveThreshold: 2,
      alwaysPromptForCritical: true,
      rememberChoices: true
    };
  }

  private getFieldPathFromConflictId(conflictId: string): string | null {
    // In a real implementation, this would map conflict IDs to field paths
    // For now, we'll return a placeholder
    return null;
  }

  private setNestedValue(obj: any, path: string, value: any): void {
    const keys = path.split('.');
    let current = obj;

    for (let i = 0; i < keys.length - 1; i++) {
      if (!(keys[i] in current)) {
        current[keys[i]] = {};
      }
      current = current[keys[i]];
    }

    current[keys[keys.length - 1]] = value;
  }
}

/**
 * Modal for user conflict resolution
 */
class ConflictResolutionModal extends Modal {
  private conflicts: Conflict[];
  private resolveCallback: (resolution: ConflictResolution) => void;
  private resolutions: Map<string, ResolvedConflict> = new Map();

  constructor(app: App, conflicts: Conflict[], resolveCallback: (resolution: ConflictResolution) => void) {
    super(app);
    this.conflicts = conflicts;
    this.resolveCallback = resolveCallback;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();

    contentEl.createEl('h2', { text: 'Resolve Configuration Conflicts' });
    contentEl.createEl('p', {
      text: `Found ${this.conflicts.length} conflicts that require your attention.`
    });

    const conflictContainer = contentEl.createDiv('conflict-container');

    this.conflicts.forEach((conflict, index) => {
      this.createConflictSection(conflictContainer, conflict, index);
    });

    // Action buttons
    const buttonContainer = contentEl.createDiv('conflict-buttons');
    buttonContainer.style.marginTop = '20px';
    buttonContainer.style.textAlign = 'right';

    const autoResolveBtn = buttonContainer.createEl('button', { text: 'Auto Resolve Safe Conflicts' });
    autoResolveBtn.className = 'mod-cta';
    autoResolveBtn.style.marginRight = '10px';
    autoResolveBtn.onclick = () => this.autoResolveSafeConflicts();

    const applyBtn = buttonContainer.createEl('button', { text: 'Apply Resolutions' });
    applyBtn.className = 'mod-cta';
    applyBtn.onclick = () => this.applyResolutions();

    const cancelBtn = buttonContainer.createEl('button', { text: 'Cancel' });
    cancelBtn.onclick = () => this.close();
  }

  private createConflictSection(container: HTMLElement, conflict: Conflict, index: number) {
    const section = container.createDiv('conflict-section');
    section.style.border = '1px solid var(--background-modifier-border)';
    section.style.borderRadius = '8px';
    section.style.padding = '15px';
    section.style.marginBottom = '15px';

    // Header
    const header = section.createDiv('conflict-header');
    header.innerHTML = `
      <h3 style="margin: 0 0 10px 0; color: ${this.getSeverityColor(conflict.severity)}">
        ${conflict.severity} Conflict: ${conflict.fieldPath}
      </h3>
      <p style="margin: 0 0 10px 0; color: var(--text-muted);">${conflict.description}</p>
    `;

    // Values comparison
    const comparison = section.createDiv('conflict-comparison');
    comparison.style.display = 'grid';
    comparison.style.gridTemplateColumns = '1fr 1fr';
    comparison.style.gap = '15px';
    comparison.style.marginBottom = '15px';

    const localDiv = comparison.createDiv();
    localDiv.innerHTML = `
      <strong>Local Value:</strong>
      <div style="background: var(--background-secondary); padding: 10px; border-radius: 4px; margin-top: 5px;">
        ${this.formatValue(conflict.localValue)}
      </div>
    `;

    const remoteDiv = comparison.createDiv();
    remoteDiv.innerHTML = `
      <strong>Remote Value:</strong>
      <div style="background: var(--background-secondary); padding: 10px; border-radius: 4px; margin-top: 5px;">
        ${this.formatValue(conflict.remoteValue)}
      </div>
    `;

    // Resolution options
    const resolutionDiv = section.createDiv('conflict-resolution');

    new Setting(resolutionDiv)
      .setName('Resolution Strategy')
      .addDropdown(dropdown => {
        dropdown.addOption('KEEP_LOCAL', 'Keep Local');
        dropdown.addOption('KEEP_REMOTE', 'Keep Remote');
        dropdown.addOption('MERGE', 'Smart Merge');
        dropdown.addOption('MANUAL', 'Manual Entry');

        if (conflict.suggestedResolution) {
          dropdown.setValue(conflict.suggestedResolution);
        }

        dropdown.onChange(async (value) => {
          await this.handleResolutionChange(conflict, value as ResolutionStrategy);
        });
      });

    // Manual input (initially hidden)
    const manualInput = section.createDiv('manual-input');
    manualInput.style.display = 'none';

    new Setting(manualInput)
      .setName('Custom Value')
      .addText(text => {
        text.setPlaceholder('Enter custom value...');
        text.onChange((value) => {
          this.updateManualResolution(conflict, value);
        });
      });
  }

  private async handleResolutionChange(conflict: Conflict, strategy: ResolutionStrategy) {
    const section = this.contentEl.querySelector(`[data-conflict="${conflict.id}"]`);
    const manualInput = section?.querySelector('.manual-input') as HTMLElement;

    if (strategy === 'MANUAL') {
      if (manualInput) {
        manualInput.style.display = 'block';
      }
    } else {
      if (manualInput) {
        manualInput.style.display = 'none';
      }

      // Auto-resolve with selected strategy
      const resolver = new ConflictResolver(this.app);
      const resolution = await resolver.resolveConflict(conflict, strategy);
      this.resolutions.set(conflict.id, resolution);
    }
  }

  private updateManualResolution(conflict: Conflict, customValue: string) {
    try {
      const parsedValue = JSON.parse(customValue);
      const resolution: ResolvedConflict = {
        conflictId: conflict.id,
        strategy: 'MANUAL',
        resolvedValue: parsedValue,
        resolvedAt: Date.now(),
        resolvedBy: 'USER',
        rationale: 'User provided custom value'
      };
      this.resolutions.set(conflict.id, resolution);
    } catch (error) {
      // If not valid JSON, treat as string
      const resolution: ResolvedConflict = {
        conflictId: conflict.id,
        strategy: 'MANUAL',
        resolvedValue: customValue,
        resolvedAt: Date.now(),
        resolvedBy: 'USER',
        rationale: 'User provided custom value'
      };
      this.resolutions.set(conflict.id, resolution);
    }
  }

  private async autoResolveSafeConflicts() {
    const resolver = new ConflictResolver(this.app);
    const autoResolved = await resolver.autoResolveConflicts(this.conflicts);

    for (const resolution of autoResolved) {
      this.resolutions.set(resolution.conflictId, resolution);
    }

    // Update UI to show auto-resolved conflicts
    this.onOpen(); // Refresh the modal
  }

  private applyResolutions() {
    const result: ConflictResolution = {
      conflicts: this.conflicts,
      resolutions: Array.from(this.resolutions.values()),
      resolvedCount: this.resolutions.size,
      unresolvedCount: this.conflicts.length - this.resolutions.size,
      autoResolvedCount: Array.from(this.resolutions.values()).filter(r => r.resolvedBy === 'AUTOMATIC').length,
      manualResolvedCount: Array.from(this.resolutions.values()).filter(r => r.resolvedBy === 'USER').length
    };

    this.resolveCallback(result);
    this.close();
  }

  private getSeverityColor(severity: string): string {
    switch (severity) {
      case 'LOW': return 'var(--text-success)';
      case 'MEDIUM': return 'var(--text-warning)';
      case 'HIGH': return 'var(--text-error)';
      case 'CRITICAL': return 'var(--text-error)';
      default: return 'var(--text-normal)';
    }
  }

  private formatValue(value: any): string {
    if (value === null) return 'null';
    if (value === undefined) return 'undefined';
    if (typeof value === 'string') return `"${value}"`;
    return JSON.stringify(value, null, 2);
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}
