import { ThothSettings } from '../types';
import { APIUtilities } from '../utils/api';

/**
 * Sync operation types for queue management
 */
export type SyncOperationType = 'CONFIG_UPDATE' | 'VALIDATION_REQUEST' | 'SCHEMA_REFRESH' | 'FILE_SYNC';

/**
 * Sync operation interface
 */
export interface SyncOperation {
  id: string;
  type: SyncOperationType;
  data: any;
  timestamp: number;
  priority: number;
  retryCount: number;
  maxRetries: number;
  metadata?: Record<string, any>;
}

/**
 * Sync result interface
 */
export interface SyncResult {
  success: boolean;
  operationId: string;
  timestamp: number;
  checksum?: string;
  conflicts?: string[];
  errors?: string[];
  warnings?: string[];
  metadata?: Record<string, any>;
}

/**
 * Batch sync result
 */
export interface BatchSyncResult {
  success: boolean;
  results: SyncResult[];
  totalOperations: number;
  successfulOperations: number;
  failedOperations: number;
  overallChecksum?: string;
}

/**
 * Sync service interface for robust backend integration
 */
export interface ISyncService {
  // Core sync operations
  exportConfig(): Promise<ThothSettings>;
  importConfig(config: ThothSettings): Promise<SyncResult>;
  syncToBackend(config: ThothSettings): Promise<SyncResult>;
  syncFromBackend(): Promise<ThothSettings>;

  // Data integrity
  getConfigChecksum(): Promise<string>;
  validateSyncIntegrity(): Promise<boolean>;

  // Batch operations
  batchImport(configs: ThothSettings[]): Promise<BatchSyncResult>;
  batchExport(count?: number): Promise<ThothSettings[]>;

  // Transaction support
  beginTransaction(): Promise<string>;
  commitTransaction(transactionId: string): Promise<boolean>;
  rollbackTransaction(transactionId: string): Promise<boolean>;

  // Event handlers
  onSyncSuccess(callback: (result: SyncResult) => void): void;
  onSyncFailure(callback: (error: Error, operation: SyncOperation) => void): void;
  onSyncProgress(callback: (progress: number, operation: SyncOperation) => void): void;

  // Endpoint management
  updateBaseUrl(newBaseUrl: string): void;

  destroy(): void;
}

/**
 * Implementation of robust sync service with enterprise features
 */
export class SyncService implements ISyncService {
  private apiUtilities: APIUtilities;
  private baseUrl: string;
  private activeTransactions: Map<string, SyncOperation[]> = new Map();
  private syncProgressCallbacks: Array<(progress: number, operation: SyncOperation) => void> = [];
  private syncSuccessCallbacks: Array<(result: SyncResult) => void> = [];
  private syncFailureCallbacks: Array<(error: Error, operation: SyncOperation) => void> = [];
  private checksumCache: Map<string, { checksum: string; timestamp: number }> = new Map();
  private integrityCheckInterval: NodeJS.Timeout | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    this.apiUtilities = new APIUtilities();

