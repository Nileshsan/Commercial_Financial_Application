import AsyncStorage from '@react-native-async-storage/async-storage';
import NetworkService from './NetworkService';
import { NetworkError, ApiError, AuthenticationError, OfflineError } from './errors';

interface ApiResponse<T = any> {
  status: 'success' | 'error';
  data?: T & {
    token?: string;
    api_token?: string;
    user?: User;
  };
  message?: string;
}

interface UserCompany {
  id: number;
  name: string;
  address?: string;
}

interface Company {
  id: number;
  name: string;
  address?: string;
  api_key?: string;
  user_company_id: number;
}

interface User {
  id: number;
  username: string;
  email: string;
  user_company: UserCompany;
  companies: Company[];
  active_company?: Company;
}

interface LoginResponse {
  token: string;
  user: User;
}

interface PartyBalance {
  party_name: string;
  balance: number;
  last_transaction_date?: string;
  prediction?: number;
  confidence?: number;
}

interface BankBalance {
  balance: number;
  as_of_date: string;
  account_name: string;
}

class ApiClient {
  private static instance: ApiClient;
  private ns = NetworkService.getInstance();
  private authToken: string | null = null;
  private initialized = false;

  private constructor() {
    // Bind methods to preserve this context
    this.handle = this.handle.bind(this);
    this.getAuthHeaders = this.getAuthHeaders.bind(this);
    this.setAuthToken = this.setAuthToken.bind(this);
    // Initialize with stored auth token
    this.initialize();
  }

  private async initialize() {
    if (this.initialized) return;
    
    try {
      this.authToken = await AsyncStorage.getItem('@auth_token');
      this.initialized = true;
    } catch (error) {
      console.error('Failed to initialize API client:', error);
    }
  }

  public static getInstance() {
    if (!ApiClient.instance) ApiClient.instance = new ApiClient();
    return ApiClient.instance;
  }

  public async init(): Promise<void> {
    const token = await AsyncStorage.getItem('sessionToken');
    if (token) {
      this.authToken = token;
      try { this.ns.setAuthToken(token); } catch (e) { /* ignore */ }
    }
  }

  private async persistUserSession(userData: any, token: string) {
    try {
      await Promise.all([
        AsyncStorage.setItem('sessionToken', token),
        AsyncStorage.setItem('userId', userData.id.toString()),
        AsyncStorage.setItem('username', userData.username),
        AsyncStorage.setItem('userEmail', userData.email),
        AsyncStorage.setItem('companyId', userData.company_id?.toString() || ''),
        AsyncStorage.setItem('companyName', userData.company_name || ''),
        AsyncStorage.setItem('userCompanyId', userData.user_company_id?.toString() || ''),
        AsyncStorage.setItem('userCompanyName', userData.user_company_name || ''),
        AsyncStorage.setItem('lastLoginTime', Date.now().toString()),
      ]);
    } catch (error) {
      console.error('Error persisting user session:', error);
    }
  }

  public async setAuthToken(token: string | null) {
    if (token === null) {
      this.authToken = null;
      // Clear all session data
      const keysToRemove = [
        'sessionToken',
        'refreshToken',
        'userId',
        'username',
        'userEmail',
        'companyId',
        'companyName',
        'userCompanyId',
        'userCompanyName',
        'lastLoginTime'
      ];
      await Promise.all(keysToRemove.map(key => AsyncStorage.removeItem(key)));
      try { this.ns.clearAuthToken(); } catch (e) { /* ignore */ }
      return;
    }

    // Remove any existing prefixes and store clean token
    let cleanToken = token.replace(/^(Bearer|Token)\s+/i, '');
    this.authToken = cleanToken;
    await AsyncStorage.setItem('sessionToken', cleanToken);
    try { this.ns.setAuthToken(cleanToken); } catch (e) { /* ignore */ }
  }

  private getAuthHeaders(): Record<string, string> | undefined {
    if (!this.authToken) return undefined;
    return { Authorization: `Bearer ${this.authToken}` };
  }

  private async handle<T>(op: string, fn: () => Promise<T>): Promise<T> {
    try {
      const result = await fn();
      // Basic type validation for ApiResponse
      if (result && typeof result === 'object' && 'status' in result) {
        const apiRes = result as ApiResponse<any>;
        if (apiRes.status === 'error') {
          throw new ApiError(apiRes.message || 'Unknown error', 400, apiRes);
        }
      }
      return result;
    } catch (err) {
      console.error(`[ApiClient] ${op} failed:`, err);
      
      // Handle known error types
      if (
        err instanceof OfflineError ||
        err instanceof NetworkError ||
        err instanceof ApiError ||
        err instanceof AuthenticationError
      ) {
        throw err;
      }

      // Handle axios errors through NetworkService
      if (err?.response?.status === 401) {
        await this.clearAuthToken();
        throw new AuthenticationError('Session expired');
      }

      // Throw with improved context
      throw err instanceof Error 
        ? Object.assign(err, { operation: op })
        : new Error(`${op} failed: ${err?.message || 'Unknown error'}`);
    }
  }

