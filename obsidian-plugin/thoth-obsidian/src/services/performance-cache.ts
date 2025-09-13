/**
 * Performance caching system for frontend operations.
 *
 * Provides intelligent caching for schemas, validation results, UI state,
 * and performance metrics to optimize user experience.
 */

import { FieldSchema, UISchema, ValidationResult, FieldValidationResult } from './schema-service';
import { ThothSettings } from '../types';

/**
 * Cache strategy types
 */
export type CacheStrategy = 'lru' | 'lfu' | 'ttl' | 'adaptive';

/**
 * Cache entry with metadata
 */
interface CacheEntry<T = any> {
  key: string;
  value: T;
  timestamp: number;
  accessCount: number;
  lastAccessed: number;
  ttl?: number;
  sizeBytes: number;
}

/**
 * Cache performance metrics
 */
export interface CacheMetrics {
  cacheName: string;
  totalSize: number;
  usedSize: number;
  hitCount: number;
  missCount: number;
  hitRatio: number;
  evictionCount: number;
  memoryUsageMB: number;
  entryCount: number;
  averageAccessTime: number;
}

/**
 * Performance metrics for operations
 */
export interface PerformanceMetrics {
  operationName: string;
  totalCalls: number;
  totalDuration: number;
  averageDuration: number;
  minDuration: number;
  maxDuration: number;
  cacheHits: number;
  cacheMisses: number;
  cacheHitRatio: number;
  optimizationOpportunities: string[];
}

/**
 * Intelligent cache implementation
 */
class IntelligentCache<T = any> {
  public cache: Map<string, CacheEntry<T>> = new Map();
  private accessTimes: number[] = [];
  private hitCount: number = 0;
  private missCount: number = 0;
  private evictionCount: number = 0;
  private accessPatterns: Map<string, number[]> = new Map();

  constructor(
    private name: string,
    private maxSize: number = 1000,
    public strategy: CacheStrategy = 'adaptive',
    private defaultTtl?: number
  ) {}

  get(key: string): T | null {
    const entry = this.cache.get(key);

    if (!entry) {
      this.missCount++;
      return null;
    }

    // Check TTL expiration
    if (entry.ttl && (Date.now() - entry.timestamp) > entry.ttl * 1000) {
      this.cache.delete(key);
      this.missCount++;
      return null;
    }

    // Update access metadata
    entry.lastAccessed = Date.now();
    entry.accessCount++;

    // Track access patterns
    this.trackAccessPattern(key);

    this.hitCount++;
    this.accessTimes.push(performance.now());

    return entry.value;
  }

  put(key: string, value: T, ttl?: number): void {
    // Calculate value size (rough estimate)
    const sizeBytes = this.estimateSize(value);

    // Create cache entry
    const entry: CacheEntry<T> = {
      key,
      value,
      timestamp: Date.now(),
      accessCount: 1,
      lastAccessed: Date.now(),
      ttl: ttl || this.defaultTtl,
      sizeBytes
    };

    // Check if we need to evict entries
    if (this.cache.size >= this.maxSize) {
      this.evictEntries();
    }

    this.cache.set(key, entry);
    this.trackAccessPattern(key);
  }

  invalidate(key: string): boolean {
    return this.cache.delete(key);
  }

  clear(): void {
    this.cache.clear();
    this.accessPatterns.clear();
    this.hitCount = 0;
    this.missCount = 0;
    this.evictionCount = 0;
    this.accessTimes = [];
  }

  getMetrics(): CacheMetrics {
    const totalRequests = this.hitCount + this.missCount;
    const hitRatio = totalRequests > 0 ? this.hitCount / totalRequests : 0;

    // Calculate memory usage
    const memoryUsage = Array.from(this.cache.values())
      .reduce((total, entry) => total + entry.sizeBytes, 0) / (1024 * 1024);

    // Calculate average access time
    const avgAccessTime = this.accessTimes.length > 0
      ? this.accessTimes.reduce((sum, time) => sum + time, 0) / this.accessTimes.length
      : 0;

    return {
      cacheName: this.name,
      totalSize: this.maxSize,
      usedSize: this.cache.size,
      hitCount: this.hitCount,
      missCount: this.missCount,
      hitRatio,
      evictionCount: this.evictionCount,
      memoryUsageMB: memoryUsage,
      entryCount: this.cache.size,
      averageAccessTime: avgAccessTime
    };
  }

