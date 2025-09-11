import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { config } from '../config';
import NetInfo from '@react-native-community/netinfo';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { NetworkError, ApiError, AuthenticationError, OfflineError } from './errors';
import { jwtDecode } from 'jwt-decode';

export interface RequestConfig {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH' | 'OPTIONS';
  url: string;
  data?: any;
  params?: any;
  headers?: Record<string, string>;
  timeout?: number;
}

export default class NetworkService {
  private static instance: NetworkService;
  private axiosInstance: AxiosInstance;
  private authToken: string | null = null;
  // Fallback host (will be computed in constructor to avoid primary==fallback)
  private fallbackBaseURL: string;

  private tokenRefreshPromise: Promise<string> | null = null;
  private lastTokenRefresh: number = 0;
  private readonly TOKEN_REFRESH_INTERVAL = 30 * 60 * 1000; // 30 minutes in milliseconds

  private constructor() {
    // Initialize with the base URL from config
    this.axiosInstance = axios.create({
      // Keep baseURL pointing at API root to match other clients which use relative paths
      baseURL: config.API_BASE_URL.endsWith('/') ? `${config.API_BASE_URL}api/` : `${config.API_BASE_URL}/api/`,
      timeout: 120000, // Increase timeout to 120 seconds
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      withCredentials: true, // Enable credentials
      // Retry-related configs
      maxRedirects: 5,
      maxContentLength: 50 * 1024 * 1024, // 50MB max,
      validateStatus: function (status) {
        return status >= 200 && status < 500; // Don't reject if status is >= 200
      }
    });

    console.debug('[NetworkService] initialized with baseURL=', config.API_BASE_URL);

    this.setupInterceptors();
  }

  private async tokenNeedsRefresh(): Promise<boolean> {
    const token = this.authToken ?? await AsyncStorage.getItem('sessionToken');
    if (!token) return false;

    try {
      const decoded = jwtDecode(token) as { exp: number };
      const expirationTime = decoded.exp * 1000; // Convert to milliseconds
      const currentTime = Date.now();
      const timeUntilExpiry = expirationTime - currentTime;
      
      // Refresh if token expires in less than 5 minutes
      return timeUntilExpiry < 5 * 60 * 1000;
    } catch (error) {
      console.error('Error checking token expiration:', error);
      return false;
    }
  }


  private async refreshTokenIfNeeded(): Promise<string | null> {
    try {
      const now = Date.now();
      if (now - this.lastTokenRefresh < this.TOKEN_REFRESH_INTERVAL) {
        return this.authToken;
      }

      if (this.tokenRefreshPromise) {
        return this.tokenRefreshPromise;
      }

      const refreshToken = await AsyncStorage.getItem('refreshToken');
      if (!refreshToken) {
        return null;
      }

      this.tokenRefreshPromise = (async () => {
        try {
          const response = await this.axiosInstance.post('token/refresh/', {
            refresh: refreshToken
          });

          if (response.data.access) {
            this.lastTokenRefresh = now;
            this.setAuthToken(response.data.access);
            await AsyncStorage.setItem('sessionToken', response.data.access);
            if (response.data.refresh) {
              await AsyncStorage.setItem('refreshToken', response.data.refresh);
            }
            return response.data.access;
          }
        } catch (error) {
          console.error('Token refresh failed:', error);
          return null;
        } finally {
          this.tokenRefreshPromise = null;
        }
      })();

      return this.tokenRefreshPromise;
    } catch (error) {
      console.error('Error in refreshTokenIfNeeded:', error);
      return null;
    }
  }