  public async login(username: string, password: string): Promise<ApiResponse<{ token: string; user: any }>> {
    return this.handle('login', async () => {
      console.log('==== Login Request Debug ====');
      console.log('API Base URL:', this.ns.getBaseUrl());
      console.log('Attempting login with username:', username);

      const payload = { username, password };
      let res: any = null;

      try {
        // Only attempt login endpoint, don't try token endpoints
        res = await this.ns.post('login/', payload);
        if (!res || res.status === 'error') {
          throw new Error(res?.message || 'Login failed');
        }
      } catch (err) {
        throw new Error(err?.message || 'Login failed');
      }

      console.log('Login response:', res);

      // Handle various token response formats
      let raw: string | null = null;
      let userData = null;

      try {
        // Handle JWT response (access_token + refresh_token)
        if (res?.access_token || res?.refresh_token || res?.access || res?.refresh) {
          raw = res.access_token || res.access;
          const refreshToken = res.refresh_token || res.refresh;
          
          // Store both access and refresh tokens
          await AsyncStorage.setItem('refreshToken', refreshToken);
          await AsyncStorage.setItem('sessionToken', raw);
          
          userData = {
            id: res.id || res.user_id,
            username: res.username,
            email: res.email,
            user_company: res.user_company || null,
            companies: res.companies || [],
            active_company: res.active_company || res.companies?.[0] || null
          };
        }
        // Handle legacy token response
        else if (res?.status === 'success' && res?.data?.token) {
          raw = res.data.token;
          // Remove any existing prefixes
          raw = raw.replace(/^(Bearer|Token)\s+/i, '');
          userData = res.data.user || null;
          if (userData) {
            // Store company information
            await AsyncStorage.setItem('companyId', userData.company_id?.toString() || '');
            await AsyncStorage.setItem('companyName', userData.company_name || '');
            await AsyncStorage.setItem('userCompanyId', userData.user_company_id?.toString() || '');
            await AsyncStorage.setItem('userCompanyName', userData.user_company_name || '');
            await AsyncStorage.setItem('sessionToken', raw);
            
            userData.user_company = {
              id: userData.user_company_id,
              name: userData.user_company_name
            };
            userData.companies = [{
              id: userData.company_id,
              name: userData.company_name,
              user_company_id: userData.user_company_id
            }];
            userData.active_company = userData.companies[0];
          }
        }
        // Handle simple token response
        else if (res?.token) {
          raw = res.token;
          userData = res.user || null;
        }

        if (!raw) {
          throw new Error('No valid token found in response');
        }

        // Set the auth token first
        await this.setAuthToken(raw);

        // Store user information if available
        if (userData) {
          const userInfo = {
            username: userData.username || '',
            userId: String(userData.id || userData.user_id || ''),
            email: userData.email || '',
            companyId: String(userData.company_id || ''),
            companyName: userData.company_name || '',
            userCompanyId: String(userData.user_company_id || ''),
            userCompanyName: userData.user_company_name || ''
          };

          // Write only valid values to AsyncStorage. AsyncStorage rejects null/undefined values.
          const storagePromises: Promise<any>[] = [];

          if (userData.username != null) storagePromises.push(AsyncStorage.setItem('username', String(userData.username)));
          else storagePromises.push(AsyncStorage.removeItem('username'));

          if (userData.id != null) storagePromises.push(AsyncStorage.setItem('userId', String(userData.id)));
          else storagePromises.push(AsyncStorage.removeItem('userId'));

          if (userData.email != null) storagePromises.push(AsyncStorage.setItem('email', String(userData.email)));
          else storagePromises.push(AsyncStorage.removeItem('email'));

          if (userData.user_company != null) storagePromises.push(AsyncStorage.setItem('userCompany', JSON.stringify(userData.user_company)));
          else storagePromises.push(AsyncStorage.removeItem('userCompany'));

          if (userData.companies != null) storagePromises.push(AsyncStorage.setItem('companies', JSON.stringify(userData.companies)));
          else storagePromises.push(AsyncStorage.removeItem('companies'));

          if (userData.active_company != null) storagePromises.push(AsyncStorage.setItem('activeCompany', JSON.stringify(userData.active_company)));
          else storagePromises.push(AsyncStorage.removeItem('activeCompany'));

          await Promise.all(storagePromises);
        }

        return {
          status: 'success',
          data: {
            token: raw,
            user: userData
          },
          message: res.message || 'Login successful'
        };

      } catch (e) {
        console.error('Failed to process login response:', e);
        throw new Error('Login failed: Invalid server response');
      }
    });
  }

  public async logout() {
    await this.setAuthToken(null);
    // Clear all user-related data
    await AsyncStorage.multiRemove([
      'sessionToken',
      'apiToken',
      'username',
      'userId',
      'email',
      'companyId',
      'companyName',
      'userCompanyId',
      'userCompanyName'
    ]);
  }