  private trackAccessPattern(key: string): void {
    const now = Date.now();
    const patterns = this.accessPatterns.get(key) || [];
    patterns.push(now);

    // Keep only recent accesses (last hour)
    const cutoff = now - (60 * 60 * 1000);
    const recentAccesses = patterns.filter(time => time > cutoff);
    this.accessPatterns.set(key, recentAccesses);
  }

  private evictEntries(): void {
    if (this.cache.size === 0) return;

    switch (this.strategy) {
      case 'lru':
        this.evictLRU();
        break;
      case 'lfu':
        this.evictLFU();
        break;
      case 'ttl':
        this.evictExpired();
        break;
      case 'adaptive':
        this.evictAdaptive();
        break;
      default:
        this.evictLRU();
    }
  }

  private evictLRU(): void {
    let oldestKey = '';
    let oldestTime = Infinity;

    for (const [key, entry] of this.cache.entries()) {
      if (entry.lastAccessed < oldestTime) {
        oldestTime = entry.lastAccessed;
        oldestKey = key;
      }
    }

    if (oldestKey) {
      this.cache.delete(oldestKey);
      this.evictionCount++;
    }
  }

  private evictLFU(): void {
    let leastUsedKey = '';
    let leastUsedCount = Infinity;

    for (const [key, entry] of this.cache.entries()) {
      if (entry.accessCount < leastUsedCount) {
        leastUsedCount = entry.accessCount;
        leastUsedKey = key;
      }
    }

    if (leastUsedKey) {
      this.cache.delete(leastUsedKey);
      this.evictionCount++;
    }
  }

  public evictExpired(): void {
    const now = Date.now();
    let evictedAny = false;

    for (const [key, entry] of this.cache.entries()) {
      if (entry.ttl && (now - entry.timestamp) > entry.ttl * 1000) {
        this.cache.delete(key);
        this.evictionCount++;
        evictedAny = true;
      }
    }

    // If no expired entries, fall back to LRU
    if (!evictedAny) {
      this.evictLRU();
    }
  }

  private evictAdaptive(): void {
    const now = Date.now();
    let worstKey = '';
    let worstScore = Infinity;

    for (const [key, entry] of this.cache.entries()) {
      // Calculate composite score (recency + frequency)
      const recencyScore = 1.0 / Math.max((now - entry.lastAccessed) / 1000, 1.0);
      const frequencyScore = this.accessPatterns.get(key)?.length || 0;
      const compositeScore = recencyScore * 0.3 + frequencyScore * 0.7;

      if (compositeScore < worstScore) {
        worstScore = compositeScore;
        worstKey = key;
      }
    }

    if (worstKey) {
      this.cache.delete(worstKey);
      this.evictionCount++;
    }
  }

  private estimateSize(value: any): number {
    try {
      if (typeof value === 'string') {
        return value.length * 2; // Rough Unicode estimate
      } else if (typeof value === 'object' && value !== null) {
        return JSON.stringify(value).length * 2;
      } else if (typeof value === 'number') {
        return 8;
      } else if (typeof value === 'boolean') {
        return 1;
      }
      return 100; // Default estimate
    } catch {
      return 100;
    }
  }
}

/**
 * Performance cache manager for settings operations
 */
export class PerformanceCacheManager {
  private caches: Map<string, IntelligentCache> = new Map();
  private operationTimings: Map<string, number[]> = new Map();
  private operationStartTimes: Map<string, number> = new Map();
  private enableMonitoring: boolean = true;
  private hitCount: number = 0;
  private missCount: number = 0;

  constructor() {
    this.initializeStandardCaches();
  }

  private initializeStandardCaches(): void {
    // Schema cache with TTL strategy (schemas don't change often)
    this.caches.set('schema', new IntelligentCache(
      'schema_cache',
      50,
      'ttl',
      3600 // 1 hour TTL
    ));

    // Validation cache with adaptive strategy (validation patterns vary)
    this.caches.set('validation', new IntelligentCache(
      'validation_cache',
      200,
      'adaptive',
      300 // 5 minutes TTL
    ));

    // UI state cache with LRU strategy (UI state changes frequently)
    this.caches.set('ui_state', new IntelligentCache(
      'ui_state_cache',
      100,
      'lru',
      1800 // 30 minutes TTL
    ));

    // Configuration cache with LFU strategy (frequently accessed configs stay)
    this.caches.set('config', new IntelligentCache(
      'config_cache',
      50,
      'lfu',
      1800 // 30 minutes TTL
    ));
  }

