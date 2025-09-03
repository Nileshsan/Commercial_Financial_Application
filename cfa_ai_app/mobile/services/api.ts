import AsyncStorage from '@react-native-async-storage/async-storage';
import NetworkService from './NetworkService';
import { NetworkError, ApiError, AuthenticationError, OfflineError } from './errors';

// Consolidated, single Api client for the mobile app.
// Key points:
// - Single AsyncStorage token key: 'sessionToken'
// - Use NetworkService.getInstance() for requests and for setting default header
// - Consistent endpoints (match backend `accounts/urls.py` which exposes `/api/...` paths)

interface ApiResponse<T = any> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
}

class ApiClient {
  private static instance: ApiClient;
  private ns = NetworkService.getInstance();
  private authToken: string | null = null;

  private constructor() {}

  public static getInstance() {
    if (!ApiClient.instance) ApiClient.instance = new ApiClient();
    return ApiClient.instance;
  }

  // load token from storage into memory and network service
  public async init(): Promise<void> {
    const token = await AsyncStorage.getItem('sessionToken');
    if (token) {
      this.authToken = token;
      try { this.ns.setAuthToken(token); } catch (e) { /* ignore */ }
    }
  }

  public async setAuthToken(token: string | null) {
    // Accept values like 'Token xxx' or 'Bearer xxx' or raw token
    if (token === null) {
      this.authToken = null;
      await AsyncStorage.removeItem('sessionToken');
      try { this.ns.clearAuthToken(); } catch (e) { /* ignore */ }
      return;
    }

    // normalize token
    let raw = token;
    if (raw.startsWith('Token ')) raw = raw.replace(/^Token\s+/i, '');
    if (raw.startsWith('Bearer ')) raw = raw.replace(/^Bearer\s+/i, '');

    this.authToken = raw;
    await AsyncStorage.setItem('sessionToken', raw);
    try { this.ns.setAuthToken(raw); } catch (e) { /* ignore */ }
  }

  private getAuthHeaders(): Record<string, string> | undefined {
    return this.authToken ? { Authorization: `Token ${this.authToken}` } : undefined;
  }

  private async handle<T>(op: string, fn: () => Promise<T>): Promise<T> {
    try {
      return await fn();
    } catch (err) {
      console.error(`${op} failed:`, err);
      if (err instanceof OfflineError || err instanceof NetworkError || err instanceof ApiError || err instanceof AuthenticationError) throw err;
      throw err instanceof Error ? err : new Error(`${op} failed`);
    }
  }

  // Authentication
  public async login(username: string, password: string): Promise<ApiResponse<{ token: string; user: any }>> {
    return this.handle('login', async () => {
      // Perform login without sending Authorization header
      const res = await this.ns.post<ApiResponse<{ token: string; user: any }>>('/api/login/', { username, password });
      console.log('Login response:', res); // Debug log
      
      if (res.status === 'success' && res.data?.token) {
        // Ensure token is properly formatted
        const token = res.data.token.startsWith('Token ') ? res.data.token : `Token ${res.data.token}`;
        await this.setAuthToken(token);
        // store company context if present
        if (res.data.user) {
          await AsyncStorage.setItem('companyId', String(res.data.user.company_id ?? ''));
          if (res.data.user.company_name) await AsyncStorage.setItem('companyName', res.data.user.company_name);
          if (res.data.user.user_company_name) await AsyncStorage.setItem('userCompanyName', res.data.user.user_company_name);
        }
      }
      return res;
    });
  }

  public async logout() {
    await this.setAuthToken(null);
    await AsyncStorage.multiRemove(['companyId', 'companyName', 'userCompanyName']);
  }

  // Simple wrappers for commonly used endpoints (consistent paths)
  public async getApiToken() {
    return this.handle('getApiToken', async () => {
      return this.ns.get<ApiResponse<any>>('/api/user/api-token/', undefined, this.getAuthHeaders() as any);
    });
  }

  public async fetchPaymentPredictions(companyId: string | number, days = 90) {
    return this.handle('fetchPaymentPredictions', async () => {
      return this.ns.get('/api/payment-predictions/', { company_id: companyId, days, include_stats: true }, this.getAuthHeaders() as any);
    });
  }

  public async fetchPartyBalances(companyId: string | number) {
    return this.handle('fetchPartyBalances', async () => {
      return this.ns.get('/api/party-balances/', { company_id: companyId }, this.getAuthHeaders() as any);
    });
  }

  // These methods are now deprecated, use getUnpaidSales and getPaymentAnalysisSummary instead
  public async fetchUnpaidSales(companyId: string | number) {
    return this.getUnpaidSales(Number(companyId));
  }

  public async fetchPaymentAnalysisSummary(companyId: string | number) {
    return this.getPaymentAnalysisSummary(Number(companyId));
  }

