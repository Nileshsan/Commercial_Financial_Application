import React, { useState } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from '@/services/api';
import { AnimatedGradient } from '../../components/AnimatedGradient';

export default function LoginScreen() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async () => {
    if (!username || !password) {
      Alert.alert('Error', 'Please enter both username and password');
      return;
    }

    try {
      setLoading(true);
      console.log('Starting login process...');
      
      // Authenticate user using the api object
      const response = await api.login(username, password);
      console.log('Login response:', JSON.stringify(response, null, 2));

      if (response.status !== 'success' || !response.data?.token) {
        const errorMsg = response.message || 'Invalid username or password';
        console.error('Login failed:', errorMsg);
        Alert.alert('Login Failed', errorMsg);
        return;
      }

      // Store auth data
      try {
        await AsyncStorage.multiSet([
          ['sessionToken', response.data.token],
          ['userInfo', JSON.stringify(response.data.user)],
        ]);
        console.log('Authentication data stored successfully');
      } catch (storageError) {
        console.error('Failed to store auth data:', storageError);
        Alert.alert('Error', 'Failed to save login data. Please try again.');
        return;
      }

      // Set company context from login response
      const companyId = response.data.user.company_id;
      const companyName = response.data.user.company_name;
      const userCompanyName = response.data.user.user_company_name;
      
      await AsyncStorage.setItem('companyContext', JSON.stringify({
        companyId,
        companyName,
        userCompanyName
      }));
      console.log('Company context set:', { companyId, companyName, userCompanyName });
      
      // Check model status
      try {
        const modelStatusResponse = await api.checkModelStatus();
        console.log('Model status response:', modelStatusResponse);
        
        // Store model status
        await AsyncStorage.setItem('modelTrained', String(modelStatusResponse.isReady));
        
        // Navigate based on model status
        if (modelStatusResponse.isReady) {
          console.log('Model is ready, navigating to app');
          router.replace('/(app)');
        } else {
          console.log('Model needs training, navigating to training screen');
          router.replace('/(auth)/model-training');
        }
      } catch (modelError) {
        console.error('Error checking model status:', modelError);
        // If we can't check model status, assume we need training
        await AsyncStorage.setItem('modelTrained', 'false');
        router.replace('/(auth)/model-training');
      }
    } catch (error: any) {
      console.error('Login process error:', error);
      let errorMessage = 'An unexpected error occurred';
      if (error.message && error.message.includes('Network')) {
        errorMessage = 'Network error. Please check your connection.';
      } else if (error.message) {
        errorMessage = error.message;
      }
      Alert.alert('Login Error', errorMessage);
      // Log additional debugging information using network utilities
      try {
        const apiBaseUrl = await AsyncStorage.getItem('apiBaseUrl');
        console.log('Current API URL:', apiBaseUrl);
        const { checkNetworkConnectivity } = await import('../../utils/network');
        const networkStatus = await checkNetworkConnectivity(true);
        console.log('Network Status:', networkStatus);
      } catch (debugErr) {
        console.error('Error fetching network debug info:', debugErr);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <AnimatedGradient />
      <View style={styles.card}>
        <Text style={styles.title}>CFA Login</Text>
        <Text style={styles.subtitle}>Welcome to Smart Cash Flow Analytics</Text>
        
        <TextInput
          style={styles.input}
          placeholder="Username"
          value={username}
          onChangeText={setUsername}
          autoCapitalize="none"
          autoCorrect={false}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
        />
        
        <TouchableOpacity 
          style={[styles.loginButton, loading && styles.loginButtonDisabled]} 
          onPress={handleLogin}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.loginButtonText}>Login</Text>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'transparent',
  },
  card: {
    width: '90%',
    maxWidth: 400,
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.3)',
    padding: 32,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 24,
    elevation: 12,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#2e7d32',
    opacity: 0.8,
    marginBottom: 32,
    textAlign: 'center',
  },
  input: {
    width: '100%',
    backgroundColor: 'rgba(255,255,255,0.9)',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    fontSize: 16,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.1)',
  },
  loginButton: {
    backgroundColor: '#2e7d32',
    width: '100%',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 16,
    shadowColor: '#2e7d32',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  loginButtonDisabled: {
    opacity: 0.7,
  },
  loginButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