  /**
   * Cache schema with intelligent invalidation
   */
  cacheSchema(schemaVersion: string, schema: UISchema, ttl?: number): void {
    const schemaCache = this.caches.get('schema');
    if (schemaCache) {
      schemaCache.put(`schema_${schemaVersion}`, schema, ttl);
    }
  }

  /**
   * Get cached schema
   */
  getCachedSchema(schemaVersion: string): UISchema | null {
    const schemaCache = this.caches.get('schema');
    return schemaCache ? schemaCache.get(`schema_${schemaVersion}`) : null;
  }

  /**
   * Cache validation result for unchanged fields
   */
  cacheValidationResult(fieldName: string, value: any, result: FieldValidationResult, ttl?: number): void {
    const validationCache = this.caches.get('validation');
    if (validationCache) {
      const cacheKey = this.generateValidationCacheKey(fieldName, value);
      validationCache.put(cacheKey, result, ttl);
    }
  }

  /**
   * Get cached validation result
   */
  getCachedValidationResult(fieldName: string, value: any): FieldValidationResult | null {
    const validationCache = this.caches.get('validation');
    if (validationCache) {
      const cacheKey = this.generateValidationCacheKey(fieldName, value);
      return validationCache.get(cacheKey);
    }
    return null;
  }

  /**
   * Cache UI state for faster switching
   */
  cacheUIState(stateKey: string, state: any, ttl?: number): void {
    const uiStateCache = this.caches.get('ui_state');
    if (uiStateCache) {
      uiStateCache.put(stateKey, state, ttl);
    }
  }

  /**
   * Get cached UI state
   */
  getCachedUIState(stateKey: string): any | null {
    const uiStateCache = this.caches.get('ui_state');
    return uiStateCache ? uiStateCache.get(stateKey) : null;
  }

  /**
   * Cache configuration data
   */
  cacheConfiguration(configKey: string, config: Partial<ThothSettings>, ttl?: number): void {
    const configCache = this.caches.get('config');
    if (configCache) {
      configCache.put(configKey, config, ttl);
    }
  }

  /**
   * Get cached configuration
   */
  getCachedConfiguration(configKey: string): Partial<ThothSettings> | null {
    const configCache = this.caches.get('config');
    return configCache ? configCache.get(configKey) : null;
  }

