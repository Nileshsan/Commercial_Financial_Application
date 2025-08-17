import { Platform } from 'react-native';

interface Config {
  API_BASE_URL: string;
  API_TIMEOUT: number;
  RETRY_CONFIG: {
    retries: number;
    retryDelay: number;
    retryCondition: boolean;
    maxRetries: number;
  };
}

// Helper function to get local API URL for development and production
const getLocalApiUrl = () => {
  if (Platform.OS === 'android') {
    // For Android emulator, use the special 10.0.2.2 hostname that maps to host's localhost
    return __DEV__
      ? 'http://10.0.2.2:8000'  // Android emulator special hostname
      : 'http://localhost:8000'; // Production URL
  }
  
  if (Platform.OS === 'ios') {
    return __DEV__
      ? 'http://localhost:8000'  // iOS simulator can use localhost directly
      : 'http://localhost:8000'; // Production URL
  }
  
  return 'http://localhost:8000'; // Default fallback
};

export const config: Config = {
  API_BASE_URL: getLocalApiUrl(),
  API_TIMEOUT: 60000,  // Increase timeout to 60 seconds for long-running operations
  RETRY_CONFIG: {
    retries: 2,  // Number of retry attempts
    retryDelay: 1000,  // Start with 1 second delay
    retryCondition: true,  // Enable retry on network errors
    maxRetries: 2  // Maximum of 2 retries before failing
  },
};

export const { API_BASE_URL, API_TIMEOUT } = config;