  // Model training endpoints
  public async trainModel(step: 'data-loading' | 'payment-patterns' | 'fixed-expenses' | 'cashflow-setup', companyId: number, onProgress?: (p: number) => void) {
    return this.handle('trainModel', async () => {
      const res = await this.ns.post('/api/model/train/', { company_id: companyId, step, force_update: true }, this.getAuthHeaders() as any);
      if (res.status === 'success') {
        if (onProgress) onProgress(res.data?.progress ?? 100);
      }
      return res;
    });
  }

  public async getModelStatus(companyId?: number) {
    const cid = companyId ?? Number(await AsyncStorage.getItem('companyId'));
    if (!cid) throw new Error('Company ID not found');
    return this.handle('getModelStatus', async () => {
      return this.ns.get('/api/model/status/', { company_id: cid }, this.getAuthHeaders() as any);
    });
  }

  // Backwards-compatible alias used in some older screens
  public async checkModelStatus(companyId?: number) {
    return this.getModelStatus(companyId);
  }

  // Cashflow endpoints
  public async getCashflowPredictions(companyId?: number, days = 30) {
    const cid = companyId ?? Number(await AsyncStorage.getItem('companyId'));
    if (!cid) throw new Error('Company ID not found');
    return this.handle('getCashflowPredictions', async () => {
      const res = await this.ns.get('/api/payment-predictions/', { company_id: cid, days, include_stats: true }, this.getAuthHeaders() as any);
      return res;
    });
  }

  public async updateBankBalance(companyId: number, balance: number, bankAccount = 'default') {
    return this.handle('updateBankBalance', async () => {
      return this.ns.post(`/transactions/cashflow/${companyId}/update_bank_balance/`, { balance: Number(balance), bank_account: bankAccount, force_update: true }, this.getAuthHeaders() as any);
    });
  }

  // Party and analysis
  public async getPaymentBehavior(partyName: string) {
    return this.handle('getPaymentBehavior', async () => {
      return this.ns.get(`/api/payment-behavior/${encodeURIComponent(partyName)}/`, undefined, this.getAuthHeaders() as any);
    });
  }

  public async getPaymentPredictions(companyId: number, days = 90) {
    return this.handle('getPaymentPredictions', async () => {
      return this.ns.get('/api/payment-predictions/', { company_id: companyId, days }, this.getAuthHeaders() as any);
    });
  }

  public async getUnpaidSales(companyId: number) {
    return this.handle('getUnpaidSales', async () => {
      return this.ns.get('/api/unpaid-sales/', { company_id: companyId }, this.getAuthHeaders() as any);
    });
  }

  public async getPartyBalances(companyId: number) {
    return this.handle('getPartyBalances', async () => {
      return this.ns.get('/api/party-balances/', { company_id: companyId }, this.getAuthHeaders() as any);
    });
  }

  public async getPaymentAnalysisSummary(companyId: number) {
    return this.handle('getPaymentAnalysisSummary', async () => {
      return this.ns.get('/api/payment-analysis-summary/', { company_id: companyId }, this.getAuthHeaders() as any);
    });
  }

  // Compatibility wrappers for removed/renamed functions elsewhere in the app
  // These keep older call sites working and forward to the new canonical methods.
  public async generateApiToken(): Promise<string> {
    const res = await this.getApiToken();
    const token = (res?.data as any)?.api_token || (res?.data as any)?.token || '';
    if (!token) throw new Error('No API token received from server');
    await AsyncStorage.setItem('apiToken', token);
    return token;
  }

  public async getBankBalance(companyId?: number) {
    const cid = companyId ?? Number(await AsyncStorage.getItem('companyId'));
    if (!cid) throw new Error('Company ID not found');
    return this.handle('getBankBalance', async () => {
      return this.ns.get('/api/bank-balance/', { company_id: cid, account_name: 'default' }, this.getAuthHeaders() as any);
    });
  }

  public async getDebtorBalances(companyId: number, asOfDate?: string) {
    return this.handle('getDebtorBalances', async () => {
      const params = asOfDate ? { as_of_date: asOfDate } : undefined;
      return this.ns.get(`/transactions/cashflow/${companyId}/get_debtor_balances/`, params, this.getAuthHeaders() as any);
    });
  }

  public async updatePartyBalance(companyId: number, partyBalance: any) {
    return this.handle('updatePartyBalance', async () => {
      return this.ns.post(`/transactions/cashflow/${companyId}/update_party_balance/`, partyBalance, this.getAuthHeaders() as any);
    });
  }

  public async getPartyAnalysis(companyId: number, partyName: string) {
    return this.handle('getPartyAnalysis', async () => {
      return this.ns.get(`/transactions/cashflow/${companyId}/get_party_analysis/`, { party_name: partyName }, this.getAuthHeaders() as any);
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
// Backwards-compatible named export used across the codebase
export { api };
export type { ApiClient };