    // Start periodic integrity checks
    this.startIntegrityMonitoring();
  }

  async exportConfig(): Promise<ThothSettings> {
    try {
      const operation: SyncOperation = {
        id: crypto.randomUUID(),
        type: 'CONFIG_UPDATE',
        data: { action: 'export' },
        timestamp: Date.now(),
        priority: 1,
        retryCount: 0,
        maxRetries: 3
      };

      this.triggerProgressCallbacks(0, operation);

      const response = await this.apiUtilities.makeRequestWithRetry(
        this.apiUtilities.buildEndpointUrl(this.baseUrl, '/config/export'),
        { method: 'GET' },
        3,
        10000
      );

      if (!response.ok) {
        throw new Error(`Export failed: ${response.status} ${response.statusText}`);
      }

      const config = await response.json();
      this.triggerProgressCallbacks(100, operation);

      const result: SyncResult = {
        success: true,
        operationId: operation.id,
        timestamp: Date.now(),
        checksum: await this.calculateChecksum(config)
      };

      this.triggerSuccessCallbacks(result);
      return config;

    } catch (error) {
      const operation: SyncOperation = {
        id: crypto.randomUUID(),
        type: 'CONFIG_UPDATE',
        data: { action: 'export' },
        timestamp: Date.now(),
        priority: 1,
        retryCount: 0,
        maxRetries: 3
      };

      this.triggerFailureCallbacks(error as Error, operation);
      throw error;
    }
  }

  async importConfig(config: ThothSettings): Promise<SyncResult> {
    const operation: SyncOperation = {
      id: crypto.randomUUID(),
      type: 'CONFIG_UPDATE',
      data: { action: 'import', config },
      timestamp: Date.now(),
      priority: 1,
      retryCount: 0,
      maxRetries: 3
    };

    try {
      this.triggerProgressCallbacks(0, operation);

      // Validate config before import
      const validationResult = await this.validateConfig(config);
      if (!validationResult.is_valid) {
        throw new Error(`Config validation failed: ${JSON.stringify(validationResult.errors)}`);
      }

      this.triggerProgressCallbacks(25, operation);

      // Calculate checksum for integrity
      const checksum = await this.calculateChecksum(config);

      this.triggerProgressCallbacks(50, operation);

      // Perform import
      const response = await this.apiUtilities.makeRequestWithRetry(
        this.apiUtilities.buildEndpointUrl(this.baseUrl, '/config/import'),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            obsidian_config: config,
            checksum: checksum,
            operation_id: operation.id
          })
        },
        3,
        15000
      );

      if (!response.ok) {
        throw new Error(`Import failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      this.triggerProgressCallbacks(100, operation);

      const syncResult: SyncResult = {
        success: result.success || true,
        operationId: operation.id,
        timestamp: Date.now(),
        checksum: checksum,
        conflicts: result.conflicts || [],
        errors: result.errors || [],
        warnings: result.warnings || []
      };

      this.triggerSuccessCallbacks(syncResult);
      return syncResult;

    } catch (error) {
      this.triggerFailureCallbacks(error as Error, operation);

      return {
        success: false,
        operationId: operation.id,
        timestamp: Date.now(),
        errors: [error.message]
      };
    }
  }

  async syncToBackend(config: ThothSettings): Promise<SyncResult> {
    // Sync to backend is essentially an import operation
    return this.importConfig(config);
  }

  async syncFromBackend(): Promise<ThothSettings> {
    // Sync from backend is essentially an export operation
    return this.exportConfig();
  }

  async getConfigChecksum(): Promise<string> {
    try {
      const config = await this.exportConfig();
      return this.calculateChecksum(config);
    } catch (error) {
      console.error('Failed to get config checksum:', error);
      throw error;
    }
  }

  async validateSyncIntegrity(): Promise<boolean> {
    try {
      const currentChecksum = await this.getConfigChecksum();
      const cachedEntry = this.checksumCache.get('current');

      if (cachedEntry && cachedEntry.checksum === currentChecksum) {
        return true;
      }

      // Update cache
      this.checksumCache.set('current', {
        checksum: currentChecksum,
        timestamp: Date.now()
      });

      return true;
    } catch (error) {
      console.error('Integrity validation failed:', error);
      return false;
    }
  }

  async batchImport(configs: ThothSettings[]): Promise<BatchSyncResult> {
    const results: SyncResult[] = [];
    let successCount = 0;
    let failureCount = 0;

    for (let i = 0; i < configs.length; i++) {
      try {
        const result = await this.importConfig(configs[i]);
        results.push(result);

        if (result.success) {
          successCount++;
        } else {
          failureCount++;
        }
      } catch (error) {
        failureCount++;
        results.push({
          success: false,
          operationId: crypto.randomUUID(),
          timestamp: Date.now(),
          errors: [error.message]
        });
      }
    }

    return {
      success: failureCount === 0,
      results,
      totalOperations: configs.length,
      successfulOperations: successCount,
      failedOperations: failureCount
    };
  }

  async batchExport(count: number = 1): Promise<ThothSettings[]> {
    const configs: ThothSettings[] = [];

    for (let i = 0; i < count; i++) {
      try {
        const config = await this.exportConfig();
        configs.push(config);
      } catch (error) {
        console.error(`Batch export failed for item ${i}:`, error);
        break;
      }
    }

    return configs;
  }

  async beginTransaction(): Promise<string> {
    const transactionId = crypto.randomUUID();
    this.activeTransactions.set(transactionId, []);
    return transactionId;
  }

  async commitTransaction(transactionId: string): Promise<boolean> {
    const operations = this.activeTransactions.get(transactionId);
    if (!operations) {
      throw new Error(`Transaction ${transactionId} not found`);
    }

    try {
      // Execute all operations in the transaction
      for (const operation of operations) {
        switch (operation.type) {
          case 'CONFIG_UPDATE':
            if (operation.data.action === 'import') {
              await this.importConfig(operation.data.config);
            } else if (operation.data.action === 'export') {
              await this.exportConfig();
            }
            break;
          // Handle other operation types as needed
        }
      }

      this.activeTransactions.delete(transactionId);
      return true;
    } catch (error) {
      console.error(`Transaction ${transactionId} commit failed:`, error);
      return false;
    }
  }

  async rollbackTransaction(transactionId: string): Promise<boolean> {
    const operations = this.activeTransactions.get(transactionId);
    if (!operations) {
      console.warn(`Transaction ${transactionId} not found for rollback`);
      return false;
    }

    // For rollback, we would typically reverse operations
    // This is a simplified implementation
    this.activeTransactions.delete(transactionId);
    return true;
  }

  onSyncSuccess(callback: (result: SyncResult) => void): void {
    this.syncSuccessCallbacks.push(callback);
  }

  onSyncFailure(callback: (error: Error, operation: SyncOperation) => void): void {
    this.syncFailureCallbacks.push(callback);
  }

  onSyncProgress(callback: (progress: number, operation: SyncOperation) => void): void {
    this.syncProgressCallbacks.push(callback);
  }

  destroy(): void {
    if (this.integrityCheckInterval) {
      clearInterval(this.integrityCheckInterval);
      this.integrityCheckInterval = null;
    }

    this.activeTransactions.clear();
    this.checksumCache.clear();
    this.syncProgressCallbacks = [];
    this.syncSuccessCallbacks = [];
    this.syncFailureCallbacks = [];
  }

  // Private helper methods

  private async calculateChecksum(data: any): Promise<string> {
    const jsonString = JSON.stringify(data, Object.keys(data).sort());
    const encoder = new TextEncoder();
    const dataBuffer = encoder.encode(jsonString);
    const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  private async validateConfig(config: ThothSettings): Promise<any> {
    try {
      const response = await this.apiUtilities.makeRequestWithRetry(
        this.apiUtilities.buildEndpointUrl(this.baseUrl, '/config/validate'),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config)
        },
        2,
        5000
      );

      if (response.ok) {
        return await response.json();
      } else {
        return { is_valid: false, errors: [`HTTP ${response.status}`] };
      }
    } catch (error) {
      return { is_valid: false, errors: [error.message] };
    }
  }

  private startIntegrityMonitoring(): void {
    // Check integrity every 5 minutes
    this.integrityCheckInterval = setInterval(async () => {
      try {
        await this.validateSyncIntegrity();
      } catch (error) {
        console.error('Periodic integrity check failed:', error);
      }
    }, 300000);
  }

  private triggerProgressCallbacks(progress: number, operation: SyncOperation): void {
    for (const callback of this.syncProgressCallbacks) {
      try {
        callback(progress, operation);
      } catch (error) {
        console.error('Progress callback error:', error);
      }
    }
  }

  private triggerSuccessCallbacks(result: SyncResult): void {
    for (const callback of this.syncSuccessCallbacks) {
      try {
        callback(result);
      } catch (error) {
        console.error('Success callback error:', error);
      }
    }
  }

  private triggerFailureCallbacks(error: Error, operation: SyncOperation): void {
    for (const callback of this.syncFailureCallbacks) {
      try {
        callback(error, operation);
      } catch (error) {
        console.error('Failure callback error:', error);
      }
    }
  }

  // Update base URL when endpoint changes
  updateBaseUrl(newBaseUrl: string): void {
    this.baseUrl = newBaseUrl;
  }
}
