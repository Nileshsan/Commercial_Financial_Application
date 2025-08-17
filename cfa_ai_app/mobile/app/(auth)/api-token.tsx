import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Platform, Alert, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import QRCode from 'react-native-qrcode-svg';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from '../../services/api';
import { AnimatedGradient } from '../../components/AnimatedGradient';

export default function APITokenScreen() {
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    getAuthToken();
  }, []);

  const getAuthToken = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Get auth token from storage
      const token = await AsyncStorage.getItem('sessionToken');
      const userInfo = await AsyncStorage.getItem('userInfo');
      
      if (!token) {
        throw new Error('No authentication token found. Please login again.');
      }

      // Store the session token as API token
      await AsyncStorage.setItem('apiToken', token);
      setAuthToken(token);
      
      if (userInfo) {
        const userData = JSON.parse(userInfo);
        await AsyncStorage.setItem('companyName', userData.company_name || '');
        await AsyncStorage.setItem('userCompanyName', userData.user_company_name || '');
      }
    } catch (err: any) {
      console.error('API token generation error:', err);
      setError(err.message || 'Failed to generate API token. Please try again.');
      Alert.alert('Error', err.message || 'Failed to generate API token. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (authToken) {
      await Clipboard.setStringAsync(authToken);
      Alert.alert('Copied!', 'Authentication token copied to clipboard.');
    }
  };

  const handleNext = async () => {
    if (!authToken) return;
    
    try {
      // Navigate to model training
      router.replace('/(auth)/model-training');
    } catch (error) {
      console.error('Error:', error);
      Alert.alert('Error', 'An unexpected error occurred.');
    }
  };

  return (
    <View style={styles.container}>
      <AnimatedGradient />
      <View style={styles.card}>
        <View style={styles.header}>
          <Ionicons name="key-outline" size={32} color="#2e7d32" />
          <Text style={styles.title}>Your Authentication Token</Text>
          <Text style={styles.subtitle}>Keep this token secure</Text>
        </View>

        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#2e7d32" />
            <Text style={styles.loadingText}>Loading your authentication token...</Text>
          </View>
        ) : error ? (
          <View style={styles.errorContainer}>
            <Ionicons name="alert-circle" size={48} color="#d32f2f" />
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={getAuthToken}>
              <Ionicons name="refresh" size={20} color="#2e7d32" />
              <Text style={styles.retryText}>Try Again</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            <View style={styles.qrContainer}>
              <QRCode value={authToken || ''} size={200} backgroundColor="transparent" />
            </View>
            
            <View style={styles.tokenSection}>
              <Text style={styles.tokenLabel}>Your Authentication Token:</Text>
              <View style={styles.tokenRow}>
                <Text style={styles.token}>{authToken}</Text>
                <TouchableOpacity onPress={handleCopy} style={styles.copyBtn}>
                  <Ionicons name="copy-outline" size={24} color="#2e7d32" />
                </TouchableOpacity>
              </View>
            </View>

            <View style={styles.infoContainer}>
              <Ionicons name="information-circle" size={20} color="#2e7d32" />
              <Text style={styles.info}>
                This is your authentication token. Keep it secure and do not share it with others.
              </Text>
            </View>

            <TouchableOpacity style={styles.nextBtn} onPress={handleNext}>
              <Text style={styles.nextBtnText}>Continue to Model Training</Text>
              <Ionicons name="arrow-forward" size={20} color="#fff" />
            </TouchableOpacity>
          </>
        )}
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
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.3)',
    padding: 32,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 24,
    elevation: 12,
    backdropFilter: Platform.OS === 'web' ? 'blur(12px)' : undefined,
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginTop: 8,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: '#2e7d32',
    opacity: 0.8,
  },
  loadingContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  loadingText: {
    color: '#2e7d32',
    marginTop: 16,
    fontSize: 16,
    textAlign: 'center',
  },
  errorContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  errorText: {
    color: '#d32f2f',
    textAlign: 'center',
    marginVertical: 16,
    fontSize: 16,
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(46,125,50,0.1)',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(46,125,50,0.2)',
  },
  retryText: {
    color: '#2e7d32',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  qrContainer: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 24,
    shadowColor: '#0a2a66',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 6,
  },
  tokenSection: {
    width: '100%',
    marginBottom: 20,
  },
  tokenLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#2e7d32',
    marginBottom: 8,
  },
  tokenRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.9)',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.1)',
  },
  token: {
    flex: 1,
    fontSize: 16,
    color: '#2e7d32',
    fontWeight: '600',
    letterSpacing: 1,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  copyBtn: {
    marginLeft: 12,
    padding: 8,
    borderRadius: 8,
    backgroundColor: 'rgba(46,125,50,0.1)',
  },
  infoContainer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: 'rgba(46,125,50,0.1)',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  info: {
    flex: 1,
    marginLeft: 12,
    color: '#2e7d32',
    fontSize: 14,
    lineHeight: 20,
  },
  nextBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2e7d32',
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 24,
    width: '100%',
    justifyContent: 'center',
    shadowColor: '#2e7d32',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  nextBtnText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 16,
    marginRight: 8,
  },
});

