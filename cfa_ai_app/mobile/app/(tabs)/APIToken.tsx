import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Platform, Alert, ActivityIndicator } from 'react-native';
import { AnimatedGradient } from '../../components/AnimatedGradient';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import QRCode from 'react-native-qrcode-svg';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from '@/services/api';

export default function APITokenScreen() {
  const [apiToken, setApiToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    generateToken();
  }, []);

  const generateToken = async () => {
    try {
      setLoading(true);
      setError(null);
      const token = await api.generateApiToken();
      setApiToken(token);
    } catch (err) {
      setError('Failed to generate API token. Please try again.');
      Alert.alert('Error', 'Failed to generate API token. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    Clipboard.setStringAsync(apiToken ?? '');
    Alert.alert('Copied!', 'API token copied to clipboard.');
  };

  const handleNext = async () => {
    if (!apiToken) return;
    
    try {
      // Save API token
      await AsyncStorage.setItem('apiToken', apiToken);
      
      // Navigate to model training
      router.replace('/model-training');
    } catch (error) {
      console.error('Error saving token:', error);
      Alert.alert('Error', 'Failed to save API token. Please try again.');
    }
  };

  return (
    <View style={styles.container}>
      <AnimatedGradient />
      <View style={styles.card}>
        <Text style={styles.title}>Your API Token</Text>
        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#2e7d32" />
            <Text style={styles.loadingText}>Generating your secure token...</Text>
          </View>
        ) : error ? (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={generateToken}>
              <Text style={styles.retryText}>Try Again</Text>
              <Ionicons name="refresh" size={20} color="#2e7d32" style={{ marginLeft: 8 }} />
            </TouchableOpacity>
          </View>
        ) : (
          <>
            <View style={styles.qrContainer}>
              <QRCode value={apiToken || ''} size={180} backgroundColor="transparent" />
            </View>
            <View style={styles.tokenRow}>
              <Text style={styles.token}>{apiToken}</Text>
              <TouchableOpacity onPress={handleCopy} style={styles.copyBtn}>
                <Ionicons name="copy-outline" size={22} color="#2e7d32" />
              </TouchableOpacity>
            </View>
            <Text style={styles.info}>
              Use this token in your desktop sync agent to securely link your Tally data with your account.
            </Text>
            <TouchableOpacity style={styles.nextBtn} onPress={handleNext}>
              <Text style={styles.nextBtnText}>Proceed with Authentication</Text>
              <Ionicons name="arrow-forward-circle" size={22} color="#fff" style={{ marginLeft: 8 }} />
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
  loadingContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
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
    padding: 20,
  },
  errorText: {
    color: '#d32f2f',
    textAlign: 'center',
    marginBottom: 16,
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(46,125,50,0.1)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: {
    color: '#2e7d32',
    fontSize: 16,
    fontWeight: '600',
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
    // backdropFilter is not supported in React Native StyleSheet
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginBottom: 18,
    textAlign: 'center',
  },
  qrContainer: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 12,
    marginBottom: 18,
    shadowColor: '#0a2a66',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 6,
  },
  tokenRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  token: {
    fontSize: 18,
    color: '#2e7d32',
    fontWeight: 'bold',
    letterSpacing: 1.2,
    backgroundColor: 'rgba(255,255,255,0.8)',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  copyBtn: {
    marginLeft: 10,
    padding: 6,
    borderRadius: 8,
    backgroundColor: 'rgba(210,236,248,0.5)',
  },
  info: {
    marginTop: 16,
    color: '#2e7d32',
    fontSize: 14,
    textAlign: 'center',
  },
  nextBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2e7d32',
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 24,
    width: '100%',
    justifyContent: 'center',
    marginTop: 18,
  },
  nextBtnText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 16,
  },
});
