import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { formatCurrency } from '../../../utils/formatters';

interface Client {
  id: string;
  name: string;
  email: string;
  phone: string;
  totalRevenue: number;
  outstandingBalance: number;
  lastTransaction: string;
  status: 'active' | 'inactive';
}

interface Props {
  clients: Client[];
  onClientPress?: (client: Client) => void;
}

const ClientList: React.FC<Props> = ({ clients, onClientPress }) => {
    if (!clients?.length) {
        return (
            <View style={styles.noDataContainer}>
                <Text style={styles.noDataText}>No clients found</Text>
            </View>
        );
    }

const renderClient = (client: Client) => (
    <TouchableOpacity 
      key={client.id} 
      style={styles.clientCard}
      onPress={() => onClientPress?.(client)}
    >
      <View style={styles.clientHeader}>
        <View style={styles.clientInfo}>
          <Text style={styles.clientName}>{client.name}</Text>
          <View style={styles.clientStatus}>
            <View style={[
              styles.statusDot,
              { backgroundColor: client.status === 'active' ? '#2e7d32' : '#d32f2f' }
            ]} />
            <Text style={[
              styles.statusText,
              { color: client.status === 'active' ? '#2e7d32' : '#d32f2f' }
            ]}>
              {client.status.charAt(0).toUpperCase() + client.status.slice(1)}
            </Text>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={20} color="#666" />
      </View>
      
      <View style={styles.clientDetails}>
        <View style={styles.contactInfo}>
          <View style={styles.contactItem}>
            <Ionicons name="mail-outline" size={16} color="#666" />
            <Text style={styles.contactText}>{client.email}</Text>
          </View>
          <View style={styles.contactItem}>
            <Ionicons name="call-outline" size={16} color="#666" />
            <Text style={styles.contactText}>{client.phone}</Text>
          </View>
        </View>
        
        <View style={styles.financialInfo}>
          <View style={styles.financialItem}>
            <Text style={styles.financialLabel}>Total Revenue</Text>
            <Text style={styles.financialValue}>{formatCurrency(client.totalRevenue)}</Text>
          </View>
          <View style={styles.financialItem}>
            <Text style={styles.financialLabel}>Outstanding</Text>
            <Text style={[
              styles.financialValue,
              { color: client.outstandingBalance > 0 ? '#d32f2f' : '#2e7d32' }
            ]}>
              {formatCurrency(client.outstandingBalance)}
            </Text>
          </View>
        </View>
        
        <View style={styles.lastTransaction}>
          <Text style={styles.lastTransactionText}>
            Last transaction: {new Date(client.lastTransaction).toLocaleDateString()}
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      {clients.map(client => renderClient(client))}
      {clients.length === 0 && (
        <View style={styles.noDataContainer}>
          <Text style={styles.noDataText}>No clients found</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  clientCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  clientHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  clientInfo: {
    flex: 1,
  },
  clientName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
    marginBottom: 4,
  },
  clientStatus: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    fontSize: 12,
  },
  clientDetails: {
    marginTop: 8,
  },
  contactInfo: {
    marginBottom: 12,
  },
  contactItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  contactText: {
    marginLeft: 8,
    fontSize: 14,
    color: '#666',
  },
  financialInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  financialItem: {
    flex: 1,
  },
  financialLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
  },
  financialValue: {
    fontSize: 16,
    fontWeight: '600',
  },
  lastTransaction: {
    borderTopWidth: 1,
    borderTopColor: '#eee',
    paddingTop: 12,
  },
  lastTransactionText: {
    fontSize: 12,
    color: '#666',
  },
  noDataContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  noDataText: {
    fontSize: 16,
    color: '#666',
  },
});

export default ClientList;
