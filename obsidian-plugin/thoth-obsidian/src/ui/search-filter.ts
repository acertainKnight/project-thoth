import { ThothSettings } from '../types';
import { UISchema, FieldSchema } from '../services/schema-service';

/**
 * Search result interface
 */
export interface SearchResult {
  fieldName: string;
  fieldSchema: FieldSchema;
  currentValue: any;
  score: number;
  matches: SearchMatch[];
  group?: string;
}

/**
 * Search match interface for highlighting
 */
export interface SearchMatch {
  type: 'field' | 'description' | 'value';
  start: number;
  end: number;
  text: string;
}

/**
 * Search filter interface
 */
export interface JSONSearchFilter {
  query?: string;
  types?: FieldType[];
  groups?: string[];
  statuses?: ValidationStatus[];
  showModifiedOnly?: boolean;
  showOverridesOnly?: boolean;
}

/**
 * Field types for filtering
 */
export type FieldType = 'text' | 'password' | 'number' | 'boolean' | 'select' | 'toggle' | 'directory' | 'file';

/**
 * Validation status types
 */
export type ValidationStatus = 'valid' | 'invalid' | 'warning' | 'unknown';

/**
 * Fuzzy search configuration
 */
interface FuzzySearchConfig {
  threshold: number;
  maxDistance: number;
  caseSensitive: boolean;
  includeMatches: boolean;
}

/**
 * Search and filter system with fuzzy matching
 */
export class SearchFilter {
  private schema?: UISchema;
  private currentData?: ThothSettings;
  private originalData?: ThothSettings;
  private validationState?: Map<string, ValidationStatus>;
  private environmentOverrides?: Set<string>;
  private lastSearchQuery = '';
  private searchCache = new Map<string, SearchResult[]>();
  private fuzzyConfig: FuzzySearchConfig = {
    threshold: 0.6,
    maxDistance: 10,
    caseSensitive: false,
    includeMatches: true
  };

  constructor() {
    // Initialize with default configuration
  }

  /**
   * Set schema for search context
   */
  setSchema(schema: UISchema): void {
    this.schema = schema;
    this.clearCache();
  }

  /**
   * Set current data for search
   */
  setCurrentData(data: ThothSettings): void {
    this.currentData = data;
    this.clearCache();
  }

  /**
   * Set original data for comparison
   */
  setOriginalData(data: ThothSettings): void {
    this.originalData = data;
  }

  /**
   * Set validation state for filtering
   */
  setValidationState(validationState: Map<string, ValidationStatus>): void {
    this.validationState = validationState;
  }

  /**
   * Set environment overrides for filtering
   */
  setEnvironmentOverrides(overrides: Set<string>): void {
    this.environmentOverrides = overrides;
  }

  /**
   * Search across all settings with fuzzy matching
   */
  search(query: string): SearchResult[] {
    if (!this.schema || !this.currentData) {
      return [];
    }

    // Use cache if query hasn't changed
    const cacheKey = this.getCacheKey(query);
    if (this.searchCache.has(cacheKey)) {
      return this.searchCache.get(cacheKey)!;
    }

    const results: SearchResult[] = [];

    // Search through all fields
    for (const [fieldName, fieldSchema] of Object.entries(this.schema.fields)) {
      const score = this.calculateFieldScore(query, fieldName, fieldSchema);

      if (score > 0) {
        const matches = this.findMatches(query, fieldName, fieldSchema);
        const currentValue = this.currentData[fieldName as keyof ThothSettings];

        results.push({
          fieldName,
          fieldSchema,
          currentValue,
          score,
          matches,
          group: fieldSchema.group
        });
      }
    }

    // Sort by score (highest first)
    results.sort((a, b) => b.score - a.score);

    // Cache results
    this.searchCache.set(cacheKey, results);
    this.lastSearchQuery = query;

    return results;
  }

  /**
   * Filter results by type
   */
  filterByType(results: SearchResult[], types: FieldType[]): SearchResult[] {
    if (types.length === 0) return results;

    return results.filter(result =>
      types.includes(result.fieldSchema.type as FieldType)
    );
  }

