import * as React from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Modal,
  ActivityIndicator,
  Alert
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../services/api';
import { formatCurrency } from '../lib/formatters';

interface BankBalanceInputProps {
  visible: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  balance: number | null;
  onBalanceChange: (value: number | null) => void;
}

export const BankBalanceInput: React.FC<BankBalanceInputProps> = ({
  visible,
  onClose,
  onConfirm,
  balance,
  onBalanceChange
}) => {
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async () => {
    if (!balance || isNaN(Number(balance))) {
      Alert.alert('Error', 'Please enter a valid balance');
      return;
    }

    try {
      setLoading(true);
      await onConfirm();
      onClose();
    } catch (error) {
      Alert.alert('Error', 'Failed to update bank balance. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.modalContainer}>
        <View style={styles.modalContent}>
          <Text style={styles.title}>Set Current Bank Balance</Text>
          
          <View style={styles.warningContainer}>
            <Ionicons name="warning-outline" size={24} color="#f57c00" />
            <Text style={styles.warningText}>
              Please set your current bank balance for accurate predictions
            </Text>
          </View>

          <TextInput
            style={styles.input}
            placeholder="Enter current bank balance"
            value={balance ? balance.toString() : ''}
            onChangeText={(text) => onBalanceChange(text ? Number(text) : null)}
            keyboardType="numeric"
            placeholderTextColor="#999"
          />

          <View style={styles.buttonContainer}>
            <TouchableOpacity 
              style={[styles.button, styles.cancelButton]} 
              onPress={onClose}
              disabled={loading}
            >
              <Text style={styles.buttonTextCancel}>Cancel</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.button,
                styles.submitButton,
                (!balance || loading) && styles.buttonDisabled
              ]}
              onPress={handleSubmit}
              disabled={!balance || loading}
            >
              {loading ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <Text style={styles.buttonText}>Update</Text>
              )}
            </TouchableOpacity>
          </View>

          <Text style={styles.note}>
            Note: This will be used as the starting point for cashflow predictions
          </Text>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalContainer: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginBottom: 16,
    textAlign: 'center',
  },
  warningContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff3e0',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  warningText: {
    flex: 1,
    marginLeft: 8,
    color: '#f57c00',
    fontSize: 14,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 20,
  },
  buttonContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  button: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  submitButton: {
    backgroundColor: '#2e7d32',
  },
  cancelButton: {
    backgroundColor: '#f5f5f5',
  },
  buttonDisabled: {
    backgroundColor: '#cccccc',
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonTextCancel: {
    color: '#666',
    fontSize: 16,
    fontWeight: '600',
  },
  note: {
    marginTop: 16,
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
    fontStyle: 'italic',
  },
});
