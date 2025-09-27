import { ThothSettings } from '../types';
import { SyncOperation, SyncResult, SyncOperationType } from './sync-service';
import { APIUtilities } from '../utils/api';

/**
 * Queue operation status
 */
export type QueueOperationStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'RETRY' | 'CANCELLED';

/**
 * Queue operation interface with enhanced metadata
 */
export interface QueuedOperation extends SyncOperation {
  status: QueueOperationStatus;
  attempts: number;
  lastAttempt?: number;
  nextRetry?: number;
  error?: string;
  estimatedDuration?: number;
  dependencies?: string[];
  priority: number;
}

/**
 * Queue status information
 */
export interface QueueStatus {
  totalOperations: number;
  pendingOperations: number;
  failedOperations: number;
  completedOperations: number;
  isProcessing: boolean;
  estimatedProcessingTime: number;
  lastProcessedAt?: number;
  connectionStatus: 'ONLINE' | 'OFFLINE' | 'CHECKING';
}

/**
 * Queue configuration
 */
export interface QueueConfig {
  maxQueueSize: number;
  maxRetries: number;
  retryDelayMs: number;
  maxRetryDelayMs: number;
  backoffMultiplier: number;
  connectionCheckIntervalMs: number;
  persistQueue: boolean;
  priorityLevels: number;
  batchSize: number;
}

/**
 * Offline sync queue interface
 */
export interface IOfflineSyncQueue {
  queueOperation(operation: SyncOperation): Promise<string>;
  processQueue(): Promise<SyncResult[]>;
  isOnline(): boolean;
  onConnectionChange(callback: (isOnline: boolean) => void): void;
  getQueueStatus(): QueueStatus;
  clearQueue(): void;
  cancelOperation(operationId: string): boolean;
  retryFailedOperations(): Promise<void>;
  getPendingOperations(): QueuedOperation[];
  getFailedOperations(): QueuedOperation[];

  // Priority management
  setPriority(operationId: string, priority: number): boolean;
  reorderQueue(): void;

  // Batch operations
  queueBatch(operations: SyncOperation[]): Promise<string[]>;
  processBatch(operationIds: string[]): Promise<SyncResult[]>;

  // Persistence
  saveQueueState(): Promise<void>;
  loadQueueState(): Promise<void>;

  // Endpoint management
  updateBaseUrl(newBaseUrl: string): void;

  destroy(): void;
}

/**
 * Implementation of offline sync queue with intelligent retry and prioritization
 */
export class OfflineSyncQueue implements IOfflineSyncQueue {
  private baseUrl: string;
  private apiUtilities: APIUtilities;
  private config: QueueConfig;
  private operationQueue: Map<string, QueuedOperation> = new Map();
  private isProcessingQueue: boolean = false;
  private connectionStatus: 'ONLINE' | 'OFFLINE' | 'CHECKING' = 'CHECKING';
  private connectionCallbacks: Array<(isOnline: boolean) => void> = [];
  private connectionCheckTimer: NodeJS.Timeout | null = null;
  private lastConnectionCheck: number = 0;
  private processingPromise: Promise<SyncResult[]> | null = null;

  constructor(baseUrl: string, config: Partial<QueueConfig> = {}) {
    this.baseUrl = baseUrl;
    this.apiUtilities = new APIUtilities();

    this.config = {
      maxQueueSize: 1000,
      maxRetries: 5,
      retryDelayMs: 1000,
      maxRetryDelayMs: 30000,
      backoffMultiplier: 2,
      connectionCheckIntervalMs: 5000,
      persistQueue: true,
      priorityLevels: 5,
      batchSize: 10,
      ...config
    };

    this.startConnectionMonitoring();

    if (this.config.persistQueue) {
      this.loadQueueState().catch(error => {
        console.warn('Failed to load queue state:', error);
      });
    }
  }