  /**
   * Filter results by group
   */
  filterByGroup(results: SearchResult[], groups: string[]): SearchResult[] {
    if (groups.length === 0) return results;

    return results.filter(result =>
      result.group && groups.includes(result.group)
    );
  }

  /**
   * Filter by validation status
   */
  filterByStatus(results: SearchResult[], statuses: ValidationStatus[]): SearchResult[] {
    if (statuses.length === 0 || !this.validationState) return results;

    return results.filter(result => {
      const status = this.validationState!.get(result.fieldName) || 'unknown';
      return statuses.includes(status);
    });
  }

  /**
   * Filter to show only modified fields
   */
  filterModifiedOnly(results: SearchResult[]): SearchResult[] {
    if (!this.originalData) return results;

    return results.filter(result => {
      const currentValue = this.currentData?.[result.fieldName as keyof ThothSettings];
      const originalValue = this.originalData?.[result.fieldName as keyof ThothSettings];
      return JSON.stringify(currentValue) !== JSON.stringify(originalValue);
    });
  }

  /**
   * Filter to show only environment overrides
   */
  filterOverridesOnly(results: SearchResult[]): SearchResult[] {
    if (!this.environmentOverrides) return results;

    return results.filter(result =>
      this.environmentOverrides!.has(result.fieldName)
    );
  }

  /**
   * Apply comprehensive filter
   */
  applyFilter(results: SearchResult[], filter: JSONSearchFilter): SearchResult[] {
    let filtered = results;

    if (filter.types && filter.types.length > 0) {
      filtered = this.filterByType(filtered, filter.types);
    }

    if (filter.groups && filter.groups.length > 0) {
      filtered = this.filterByGroup(filtered, filter.groups);
    }

    if (filter.statuses && filter.statuses.length > 0) {
      filtered = this.filterByStatus(filtered, filter.statuses);
    }

    if (filter.showModifiedOnly) {
      filtered = this.filterModifiedOnly(filtered);
    }

    if (filter.showOverridesOnly) {
      filtered = this.filterOverridesOnly(filtered);
    }

    return filtered;
  }

  /**
   * Highlight search terms in text
   */
  highlightMatches(text: string, matches: SearchMatch[]): string {
    if (matches.length === 0) return text;

    // Sort matches by start position (descending) to avoid index shifting
    const sortedMatches = [...matches].sort((a, b) => b.start - a.start);

    let highlightedText = text;

    for (const match of sortedMatches) {
      const before = highlightedText.substring(0, match.start);
      const matchText = highlightedText.substring(match.start, match.end);
      const after = highlightedText.substring(match.end);

      highlightedText = before + `<mark class="thoth-search-highlight">${matchText}</mark>` + after;
    }

    return highlightedText;
  }

  /**
   * Get available field types for filtering
   */
  getAvailableTypes(): FieldType[] {
    if (!this.schema) return [];

    const types = new Set<FieldType>();

    for (const fieldSchema of Object.values(this.schema.fields)) {
      types.add(fieldSchema.type as FieldType);
    }

    return Array.from(types).sort();
  }

  /**
   * Get available groups for filtering
   */
  getAvailableGroups(): string[] {
    if (!this.schema) return [];

    const groups = new Set<string>();

    for (const fieldSchema of Object.values(this.schema.fields)) {
      if (fieldSchema.group) {
        groups.add(fieldSchema.group);
      }
    }

    return Array.from(groups).sort();
  }

  /**
   * Clear search filters
   */
  clearFilters(): void {
    this.clearCache();
  }

