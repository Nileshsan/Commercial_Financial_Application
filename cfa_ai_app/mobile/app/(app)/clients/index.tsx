import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity, 
  ActivityIndicator,
  RefreshControl
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import ClientList from './ClientList';
import CashflowGraph from '../../components/CashflowGraph';
import api from 'services/api';
import AsyncStorage from '@react-native-async-storage/async-storage';
const apiClient = api;
import { formatCurrency } from '../../utils/formatters';

interface CashflowData {
  date: string;
  projectedBalance: number;
  actualBalance?: number;
  receivables?: number;
  payables?: number;
}

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

export default function ClientsScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [cashflowData, setCashflowData] = useState<CashflowData[]>([]);
  const [cashflowLoading, setCashflowLoading] = useState(true);

  useEffect(() => {
    loadInitialData();
  }, []);

  

  const loadInitialData = async () => {
    // Ensure we have a valid session token before making protected requests
    try {
      const hasToken = await apiClient.hasValidToken();
      if (!hasToken) {
        console.warn('No valid session token found - skipping protected data loads');
        setLoading(false);
        setCashflowLoading(false);
        return;
      }
    } catch (e) {
      console.warn('Error checking token, skipping protected loads', e);
      setLoading(false);
      setCashflowLoading(false);
      return;
    }

    await Promise.all([
      loadClients(),
      loadCashflowData()
    ]);
  };

  const loadClients = async () => {
    try {
      setLoading(true);
      // Use backend-provided endpoints via ApiClient if available. As a fallback,
      // we call the raw payment/party endpoints only when session token is present.
      const companyIdStr = await AsyncStorage.getItem('companyId');
      const companyId = companyIdStr ? Number(companyIdStr) : undefined;
      if (!companyId) return;

      // Fetch party balances as a proxy for clients list (backend doesn't expose a typed client list here)
      const pbRes = await apiClient.fetchPartyBalances(companyId);
      if (pbRes && pbRes.status === 'success' && pbRes.data) {
        // Normalize party balances response into an array regardless of shape
        const partyList: any[] = Array.isArray(pbRes.data)
          ? pbRes.data
          : Array.isArray(pbRes.data.party_balances)
            ? pbRes.data.party_balances
            : Array.isArray(pbRes.data.data?.party_balances)
              ? pbRes.data.data.party_balances
              : [];

        // Map PartyBalance -> Client minimal representation
        const clientsData = partyList.map((c: any, idx: number) => ({
          id: c.id ? String(c.id) : `${(c.party_name || c.party || 'client')}-${idx}`,
          name: c.party_name || c.party || 'Unknown',
          email: '',
          phone: '',
          totalRevenue: 0,
          outstandingBalance: c.current_balance || 0,
          lastTransaction: c.last_updated || new Date().toISOString(),
          status: 'active' as 'active'
        }));
        setClients(clientsData);
      }
    } catch (error) {
      console.error('Error loading clients:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadCashflowData = async () => {
    try {
      setCashflowLoading(true);
      // Use canonical payment predictions endpoint which requires company_id
      const companyIdStr = await AsyncStorage.getItem('companyId');
      const companyId = companyIdStr ? Number(companyIdStr) : undefined;
      if (!companyId) throw new Error('Company ID not found');

      const response = await apiClient.getCashflowPredictions(companyId, 30);
      if (response && response.status === 'success' && response.data) {
        setCashflowData((response.data.predictions || []).map((p: any) => ({ date: p.date, projectedBalance: p.predicted_balance })));
      }
    } catch (error) {
      console.error('Error loading cashflow data:', error);
    } finally {
      setCashflowLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadInitialData();
    setRefreshing(false);
  };

  const filteredClients = clients.filter(client => {
    if (selectedFilter === 'all') return true;
    return client.status === selectedFilter;
  });

  const renderClient = (client: Client) => (
    <TouchableOpacity key={client.id} style={styles.clientCard}>
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

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#2e7d32" />
        <Text style={styles.loadingText}>Loading clients...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scrollView}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {!cashflowLoading && cashflowData.length > 0 && (
          <CashflowGraph
            data={cashflowData}
            showReceivables={true}
            showPayables={true}
          />
        )}
        
        <View style={styles.filterContainer}>
          <TouchableOpacity 
            style={[styles.filterButton, selectedFilter === 'all' && styles.filterButtonActive]}
            onPress={() => setSelectedFilter('all')}
          >
            <Text style={[styles.filterText, selectedFilter === 'all' && styles.filterTextActive]}>All</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.filterButton, selectedFilter === 'active' && styles.filterButtonActive]}
            onPress={() => setSelectedFilter('active')}
          >
            <Text style={[styles.filterText, selectedFilter === 'active' && styles.filterTextActive]}>Active</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.filterButton, selectedFilter === 'inactive' && styles.filterButtonActive]}
            onPress={() => setSelectedFilter('inactive')}
          >
            <Text style={[styles.filterText, selectedFilter === 'inactive' && styles.filterTextActive]}>Inactive</Text>
          </TouchableOpacity>
        </View>

        {filteredClients.map(renderClient)}

        {filteredClients.length === 0 && (
          <View style={styles.noDataContainer}>
            <Ionicons name="people-outline" size={48} color="#ccc" />
            <Text style={styles.noDataText}>No clients found</Text>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  scrollView: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#666',
  },
  filterContainer: {
    flexDirection: 'row',
    padding: 16,
    backgroundColor: '#fff',
    marginBottom: 16,
  },
  filterButton: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: '#f5f5f5',
    marginHorizontal: 4,
    alignItems: 'center',
  },
  filterButtonActive: {
    backgroundColor: '#2e7d32',
  },
  filterText: {
    fontSize: 14,
    color: '#666',
  },
  filterTextActive: {
    color: '#fff',
  },
  clientCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
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
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
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
    fontWeight: '600',
  },
  clientDetails: {
    gap: 12,
  },
  contactInfo: {
    gap: 6,
  },
  contactItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  contactText: {
    fontSize: 14,
    color: '#666',
    marginLeft: 8,
  },
  financialInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#f8f9fa',
    padding: 12,
    borderRadius: 8,
  },
  financialItem: {
    alignItems: 'center',
  },
  financialLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
  },
  financialValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#2e7d32',
  },
  lastTransaction: {
    borderTopWidth: 1,
    borderTopColor: '#f0f0f0',
    paddingTop: 8,
  },
  lastTransactionText: {
    fontSize: 12,
    color: '#666',
    fontStyle: 'italic',
  },
  noDataContainer: {
    alignItems: 'center',
    padding: 40,
  },
  noDataText: {
    marginTop: 16,
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
  },
});