  /**
   * Invalidate cache entries for a specific field
   */
  invalidateFieldCache(fieldName: string): void {
    const validationCache = this.caches.get('validation');
    if (validationCache) {
      // Find and remove all entries for this field
      const keysToRemove: string[] = [];
      for (const [key] of validationCache.cache.entries()) {
        if (key.startsWith(`validation_${fieldName}_`)) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach(key => validationCache.invalidate(key));
    }
  }

  /**
   * Invalidate all schema caches
   */
  invalidateSchemaCache(): void {
    const schemaCache = this.caches.get('schema');
    if (schemaCache) {
      schemaCache.clear();
    }
  }

  /**
   * Start operation timing
   */
  startOperationTiming(operationId: string): void {
    if (this.enableMonitoring) {
      this.operationStartTimes.set(operationId, performance.now());
    }
  }

  /**
   * End operation timing and record duration
   */
  endOperationTiming(operationId: string, operationName: string): number | null {
    if (!this.enableMonitoring || !this.operationStartTimes.has(operationId)) {
      return null;
    }

    const startTime = this.operationStartTimes.get(operationId)!;
    const duration = performance.now() - startTime;

    this.operationStartTimes.delete(operationId);

    // Record timing
    if (!this.operationTimings.has(operationName)) {
      this.operationTimings.set(operationName, []);
    }

    const timings = this.operationTimings.get(operationName)!;
    timings.push(duration);

    // Keep only recent timings (last 1000)
    if (timings.length > 1000) {
      timings.splice(0, timings.length - 1000);
    }

    return duration;
  }

  /**
   * Get performance metrics for all operations
   */
  getPerformanceMetrics(): Record<string, PerformanceMetrics> {
    const metrics: Record<string, PerformanceMetrics> = {};

    for (const [operationName, timings] of this.operationTimings.entries()) {
      if (timings.length === 0) continue;

      const totalDuration = timings.reduce((sum, time) => sum + time, 0);
      const averageDuration = totalDuration / timings.length;
      const minDuration = Math.min(...timings);
      const maxDuration = Math.max(...timings);

      // Get cache stats (simplified)
      const cacheHits = this.hitCount;
      const cacheMisses = this.missCount;
      const cacheHitRatio = (cacheHits + cacheMisses) > 0 ? cacheHits / (cacheHits + cacheMisses) : 0;

      // Generate optimization opportunities
      const optimizationOpportunities = this.generateOptimizationOpportunities(operationName, timings);

      metrics[operationName] = {
        operationName,
        totalCalls: timings.length,
        totalDuration,
        averageDuration,
        minDuration,
        maxDuration,
        cacheHits,
        cacheMisses,
        cacheHitRatio,
        optimizationOpportunities
      };
    }

    return metrics;
  }

  /**
   * Get cache metrics for all caches
   */
  getCacheMetrics(): Record<string, CacheMetrics> {
    const metrics: Record<string, CacheMetrics> = {};

    for (const [name, cache] of this.caches.entries()) {
      metrics[name] = cache.getMetrics();
    }

    return metrics;
  }

  /**
   * Optimize cache configuration based on usage patterns
   */
  optimizeCacheConfiguration(cacheName: string): Record<string, any> {
    const cache = this.caches.get(cacheName);
    if (!cache) {
      return { error: `Cache ${cacheName} not found` };
    }

    const metrics = cache.getMetrics();
    const optimizations: Record<string, any> = {};

    // Optimize cache size
    if (metrics.hitRatio < 0.3 && metrics.usedSize < metrics.totalSize * 0.5) {
      optimizations.suggestedMaxSize = Math.max(metrics.usedSize * 2, 50);
      optimizations.reason = 'Low hit ratio with underutilized cache';
    }

    // Optimize strategy
    if (metrics.hitRatio < 0.5) {
      if (cache.strategy === 'lru') {
        optimizations.suggestedStrategy = 'adaptive';
        optimizations.strategyReason = 'LRU not effective, try adaptive strategy';
      }
    }

    return optimizations;
  }

  /**
   * Preload frequently accessed data
   */
  async preloadFrequentData(): Promise<void> {
    try {
      // Preload schema if not cached
      const schemaCache = this.caches.get('schema');
      if (schemaCache && schemaCache.cache.size === 0) {
        // This would typically trigger a schema load
        console.log('Preloading schema data...');
      }

      // Preload common UI states
      const uiStateCache = this.caches.get('ui_state');
      if (uiStateCache) {
        // Cache common UI states
        this.cacheUIState('default_form_state', {
          activeTab: 0,
          expandedGroups: ['API Keys', 'Directories'],
          showAdvanced: false
        });
      }

    } catch (error) {
      console.error('Failed to preload frequent data:', error);
    }
  }

  /**
   * Generate cache key for validation results
   */
  private generateValidationCacheKey(fieldName: string, value: any): string {
    // Create a stable key based on field name and value
    const valueHash = this.hashValue(value);
    return `validation_${fieldName}_${valueHash}`;
  }

  /**
   * Hash a value for cache key generation
   */
  private hashValue(value: any): string {
    try {
      const str = typeof value === 'string' ? value : JSON.stringify(value);
      let hash = 0;
      for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32-bit integer
      }
      return Math.abs(hash).toString(36);
    } catch {
      return 'unknown';
    }
  }

  /**
   * Generate optimization opportunities for operations
   */
  private generateOptimizationOpportunities(operationName: string, timings: number[]): string[] {
    const opportunities: string[] = [];
    const avgDuration = timings.reduce((sum, time) => sum + time, 0) / timings.length;

    if (avgDuration > 500) { // More than 500ms
      opportunities.push('Consider adding caching');
    }

    if (avgDuration > 1000) { // More than 1 second
      opportunities.push('Consider async processing');
    }

    if (timings.length > 100 && Math.max(...timings) > avgDuration * 5) {
      opportunities.push('Investigate performance outliers');
    }

    const cacheMetrics = this.getCacheMetrics();
    const relevantCache = Object.values(cacheMetrics).find(cache =>
      cache.cacheName.includes(operationName.toLowerCase())
    );

    if (relevantCache && relevantCache.hitRatio < 0.5) {
      opportunities.push('Improve cache hit ratio');
    }

    return opportunities;
  }