  /**
   * Calculate fuzzy search score for a field
   */
  private calculateFieldScore(query: string, fieldName: string, fieldSchema: FieldSchema): number {
    if (!query.trim()) return 0;

    const queryLower = query.toLowerCase();
    const fieldNameLower = fieldName.toLowerCase();
    const description = fieldSchema.description || '';
    const descriptionLower = description.toLowerCase();

    let score = 0;

    // Exact field name match (highest priority)
    if (fieldNameLower === queryLower) {
      score += 100;
    }
    // Field name starts with query
    else if (fieldNameLower.startsWith(queryLower)) {
      score += 80;
    }
    // Field name contains query
    else if (fieldNameLower.includes(queryLower)) {
      score += 60;
    }
    // Fuzzy match on field name
    else {
      const fuzzyScore = this.fuzzyMatch(queryLower, fieldNameLower);
      if (fuzzyScore > this.fuzzyConfig.threshold) {
        score += fuzzyScore * 40;
      }
    }

    // Description matches
    if (description) {
      if (descriptionLower.includes(queryLower)) {
        score += 30;
      } else {
        const fuzzyScore = this.fuzzyMatch(queryLower, descriptionLower);
        if (fuzzyScore > this.fuzzyConfig.threshold) {
          score += fuzzyScore * 20;
        }
      }
    }

    // Value matches (for current data)
    if (this.currentData) {
      const currentValue = this.currentData[fieldName as keyof ThothSettings];
      if (currentValue !== undefined && currentValue !== null) {
        const valueStr = String(currentValue).toLowerCase();
        if (valueStr.includes(queryLower)) {
          score += 20;
        }
      }
    }

    return score;
  }

  /**
   * Find specific matches for highlighting
   */
  private findMatches(query: string, fieldName: string, fieldSchema: FieldSchema): SearchMatch[] {
    const matches: SearchMatch[] = [];
    const queryLower = query.toLowerCase();

    // Field name matches
    const fieldNameLower = fieldName.toLowerCase();
    let index = fieldNameLower.indexOf(queryLower);
    while (index !== -1) {
      matches.push({
        type: 'field',
        start: index,
        end: index + query.length,
        text: fieldName.substring(index, index + query.length)
      });
      index = fieldNameLower.indexOf(queryLower, index + 1);
    }

    // Description matches
    if (fieldSchema.description) {
      const descriptionLower = fieldSchema.description.toLowerCase();
      let descIndex = descriptionLower.indexOf(queryLower);
      while (descIndex !== -1) {
        matches.push({
          type: 'description',
          start: descIndex,
          end: descIndex + query.length,
          text: fieldSchema.description.substring(descIndex, descIndex + query.length)
        });
        descIndex = descriptionLower.indexOf(queryLower, descIndex + 1);
      }
    }

    // Value matches
    if (this.currentData) {
      const currentValue = this.currentData[fieldName as keyof ThothSettings];
      if (currentValue !== undefined && currentValue !== null) {
        const valueStr = String(currentValue);
        const valueStrLower = valueStr.toLowerCase();
        let valueIndex = valueStrLower.indexOf(queryLower);
        while (valueIndex !== -1) {
          matches.push({
            type: 'value',
            start: valueIndex,
            end: valueIndex + query.length,
            text: valueStr.substring(valueIndex, valueIndex + query.length)
          });
          valueIndex = valueStrLower.indexOf(queryLower, valueIndex + 1);
        }
      }
    }

    return matches;
  }

  /**
   * Fuzzy matching algorithm with typo tolerance
   */
  private fuzzyMatch(query: string, target: string): number {
    if (query === target) return 1;
    if (query.length === 0) return 0;

    const distance = this.levenshteinDistance(query, target);
    const maxLength = Math.max(query.length, target.length);

    if (distance > this.fuzzyConfig.maxDistance) return 0;

    return 1 - (distance / maxLength);
  }

  /**
   * Calculate Levenshtein distance for fuzzy matching
   */
  private levenshteinDistance(str1: string, str2: string): number {
    const matrix = Array(str2.length + 1).fill(null).map(() => Array(str1.length + 1).fill(null));

    for (let i = 0; i <= str1.length; i++) {
      matrix[0][i] = i;
    }

    for (let j = 0; j <= str2.length; j++) {
      matrix[j][0] = j;
    }

    for (let j = 1; j <= str2.length; j++) {
      for (let i = 1; i <= str1.length; i++) {
        const indicator = str1[i - 1] === str2[j - 1] ? 0 : 1;
        matrix[j][i] = Math.min(
          matrix[j][i - 1] + 1, // deletion
          matrix[j - 1][i] + 1, // insertion
          matrix[j - 1][i - 1] + indicator // substitution
        );
      }
    }

    return matrix[str2.length][str1.length];
  }

