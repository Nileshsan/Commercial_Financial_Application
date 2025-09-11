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
  // Always use http for local development
  const protocol = 'http://';
  
  // For Android emulator - use 10.0.2.2 which maps to host's localhost
  if (Platform.OS === 'android' && __DEV__) {
    return `${protocol}10.0.2.2:8000`;  // Remove trailing slash
  }
  
  // For iOS simulator - use localhost
  if (Platform.OS === 'ios' && __DEV__) {
    return `${protocol}localhost:8000`;  // Remove trailing slash
  }
  
  // For physical devices or web, use the local network IP
  return `${protocol}192.168.0.104:8000`;  // Remove trailing slash
};

export const config: Config = {
  API_BASE_URL: getLocalApiUrl(),
  API_TIMEOUT: 120000,  // Increase timeout to 120 seconds for better stability
  RETRY_CONFIG: {
    retries: 3,  // Increase retry attempts
    retryDelay: 2000,  // Start with 2 second delay
    retryCondition: true,  // Enable retry on network errors
    maxRetries: 3  // Maximum of 3 retries before failing
  },
};

export const { API_BASE_URL, API_TIMEOUT } = config;
