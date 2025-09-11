import axios, { AxiosInstance } from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL, API_TIMEOUT } from '../config';

export const createApiInstance = (): AxiosInstance => {
  const instance = axios.create({
    baseURL: `${API_BASE_URL}/api/`,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    timeout: API_TIMEOUT,
  });

  // Request interceptor for adding token
  instance.interceptors.request.use(
    async (config) => {
      const token = await AsyncStorage.getItem('sessionToken');
      if (token) {
        config.headers.Authorization = `Token ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // Response interceptor for error handling
  instance.interceptors.response.use(
    (response) => response,
    async (error) => {
      if (error.response?.status === 401) {
        // Clear auth data on unauthorized
        await AsyncStorage.multiRemove(['sessionToken', 'userInfo']);
      }
      return Promise.reject(error);
    }
  );

  return instance;
};

export const api = createApiInstance();

export default api;
