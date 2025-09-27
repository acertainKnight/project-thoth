import { ThothSettings } from '../types';
import { UISchema, GroupSchema, FieldSchema } from '../services/schema-service';

/**
 * Structured JSON node types
 */
export type JSONNodeType = 'object' | 'array' | 'string' | 'number' | 'boolean' | 'null';

/**
 * Structured JSON node interface
 */
export interface JSONNode {
  key: string;
  value: any;
  type: JSONNodeType;
  parent?: JSONNode;
  children?: JSONNode[];
  path: string[];
  isExpanded?: boolean;
  isEditable?: boolean;
  schema?: FieldSchema;
  group?: string;
}

/**
 * Structured JSON view configuration
 */
export interface StructuredJSONConfig {
  showSearch?: boolean;
  showGroupHeaders?: boolean;
  allowInlineEditing?: boolean;
  collapsibleGroups?: boolean;
  maxValueLength?: number;
  showTypes?: boolean;
  showPaths?: boolean;
}

/**
 * Search filter interface
 */
export interface JSONSearchFilter {
  query: string;
  matchKeys?: boolean;
  matchValues?: boolean;
  matchTypes?: boolean;
  caseSensitive?: boolean;
}

/**
 * Structured JSON view interface
 */
export interface IStructuredJSONView {
  render(container: HTMLElement): void;
  setData(data: any, schema?: UISchema): void;
  getData(): any;
  expandAll(): void;
  collapseAll(): void;
  search(filter: JSONSearchFilter): void;
  clearSearch(): void;
  onDataChange(callback: (data: any) => void): void;
  focus(): void;
  destroy(): void;
}

/**
 * StructuredJSONView implementation with hierarchical display and editing
 */
export class StructuredJSONView implements IStructuredJSONView {
  private container?: HTMLElement;
  private config: StructuredJSONConfig;
  private rootNode?: JSONNode;
  private schema?: UISchema;
  private changeCallback?: (data: any) => void;
  private searchFilter?: JSONSearchFilter;
  private contentContainer?: HTMLElement;
  private searchContainer?: HTMLElement;
  private expandedPaths: Set<string> = new Set();

  constructor(config: StructuredJSONConfig = {}) {
    this.config = {
      showSearch: true,
      showGroupHeaders: true,
      allowInlineEditing: true,
      collapsibleGroups: true,
      maxValueLength: 100,
      showTypes: false,
      showPaths: false,
      ...config
    };

    this.initializeStyles();
  }

  /**
   * Render the structured JSON view
   */
  render(container: HTMLElement): void {
    this.container = container;
    container.className = 'thoth-structured-json-container';

    // Create search bar if enabled
    if (this.config.showSearch) {
      this.searchContainer = container.createEl('div', { cls: 'thoth-json-search' });
      this.createSearchInterface();
    }

    // Create content container
    this.contentContainer = container.createEl('div', { cls: 'thoth-json-content' });

    // Render content if data exists
    if (this.rootNode) {
      this.renderContent();
    }
  }

  /**
   * Set data and optional schema
   */
  setData(data: any, schema?: UISchema): void {
    this.schema = schema;
    this.rootNode = this.buildNodeTree(data, '', []);

    if (this.contentContainer) {
      this.renderContent();
    }
  }

  /**
   * Get current data
   */
  getData(): any {
    return this.rootNode ? this.nodeToData(this.rootNode) : {};
  }

  /**
   * Expand all nodes
   */
  expandAll(): void {
    this.setAllNodesExpanded(true);
    this.renderContent();
  }

  /**
   * Collapse all nodes
   */
  collapseAll(): void {
    this.setAllNodesExpanded(false);
    this.renderContent();
  }

  /**
   * Search nodes with filter
   */
  search(filter: JSONSearchFilter): void {
    this.searchFilter = filter;
    this.renderContent();
  }

  /**
   * Clear search filter
   */
  clearSearch(): void {
    this.searchFilter = undefined;
    if (this.searchContainer) {
      const searchInput = this.searchContainer.querySelector('.thoth-search-input') as HTMLInputElement;
      if (searchInput) {
        searchInput.value = '';
      }
    }
    this.renderContent();
  }