  /**
   * Generate cache key for search results
   */
  private getCacheKey(query: string): string {
    return `${query}:${this.schema ? Object.keys(this.schema.fields).length : 0}`;
  }

  /**
   * Clear search cache
   */
  private clearCache(): void {
    this.searchCache.clear();
  }
}

/**
 * Search UI component for rendering search interface
 */
export class SearchUI {
  private container?: HTMLElement;
  private searchFilter: SearchFilter;
  private currentResults: SearchResult[] = [];
  private currentFilter: JSONSearchFilter = {};
  private onResultSelect?: (result: SearchResult) => void;
  private selectedIndex = -1;

  constructor(searchFilter: SearchFilter) {
    this.searchFilter = searchFilter;
  }

  /**
   * Render search interface
   */
  render(container: HTMLElement): void {
    this.container = container;
    container.className = 'thoth-search-container';

    this.createSearchInput();
    this.createFilterControls();
    this.createResultsList();
    this.initializeStyles();
  }

  /**
   * Set result selection callback
   */
  onResultSelected(callback: (result: SearchResult) => void): void {
    this.onResultSelect = callback;
  }

  /**
   * Focus search input
   */
  focus(): void {
    const searchInput = this.container?.querySelector('.thoth-search-input') as HTMLInputElement;
    if (searchInput) {
      searchInput.focus();
    }
  }

  /**
   * Clear search and filters
   */
  clear(): void {
    const searchInput = this.container?.querySelector('.thoth-search-input') as HTMLInputElement;
    if (searchInput) {
      searchInput.value = '';
    }

    this.currentFilter = {};
    this.currentResults = [];
    this.selectedIndex = -1;
    this.updateResults();
  }

  /**
   * Create search input
   */
  private createSearchInput(): void {
    if (!this.container) return;

    const searchSection = this.container.createEl('div', { cls: 'thoth-search-section' });

    const searchWrapper = searchSection.createEl('div', { cls: 'thoth-search-wrapper' });

    const searchIcon = searchWrapper.createEl('span', { cls: 'thoth-search-icon' });
    searchIcon.innerHTML = '🔍';

    const searchInput = searchWrapper.createEl('input', {
      cls: 'thoth-search-input',
      attr: {
        type: 'text',
        placeholder: 'Search settings...',
        autocomplete: 'off'
      }
    });

    const clearBtn = searchWrapper.createEl('button', { cls: 'thoth-search-clear' });
    clearBtn.innerHTML = '×';
    clearBtn.style.display = 'none';

    // Search input events
    searchInput.addEventListener('input', (e) => {
      const query = (e.target as HTMLInputElement).value;
      clearBtn.style.display = query ? 'block' : 'none';
      this.performSearch(query);
    });

    searchInput.addEventListener('keydown', (e) => {
      this.handleKeyNavigation(e);
    });

    // Clear button event
    clearBtn.addEventListener('click', () => {
      searchInput.value = '';
      clearBtn.style.display = 'none';
      this.performSearch('');
    });
  }

  /**
   * Create filter controls
   */
  private createFilterControls(): void {
    if (!this.container) return;

    const filterSection = this.container.createEl('div', { cls: 'thoth-filter-section' });

    // Type filter
    this.createTypeFilter(filterSection);

    // Group filter
    this.createGroupFilter(filterSection);

    // Status filter
    this.createStatusFilter(filterSection);

    // Toggle filters
    this.createToggleFilters(filterSection);
  }

  /**
   * Create type filter dropdown
   */
  private createTypeFilter(parent: HTMLElement): void {
    const typeWrapper = parent.createEl('div', { cls: 'thoth-filter-wrapper' });

    const typeLabel = typeWrapper.createEl('label', { text: 'Type:', cls: 'thoth-filter-label' });

    const typeSelect = typeWrapper.createEl('select', { cls: 'thoth-filter-select' });
    typeSelect.createEl('option', { value: '', text: 'All Types' });

    const availableTypes = this.searchFilter.getAvailableTypes();
    for (const type of availableTypes) {
      typeSelect.createEl('option', { value: type, text: this.formatTypeName(type) });
    }

    typeSelect.addEventListener('change', () => {
      const selectedTypes = typeSelect.value ? [typeSelect.value as FieldType] : [];
      this.currentFilter.types = selectedTypes;
      this.applyFilters();
    });
  }