  private setupInterceptors() {
    // Request interceptor
    this.axiosInstance.interceptors.request.use(
      async (config: any) => {
        // Check network connectivity first
        const netInfo = await NetInfo.fetch();
        if (!netInfo.isConnected) {
          throw new OfflineError('No internet connection available');
        }
        
        // Proactively refresh token if needed
        try {
          const tokenNeedsRefresh = await this.tokenNeedsRefresh();
          if (tokenNeedsRefresh) {
            await this.refreshTokenIfNeeded();
          }
        } catch (error) {
          console.error('Proactive token refresh failed:', error);
        }

        console.log('[NetworkService] Making request to:', config.baseURL + config.url);
        console.log('[NetworkService] Request data:', config.data);
        const headers = { ...config.headers } as Record<string, string>;
        
        // Add auth token if available
        if (this.authToken) {
          headers['Authorization'] = `Bearer ${this.authToken}`;
        }
        
        // Ensure proper content type and accept headers
        headers['Content-Type'] = 'application/json';
        headers['Accept'] = 'application/json';
        
        // Log request details
        console.log('Making request to:', config.url);
        console.log('Request headers:', config.headers);
        console.log('Request data:', config.data);
        
        const net = await NetInfo.fetch();
        if (!net.isConnected) {
          console.error('[NetworkService] No network connection available');
          throw new OfflineError();
        }
        
        // Prefer in-memory token to avoid AsyncStorage race conditions.
        const token = this.authToken ?? await AsyncStorage.getItem('sessionToken');
        if (token) {
          if (!config.headers) config.headers = {} as any;
          // Always use Bearer for JWT tokens
          (config.headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
          console.debug('[NetworkService] Adding auth token to request:', config.url);
        } else {
          console.warn('[NetworkService] No auth token available for request:', config.url);
        }
        
        return {
          ...config,
          headers: config.headers
        };
      },
      (err) => {
        console.error('[NetworkService] Request setup failed:', err);
        return Promise.reject(new NetworkError('Request failed', err as AxiosError));
      }
    );

    this.axiosInstance.interceptors.response.use(
      (res) => res,
      async (err: AxiosError) => {
        // Handle authentication errors
        if (err.response?.status === 401 || 
            (err.response?.data as any)?.code === 'token_not_valid' ||
            (err.response?.data as any)?.detail?.includes('token')) {
          
          console.error('[NetworkService] Token error:', err.response?.data);
          
          try {
            // Try to refresh the token
            const refreshToken = await AsyncStorage.getItem('refreshToken');
            if (refreshToken) {
              const response = await this.axiosInstance.post('token/refresh/', {
                refresh: refreshToken
              });
              
              if (response.data.access) {
                // Update the access token
                this.setAuthToken(response.data.access);
                await AsyncStorage.setItem('sessionToken', response.data.access);
                
                // Retry the original request with new token
                const config = err.config;
                if (config && config.headers) {
                  config.headers['Authorization'] = `Bearer ${response.data.access}`;
                  return this.axiosInstance.request(config);
                }
              }
            }
          } catch (refreshError) {
            console.error('[NetworkService] Token refresh failed:', refreshError);
            // Clear tokens on refresh failure
            this.authToken = null;
            await AsyncStorage.removeItem('sessionToken');
            await AsyncStorage.removeItem('refreshToken');
            throw new AuthenticationError('Session expired. Please login again.');
          }
          
          throw new AuthenticationError('Authentication failed');
        }
        
        if (!err.response) {
            // Network error handling with simple retry logic
            const retryCfg = err.config as AxiosRequestConfig & { _retry?: number };
            retryCfg._retry = retryCfg._retry ?? 0;
            
            // Check if we've exceeded max retries
            if (retryCfg._retry >= config.RETRY_CONFIG.maxRetries) {
              console.error('[NetworkService] Max retries exceeded for', retryCfg.url);
              throw new NetworkError('Max retries exceeded', err);
            }

            // Simple retry with exponential backoff
            if (retryCfg._retry < config.RETRY_CONFIG.retries) {
              retryCfg._retry++;
              
              // Ensure Authorization header is present
              try {
                const token = this.authToken ?? await AsyncStorage.getItem('sessionToken');
                if (token) {
                  if (!retryCfg.headers) retryCfg.headers = {} as any;
                  (retryCfg.headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
                }
              } catch (e) {
                // Ignore token errors, retry anyway
              }

              const delay = Math.min(
                config.RETRY_CONFIG.retryDelay * Math.pow(1.5, retryCfg._retry - 1),
                10000
              );

              console.debug(`[NetworkService] retry #${retryCfg._retry} for ${retryCfg.url} after ${delay}ms`);
              await new Promise((r) => setTimeout(r, delay));
              return this.axiosInstance.request(retryCfg);
            }
            
            throw new NetworkError('Network error after retries', err);
          }

        const msg = (err.response && (err.response.data && (err.response.data as any).message)) || err.message || 'API error';
        throw new ApiError(msg, err.response.status, err.response.data);
      }
    );
  }

  public static getInstance(): NetworkService {
    if (!NetworkService.instance) NetworkService.instance = new NetworkService();
    return NetworkService.instance;
  }

  public async request<T = any>(cfg: RequestConfig): Promise<T> {
    try {
      const res = await this.axiosInstance.request(cfg as AxiosRequestConfig);
      return res.data as T;
    } catch (e) {
      if (e instanceof AxiosError) {
        if (!e.response) throw new NetworkError('Network error', e);
        if (e.response.status === 401) throw new AuthenticationError();
        const message = e.response.data?.message || e.message || 'Unknown API error';
        throw new ApiError(message, e.response.status, e.response.data || {});
      }
      throw e;
    }
  }

  public async get<T = any>(url: string, params?: any, headers?: Record<string, string>): Promise<T> {
    return this.request<T>({ method: 'GET', url, params, headers });
  }

  public async post<T = any>(url: string, data?: any, headers?: Record<string, string>): Promise<T> {
    return this.request<T>({ method: 'POST', url, data, headers });
  }

  public async put<T = any>(url: string, data?: any, headers?: Record<string, string>): Promise<T> {
    return this.request<T>({ method: 'PUT', url, data, headers });
  }

  public async delete<T = any>(url: string, headers?: Record<string, string>): Promise<T> {
    return this.request<T>({ method: 'DELETE', url, headers });
  }

public setAuthToken(token: string) {
  // Remove any existing prefixes and store clean token
  const cleanToken = token.replace(/^(Bearer|Token)\s+/i, '');
  this.authToken = cleanToken;
  // Always use Bearer prefix for JWT authentication
  this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${cleanToken}`;
}  public clearAuthToken() {
    this.authToken = null;
    delete this.axiosInstance.defaults.headers.common['Authorization'];
    return AsyncStorage.removeItem('sessionToken');
  }

  public async getAuthToken(): Promise<string | null> {
    if (this.authToken) return this.authToken;
    return AsyncStorage.getItem('sessionToken');
  }

  public getBaseUrl(): string {
    return this.axiosInstance.defaults.baseURL ?? '';
  }
}

