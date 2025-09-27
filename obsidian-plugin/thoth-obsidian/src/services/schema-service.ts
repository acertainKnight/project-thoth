import { APIUtilities } from '../utils/api';
import { ThothSettings } from '../types';

/**
 * Field dependency interface for advanced organization
 */
export interface FieldDependency {
  field_path: string;
  depends_on: string;
  condition: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains' | 'not_empty';
  value: any;
  action: 'show' | 'hide' | 'enable' | 'disable' | 'require' | 'optional';
}

/**
 * Conditional rule interface for advanced organization
 */
export interface ConditionalRule {
  rule_id: string;
  description: string;
  condition_expression: string;
  affected_fields: string[];
  action: 'show' | 'hide' | 'enable' | 'disable' | 'require' | 'optional';
  priority: number;
}

/**
 * Advanced category interface
 */
export interface AdvancedCategory {
  category_id: string;
  title: string;
  description: string;
  parent_category?: string;
  subcategories: string[];
  priority: number;
  icon?: string;
  collapsed_by_default: boolean;
  visibility_condition?: string;
  required_for_functionality: string[];
}

/**
 * UI Schema interfaces based on backend schema structure with advanced features
 */
export interface UISchema {
  version: string;
  fields: Record<string, FieldSchema>;
  groups: Record<string, GroupSchema>;
  // Advanced organization features
  field_dependencies?: FieldDependency[];
  conditional_rules?: ConditionalRule[];
  field_relationships?: any[];
  advanced_categories?: AdvancedCategory[];
  configuration_use_cases?: any[];
  ui_metadata?: {
    supports_conditional_visibility: boolean;
    supports_auto_fix: boolean;
    supports_guided_setup: boolean;
    supports_advanced_organization: boolean;
  };
}

export interface FieldSchema {
  type: 'text' | 'password' | 'number' | 'boolean' | 'select' | 'multiselect' | 'file' | 'directory';
  required: boolean;
  group: string;
  title: string;
  description: string;
  env_var?: string;
  validation?: {
    pattern?: string;
    min?: number;
    max?: number;
    message?: string;
  };
  options?: string[]; // for select/multiselect
  default?: any;
}

export interface GroupSchema {
  title: string;
  description: string;
  order: number;
  collapsed?: boolean;
}

export interface ValidationResult {
  is_valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  error_count: number;
  warning_count: number;
}

export interface FieldValidationResult {
  is_valid: boolean;
  error?: string;
  warning?: string;
}

export interface ValidationError {
  field: string;
  message: string;
  code: string;
}

export interface ValidationWarning {
  field: string;
  message: string;
  code: string;
}

/**
 * Schema service interface
 */
export interface ISchemaService {
  getSchema(): Promise<UISchema>;
  validateConfig(config: Partial<ThothSettings>): Promise<ValidationResult>;
  validatePartialConfig(field: string, value: any): Promise<FieldValidationResult>;
  isSchemaOutdated(): Promise<boolean>;
  refreshSchema(): Promise<void>;
  updateBaseUrl(newBaseUrl: string): void;
  clearCache(): void;
  isBackendReachable(): Promise<boolean>;
}

/**
 * Schema caching configuration
 */
interface SchemaCacheEntry {
  schema: UISchema;
  timestamp: number;
  expires: number;
  version: string;
}

/**
 * SchemaService implementation with caching and fallback
 */
export class SchemaService implements ISchemaService {
  private apiUtils: APIUtilities;
  private baseUrl: string;
  private cache: SchemaCacheEntry | null = null;
  private readonly CACHE_TTL = 5 * 60 * 1000; // 5 minutes
  private readonly SCHEMA_ENDPOINT = '/config/schema';
  private readonly VALIDATE_ENDPOINT = '/config/validate';
  private readonly VALIDATE_PARTIAL_ENDPOINT = '/config/validate-partial';
  private readonly SCHEMA_VERSION_ENDPOINT = '/config/schema/version';

  constructor(baseUrl: string) {
    this.apiUtils = new APIUtilities();
    this.baseUrl = baseUrl;
  }

  /**
   * Get schema with caching and fallback
   */
  async getSchema(): Promise<UISchema> {
    // Check cache first
    if (this.cache && Date.now() < this.cache.expires) {
      return this.cache.schema;
    }

    try {
      // Try to fetch from backend
      const response = await this.apiUtils.makeRequest(
        this.apiUtils.buildEndpointUrl(this.baseUrl, this.SCHEMA_ENDPOINT)
      );

      if (response.ok) {
        const schema = await response.json();

        // Cache the schema
        this.cache = {
          schema,
          timestamp: Date.now(),
          expires: Date.now() + this.CACHE_TTL,
          version: schema.version || '1.0.0'
        };

        return schema;
      } else {
        throw new Error(`Schema fetch failed: ${response.statusText}`);
      }
    } catch (error) {
      console.warn('Failed to fetch schema from backend:', error);

      // Return fallback schema if backend is unreachable
      return this.getFallbackSchema();
    }
  }

