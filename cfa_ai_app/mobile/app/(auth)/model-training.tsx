import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert, Animated } from 'react-native';
import { useRouter } from 'expo-router';
import Ionicons from '@expo/vector-icons/Ionicons';
import { api } from '@/services/api';
import NetworkService from '@/services/NetworkService';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AnimatedGradient } from '../../components/AnimatedGradient';

export default function ModelTrainingScreen() {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('initializing');
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  // Animation values
  const progressAnim = new Animated.Value(0);
  const scaleAnim = new Animated.Value(1);

  const [trainingReason, setTrainingReason] = useState<string>('');

  useEffect(() => {
    checkTrainingStatus();
  }, []);

  useEffect(() => {
    // Animate progress bar
    Animated.timing(progressAnim, {
      toValue: progress / 100,
      duration: 500,
      useNativeDriver: false,
    }).start();
  }, [progress]);

  const checkTrainingStatus = async () => {
    try {
      const networkService = NetworkService.getInstance();
      const response = await networkService.request({
        method: 'GET',
        url: 'model/status/'
      });
      const {
        isReady,
        lastTrainingDate,
        dataLastModifiedDate,
        hasTrainingData
      } = response.data || {};

      let reason = '';
      if (!isReady) {
        reason = 'Initial model setup required';
      } else if (!lastTrainingDate) {
        reason = 'First-time training needed';
      } else if (dataLastModifiedDate && new Date(dataLastModifiedDate) > new Date(lastTrainingDate)) {
        reason = 'Data has been modified since last training';
      } else if (!hasTrainingData) {
        reason = 'No training data available';
      }

      setTrainingReason(reason);
      startTraining();
    } catch (error) {
      console.error('Error checking training status:', error);
      setError('Failed to check training status');
    }
  };


  const startTraining = async () => {
    try {
      setStatus('training');
      setError(null);

      // Get company ID and session token
      const [companyId, sessionToken] = await Promise.all([
        AsyncStorage.getItem('companyId'),
        AsyncStorage.getItem('sessionToken')
      ]);

      console.log('Training with companyId:', companyId);
      console.log('Training with sessionToken:', sessionToken);
      
      if (!companyId || !sessionToken) {
        console.error('Missing data:', { companyId, sessionToken });
        throw new Error('Company ID or session token not found. Please login again.');
      }

      // Initialize api client and set token
      await api.init();
      await api.setAuthToken(sessionToken);

      // Check model status and data availability
      try {
        console.debug('[ModelTraining] companyId=', companyId, 'sessionTokenPresent=', !!sessionToken);
        
        // First check if we have a trained model
        const modelStatus = await api.checkModelStatus();
        const hasTrainedModel = modelStatus?.data?.status === 'trained';
        const hasNewData = modelStatus?.data?.has_new_data;
        
        // If we have trained model but no new data, use existing predictions
        if (hasTrainedModel && !hasNewData) {
          console.log('Using existing model - no new data available');
          setProgress(100);
          setStatus('completed');
          return;
        }
        
        // Check if we have any transaction data before starting new training
        const dataCheckResponse = await api.getCashflowPredictions(parseInt(companyId, 10), 1);
        if (dataCheckResponse.status === 'error' || !dataCheckResponse.data) {
          throw new Error('No transaction data found. Please import your Tally data first.');
        }
      } catch (dataError: any) {
        if (dataError.message && dataError.message.includes('No transaction data')) {
          throw new Error('No transaction data found. Please import your Tally data first using the desktop sync agent or manual import.');
        }
        // If it's not a data error, continue with training
      }

      // Step 1: Load and preprocess data
      console.log('Starting data loading step...');
      try {
        const response = await api.trainModel('data-loading', parseInt(companyId, 10), (progress: number) => {
          setProgress(progress * 0.25); // 0-25%
        });
        console.log('Data loading response:', response);
        setProgress(25);
      } catch (error: any) {
        console.error('Data loading error:', {
          message: error.message,
          response: error.response?.data,
          status: error.response?.status,
          company: companyId
        });
        
        // Check response for detailed status
        const response = error.response?.data;
        if (response?.data?.using_cached) {
          console.log('Using cached data - no new transactions to process');
          setProgress(100);
          setStatus('completed');
          return;
        }
        
        // If we have a specific backend message, use it
        if (response?.message) {
          throw new Error(response.message);
        }
        
        throw new Error('Failed to load data. Please ensure you have transaction data available.');
      }

      // Step 2: Analyze payment patterns
      console.log('Starting payment patterns analysis...');
      try {
        const response = await api.trainModel('payment-patterns', parseInt(companyId, 10), (progress: number) => {
          setProgress(25 + progress * 0.25); // 25-50%
        });
        setProgress(50);
        
        // Validate the response
        if (!response || response.status === 'error') {
          throw new Error(response?.message || 'Failed to analyze payment patterns');
        }
      } catch (error: any) {
        console.error('Payment patterns error:', {
          message: error.message,
          response: error.response?.data,
          status: error.response?.status
        });
        
        // Check if it's a data-related error
        if (error.message && (
          error.message.includes('No transaction data found') ||
          error.message.includes('No sales transactions found') ||
          error.message.includes('No receipt transactions found')
        )) {
          throw new Error('No transaction data found. Please import your Tally data first using the desktop sync agent or manual import.');
        }
        
        throw new Error('Failed to analyze payment patterns. Please ensure you have valid transaction data with matching sales and receipts.');
      }

      // Step 3: Process fixed expenses
      console.log('Processing fixed expenses...');
      try {
        const response = await api.trainModel('fixed-expenses', parseInt(companyId, 10), (progress: number) => {
          setProgress(50 + progress * 0.25); // 50-75%
        });
        
        // Validate the response
        if (!response || response.status === 'error') {
          throw new Error(response?.message || 'Failed to process fixed expenses');
        }
      } catch (error: any) {
        console.error('Fixed expenses error:', {
          message: error.message,
          response: error.response?.data,
          status: error.response?.status
        });
        throw new Error('Failed to process fixed expenses. Please ensure you have valid payment transactions.');
      }

      // Step 4: Setup cashflow predictions
      console.log('Setting up cashflow predictions...');
      try {
        const response = await api.trainModel('cashflow-setup', parseInt(companyId, 10), (progress: number) => {
          setProgress(75 + progress * 0.25); // 75-100%
        });
        // Validate the response
        if (!response || response.status === 'error') {
          throw new Error(response?.message || 'Failed to setup cashflow predictions');
        }
      } catch (error: any) {
        console.error('Cashflow setup error:', {
          message: error.message,
          response: error.response?.data,
          status: error.response?.status
        });
        throw new Error('Failed to setup cashflow predictions. Please check if all previous steps completed successfully.');
      }

      // If training completes successfully
      setStatus('completed');
      await AsyncStorage.setItem('modelTrained', 'true');

      // Animate completion
      Animated.sequence([
        Animated.timing(scaleAnim, {
          toValue: 1.1,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(scaleAnim, {
          toValue: 1,
          duration: 200,
          useNativeDriver: true,
        }),
      ]).start();

      // Navigate to main app after a short delay
      setTimeout(() => {
        router.replace('/(app)');
      }, 2000);
    } catch (err: any) {
      console.error('Training error:', err);
      let errorMessage = 'Failed to train the model. Please try again.';
      
      if (err.response?.data?.message) {
        errorMessage = err.response.data.message;
      } else if (err.response?.status === 500) {
        errorMessage = 'Server error occurred. Please ensure you have:\n\n' +
          '1. Transaction data in the system\n' +
          '2. Both sales and receipt records\n' +
          '3. Valid party names and amounts\n\n' +
          'Try importing your data first if not already done.';
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      console.log('Detailed error:', {
        status: err.response?.status,
        data: err.response?.data,
        message: err.message
      });
      
      setError(errorMessage);
      setStatus('error');
      Alert.alert('Training Error', errorMessage, [
        { 
          text: 'OK',
          onPress: () => console.log('Error alert closed')
        },
        {
          text: 'Retry',
          onPress: () => {
            setError(null);
            setProgress(0);
            startTraining();
          }
        }
      ]);
    }
  };

  const renderContent = () => {
    switch (status) {
      case 'training':
        return (
          <>
            <View style={styles.progressContainer}>
              {trainingReason && (
                <Text style={[styles.progressText, { marginBottom: 20, fontStyle: 'italic' }]}>
                  {trainingReason}
                </Text>
              )}
              <ActivityIndicator size="large" color="#2e7d32" style={styles.spinner} />
              <Text style={styles.progressText}>{Math.round(progress)}% Complete</Text>
              
              <View style={styles.progressBarContainer}>
                <View style={styles.progressBar}>
                  <Animated.View
                    style={[
                      styles.progressBarFill,
                      {
                        width: progressAnim.interpolate({
                          inputRange: [0, 1],
                          outputRange: ['0%', '100%'],
                        }),
                      },
                    ]}
                  />
                </View>
              </View>
            </View>
            
            <Text style={styles.description}>
              Training your AI model to recognize and analyze your business data patterns...
            </Text>
            
            <View style={styles.stepsContainer}>
              <View style={styles.step}>
                <Ionicons name="checkmark-circle" size={20} color="#2e7d32" />
                <Text style={styles.stepText}>Data preprocessing</Text>
              </View>
              <View style={styles.step}>
                <Ionicons name="checkmark-circle" size={20} color="#2e7d32" />
                <Text style={styles.stepText}>Feature extraction</Text>
              </View>
              <View style={styles.step}>
                <Ionicons name="checkmark-circle" size={20} color="#2e7d32" />
                <Text style={styles.stepText}>Model training</Text>
              </View>
              <View style={styles.step}>
                <Ionicons name="checkmark-circle" size={20} color="#2e7d32" />
                <Text style={styles.stepText}>Validation</Text>
              </View>
            </View>
          </>
        );

      case 'completed':
        return (
          <Animated.View style={[styles.completedContainer, { transform: [{ scale: scaleAnim }] }]}>
            <Ionicons name="checkmark-circle" size={80} color="#2e7d32" />
            <Text style={styles.successText}>Training Complete!</Text>
            <Text style={styles.description}>
              Your AI model is now ready to analyze your business data and provide intelligent insights.
            </Text>
            <View style={styles.successSteps}>
              <Text style={styles.successStep}>✓ Model trained successfully</Text>
              <Text style={styles.successStep}>✓ Data patterns learned</Text>
              <Text style={styles.successStep}>✓ Ready for predictions</Text>
            </View>
          </Animated.View>
        );

      case 'error':
        return (
          <>
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={48} color="#d32f2f" />
              <Text style={styles.errorText}>{error}</Text>
            </View>
            
            <View style={styles.actionButtons}>
              <TouchableOpacity style={styles.retryButton} onPress={startTraining}>
                <Ionicons name="refresh" size={20} color="#fff" />
                <Text style={styles.retryText}>Try Again</Text>
              </TouchableOpacity>
              
              {error && error.includes('No transaction data found') && (
                <TouchableOpacity 
                  style={styles.importButton} 
                  onPress={() => {
                    Alert.alert(
                      'Import Data',
                      'To import your Tally data, you need to:\n\n1. Download the desktop sync agent\n2. Install it on your computer with Tally\n3. Use the API key from your mobile app\n4. Run the sync to import your data\n\nWould you like to see the API key?',
                      [
                        { text: 'Cancel', style: 'cancel' },
                        { 
                          text: 'Show API Key', 
                          onPress: () => router.push('/(auth)/api-token')
                        }
                      ]
                    );
                  }}
                >
                  <Ionicons name="download" size={20} color="#2e7d32" />
                  <Text style={styles.importText}>Import Data</Text>
                </TouchableOpacity>
              )}
            </View>
          </>
        );

      default:
        return <ActivityIndicator size="large" color="#2e7d32" />;
    }
  };

  return (
    <View style={styles.container}>
      <AnimatedGradient />
      <View style={styles.card}>
        <View style={styles.header}>
          <Ionicons name="analytics-outline" size={32} color="#2e7d32" />
          <Text style={styles.title}>AI Model Training</Text>
          <Text style={styles.subtitle}>Preparing your intelligent assistant</Text>
        </View>
        
        {renderContent()}
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
  },
  header: {
    alignItems: 'center',
    marginBottom: 32,
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
  progressContainer: {
    alignItems: 'center',
    marginBottom: 24,
  },
  spinner: {
    marginBottom: 16,
  },
  progressText: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginBottom: 16,
  },
  progressBarContainer: {
    width: '100%',
    marginBottom: 16,
  },
  progressBar: {
    width: '100%',
    height: 8,
    backgroundColor: 'rgba(46,125,50,0.2)',
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#2e7d32',
    borderRadius: 4,
  },
  description: {
    fontSize: 16,
    color: '#2e7d32',
    textAlign: 'center',
    opacity: 0.8,
    marginBottom: 24,
    lineHeight: 22,
  },
  stepsContainer: {
    width: '100%',
  },
  step: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: 'rgba(46,125,50,0.1)',
    borderRadius: 8,
  },
  stepText: {
    marginLeft: 12,
    fontSize: 14,
    color: '#2e7d32',
    fontWeight: '500',
  },
  completedContainer: {
    alignItems: 'center',
  },
  successText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginVertical: 16,
  },
  successSteps: {
    marginTop: 16,
    alignItems: 'flex-start',
  },
  successStep: {
    fontSize: 14,
    color: '#2e7d32',
    marginBottom: 8,
    fontWeight: '500',
  },
  errorContainer: {
    alignItems: 'center',
    marginBottom: 24,
  },
  errorText: {
    fontSize: 16,
    color: '#d32f2f',
    textAlign: 'center',
    marginTop: 16,
    lineHeight: 24,
  },
  actionButtons: {
    width: '100%',
    alignItems: 'center',
  },
  retryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2e7d32',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
    shadowColor: '#2e7d32',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  retryText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  importButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#e8f5e8',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
    marginTop: 16,
    borderWidth: 1,
    borderColor: '#2e7d32',
  },
  importText: {
    color: '#2e7d32',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
});