  public async getApiToken() {
    return this.handle('getApiToken', async () => {
      return this.ns.get<ApiResponse<any>>('user/api-token/', undefined, this.getAuthHeaders() as any);
    });
  }

  public async fetchPaymentPredictions(companyId: string | number, days = 90) {
    return this.handle('fetchPaymentPredictions', async () => {
      return this.ns.get('payment-predictions/', { company_id: companyId, days, include_stats: true }, this.getAuthHeaders() as any);
    });
  }

  public async fetchPartyBalances(companyId: string | number) {
    return this.handle('fetchPartyBalances', async () => {
      return this.ns.get('party-balances/', { company_id: companyId }, this.getAuthHeaders() as any);
    });
  }

  public async getPaymentPredictions(companyId: number, days = 90) {
    return this.handle('getPaymentPredictions', async () => {
      return this.ns.get('payment-predictions/', { company_id: companyId, days }, this.getAuthHeaders() as any);
    });
  }

  public async getUnpaidSales(companyId: number) {
    return this.handle('getUnpaidSales', async () => {
      return this.ns.get('unpaid-sales/', { company_id: companyId }, this.getAuthHeaders() as any);
    });
  }

  public async getPartyBalances(companyId: number) {
    return this.handle('getPartyBalances', async () => {
      return this.ns.get('party-balances/', { company_id: companyId }, this.getAuthHeaders() as any);
    });
  }

  public async getPaymentAnalysisSummary(companyId: number) {
    return this.handle('getPaymentAnalysisSummary', async () => {
      return this.ns.get('payment-analysis-summary/', { company_id: companyId }, this.getAuthHeaders() as any);
    });
  }

  public async generateApiToken(): Promise<string> {
    const res = await this.getApiToken();
    const token = (res?.data as any)?.api_token || (res?.data as any)?.token || '';
    if (!token) throw new Error('No API token received from server');
    await AsyncStorage.setItem('apiToken', token);
    return token;
  }

  public async getBankBalance(companyId?: number) {
    const cid = companyId ?? Number(await AsyncStorage.getItem('companyId'));
    if (!cid || isNaN(cid)) throw new Error('Valid company ID not found');
    return this.handle('getBankBalance', async () => {
      return this.ns.get('bank-balance/', { company_id: cid, account_name: 'default' }, this.getAuthHeaders());
    });
  }

  public async getDebtorBalances(companyId: number, asOfDate?: string) {
    if (!companyId || isNaN(companyId)) throw new Error('Valid company ID required');
    return this.handle('getDebtorBalances', async () => {
      const params = { company_id: companyId, ...(asOfDate ? { as_of_date: asOfDate } : {}) };
      return this.ns.get('transactions/debtor-balances/', params, this.getAuthHeaders());
    });
  }

  public async updatePartyBalance(companyId: number, partyBalance: any) {
    if (!companyId || isNaN(companyId)) throw new Error('Valid company ID required');
    if (!partyBalance) throw new Error('Party balance data required');
    return this.handle('updatePartyBalance', async () => {
      return this.ns.post('transactions/party-balance/', 
        { company_id: companyId, ...partyBalance },
        this.getAuthHeaders()
      );
    });
  }

  public async getPartyAnalysis(companyId: number, partyName: string) {
    if (!companyId || isNaN(companyId)) throw new Error('Valid company ID required');
    if (!partyName) throw new Error('Party name required');
    return this.handle('getPartyAnalysis', async () => {
      return this.ns.get('transactions/party-analysis/', 
        { company_id: companyId, party_name: partyName },
        this.getAuthHeaders()
      );
    });
  }

  // Backwards-compatible aliases and additional endpoints expected by the app
  public async getCashflowPredictions(companyId: number, days = 90) {
    // older code expects this name; delegate to payment-predictions
    return this.getPaymentPredictions(companyId, days);
  }

  public async updateBankBalance(companyId: number, balance: number, bankAccount = 'default') {
    return this.handle('updateBankBalance', async () => {
      return this.ns.post(`transactions/cashflow/${companyId}/update_bank_balance/`, { balance, bank_account: bankAccount }, this.getAuthHeaders() as any);
    });
  }

  public async checkModelStatus() {
    return this.handle('checkModelStatus', async () => {
      return this.ns.get('model/status/', undefined, this.getAuthHeaders() as any);
    });
  }

  public async trainModel(action: string, companyId?: number, onProgress?: (p: number) => void) {
    // action: 'data-loading' | 'payment-patterns' | ...
    return this.handle('trainModel', async () => {
      const payload: any = { action };
      if (companyId) payload.company_id = companyId;
      // onProgress is not yet used (server doesn't stream progress in this setup)
      return this.ns.post('model/train/', payload, this.getAuthHeaders() as any);
    });
  }

  public async hasValidToken(): Promise<boolean> {
    const token = await AsyncStorage.getItem('sessionToken');
    return !!token;
  }

  public async clearAuthToken(): Promise<void> {
    await this.setAuthToken(null);
  }

}

const api = ApiClient.getInstance();
export default api;
export { api };
export type { ApiClient };