  /**
   * Set data change callback
   */
  onDataChange(callback: (data: any) => void): void {
    this.changeCallback = callback;
  }

  /**
   * Focus the search input or first editable field
   */
  focus(): void {
    if (this.searchContainer) {
      const searchInput = this.searchContainer.querySelector('.thoth-search-input') as HTMLInputElement;
      if (searchInput) {
        searchInput.focus();
        return;
      }
    }

    // Focus first editable field
    const firstEditable = this.container?.querySelector('.thoth-node-value-editable') as HTMLElement;
    if (firstEditable) {
      firstEditable.focus();
    }
  }

  /**
   * Destroy view and clean up
   */
  destroy(): void {
    this.container = undefined;
    this.contentContainer = undefined;
    this.searchContainer = undefined;
    this.rootNode = undefined;
    this.schema = undefined;
    this.changeCallback = undefined;
    this.searchFilter = undefined;
    this.expandedPaths.clear();
  }

  /**
   * Build node tree from data
   */
  private buildNodeTree(data: any, key: string, path: string[], parent?: JSONNode): JSONNode {
    const node: JSONNode = {
      key,
      value: data,
      type: this.getNodeType(data),
      parent,
      path: [...path, key].filter(Boolean),
      isExpanded: this.expandedPaths.has([...path, key].filter(Boolean).join('.')),
      isEditable: this.config.allowInlineEditing
    };

    // Add schema information if available
    if (this.schema && key) {
      const fieldSchema = this.schema.fields[key];
      if (fieldSchema) {
        node.schema = fieldSchema;
        node.group = fieldSchema.group;
      }
    }

    // Build children for objects and arrays
    if (data && typeof data === 'object') {
      node.children = [];

      if (Array.isArray(data)) {
        data.forEach((item, index) => {
          const childNode = this.buildNodeTree(item, index.toString(), node.path, node);
          node.children!.push(childNode);
        });
      } else {
        Object.entries(data).forEach(([childKey, childValue]) => {
          const childNode = this.buildNodeTree(childValue, childKey, node.path, node);
          node.children!.push(childNode);
        });
      }
    }

    return node;
  }

  /**
   * Get node type from value
   */
  private getNodeType(value: any): JSONNodeType {
    if (value === null) return 'null';
    if (Array.isArray(value)) return 'array';
    if (typeof value === 'object') return 'object';
    if (typeof value === 'string') return 'string';
    if (typeof value === 'number') return 'number';
    if (typeof value === 'boolean') return 'boolean';
    return 'string'; // fallback
  }

  /**
   * Convert node tree back to data
   */
  private nodeToData(node: JSONNode): any {
    if (node.type === 'object' && node.children) {
      const obj: any = {};
      for (const child of node.children) {
        obj[child.key] = this.nodeToData(child);
      }
      return obj;
    }

    if (node.type === 'array' && node.children) {
      return node.children.map(child => this.nodeToData(child));
    }

    return node.value;
  }

  /**
   * Create search interface
   */
  private createSearchInterface(): void {
    if (!this.searchContainer) return;

    // Search input
    const searchWrapper = this.searchContainer.createEl('div', { cls: 'thoth-search-wrapper' });

    const searchInput = searchWrapper.createEl('input', {
      cls: 'thoth-search-input',
      type: 'text',
      placeholder: 'Search settings...'
    });

    const searchBtn = searchWrapper.createEl('button', {
      text: '🔍',
      cls: 'thoth-search-btn'
    });

    const clearBtn = searchWrapper.createEl('button', {
      text: '✕',
      cls: 'thoth-search-clear'
    });

    // Search options
    const searchOptions = this.searchContainer.createEl('div', { cls: 'thoth-search-options' });

    const keysCheckbox = this.createCheckbox(searchOptions, 'search-keys', 'Keys', true);
    const valuesCheckbox = this.createCheckbox(searchOptions, 'search-values', 'Values', true);
    const typesCheckbox = this.createCheckbox(searchOptions, 'search-types', 'Types', false);
    const caseCheckbox = this.createCheckbox(searchOptions, 'search-case', 'Case sensitive', false);

    // Event handlers
    const performSearch = () => {
      const query = searchInput.value.trim();
      if (!query) {
        this.clearSearch();
        return;
      }

      this.search({
        query,
        matchKeys: keysCheckbox.checked,
        matchValues: valuesCheckbox.checked,
        matchTypes: typesCheckbox.checked,
        caseSensitive: caseCheckbox.checked
      });
    };

    searchInput.addEventListener('input', performSearch);
    searchBtn.addEventListener('click', performSearch);
    clearBtn.addEventListener('click', () => {
      searchInput.value = '';
      this.clearSearch();
    });
  }