  async queueOperation(operation: SyncOperation): Promise<string> {
    if (this.operationQueue.size >= this.config.maxQueueSize) {
      throw new Error('Queue is full. Cannot add more operations.');
    }

    const queuedOperation: QueuedOperation = {
      ...operation,
      status: 'PENDING',
      attempts: 0,
      priority: operation.priority || 1
    };

    this.operationQueue.set(operation.id, queuedOperation);
    this.reorderQueue();

    if (this.config.persistQueue) {
      await this.saveQueueState();
    }

    console.log(`OfflineSyncQueue: Queued operation ${operation.id} (${operation.type})`);

    // Start processing if we're online and not already processing
    if (this.isOnline() && !this.isProcessingQueue) {
      this.processQueue().catch(error => {
        console.error('Queue processing failed:', error);
      });
    }

    return operation.id;
  }

  async processQueue(): Promise<SyncResult[]> {
    if (this.isProcessingQueue) {
      // Return existing processing promise if already running
      return this.processingPromise || Promise.resolve([]);
    }

    if (!this.isOnline()) {
      console.log('OfflineSyncQueue: Cannot process queue while offline');
      return [];
    }

    this.isProcessingQueue = true;
    const results: SyncResult[] = [];

    try {
      this.processingPromise = this.executeQueueProcessing();
      const processingResults = await this.processingPromise;
      results.push(...processingResults);
    } finally {
      this.isProcessingQueue = false;
      this.processingPromise = null;
    }

    return results;
  }

  private async executeQueueProcessing(): Promise<SyncResult[]> {
    const results: SyncResult[] = [];
    const pendingOperations = Array.from(this.operationQueue.values())
      .filter(op => op.status === 'PENDING' || op.status === 'RETRY')
      .sort((a, b) => b.priority - a.priority);

    console.log(`OfflineSyncQueue: Processing ${pendingOperations.length} operations`);

    // Process operations in batches
    for (let i = 0; i < pendingOperations.length; i += this.config.batchSize) {
      const batch = pendingOperations.slice(i, i + this.config.batchSize);
      const batchResults = await this.processBatch(batch.map(op => op.id));
      results.push(...batchResults);

      // Check if we're still online between batches
      if (!this.isOnline()) {
        console.log('OfflineSyncQueue: Going offline, stopping queue processing');
        break;
      }
    }

    return results;
  }

  async processBatch(operationIds: string[]): Promise<SyncResult[]> {
    const results: SyncResult[] = [];

    for (const operationId of operationIds) {
      const operation = this.operationQueue.get(operationId);
      if (!operation) continue;

      try {
        operation.status = 'IN_PROGRESS';
        operation.lastAttempt = Date.now();
        operation.attempts++;

        const result = await this.executeOperation(operation);

        if (result.success) {
          operation.status = 'COMPLETED';
          this.operationQueue.delete(operationId);
        } else {
          await this.handleOperationFailure(operation, result.errors?.[0] || 'Unknown error');
        }

        results.push(result);

      } catch (error) {
        await this.handleOperationFailure(operation, error.message);

        results.push({
          success: false,
          operationId: operationId,
          timestamp: Date.now(),
          errors: [error.message]
        });
      }
    }

    if (this.config.persistQueue) {
      await this.saveQueueState();
    }

    return results;
  }

  private async executeOperation(operation: QueuedOperation): Promise<SyncResult> {
    switch (operation.type) {
      case 'CONFIG_UPDATE':
        return await this.executeConfigUpdate(operation);
      case 'VALIDATION_REQUEST':
        return await this.executeValidation(operation);
      case 'SCHEMA_REFRESH':
        return await this.executeSchemaRefresh(operation);
      case 'FILE_SYNC':
        return await this.executeFileSync(operation);
      default:
        throw new Error(`Unknown operation type: ${operation.type}`);
    }
  }