  /**
   * Clean up expired entries across all caches
   */
  cleanupExpiredEntries(): number {
    let totalCleaned = 0;

    for (const cache of this.caches.values()) {
      const initialSize = cache.cache.size;
      cache.evictExpired();
      totalCleaned += initialSize - cache.cache.size;
    }

    return totalCleaned;
  }

  /**
   * Get memory usage across all caches
   */
  getTotalMemoryUsage(): number {
    return Object.values(this.getCacheMetrics())
      .reduce((total, metrics) => total + metrics.memoryUsageMB, 0);
  }

  /**
   * Create performance report
   */
  generatePerformanceReport(): Record<string, any> {
    return {
      cacheMetrics: this.getCacheMetrics(),
      performanceMetrics: this.getPerformanceMetrics(),
      totalMemoryUsageMB: this.getTotalMemoryUsage(),
      monitoringEnabled: this.enableMonitoring,
      generatedAt: new Date().toISOString(),
      recommendations: this.generatePerformanceRecommendations()
    };
  }

  /**
   * Generate performance recommendations
   */
  private generatePerformanceRecommendations(): string[] {
    const recommendations: string[] = [];
    const cacheMetrics = this.getCacheMetrics();
    const memoryUsage = this.getTotalMemoryUsage();

    // Memory usage recommendations
    if (memoryUsage > 50) {
      recommendations.push('High memory usage detected - consider reducing cache sizes');
    }

    // Cache efficiency recommendations
    for (const [cacheName, metrics] of Object.entries(cacheMetrics)) {
      if (metrics.hitRatio < 0.3) {
        recommendations.push(`Low hit ratio for ${cacheName} - consider adjusting cache strategy`);
      }
    }

    // Performance recommendations
    const performanceMetrics = this.getPerformanceMetrics();
    for (const [operation, metrics] of Object.entries(performanceMetrics)) {
      if (metrics.averageDuration > 1000) {
        recommendations.push(`Slow ${operation} operation - consider optimization`);
      }
    }

    return recommendations;
  }

  /**
   * Configure monitoring
   */
  setMonitoringEnabled(enabled: boolean): void {
    this.enableMonitoring = enabled;
  }

  /**
   * Get specific cache
   */
  getCache(cacheName: string): IntelligentCache | undefined {
    return this.caches.get(cacheName);
  }

  /**
   * Create custom cache
   */
  createCache(
    name: string,
    maxSize: number = 100,
    strategy: CacheStrategy = 'adaptive',
    ttl?: number
  ): IntelligentCache {
    const cache = new IntelligentCache(name, maxSize, strategy, ttl);
    this.caches.set(name, cache);
    return cache;
  }
}

// Global performance cache manager instance
let globalCacheManager: PerformanceCacheManager | null = null;

/**
 * Get global cache manager instance
 */
export function getGlobalCacheManager(): PerformanceCacheManager {
  if (!globalCacheManager) {
    globalCacheManager = new PerformanceCacheManager();
  }
  return globalCacheManager;
}

/**
 * Performance tracking decorator
 */
export function trackPerformance(operationName: string) {
  return function (target: any, propertyName: string, descriptor: PropertyDescriptor) {
    const method = descriptor.value;

    descriptor.value = async function (...args: any[]) {
      const cacheManager = getGlobalCacheManager();
      const operationId = `${operationName}_${Date.now()}_${Math.random()}`;

      cacheManager.startOperationTiming(operationId);

      try {
        const result = await method.apply(this, args);
        cacheManager.endOperationTiming(operationId, operationName);
        return result;
      } catch (error) {
        cacheManager.endOperationTiming(operationId, `${operationName}_error`);
        throw error;
      }
    };

    return descriptor;
  };
}

/**
 * Cache key generation utilities
 */
export class CacheKeyUtils {
  /**
   * Generate cache key for field validation
   */
  static generateFieldValidationKey(fieldName: string, value: any, schemaVersion?: string): string {
    const manager = getGlobalCacheManager();
    let key = `${fieldName}_${manager['hashValue'](value)}`;
    if (schemaVersion) {
      key += `_${schemaVersion}`;
    }
    return key;
  }

  /**
   * Generate cache key for UI state
   */
  static generateUIStateKey(component: string, state: Record<string, any>): string {
    const manager = getGlobalCacheManager();
    return `${component}_${manager['hashValue'](state)}`;
  }

  /**
   * Generate cache key for schema
   */
  static generateSchemaKey(version: string, variant?: string): string {
    return variant ? `schema_${version}_${variant}` : `schema_${version}`;
  }
}
