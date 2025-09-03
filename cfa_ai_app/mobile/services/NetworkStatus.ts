import NetInfo, { NetInfoState } from '@react-native-community/netinfo';
import { Platform } from 'react-native';
import { config } from '../config';

class NetworkStatus {
  private static instance: NetworkStatus;
  private isConnected: boolean = false;
  private listeners: Set<(isConnected: boolean) => void> = new Set();

  private constructor() {
    this.setupNetInfoListener();
  }

  public static getInstance(): NetworkStatus {
    if (!NetworkStatus.instance) {
      NetworkStatus.instance = new NetworkStatus();
    }
    return NetworkStatus.instance;
  }

  private setupNetInfoListener() {
    // Subscribe to network state updates
    NetInfo.addEventListener((state: NetInfoState) => {
      this.isConnected = state.isConnected ?? false;
      this.notifyListeners();
    });
  }

  public async checkConnection(): Promise<boolean> {
    try {
      const netInfo = await NetInfo.fetch();
      this.isConnected = netInfo.isConnected ?? false;
      
      // If connected, try to ping the backend
      if (this.isConnected) {
        const testUrl = `${config.API_BASE_URL}/api/health-check/`;
        const timeout = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Timeout')), 5000)
        );
        const response = await Promise.race([
          fetch(testUrl),
          timeout
        ]) as Response;
        
        return response.ok;
      }
      
      return false;
    } catch (error) {
      console.error('Network check failed:', error);
      return false;
    }
  }

  public addListener(listener: (isConnected: boolean) => void) {
    this.listeners.add(listener);
    // Immediately notify the new listener of current status
    listener(this.isConnected);
  }

  public removeListener(listener: (isConnected: boolean) => void) {
    this.listeners.delete(listener);
  }

  private notifyListeners() {
    this.listeners.forEach(listener => listener(this.isConnected));
  }

  public getConnectionInfo(): Promise<NetInfoState> {
    return NetInfo.fetch();
  }

  public async getConnectionDetails(): Promise<string> {
    const netInfo = await this.getConnectionInfo();
    if (!netInfo.isConnected) {
      return 'No internet connection';
    }

    if (Platform.OS === 'android') {
      return `Connected (${netInfo.type})${netInfo.details?.isConnectionExpensive ? ' - Metered' : ''}`;  // Using optional chaining
    }

    return `Connected (${netInfo.type})`;
  }
}

export default NetworkStatus.getInstance();