  private async executeConfigUpdate(operation: QueuedOperation): Promise<SyncResult> {
    const response = await this.apiUtilities.makeRequestWithRetry(
      this.apiUtilities.buildEndpointUrl(this.baseUrl, '/config/import'),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          obsidian_config: operation.data.config,
          operation_id: operation.id
        })
      },
      2,
      10000
    );

    if (response.ok) {
      const result = await response.json();
      return {
        success: true,
        operationId: operation.id,
        timestamp: Date.now(),
        metadata: result
      };
    } else {
      throw new Error(`Config update failed: ${response.status} ${response.statusText}`);
    }
  }

  private async executeValidation(operation: QueuedOperation): Promise<SyncResult> {
    const response = await this.apiUtilities.makeRequestWithRetry(
      this.apiUtilities.buildEndpointUrl(this.baseUrl, '/config/validate'),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(operation.data)
      },
      2,
      5000
    );

    if (response.ok) {
      const validation = await response.json();
      return {
        success: validation.is_valid,
        operationId: operation.id,
        timestamp: Date.now(),
        errors: validation.errors || [],
        warnings: validation.warnings || []
      };
    } else {
      throw new Error(`Validation failed: ${response.status} ${response.statusText}`);
    }
  }

  private async executeSchemaRefresh(operation: QueuedOperation): Promise<SyncResult> {
    const response = await this.apiUtilities.makeRequestWithRetry(
      this.apiUtilities.buildEndpointUrl(this.baseUrl, '/config/schema'),
      { method: 'GET' },
      2,
      5000
    );

    if (response.ok) {
      const schema = await response.json();
      return {
        success: true,
        operationId: operation.id,
        timestamp: Date.now(),
        metadata: { schema }
      };
    } else {
      throw new Error(`Schema refresh failed: ${response.status} ${response.statusText}`);
    }
  }

  private async executeFileSync(operation: QueuedOperation): Promise<SyncResult> {
    // This would implement file synchronization logic
    // For now, return a success response
    return {
      success: true,
      operationId: operation.id,
      timestamp: Date.now(),
      metadata: { type: 'file_sync', data: operation.data }
    };
  }

  private async handleOperationFailure(operation: QueuedOperation, error: string): Promise<void> {
    operation.error = error;

    if (operation.attempts >= this.config.maxRetries) {
      operation.status = 'FAILED';
      console.error(`OfflineSyncQueue: Operation ${operation.id} failed permanently:`, error);
    } else {
      operation.status = 'RETRY';
      operation.nextRetry = this.calculateNextRetry(operation.attempts);
      console.warn(`OfflineSyncQueue: Operation ${operation.id} failed, will retry:`, error);
    }
  }

  private calculateNextRetry(attempts: number): number {
    const delay = Math.min(
      this.config.retryDelayMs * Math.pow(this.config.backoffMultiplier, attempts - 1),
      this.config.maxRetryDelayMs
    );
    return Date.now() + delay;
  }

  isOnline(): boolean {
    return this.connectionStatus === 'ONLINE';
  }

  onConnectionChange(callback: (isOnline: boolean) => void): void {
    this.connectionCallbacks.push(callback);
  }

  getQueueStatus(): QueueStatus {
    const operations = Array.from(this.operationQueue.values());
    const pending = operations.filter(op => op.status === 'PENDING' || op.status === 'RETRY').length;
    const failed = operations.filter(op => op.status === 'FAILED').length;
    const completed = operations.filter(op => op.status === 'COMPLETED').length;

    return {
      totalOperations: operations.length,
      pendingOperations: pending,
      failedOperations: failed,
      completedOperations: completed,
      isProcessing: this.isProcessingQueue,
      estimatedProcessingTime: this.calculateEstimatedProcessingTime(),
      lastProcessedAt: this.lastConnectionCheck,
      connectionStatus: this.connectionStatus
    };
  }

  clearQueue(): void {
    this.operationQueue.clear();
    if (this.config.persistQueue) {
      this.saveQueueState().catch(error => {
        console.error('Failed to save queue state after clearing:', error);
      });
    }
    console.log('OfflineSyncQueue: Queue cleared');
  }

  cancelOperation(operationId: string): boolean {
    const operation = this.operationQueue.get(operationId);
    if (operation && operation.status !== 'COMPLETED') {
      operation.status = 'CANCELLED';
      this.operationQueue.delete(operationId);
      return true;
    }
    return false;
  }

  async retryFailedOperations(): Promise<void> {
    const failedOperations = Array.from(this.operationQueue.values())
      .filter(op => op.status === 'FAILED');

    for (const operation of failedOperations) {
      operation.status = 'RETRY';
      operation.attempts = 0;
      operation.error = undefined;
      operation.nextRetry = undefined;
    }

    if (this.isOnline()) {
      await this.processQueue();
    }
  }

  getPendingOperations(): QueuedOperation[] {
    return Array.from(this.operationQueue.values())
      .filter(op => op.status === 'PENDING' || op.status === 'RETRY');
  }

  getFailedOperations(): QueuedOperation[] {
    return Array.from(this.operationQueue.values())
      .filter(op => op.status === 'FAILED');
  }

  setPriority(operationId: string, priority: number): boolean {
    const operation = this.operationQueue.get(operationId);
    if (operation) {
      operation.priority = Math.max(1, Math.min(priority, this.config.priorityLevels));
      this.reorderQueue();
      return true;
    }
    return false;
  }

  reorderQueue(): void {
    // Queue is automatically ordered by priority when processing
    // This method is here for explicit reordering if needed
  }

  async queueBatch(operations: SyncOperation[]): Promise<string[]> {
    const operationIds: string[] = [];

    for (const operation of operations) {
      const id = await this.queueOperation(operation);
      operationIds.push(id);
    }

    return operationIds;
  }

  async saveQueueState(): Promise<void> {
    try {
      const queueData = {
        operations: Array.from(this.operationQueue.entries()),
        timestamp: Date.now()
      };

      localStorage.setItem('thoth-sync-queue', JSON.stringify(queueData));
    } catch (error) {
      console.error('Failed to save queue state:', error);
    }
  }

  async loadQueueState(): Promise<void> {
    try {
      const stored = localStorage.getItem('thoth-sync-queue');
      if (stored) {
        const queueData = JSON.parse(stored);
        this.operationQueue = new Map(queueData.operations);
        console.log(`OfflineSyncQueue: Loaded ${this.operationQueue.size} operations from storage`);
      }
    } catch (error) {
      console.error('Failed to load queue state:', error);
    }
  }

  destroy(): void {
    if (this.connectionCheckTimer) {
      clearInterval(this.connectionCheckTimer);
      this.connectionCheckTimer = null;
    }

    if (this.config.persistQueue) {
      this.saveQueueState().catch(error => {
        console.error('Failed to save queue state on destroy:', error);
      });
    }

    this.operationQueue.clear();
    this.connectionCallbacks = [];
  }

  // Private helper methods

  private startConnectionMonitoring(): void {
    this.connectionCheckTimer = setInterval(async () => {
      await this.checkConnection();
    }, this.config.connectionCheckIntervalMs);

    // Initial connection check
    this.checkConnection();
  }

  private async checkConnection(): Promise<void> {
    const previousStatus = this.connectionStatus;
    this.connectionStatus = 'CHECKING';
    this.lastConnectionCheck = Date.now();

    try {
      const isOnline = await this.apiUtilities.isBackendOnline(this.baseUrl);
      const wasOnline = previousStatus === 'ONLINE';

      this.connectionStatus = isOnline ? 'ONLINE' : 'OFFLINE';

      // Trigger callbacks if status changed
      if (wasOnline !== isOnline) {
        this.triggerConnectionCallbacks(isOnline);

        // Start processing queue if we just came online
        if (isOnline && !this.isProcessingQueue && this.operationQueue.size > 0) {
          this.processQueue().catch(error => {
            console.error('Failed to process queue after coming online:', error);
          });
        }
      }
    } catch (error) {
      this.connectionStatus = 'OFFLINE';
      console.warn('Connection check failed:', error);
    }
  }

  private triggerConnectionCallbacks(isOnline: boolean): void {
    for (const callback of this.connectionCallbacks) {
      try {
        callback(isOnline);
      } catch (error) {
        console.error('Connection callback error:', error);
      }
    }
  }

  private calculateEstimatedProcessingTime(): number {
    const pendingOperations = this.getPendingOperations();
    const avgOperationTime = 2000; // 2 seconds average per operation
    return pendingOperations.length * avgOperationTime;
  }

  // Update base URL when endpoint changes
  updateBaseUrl(newBaseUrl: string): void {
    this.baseUrl = newBaseUrl;
  }
}