  /**
   * Create checkbox for search options
   */
  private createCheckbox(container: HTMLElement, id: string, label: string, checked: boolean): HTMLInputElement {
    const wrapper = container.createEl('label', { cls: 'thoth-search-option' });
    const checkbox = wrapper.createEl('input', { type: 'checkbox' }) as HTMLInputElement;
    checkbox.id = id;
    checkbox.checked = checked;
    wrapper.createEl('span', { text: label });
    return checkbox;
  }

  /**
   * Render content based on current state
   */
  private renderContent(): void {
    if (!this.contentContainer || !this.rootNode) return;

    this.contentContainer.empty();

    if (this.config.showGroupHeaders && this.schema) {
      this.renderGroupedContent();
    } else {
      this.renderFlatContent();
    }
  }

  /**
   * Render content grouped by schema groups
   */
  private renderGroupedContent(): void {
    if (!this.contentContainer || !this.rootNode || !this.schema) return;

    // Group nodes by schema group
    const groups = this.groupNodesBySchema(this.rootNode);

    // Sort groups by order
    const sortedGroups = Array.from(groups.entries())
      .sort(([a], [b]) => {
        const groupA = this.schema!.groups[a];
        const groupB = this.schema!.groups[b];
        return (groupA?.order || 0) - (groupB?.order || 0);
      });

    // Render each group
    for (const [groupName, nodes] of sortedGroups) {
      if (nodes.length === 0) continue;

      const groupSchema = this.schema.groups[groupName];
      const groupEl = this.createGroupSection(groupName, groupSchema, nodes);
      this.contentContainer.appendChild(groupEl);
    }

    // Render ungrouped nodes
    const ungroupedNodes = this.getUngroupedNodes(this.rootNode);
    if (ungroupedNodes.length > 0) {
      const ungroupedEl = this.createGroupSection('other', { title: 'Other Settings', description: 'Additional configuration options' }, ungroupedNodes);
      this.contentContainer.appendChild(ungroupedEl);
    }
  }

  /**
   * Render content in flat structure
   */
  private renderFlatContent(): void {
    if (!this.contentContainer || !this.rootNode) return;

    const contentEl = this.contentContainer.createEl('div', { cls: 'thoth-json-flat' });
    this.renderNode(this.rootNode, contentEl, 0);
  }

  /**
   * Group nodes by their schema groups
   */
  private groupNodesBySchema(node: JSONNode): Map<string, JSONNode[]> {
    const groups = new Map<string, JSONNode[]>();

    if (node.children) {
      for (const child of node.children) {
        const groupName = child.group || 'other';

        if (!groups.has(groupName)) {
          groups.set(groupName, []);
        }

        groups.get(groupName)!.push(child);
      }
    }

    return groups;
  }

  /**
   * Get nodes that don't belong to any schema group
   */
  private getUngroupedNodes(node: JSONNode): JSONNode[] {
    if (!node.children) return [];

    return node.children.filter(child => !child.group);
  }

  /**
   * Create group section
   */
  private createGroupSection(groupName: string, groupSchema: GroupSchema | { title: string; description: string }, nodes: JSONNode[]): HTMLElement {
    const groupEl = document.createElement('div');
    groupEl.className = 'thoth-json-group';
    groupEl.dataset.groupName = groupName;

    // Group header
    const headerEl = groupEl.createEl('div', { cls: 'thoth-json-group-header' });

    if (this.config.collapsibleGroups) {
      headerEl.classList.add('collapsible');
      headerEl.addEventListener('click', () => this.toggleGroup(groupName));
    }

    const titleEl = headerEl.createEl('h3', { text: groupSchema.title });

    if (this.config.collapsibleGroups) {
      const toggleEl = headerEl.createEl('span', { cls: 'thoth-group-toggle' });
      toggleEl.textContent = '▼'; // Expanded by default
    }

    if (groupSchema.description) {
      headerEl.createEl('p', { text: groupSchema.description, cls: 'thoth-group-description' });
    }

    // Group content
    const contentEl = groupEl.createEl('div', { cls: 'thoth-json-group-content' });

    // Filter nodes based on search
    const filteredNodes = this.searchFilter ? this.filterNodes(nodes) : nodes;

    // Render nodes
    for (const node of filteredNodes) {
      this.renderNode(node, contentEl, 0);
    }

    // Show empty state if no nodes after filtering
    if (filteredNodes.length === 0 && this.searchFilter) {
      contentEl.createEl('div', {
        text: 'No matching settings found',
        cls: 'thoth-json-empty-search'
      });
    }

    return groupEl;
  }

