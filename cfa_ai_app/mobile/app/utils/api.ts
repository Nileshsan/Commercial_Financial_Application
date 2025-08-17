import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL, API_TIMEOUT } from '../../config';

const baseURL = Array.isArray(API_BASE_URL) ? API_BASE_URL[0] : API_BASE_URL;

const apiClient = axios.create({
  baseURL,
  timeout: API_TIMEOUT || 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add a request interceptor to add auth token
apiClient.interceptors.request.use(
  async (cfg) => {
    try {
      const token = await AsyncStorage.getItem('sessionToken');
      if (token) {
        if (!cfg.headers) cfg.headers = {} as any;
        (cfg.headers as Record<string, string>)['Authorization'] = `Token ${token}`;
      }
    } catch (e) {
      // ignore storage read errors
    }
    return cfg;
  },
  (error) => Promise.reject(error)
);

// Provide both named and default export to avoid route warnings
export { apiClient };
export default apiClient;
