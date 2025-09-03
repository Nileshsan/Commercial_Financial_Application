import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';
import { config } from '../config';
import NetInfo from '@react-native-community/netinfo';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { NetworkError, ApiError, AuthenticationError, OfflineError } from './errors';

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

  private constructor() {
    // Initialize with the base URL from config
    this.axiosInstance = axios.create({
      baseURL: config.API_BASE_URL,
      timeout: config.API_TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // We won't use fallback URLs anymore since we're using the correct Android emulator URL
    this.fallbackBaseURL = '';

    console.debug('[NetworkService] initialized with baseURL=', config.API_BASE_URL, 'fallback=', this.fallbackBaseURL);

    this.setupInterceptors();
  }

  private setupInterceptors() {
    this.axiosInstance.interceptors.request.use(
      async (cfg) => {
        const net = await NetInfo.fetch();
        if (!net.isConnected) {
          console.error('[NetworkService] No network connection available');
          throw new OfflineError();
        }
        
        // Prefer in-memory token to avoid AsyncStorage race conditions.
        const token = this.authToken ?? await AsyncStorage.getItem('sessionToken');
        if (token) {
          if (!cfg.headers) cfg.headers = {} as any;
          (cfg.headers as Record<string, string>)['Authorization'] = `Token ${token}`;
          console.debug('[NetworkService] Adding auth token to request:', cfg.url);
        } else {
          console.warn('[NetworkService] No auth token available for request:', cfg.url);
        }
        return cfg;
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
        if (err.response?.status === 401) {
          console.error('[NetworkService] Authentication failed:', err.response.data);
          // Clear the token since it's invalid
          this.authToken = null;
          await AsyncStorage.removeItem('sessionToken');
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
                  (retryCfg.headers as Record<string, string>)['Authorization'] = `Token ${token}`;
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

        if (err.response.status === 401) throw new AuthenticationError();
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
        throw new ApiError(e.response.data?.message || e.message, e.response.status, e.response.data);
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

  public setAuthToken(token: string) {
  this.authToken = token;
  this.axiosInstance.defaults.headers.common['Authorization'] = `Token ${token}`;
  }

  public clearAuthToken() {
  this.authToken = null;
  delete this.axiosInstance.defaults.headers.common['Authorization'];
  }
}