  /**
   * Render individual JSON node
   */
  private renderNode(node: JSONNode, container: HTMLElement, depth: number): void {
    const nodeEl = container.createEl('div', { cls: 'thoth-json-node' });
    nodeEl.dataset.nodePath = node.path.join('.');
    nodeEl.dataset.nodeType = node.type;
    nodeEl.style.marginLeft = `${depth * 20}px`;

    // Node header with key, type, and value
    const headerEl = nodeEl.createEl('div', { cls: 'thoth-json-node-header' });

    // Expandable indicator for objects/arrays
    if ((node.type === 'object' || node.type === 'array') && node.children && node.children.length > 0) {
      const expandEl = headerEl.createEl('span', {
        text: node.isExpanded ? '▼' : '▶',
        cls: 'thoth-node-expand'
      });
      expandEl.addEventListener('click', () => this.toggleNodeExpansion(node));
    } else {
      headerEl.createEl('span', { cls: 'thoth-node-expand-spacer' });
    }

    // Key name
    const keyEl = headerEl.createEl('span', {
      text: node.key || 'root',
      cls: 'thoth-node-key'
    });

    // Schema info (if available)
    if (node.schema) {
      keyEl.title = node.schema.description;
      if (node.schema.required) {
        keyEl.classList.add('required');
      }
    }

    // Type indicator (if enabled)
    if (this.config.showTypes) {
      headerEl.createEl('span', {
        text: `[${node.type}]`,
        cls: 'thoth-node-type'
      });
    }

    // Value display/editor
    this.renderNodeValue(node, headerEl);

    // Children (if expanded)
    if ((node.type === 'object' || node.type === 'array') && node.isExpanded && node.children) {
      const childrenEl = nodeEl.createEl('div', { cls: 'thoth-json-node-children' });

      for (const child of node.children) {
        this.renderNode(child, childrenEl, depth + 1);
      }
    }

    // Add to search results highlighting
    if (this.searchFilter && this.nodeMatchesSearch(node, this.searchFilter)) {
      nodeEl.classList.add('search-match');
    }
  }

  /**
   * Render node value with inline editing support
   */
  private renderNodeValue(node: JSONNode, container: HTMLElement): void {
    const valueContainer = container.createEl('span', { cls: 'thoth-node-value-container' });

    if (node.type === 'object' || node.type === 'array') {
      // Show object/array summary
      const summary = node.type === 'array'
        ? `[${node.children?.length || 0} items]`
        : `{${node.children?.length || 0} properties}`;

      valueContainer.createEl('span', {
        text: summary,
        cls: 'thoth-node-summary'
      });
    } else {
      // Primitive value - show with inline editing
      this.renderPrimitiveValue(node, valueContainer);
    }
  }