  /**
   * Create group filter dropdown
   */
  private createGroupFilter(parent: HTMLElement): void {
    const groupWrapper = parent.createEl('div', { cls: 'thoth-filter-wrapper' });

    const groupLabel = groupWrapper.createEl('label', { text: 'Group:', cls: 'thoth-filter-label' });

    const groupSelect = groupWrapper.createEl('select', { cls: 'thoth-filter-select' });
    groupSelect.createEl('option', { value: '', text: 'All Groups' });

    const availableGroups = this.searchFilter.getAvailableGroups();
    for (const group of availableGroups) {
      groupSelect.createEl('option', { value: group, text: this.formatGroupName(group) });
    }

    groupSelect.addEventListener('change', () => {
      const selectedGroups = groupSelect.value ? [groupSelect.value] : [];
      this.currentFilter.groups = selectedGroups;
      this.applyFilters();
    });
  }

  /**
   * Create status filter dropdown
   */
  private createStatusFilter(parent: HTMLElement): void {
    const statusWrapper = parent.createEl('div', { cls: 'thoth-filter-wrapper' });

    const statusLabel = statusWrapper.createEl('label', { text: 'Status:', cls: 'thoth-filter-label' });

    const statusSelect = statusWrapper.createEl('select', { cls: 'thoth-filter-select' });
    statusSelect.createEl('option', { value: '', text: 'All Status' });
    statusSelect.createEl('option', { value: 'valid', text: 'Valid' });
    statusSelect.createEl('option', { value: 'invalid', text: 'Invalid' });
    statusSelect.createEl('option', { value: 'warning', text: 'Warning' });
    statusSelect.createEl('option', { value: 'unknown', text: 'Unknown' });

    statusSelect.addEventListener('change', () => {
      const selectedStatuses = statusSelect.value ? [statusSelect.value as ValidationStatus] : [];
      this.currentFilter.statuses = selectedStatuses;
      this.applyFilters();
    });
  }

  /**
   * Create toggle filters for modified/overrides
   */
  private createToggleFilters(parent: HTMLElement): void {
    const toggleWrapper = parent.createEl('div', { cls: 'thoth-filter-toggles' });

    // Modified only toggle
    const modifiedLabel = toggleWrapper.createEl('label', { cls: 'thoth-filter-toggle' });
    const modifiedCheckbox = modifiedLabel.createEl('input', {
      type: 'checkbox',
      cls: 'thoth-filter-checkbox'
    });
    modifiedLabel.createEl('span', { text: 'Modified Only' });

    modifiedCheckbox.addEventListener('change', () => {
      this.currentFilter.showModifiedOnly = modifiedCheckbox.checked;
      this.applyFilters();
    });

    // Overrides only toggle
    const overridesLabel = toggleWrapper.createEl('label', { cls: 'thoth-filter-toggle' });
    const overridesCheckbox = overridesLabel.createEl('input', {
      type: 'checkbox',
      cls: 'thoth-filter-checkbox'
    });
    overridesLabel.createEl('span', { text: 'Overrides Only' });

    overridesCheckbox.addEventListener('change', () => {
      this.currentFilter.showOverridesOnly = overridesCheckbox.checked;
      this.applyFilters();
    });
  }

  /**
   * Create results list container
   */
  private createResultsList(): void {
    if (!this.container) return;

    const resultsSection = this.container.createEl('div', { cls: 'thoth-results-section' });

    const resultsHeader = resultsSection.createEl('div', { cls: 'thoth-results-header' });
    resultsHeader.createEl('span', { text: 'Search Results', cls: 'thoth-results-title' });

    const resultsCount = resultsHeader.createEl('span', { cls: 'thoth-results-count' });
    resultsCount.textContent = '0 results';

    const resultsList = resultsSection.createEl('div', { cls: 'thoth-results-list' });
    resultsList.innerHTML = '<div class="thoth-results-empty">Type to search settings...</div>';
  }

