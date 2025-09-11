import NetInfo, { NetInfoState, NetInfoStateType } from '@react-native-community/netinfo';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getAuthToken, API_KEY } from './auth';

interface NetworkStatus {
  isConnected: boolean;
  type: NetInfoState['type'];
  details: {
    isConnected: boolean;
    isInternetReachable: boolean | null;
    type: NetInfoState['type'];
  };
  serverReachable: boolean;
  lastChecked: number;
}

let cachedStatus: NetworkStatus | null = null;

/**
 * Checks network connectivity and server availability
 * @param forceCheck Force a new check instead of using cached results
 * @returns NetworkStatus object
 */
export const checkNetworkConnectivity = async (forceCheck: boolean = false): Promise<NetworkStatus> => {
  // Return cached result if available and less than 5 seconds old
  if (!forceCheck && cachedStatus && Date.now() - cachedStatus.lastChecked < 5000) {
    return cachedStatus;
  }

  try {
    const networkState = await NetInfo.fetch();
    const isConnected = networkState.isConnected || false;
    const type = networkState.type;
    
    // Load config and log it
    const { API_BASE_URL } = await import('../config');
    console.log('Loaded API_BASE_URL from config:', API_BASE_URL);
    
    if (!API_BASE_URL) {
      console.error('API_BASE_URL is not configured');
      throw new Error('API_BASE_URL is not configured');
    }
    
    // Check server reachability
    console.log('Checking server reachability...');
    const serverReachable = await isServerReachable(API_BASE_URL);
    console.log('Server reachability result:', serverReachable);

    cachedStatus = {
      isConnected: !!isConnected,
      type: type || NetInfoStateType.none,
      details: {
        isConnected: !!isConnected,
        isInternetReachable: isConnected,
        type: type || NetInfoStateType.unknown
      },
      serverReachable,
      lastChecked: Date.now()
    };

    return cachedStatus;
  } catch (error) {
    console.error('Network check failed:', error);
    return {
      isConnected: false,
      type: NetInfoStateType.unknown,
      details: null,
      serverReachable: false,
      lastChecked: Date.now()
    };
  }
};

/**
 * Checks if the server is reachable
 * @param url Base URL of the server
 * @param timeout Timeout in milliseconds
 * @returns boolean indicating if server is reachable
 */
export const isServerReachable = async (url: string, timeout: number = 5000): Promise<boolean> => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    // Try multiple endpoints that should be accessible
    const endpoints = ['/api/login/', '/admin/login/', '/'];
    for (const endpoint of endpoints) {
      try {
        const checkUrl = `${url}${endpoint}`;
        console.log('Checking server reachability at:', checkUrl);

        const response = await fetch(checkUrl, {
          method: 'OPTIONS',  // Use OPTIONS to avoid triggering actual login logic
          signal: controller.signal,
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          mode: 'cors'  // Explicitly set CORS mode
        });
        clearTimeout(timeoutId);
        console.log('Server reachability response:', response.status);
        if (response.ok) {
          return true;
        }
      } catch (error) {
        console.error('Server reachability check failed:', error);
        // Continue to next endpoint
      }
    }
    clearTimeout(timeoutId);
    return false;
  } catch (error) {
    console.error('Server reachability check failed:', error);
    return false;
  }
};

/**
 * Sets up network change listeners
 * @param onNetworkChange Callback function when network status changes
 * @returns Unsubscribe function
 */
// expo-network does not support listeners in the same way as NetInfo
// You can poll network status periodically if needed
export const setupNetworkListener = (
  onNetworkChange: (status: NetworkStatus) => void,
  interval: number = 5000
): (() => void) => {
  const timer = setInterval(async () => {
    const fullStatus = await checkNetworkConnectivity(true);
    onNetworkChange(fullStatus);
  }, interval);
  return () => clearInterval(timer);
};

/**
 * Validates API URL format
 * @param url URL to validate
 * @returns boolean indicating if URL is valid
 */
export const isValidApiUrl = (url: string): boolean => {
  try {
    const urlObj = new URL(url);
    return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
  } catch {
    return false;
  }
};

/**
 * Updates the API base URL
 * @param newUrl New base URL for the API
 * @returns Promise<boolean> indicating if update was successful
 */
export const updateApiBaseUrl = async (newUrl: string): Promise<boolean> => {
  if (!isValidApiUrl(newUrl)) {
    return false;
  }

  try {
    await AsyncStorage.setItem('apiBaseUrl', newUrl);
    // Clear cached status to force new check with new URL
    cachedStatus = null;
    return true;
  } catch (error) {
    console.error('Failed to update API base URL:', error);
    return false;
  }
};