  /**
   * Render primitive value with editing capabilities
   */
  private renderPrimitiveValue(node: JSONNode, container: HTMLElement): void {
    const valueEl = container.createEl('span', { cls: 'thoth-node-value' });

    if (this.config.allowInlineEditing && node.isEditable) {
      valueEl.classList.add('thoth-node-value-editable');
      valueEl.contentEditable = 'true';
      valueEl.spellcheck = false;
    }

    // Format value based on type
    let displayValue = this.formatValueForDisplay(node.value, node.type);

    // Truncate long values
    if (displayValue.length > (this.config.maxValueLength || 100)) {
      displayValue = displayValue.substring(0, this.config.maxValueLength! - 3) + '...';
      valueEl.title = String(node.value); // Show full value in tooltip
    }

    valueEl.textContent = displayValue;

    // Add type-specific styling
    valueEl.classList.add(`thoth-value-${node.type}`);

    // Event handlers for editing
    if (this.config.allowInlineEditing && node.isEditable) {
      valueEl.addEventListener('blur', () => {
        this.handleValueEdit(node, valueEl.textContent || '');
      });

      valueEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          valueEl.blur();
        }
        if (e.key === 'Escape') {
          e.preventDefault();
          valueEl.textContent = this.formatValueForDisplay(node.value, node.type);
          valueEl.blur();
        }
      });
    }
  }

  /**
   * Format value for display
   */
  private formatValueForDisplay(value: any, type: JSONNodeType): string {
    switch (type) {
      case 'string':
        return `"${value}"`;
      case 'number':
      case 'boolean':
        return String(value);
      case 'null':
        return 'null';
      default:
        return String(value);
    }
  }

  /**
   * Handle value editing
   */
  private handleValueEdit(node: JSONNode, newValue: string): void {
    try {
      let parsedValue: any;

      // Parse value based on original type
      if (newValue.startsWith('"') && newValue.endsWith('"')) {
        // String value
        parsedValue = newValue.slice(1, -1);
      } else if (newValue === 'true' || newValue === 'false') {
        // Boolean value
        parsedValue = newValue === 'true';
      } else if (newValue === 'null') {
        // Null value
        parsedValue = null;
      } else if (!isNaN(Number(newValue)) && newValue.trim() !== '') {
        // Number value
        parsedValue = Number(newValue);
      } else {
        // Default to string
        parsedValue = newValue;
      }

      // Update node value
      node.value = parsedValue;

      // Trigger change callback
      if (this.changeCallback) {
        this.changeCallback(this.getData());
      }

    } catch (error) {
      console.warn('Failed to parse edited value:', error);
      // Revert to original value
      this.renderContent();
    }
  }

  /**
   * Toggle node expansion
   */
  private toggleNodeExpansion(node: JSONNode): void {
    node.isExpanded = !node.isExpanded;

    // Update expanded paths tracking
    const pathKey = node.path.join('.');
    if (node.isExpanded) {
      this.expandedPaths.add(pathKey);
    } else {
      this.expandedPaths.delete(pathKey);
    }

    this.renderContent();
  }

  /**
   * Toggle group expansion
   */
  private toggleGroup(groupName: string): void {
    const groupEl = this.container?.querySelector(`[data-group-name="${groupName}"]`) as HTMLElement;
    if (!groupEl) return;

    const contentEl = groupEl.querySelector('.thoth-json-group-content') as HTMLElement;
    const toggleEl = groupEl.querySelector('.thoth-group-toggle') as HTMLElement;

    if (contentEl && toggleEl) {
      const isExpanded = contentEl.style.display !== 'none';
      contentEl.style.display = isExpanded ? 'none' : 'block';
      toggleEl.textContent = isExpanded ? '▶' : '▼';
    }
  }

  /**
   * Set all nodes expanded/collapsed state
   */
  private setAllNodesExpanded(expanded: boolean): void {
    this.expandedPaths.clear();

    if (expanded && this.rootNode) {
      this.collectAllPaths(this.rootNode, this.expandedPaths);
    }

    if (this.rootNode) {
      this.updateNodeExpansionState(this.rootNode, expanded);
    }
  }

  /**
   * Collect all possible paths for expansion
   */
  private collectAllPaths(node: JSONNode, paths: Set<string>): void {
    if (node.children && node.children.length > 0) {
      paths.add(node.path.join('.'));

      for (const child of node.children) {
        this.collectAllPaths(child, paths);
      }
    }
  }

  /**
   * Update node expansion state recursively
   */
  private updateNodeExpansionState(node: JSONNode, expanded: boolean): void {
    if (node.children && node.children.length > 0) {
      node.isExpanded = expanded;

      for (const child of node.children) {
        this.updateNodeExpansionState(child, expanded);
      }
    }
  }

  /**
   * Filter nodes based on search criteria
   */
  private filterNodes(nodes: JSONNode[]): JSONNode[] {
    if (!this.searchFilter) return nodes;

    return nodes.filter(node => this.nodeMatchesSearch(node, this.searchFilter!));
  }

  /**
   * Check if node matches search filter
   */
  private nodeMatchesSearch(node: JSONNode, filter: JSONSearchFilter): boolean {
    const query = filter.caseSensitive ? filter.query : filter.query.toLowerCase();

    // Check key
    if (filter.matchKeys) {
      const key = filter.caseSensitive ? node.key : node.key.toLowerCase();
      if (key.includes(query)) {
        return true;
      }
    }

    // Check value
    if (filter.matchValues) {
      const value = filter.caseSensitive ? String(node.value) : String(node.value).toLowerCase();
      if (value.includes(query)) {
        return true;
      }
    }

    // Check type
    if (filter.matchTypes) {
      const type = filter.caseSensitive ? node.type : node.type.toLowerCase();
      if (type.includes(query)) {
        return true;
      }
    }

    // Check children recursively
    if (node.children) {
      return node.children.some(child => this.nodeMatchesSearch(child, filter));
    }

    return false;
  }

  /**
   * Initialize structured JSON view styles
   */
  private initializeStyles(): void {
    if (document.getElementById('thoth-structured-json-styles')) {
      return; // Styles already loaded
    }

    const style = document.createElement('style');
    style.id = 'thoth-structured-json-styles';
    style.textContent = `
      /* Structured JSON container */
      .thoth-structured-json-container {
        height: 100%;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      /* Search interface */
      .thoth-json-search {
        padding: 12px;
        background: var(--background-secondary);
        border-bottom: 1px solid var(--background-modifier-border);
        flex-shrink: 0;
      }

      .thoth-search-wrapper {
        display: flex;
        gap: 6px;
        margin-bottom: 8px;
      }

      .thoth-search-input {
        flex: 1;
        padding: 6px 10px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        background: var(--background-primary);
        color: var(--text-normal);
        font-size: 13px;
      }

      .thoth-search-input:focus {
        border-color: var(--interactive-accent);
        outline: none;
      }

      .thoth-search-btn,
      .thoth-search-clear {
        padding: 6px 10px;
        background: var(--background-modifier-form-field);
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      }

      .thoth-search-btn:hover,
      .thoth-search-clear:hover {
        background: var(--background-modifier-hover);
      }

      .thoth-search-options {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }

      .thoth-search-option {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        cursor: pointer;
        user-select: none;
      }

      .thoth-search-option input[type="checkbox"] {
        margin: 0;
      }

      /* Content area */
      .thoth-json-content {
        flex: 1;
        overflow-y: auto;
        padding: 12px;
      }

      /* Group styles */
      .thoth-json-group {
        margin-bottom: 20px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 6px;
        overflow: hidden;
      }

      .thoth-json-group-header {
        padding: 12px 16px;
        background: var(--background-secondary);
        border-bottom: 1px solid var(--background-modifier-border);
      }

      .thoth-json-group-header.collapsible {
        cursor: pointer;
        user-select: none;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }

      .thoth-json-group-header.collapsible:hover {
        background: var(--background-modifier-hover);
      }

      .thoth-json-group-header h3 {
        margin: 0 0 4px 0;
        font-size: 14px;
        color: var(--text-normal);
      }

      .thoth-group-description {
        margin: 0;
        font-size: 12px;
        color: var(--text-muted);
      }

      .thoth-group-toggle {
        font-size: 14px;
        color: var(--text-muted);
        transition: transform 0.2s ease;
      }

      .thoth-json-group-content {
        padding: 12px;
        background: var(--background-primary);
      }

      /* Node styles */
      .thoth-json-node {
        margin: 2px 0;
        padding: 4px 0;
      }

      .thoth-json-node-header {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 2px 4px;
        border-radius: 3px;
        transition: background 0.2s ease;
      }

      .thoth-json-node:hover .thoth-json-node-header {
        background: var(--background-modifier-hover);
      }

      .thoth-node-expand {
        width: 12px;
        text-align: center;
        cursor: pointer;
        color: var(--text-muted);
        font-size: 12px;
        user-select: none;
      }

      .thoth-node-expand:hover {
        color: var(--text-normal);
      }

      .thoth-node-expand-spacer {
        width: 12px;
      }

      .thoth-node-key {
        font-weight: 500;
        color: var(--text-accent);
        font-size: 13px;
        min-width: 120px;
      }

      .thoth-node-key.required::after {
        content: ' *';
        color: var(--color-red);
      }

      .thoth-node-type {
        font-size: 11px;
        color: var(--text-muted);
        font-style: italic;
        min-width: 60px;
      }

      .thoth-node-value-container {
        flex: 1;
        margin-left: 8px;
      }

      .thoth-node-value {
        padding: 2px 4px;
        border-radius: 3px;
        font-family: Monaco, Menlo, "Ubuntu Mono", monospace;
        font-size: 12px;
      }

      .thoth-node-value-editable {
        cursor: text;
        border: 1px solid transparent;
        transition: all 0.2s ease;
      }

      .thoth-node-value-editable:hover {
        background: var(--background-modifier-hover);
        border-color: var(--background-modifier-border);
      }

      .thoth-node-value-editable:focus {
        outline: none;
        background: var(--background-primary);
        border-color: var(--interactive-accent);
        box-shadow: 0 0 0 2px rgba(var(--interactive-accent-rgb), 0.2);
      }

      .thoth-node-summary {
        color: var(--text-muted);
        font-style: italic;
        font-size: 12px;
      }

      /* Value type styles */
      .thoth-value-string {
        color: var(--color-green);
      }

      .thoth-value-number {
        color: var(--color-blue);
      }

      .thoth-value-boolean {
        color: var(--color-purple);
        font-weight: 500;
      }

      .thoth-value-null {
        color: var(--text-muted);
        font-style: italic;
      }

      /* Search highlighting */
      .thoth-json-node.search-match {
        background: rgba(var(--interactive-accent-rgb), 0.1);
        border-left: 3px solid var(--interactive-accent);
        padding-left: 8px;
        margin-left: -8px;
      }

      .thoth-json-empty-search {
        text-align: center;
        color: var(--text-muted);
        font-style: italic;
        padding: 40px 20px;
      }

      /* Flat view styles */
      .thoth-json-flat {
        padding: 8px;
      }

      /* Node children */
      .thoth-json-node-children {
        margin-top: 4px;
      }

      /* Responsive design */
      @media (max-width: 600px) {
        .thoth-search-options {
          flex-direction: column;
          gap: 6px;
        }

        .thoth-node-key {
          min-width: 80px;
        }

        .thoth-json-node {
          margin-left: 0 !important;
        }

        .thoth-json-node-header {
          flex-wrap: wrap;
        }
      }

      /* High contrast mode */
      @media (prefers-contrast: high) {
        .thoth-json-node.search-match {
          border-left-width: 4px;
          background: rgba(var(--interactive-accent-rgb), 0.2);
        }

        .thoth-node-value-editable:focus {
          border-width: 2px;
        }
      }

      /* Animation for expanding/collapsing */
      .thoth-json-node-children {
        animation: fadeInChildren 0.2s ease;
      }

      @keyframes fadeInChildren {
        from {
          opacity: 0;
          transform: translateY(-5px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }
    `;

    document.head.appendChild(style);
  }
}

