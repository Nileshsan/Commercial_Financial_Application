import { useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from 'services/api';

export function useAuth() {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [apiToken, setApiToken] = useState<string | null>(null);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const [token, modelTrained] = await Promise.all([
        AsyncStorage.getItem('apiToken'),
        AsyncStorage.getItem('modelTrained'),
      ]);

      if (token && modelTrained === 'true') {
        setIsAuthenticated(true);
        setApiToken(token);
      } else {
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Error checking auth status:', error);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (token: string) => {
    try {
      await AsyncStorage.setItem('apiToken', token);
      setApiToken(token);
      setIsAuthenticated(true);
    } catch (error) {
      console.error('Error during login:', error);
      throw error;
    }
  };

  const logout = async () => {
    try {
      await Promise.all([
        AsyncStorage.removeItem('apiToken'),
        AsyncStorage.removeItem('modelTrained'),
      ]);
      setApiToken(null);
      setIsAuthenticated(false);
    } catch (error) {
      console.error('Error during logout:', error);
      throw error;
    }
  };

  return {
    isLoading,
    isAuthenticated,
    apiToken,
    login,
    logout,
    checkAuthStatus,
  };
}