  /**
   * Perform search with current query
   */
  private performSearch(query: string): void {
    const results = this.searchFilter.search(query);
    this.currentResults = this.searchFilter.applyFilter(results, this.currentFilter);
    this.selectedIndex = -1;
    this.updateResults();
  }

  /**
   * Apply current filters to results
   */
  private applyFilters(): void {
    const searchInput = this.container?.querySelector('.thoth-search-input') as HTMLInputElement;
    const query = searchInput?.value || '';

    if (query) {
      this.performSearch(query);
    }
  }

  /**
   * Update results display
   */
  private updateResults(): void {
    if (!this.container) return;

    const resultsCount = this.container.querySelector('.thoth-results-count');
    const resultsList = this.container.querySelector('.thoth-results-list');

    if (!resultsCount || !resultsList) return;

    // Update count
    resultsCount.textContent = `${this.currentResults.length} result${this.currentResults.length !== 1 ? 's' : ''}`;

    // Clear previous results
    resultsList.innerHTML = '';

    if (this.currentResults.length === 0) {
      const emptyMsg = resultsList.createEl('div', { cls: 'thoth-results-empty' });
      emptyMsg.textContent = 'No matching settings found';
      return;
    }

    // Render results
    this.currentResults.forEach((result, index) => {
      const resultItem = this.createResultItem(result, index);
      resultsList.appendChild(resultItem);
    });
  }

  /**
   * Create individual result item
   */
  private createResultItem(result: SearchResult, index: number): HTMLElement {
    const item = document.createElement('div');
    item.className = 'thoth-result-item';
    if (index === this.selectedIndex) {
      item.classList.add('selected');
    }

    // Field name with highlighting
    const fieldName = item.createEl('div', { cls: 'thoth-result-field' });
    const fieldMatches = result.matches.filter(m => m.type === 'field');
    fieldName.innerHTML = this.searchFilter.highlightMatches(result.fieldName, fieldMatches);

    // Field description
    if (result.fieldSchema.description) {
      const description = item.createEl('div', { cls: 'thoth-result-description' });
      const descMatches = result.matches.filter(m => m.type === 'description');
      description.innerHTML = this.searchFilter.highlightMatches(result.fieldSchema.description, descMatches);
    }

    // Current value
    if (result.currentValue !== undefined && result.currentValue !== null) {
      const value = item.createEl('div', { cls: 'thoth-result-value' });
      const valueStr = String(result.currentValue);
      const valueMatches = result.matches.filter(m => m.type === 'value');
      value.innerHTML = `Current: ${this.searchFilter.highlightMatches(valueStr, valueMatches)}`;
    }

    // Metadata
    const metadata = item.createEl('div', { cls: 'thoth-result-metadata' });
    metadata.createEl('span', { text: this.formatTypeName(result.fieldSchema.type as FieldType), cls: 'thoth-result-type' });

    if (result.group) {
      metadata.createEl('span', { text: this.formatGroupName(result.group), cls: 'thoth-result-group' });
    }

    // Score (for debugging)
    if (process.env.NODE_ENV === 'development') {
      metadata.createEl('span', { text: `Score: ${result.score.toFixed(1)}`, cls: 'thoth-result-score' });
    }

    // Click handler
    item.addEventListener('click', () => {
      this.selectResult(index);
    });

    return item;
  }