  /**
   * Validate full configuration
   */
  async validateConfig(config: Partial<ThothSettings>): Promise<ValidationResult> {
    try {
      const response = await this.apiUtils.makeRequest(
        this.apiUtils.buildEndpointUrl(this.baseUrl, this.VALIDATE_ENDPOINT),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config)
        }
      );

      if (response.ok) {
        return await response.json();
      } else {
        throw new Error(`Validation failed: ${response.statusText}`);
      }
    } catch (error) {
      console.warn('Backend validation failed, using client-side fallback:', error);

      // Fallback to basic client-side validation
      return this.fallbackValidation(config);
    }
  }

  /**
   * Validate partial configuration (real-time validation)
   */
  async validatePartialConfig(field: string, value: any): Promise<FieldValidationResult> {
    try {
      const response = await this.apiUtils.makeRequest(
        this.apiUtils.buildEndpointUrl(this.baseUrl, this.VALIDATE_PARTIAL_ENDPOINT),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ field, value })
        }
      );

      if (response.ok) {
        return await response.json();
      } else {
        throw new Error(`Partial validation failed: ${response.statusText}`);
      }
    } catch (error) {
      console.warn('Backend partial validation failed, using client-side fallback:', error);

      // Fallback to basic client-side validation
      return this.fallbackPartialValidation(field, value);
    }
  }

  /**
   * Check if schema is outdated
   */
  async isSchemaOutdated(): Promise<boolean> {
    if (!this.cache) {
      return true; // No cache means we need to fetch
    }

    try {
      const response = await this.apiUtils.makeRequest(
        this.apiUtils.buildEndpointUrl(this.baseUrl, this.SCHEMA_VERSION_ENDPOINT)
      );

      if (response.ok) {
        const versionInfo = await response.json();
        return versionInfo.version !== this.cache.version;
      }
    } catch (error) {
      console.warn('Failed to check schema version:', error);
    }

    // If we can't check, assume it's outdated if cache is expired
    return Date.now() >= this.cache.expires;
  }

  /**
   * Force refresh schema from backend
   */
  async refreshSchema(): Promise<void> {
    this.cache = null; // Clear cache
    await this.getSchema(); // This will fetch fresh schema
  }

  /**
   * Update base URL (for when connection settings change)
   */
  updateBaseUrl(newBaseUrl: string): void {
    this.baseUrl = newBaseUrl;
    this.cache = null; // Invalidate cache when URL changes
  }

  /**
   * Get fallback schema when backend is unreachable
   */
  private getFallbackSchema(): UISchema {
    return {
      version: '1.0.0-fallback',
      groups: {
        'api-keys': {
          title: 'API Keys',
          description: 'Configure API keys for external services',
          order: 1
        },
        'directories': {
          title: 'Directories',
          description: 'Configure file and data directories',
          order: 2
        },
        'connection': {
          title: 'Connection',
          description: 'Configure connection settings',
          order: 3
        },
        'llm': {
          title: 'Language Models',
          description: 'Configure LLM models and parameters',
          order: 4
        },
        'agent': {
          title: 'Agent Behavior',
          description: 'Configure agent behavior and performance',
          order: 5
        },
        'discovery': {
          title: 'Discovery System',
          description: 'Configure research discovery automation',
          order: 6
        },
        'ui': {
          title: 'User Interface',
          description: 'Configure plugin UI preferences',
          order: 7
        }
      },
      fields: {
        'mistralKey': {
          type: 'password',
          required: true,
          group: 'api-keys',
          title: 'Mistral API Key',
          description: 'Required for PDF processing and document analysis',
          env_var: 'API_MISTRAL_KEY'
        },
        'openrouterKey': {
          type: 'password',
          required: true,
          group: 'api-keys',
          title: 'OpenRouter API Key',
          description: 'Required for AI research capabilities and language models',
          env_var: 'API_OPENROUTER_KEY'
        },
        'workspaceDirectory': {
          type: 'directory',
          required: true,
          group: 'directories',
          title: 'Workspace Directory',
          description: 'Path to your Thoth workspace (where you cloned project-thoth)',
          env_var: 'WORKSPACE_DIR'
        },
        'obsidianDirectory': {
          type: 'directory',
          required: true,
          group: 'directories',
          title: 'Obsidian Notes Directory',
          description: 'Directory in your vault where Thoth will store research notes',
          env_var: 'NOTES_DIR'
        },
        'remoteMode': {
          type: 'boolean',
          required: false,
          group: 'connection',
          title: 'Remote Mode',
          description: 'Connect to a remote Thoth server (WSL, Docker, or remote machine)',
          default: false
        },
        'remoteEndpointUrl': {
          type: 'text',
          required: false,
          group: 'connection',
          title: 'Remote Endpoint URL',
          description: 'Full URL of the remote Thoth server',
          validation: {
            pattern: '^https?://.+',
            message: 'Must be a valid HTTP/HTTPS URL'
          }
        },
        'primaryLlmModel': {
          type: 'select',
          required: true,
          group: 'llm',
          title: 'Primary LLM Model',
          description: 'Main language model for research and general tasks',
          options: [
            'anthropic/claude-3-opus',
            'anthropic/claude-3-sonnet',
            'anthropic/claude-3-haiku',
            'openai/gpt-4',
            'openai/gpt-4-turbo',
            'openai/gpt-3.5-turbo',
            'mistral/mistral-large',
            'mistral/mistral-medium'
          ],
          default: 'anthropic/claude-3-sonnet'
        },
        'showStatusBar': {
          type: 'boolean',
          required: false,
          group: 'ui',
          title: 'Show Status Bar',
          description: 'Display agent status in Obsidian status bar',
          default: true
        }
      }
    };
  }

  /**
   * Fallback validation when backend is unreachable
   */
  private fallbackValidation(config: Partial<ThothSettings>): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];

    // Basic validation for essential fields
    if (!config.mistralKey) {
      errors.push({
        field: 'mistralKey',
        message: 'Mistral API Key is required',
        code: 'REQUIRED_FIELD'
      });
    }

    if (!config.openrouterKey) {
      errors.push({
        field: 'openrouterKey',
        message: 'OpenRouter API Key is required',
        code: 'REQUIRED_FIELD'
      });
    }

    if (!config.workspaceDirectory) {
      errors.push({
        field: 'workspaceDirectory',
        message: 'Workspace Directory is required',
        code: 'REQUIRED_FIELD'
      });
    }

    if (config.remoteMode && !config.remoteEndpointUrl) {
      errors.push({
        field: 'remoteEndpointUrl',
        message: 'Remote Endpoint URL is required when Remote Mode is enabled',
        code: 'CONDITIONAL_REQUIRED'
      });
    }

    if (config.remoteEndpointUrl && !config.remoteEndpointUrl.match(/^https?:\/\/.+/)) {
      errors.push({
        field: 'remoteEndpointUrl',
        message: 'Remote Endpoint URL must be a valid HTTP/HTTPS URL',
        code: 'INVALID_FORMAT'
      });
    }

    return {
      is_valid: errors.length === 0,
      errors,
      warnings,
      error_count: errors.length,
      warning_count: warnings.length
    };
  }

  /**
   * Fallback partial validation when backend is unreachable
   */
  private fallbackPartialValidation(field: string, value: any): FieldValidationResult {
    switch (field) {
      case 'mistralKey':
      case 'openrouterKey':
      case 'workspaceDirectory':
        if (!value || (typeof value === 'string' && value.trim() === '')) {
          return {
            is_valid: false,
            error: 'This field is required'
          };
        }
        break;

      case 'remoteEndpointUrl':
        if (value && !value.match(/^https?:\/\/.+/)) {
          return {
            is_valid: false,
            error: 'Must be a valid HTTP/HTTPS URL'
          };
        }
        break;

      case 'endpointPort':
        const port = Number(value);
        if (isNaN(port) || port < 1000 || port > 65535) {
          return {
            is_valid: false,
            error: 'Port must be between 1000 and 65535'
          };
        }
        break;
    }

    return { is_valid: true };
  }

  /**
   * Clear schema cache
   */
  clearCache(): void {
    this.cache = null;
  }

  /**
   * Get cached schema if available and not expired
   */
  getCachedSchema(): UISchema | null {
    if (this.cache && Date.now() < this.cache.expires) {
      return this.cache.schema;
    }
    return null;
  }

  /**
   * Check if backend is reachable
   */
  async isBackendReachable(): Promise<boolean> {
    try {
      // Create abort controller for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(this.apiUtils.buildEndpointUrl(this.baseUrl, '/health'), {
        method: 'GET',
        signal: controller.signal
      });

      clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      return false;
    }
  }

  /**
   * Get schema version from backend
   */
  async getSchemaVersion(): Promise<string | null> {
    try {
      const response = await this.apiUtils.makeRequest(
        this.apiUtils.buildEndpointUrl(this.baseUrl, this.SCHEMA_VERSION_ENDPOINT)
      );

      if (response.ok) {
        const versionInfo = await response.json();
        return versionInfo.version;
      }
    } catch (error) {
      console.warn('Failed to get schema version:', error);
    }
    return null;
  }
}