/**
 * Structured JSON view factory
 */
export class StructuredJSONViewFactory {
  /**
   * Create structured JSON view
   */
  static create(config: StructuredJSONConfig = {}): IStructuredJSONView {
    return new StructuredJSONView(config);
  }

  /**
   * Create read-only structured view
   */
  static createReadOnly(config: StructuredJSONConfig = {}): IStructuredJSONView {
    const readOnlyConfig = { ...config, allowInlineEditing: false };
    return new StructuredJSONView(readOnlyConfig);
  }

  /**
   * Create searchable structured view
   */
  static createSearchable(config: StructuredJSONConfig = {}): IStructuredJSONView {
    const searchableConfig = { ...config, showSearch: true };
    return new StructuredJSONView(searchableConfig);
  }

  /**
   * Create grouped view with schema
   */
  static createGrouped(schema: UISchema, config: StructuredJSONConfig = {}): IStructuredJSONView {
    const groupedConfig = {
      ...config,
      showGroupHeaders: true,
      collapsibleGroups: true
    };
    const view = new StructuredJSONView(groupedConfig);
    return view;
  }
}

/**
 * Structured JSON utilities
 */
export class StructuredJSONUtils {
  /**
   * Convert settings to structured display format
   */
  static structureSettings(settings: ThothSettings, schema?: UISchema): any {
    if (!schema) {
      return settings;
    }

    const structured: any = {};

    // Group settings by schema groups
    for (const [groupName, groupSchema] of Object.entries(schema.groups)) {
      structured[groupName] = {};

      // Add fields belonging to this group
      for (const [fieldName, fieldSchema] of Object.entries(schema.fields)) {
        if (fieldSchema.group === groupName) {
          structured[groupName][fieldName] = settings[fieldName as keyof ThothSettings];
        }
      }
    }

    // Add ungrouped fields
    const ungroupedFields: any = {};
    for (const [fieldName, fieldSchema] of Object.entries(schema.fields)) {
      if (!fieldSchema.group || !schema.groups[fieldSchema.group]) {
        ungroupedFields[fieldName] = settings[fieldName as keyof ThothSettings];
      }
    }

    if (Object.keys(ungroupedFields).length > 0) {
      structured['other'] = ungroupedFields;
    }

    return structured;
  }