  /**
   * Handle keyboard navigation
   */
  private handleKeyNavigation(e: KeyboardEvent): void {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.selectedIndex = Math.min(this.selectedIndex + 1, this.currentResults.length - 1);
        this.updateSelection();
        break;

      case 'ArrowUp':
        e.preventDefault();
        this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
        this.updateSelection();
        break;

      case 'Enter':
        e.preventDefault();
        if (this.selectedIndex >= 0 && this.selectedIndex < this.currentResults.length) {
          this.selectResult(this.selectedIndex);
        }
        break;

      case 'Escape':
        e.preventDefault();
        this.clear();
        break;
    }
  }

  /**
   * Update visual selection
   */
  private updateSelection(): void {
    if (!this.container) return;

    const resultItems = this.container.querySelectorAll('.thoth-result-item');

    resultItems.forEach((item, index) => {
      if (index === this.selectedIndex) {
        item.classList.add('selected');
        item.scrollIntoView({ block: 'nearest' });
      } else {
        item.classList.remove('selected');
      }
    });
  }

  /**
   * Select a result and trigger callback
   */
  private selectResult(index: number): void {
    if (index >= 0 && index < this.currentResults.length) {
      this.selectedIndex = index;
      this.updateSelection();

      if (this.onResultSelect) {
        this.onResultSelect(this.currentResults[index]);
      }
    }
  }

  /**
   * Format type name for display
   */
  private formatTypeName(type: FieldType): string {
    const typeNames: Record<FieldType, string> = {
      text: 'Text',
      password: 'Password',
      number: 'Number',
      boolean: 'Boolean',
      select: 'Select',
      toggle: 'Toggle',
      directory: 'Directory',
      file: 'File'
    };

    return typeNames[type] || type;
  }

  /**
   * Format group name for display
   */
  private formatGroupName(group: string): string {
    return group.split('_').map(word =>
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  }

  /**
   * Initialize search UI styles
   */
  private initializeStyles(): void {
    if (document.getElementById('thoth-search-styles')) {
      return; // Styles already loaded
    }

    const style = document.createElement('style');
    style.id = 'thoth-search-styles';
    style.textContent = `
      /* Search container */
      .thoth-search-container {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--background-primary);
      }

      /* Search section */
      .thoth-search-section {
        padding: 12px;
        border-bottom: 1px solid var(--background-modifier-border);
        flex-shrink: 0;
      }

      .thoth-search-wrapper {
        position: relative;
        display: flex;
        align-items: center;
      }

      .thoth-search-icon {
        position: absolute;
        left: 8px;
        color: var(--text-muted);
        font-size: 14px;
        z-index: 1;
      }

      .thoth-search-input {
        width: 100%;
        padding: 8px 32px 8px 28px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        background: var(--background-primary);
        color: var(--text-normal);
        font-size: 13px;
      }

      .thoth-search-input:focus {
        outline: none;
        border-color: var(--interactive-accent);
        box-shadow: 0 0 0 2px rgba(var(--interactive-accent-rgb), 0.2);
      }

      .thoth-search-clear {
        position: absolute;
        right: 6px;
        background: none;
        border: none;
        color: var(--text-muted);
        cursor: pointer;
        font-size: 16px;
        padding: 2px;
        border-radius: 2px;
      }

      .thoth-search-clear:hover {
        background: var(--background-modifier-hover);
        color: var(--text-normal);
      }

      /* Filter section */
      .thoth-filter-section {
        padding: 8px 12px;
        background: var(--background-secondary);
        border-bottom: 1px solid var(--background-modifier-border);
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        align-items: center;
        flex-shrink: 0;
      }

      .thoth-filter-wrapper {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .thoth-filter-label {
        font-size: 11px;
        color: var(--text-muted);
        font-weight: 500;
      }

      .thoth-filter-select {
        padding: 2px 6px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 3px;
        background: var(--background-primary);
        color: var(--text-normal);
        font-size: 11px;
        min-width: 80px;
      }

      .thoth-filter-toggles {
        display: flex;
        gap: 12px;
      }

      .thoth-filter-toggle {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 11px;
        color: var(--text-normal);
        cursor: pointer;
        user-select: none;
      }

      .thoth-filter-checkbox {
        margin: 0;
      }

      /* Results section */
      .thoth-results-section {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .thoth-results-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        border-bottom: 1px solid var(--background-modifier-border);
        background: var(--background-secondary);
        flex-shrink: 0;
      }

      .thoth-results-title {
        font-size: 12px;
        font-weight: 500;
        color: var(--text-normal);
      }

      .thoth-results-count {
        font-size: 11px;
        color: var(--text-muted);
      }

      .thoth-results-list {
        flex: 1;
        overflow-y: auto;
        padding: 4px;
      }

      .thoth-results-empty {
        text-align: center;
        color: var(--text-muted);
        font-style: italic;
        padding: 40px 20px;
      }

      /* Result items */
      .thoth-result-item {
        padding: 8px 12px;
        border-radius: 4px;
        margin-bottom: 2px;
        cursor: pointer;
        transition: all 0.1s ease;
        border: 1px solid transparent;
      }

      .thoth-result-item:hover {
        background: var(--background-modifier-hover);
      }

      .thoth-result-item.selected {
        background: var(--background-modifier-active-hover);
        border-color: var(--interactive-accent);
      }

      .thoth-result-field {
        font-weight: 500;
        font-size: 13px;
        color: var(--text-normal);
        margin-bottom: 2px;
      }

      .thoth-result-description {
        font-size: 11px;
        color: var(--text-muted);
        margin-bottom: 4px;
        line-height: 1.3;
      }

      .thoth-result-value {
        font-size: 11px;
        color: var(--text-accent);
        margin-bottom: 4px;
        font-family: monospace;
      }

      .thoth-result-metadata {
        display: flex;
        gap: 8px;
        font-size: 10px;
      }

      .thoth-result-type {
        background: var(--interactive-accent);
        color: white;
        padding: 1px 4px;
        border-radius: 2px;
        font-weight: 500;
      }

      .thoth-result-group {
        background: var(--background-modifier-border);
        color: var(--text-muted);
        padding: 1px 4px;
        border-radius: 2px;
      }

      .thoth-result-score {
        color: var(--text-muted);
        font-family: monospace;
      }

      /* Search highlighting */
      .thoth-search-highlight {
        background: var(--text-highlight-bg);
        color: var(--text-normal);
        padding: 1px 2px;
        border-radius: 2px;
        font-weight: 500;
      }

      /* Responsive design */
      @media (max-width: 600px) {
        .thoth-filter-section {
          flex-direction: column;
          align-items: stretch;
          gap: 8px;
        }

        .thoth-filter-wrapper {
          justify-content: space-between;
        }

        .thoth-filter-toggles {
          justify-content: space-around;
        }

        .thoth-result-metadata {
          flex-direction: column;
          gap: 2px;
        }
      }

      /* Focus styles for accessibility */
      .thoth-filter-select:focus,
      .thoth-filter-checkbox:focus {
        outline: 2px solid var(--interactive-accent);
        outline-offset: 1px;
      }

      .thoth-result-item:focus {
        outline: 2px solid var(--interactive-accent);
        outline-offset: -2px;
      }

      /* Dark theme adjustments */
      .theme-dark .thoth-search-highlight {
        background: rgba(255, 255, 0, 0.3);
      }

      /* Animation for results */
      .thoth-result-item {
        animation: fadeInResult 0.2s ease;
      }

      @keyframes fadeInResult {
        from {
          opacity: 0;
          transform: translateY(4px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }
    `;

    document.head.appendChild(style);
  }

  /**
   * Destroy search UI and clean up
   */
  destroy(): void {
    this.container = undefined;
    this.currentResults = [];
    this.selectedIndex = -1;
    this.onResultSelect = undefined;
  }
}

/**
 * Search filter factory for creating configured instances
 */
export class SearchFilterFactory {
  /**
   * Create search filter with default configuration
   */
  static create(): SearchFilter {
    return new SearchFilter();
  }

  /**
   * Create search UI with filter
   */
  static createWithUI(): { filter: SearchFilter; ui: SearchUI } {
    const filter = new SearchFilter();
    const ui = new SearchUI(filter);

    return { filter, ui };
  }

  /**
   * Create search filter with custom fuzzy matching configuration
   */
  static createWithFuzzyConfig(config: Partial<FuzzySearchConfig>): SearchFilter {
    const filter = new SearchFilter();
    (filter as any).fuzzyConfig = { ...(filter as any).fuzzyConfig, ...config };
    return filter;
  }
}
