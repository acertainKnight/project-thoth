export class APIUtilities {
  private requestCache: Map<string, { data: any; timestamp: number; expires: number }> = new Map();
  private requestQueue: Array<{ request: () => Promise<any>; resolve: (value: any) => void; reject: (error: any) => void }> = [];
  private isProcessingQueue: boolean = false;
  private maxConcurrentRequests: number = 3;
  private activeRequests: number = 0;
  private cacheDefaultTTL: number = 300000; // 5 minutes

  constructor() {}

  /**
   * Build Authorization headers for multi-user mode.
   *
   * Returns an Authorization header when apiToken is set (multi-user mode).
   * Returns an empty object in single-user mode so existing requests are unaffected.
   *
   * @param apiToken - The user's API token from settings (empty string = single-user)
   * @returns Header object to spread into fetch options
   */
  static buildAuthHeaders(apiToken: string): Record<string, string> {
    if (!apiToken) return {};
    return { Authorization: `Bearer ${apiToken}` };
  }

  /**
   * Resolve the current user's Letta agent IDs via GET /auth/me.
   *
   * In multi-user mode, each user has their own namespaced agents
   * (e.g. thoth_main_orchestrator_alice). The /auth/me endpoint returns
   * the orchestrator_agent_id directly so we don't need to scan all agents.
   *
   * Falls back to null in single-user mode (no apiToken set).
   *
   * @param thothBaseUrl - Thoth API base URL
   * @param apiToken - Bearer token (empty = single-user mode)
   * @returns Object with orchestratorId and analystId, or null values if unavailable
   */
  async resolveUserAgentIds(
    thothBaseUrl: string,
    apiToken: string
  ): Promise<{ orchestratorId: string | null; analystId: string | null }> {
    if (!apiToken) {
      return { orchestratorId: null, analystId: null };
    }

    try {
      const url = this.buildEndpointUrl(thothBaseUrl, '/auth/me');
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${apiToken}` },
      });

      if (response.ok) {
        const userInfo = await response.json();
        return {
          orchestratorId: userInfo.orchestrator_agent_id ?? null,
          analystId: userInfo.analyst_agent_id ?? null,
        };
      }
    } catch (e) {
      console.warn('[APIUtilities] Could not resolve agent IDs from /auth/me:', e);
    }

    return { orchestratorId: null, analystId: null };
  }

  /**
   * Cache management utilities
   */
  getCachedRequest(key: string): any {
    const cached = this.requestCache.get(key);
    if (cached && cached.expires > Date.now()) {
      return cached.data;
    }
    if (cached) {
      this.requestCache.delete(key);
    }
    return null;
  }

  setCachedRequest(key: string, data: any, ttl: number = this.cacheDefaultTTL): void {
    this.requestCache.set(key, {
      data,
      timestamp: Date.now(),
      expires: Date.now() + ttl
    });
  }

  clearCache(): void {
    this.requestCache.clear();
  }

  /**
   * Request queue management
   */
  async queueRequest<T>(request: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.requestQueue.push({ request, resolve, reject });
      this.processQueue();
    });
  }

  private async processQueue(): Promise<void> {
    if (this.isProcessingQueue || this.activeRequests >= this.maxConcurrentRequests) {
      return;
    }

    this.isProcessingQueue = true;

    while (this.requestQueue.length > 0 && this.activeRequests < this.maxConcurrentRequests) {
      const { request, resolve, reject } = this.requestQueue.shift()!;
      this.activeRequests++;

      try {
        const result = await request();
        resolve(result);
      } catch (error) {
        reject(error);
      } finally {
        this.activeRequests--;
      }
    }

    this.isProcessingQueue = false;

    // Continue processing if there are more requests
    if (this.requestQueue.length > 0) {
      setTimeout(() => this.processQueue(), 10);
    }
  }

  /**
   * HTTP request utilities
   */
  async makeRequest(url: string, options: RequestInit = {}): Promise<Response> {
    const cacheKey = `${url}-${JSON.stringify(options)}`;
    const cached = this.getCachedRequest(cacheKey);

    if (cached && options.method === 'GET') {
      return new Response(JSON.stringify(cached), { status: 200 });
    }

    return this.queueRequest(async () => {
      const response = await fetch(url, options);

      if (response.ok && options.method === 'GET') {
        const data = await response.clone().json();
        this.setCachedRequest(cacheKey, data);
      }

      return response;
    });
  }

  async makeRequestWithRetry(url: string, options: RequestInit = {}, retries: number = 3, timeout: number = 5000): Promise<Response> {
    let lastError: Error;

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        const requestOptions = {
          ...options,
          signal: controller.signal
        };

        const response = await this.makeRequest(url, requestOptions);
        clearTimeout(timeoutId);

        if (response.ok || response.status < 500) {
          return response;
        }

        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      } catch (error) {
        lastError = error as Error;

        if (attempt < retries) {
          const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    throw lastError!;
  }

  async isBackendOnline(baseUrl: string): Promise<boolean> {
    try {
      const healthUrl = this.buildEndpointUrl(baseUrl, '/health');
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(healthUrl, {
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
   * Endpoint URL helpers
   */
  buildEndpointUrl(baseUrl: string, path: string): string {
    const cleanBase = baseUrl.replace(/\/$/, '');
    const cleanPath = path.replace(/^\//, '');
    return `${cleanBase}/${cleanPath}`;
  }

  /**
   * Error handling utilities
   */
  handleAPIError(error: any): string {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      return 'Network error: Could not connect to Thoth server';
    }
    if (error.status) {
      switch (error.status) {
        case 401:
          return 'Authentication failed: Check your API keys';
        case 403:
          return 'Access denied: Invalid permissions';
        case 404:
          return 'Endpoint not found: Check server configuration';
        case 500:
          return 'Server error: Internal server error';
        default:
          return `HTTP ${error.status}: ${error.statusText || 'Unknown error'}`;
      }
    }
    return error.message || 'Unknown error occurred';
  }
}