  /**
   * Flatten structured settings back to ThothSettings format
   */
  static flattenStructuredSettings(structured: any): Partial<ThothSettings> {
    const flattened: any = {};

    for (const [groupName, groupData] of Object.entries(structured)) {
      if (typeof groupData === 'object' && groupData !== null) {
        Object.assign(flattened, groupData);
      }
    }

    return flattened;
  }

  /**
   * Find value at path in structured data
   */
  static getValueAtPath(data: any, path: string[]): any {
    let current = data;

    for (const key of path) {
      if (current && typeof current === 'object' && key in current) {
        current = current[key];
      } else {
        return undefined;
      }
    }

    return current;
  }

  /**
   * Set value at path in structured data
   */
  static setValueAtPath(data: any, path: string[], value: any): any {
    if (path.length === 0) return value;

    const result = { ...data };
    let current = result;

    // Navigate to parent of target
    for (let i = 0; i < path.length - 1; i++) {
      const key = path[i];
      if (!(key in current) || typeof current[key] !== 'object') {
        current[key] = {};
      }
      current = current[key];
    }

    // Set the value
    current[path[path.length - 1]] = value;
    return result;
  }

  /**
   * Get all paths in structured data
   */
  static getAllPaths(data: any, prefix: string[] = []): string[][] {
    const paths: string[][] = [];

    if (data && typeof data === 'object') {
      for (const [key, value] of Object.entries(data)) {
        const currentPath = [...prefix, key];
        paths.push(currentPath);

        if (value && typeof value === 'object') {
          paths.push(...this.getAllPaths(value, currentPath));
        }
      }
    }

    return paths;
  }

