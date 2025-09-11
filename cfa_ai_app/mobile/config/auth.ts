import AsyncStorage from '@react-native-async-storage/async-storage';

// Auth token storage key
export const AUTH_TOKEN_KEY = '@auth_token';

// Authentication configuration
export const AUTH_CONFIG = {
  API_KEY: '5ac22546aab77b566c262459e5cc19e8055f4418',
  TOKEN_HEADER: 'Authorization',
  TOKEN_PREFIX: 'Bearer',
  API_KEY_HEADER: 'API-Key'
};

// Auth token management
export const getAuthToken = async () => {
  try {
    return await AsyncStorage.getItem(AUTH_TOKEN_KEY);
  } catch (error) {
    console.error('Failed to get auth token:', error);
    return null;
  }
};

export const setAuthToken = async (token: string) => {
  try {
    await AsyncStorage.setItem(AUTH_TOKEN_KEY, token);
  } catch (error) {
    console.error('Failed to save auth token:', error);
  }
};

export const clearAuthToken = async () => {
  try {
    await AsyncStorage.removeItem(AUTH_TOKEN_KEY);
  } catch (error) {
    console.error('Failed to clear auth token:', error);
  }
};

// Header generators
export const getAuthHeaders = async () => {
  const token = await getAuthToken();
  return {
    [AUTH_CONFIG.API_KEY_HEADER]: AUTH_CONFIG.API_KEY,
    ...(token ? { [AUTH_CONFIG.TOKEN_HEADER]: `${AUTH_CONFIG.TOKEN_PREFIX} ${token}` } : {})
  };
};
