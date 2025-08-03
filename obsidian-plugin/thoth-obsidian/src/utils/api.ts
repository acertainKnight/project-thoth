export class APIUtilities {
  private requestCache: Map<string, { data: any; timestamp: number; expires: number }> = new Map();
  private requestQueue: Array<{ request: () => Promise<any>; resolve: (value: any) => void; reject: (error: any) => void }> = [];
  private isProcessingQueue: boolean = false;
  private maxConcurrentRequests: number = 3;
  private activeRequests: number = 0;
  private cacheDefaultTTL: number = 300000; // 5 minutes

  constructor() {}

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