  /**
   * Search structured data for matching nodes
   */
  static searchStructuredData(data: any, query: string, options: {
    matchKeys?: boolean;
    matchValues?: boolean;
    caseSensitive?: boolean;
  } = {}): string[][] {
    const { matchKeys = true, matchValues = true, caseSensitive = false } = options;
    const searchQuery = caseSensitive ? query : query.toLowerCase();
    const matchingPaths: string[][] = [];

    function searchRecursive(obj: any, path: string[] = []): void {
      if (obj && typeof obj === 'object') {
        for (const [key, value] of Object.entries(obj)) {
          const currentPath = [...path, key];
          let matches = false;

          // Check key match
          if (matchKeys) {
            const keyToCheck = caseSensitive ? key : key.toLowerCase();
            if (keyToCheck.includes(searchQuery)) {
              matches = true;
            }
          }

          // Check value match
          if (matchValues && typeof value === 'string') {
            const valueToCheck = caseSensitive ? value : value.toLowerCase();
            if (valueToCheck.includes(searchQuery)) {
              matches = true;
            }
          }

          if (matches) {
            matchingPaths.push(currentPath);
          }

          // Recurse into objects/arrays
          if (value && typeof value === 'object') {
            searchRecursive(value, currentPath);
          }
        }
      }
    }

    searchRecursive(data);
    return matchingPaths;
  }
}
