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
import { formatCurrency } from '../../../utils/formatters';

interface Transaction {
  id: string;
  date: string;
  description: string;
  amount: number;
  type: 'income' | 'expense';
  category: string;
  party?: string;
}

export default function TransactionsScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'income' | 'expense'>('all');

  useEffect(() => {
    loadTransactions();
  }, []);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Mock data
      const mockTransactions: Transaction[] = [
        {
          id: '1',
          date: '2024-01-15',
          description: 'Client Payment - ABC Corp',
          amount: 50000,
          type: 'income',
          category: 'Sales',
          party: 'ABC Corp'
        },
        {
          id: '2',
          date: '2024-01-14',
          description: 'Office Supplies',
          amount: 2500,
          type: 'expense',
          category: 'Office'
        },
        {
          id: '3',
          date: '2024-01-13',
          description: 'Service Revenue - XYZ Ltd',
          amount: 35000,
          type: 'income',
          category: 'Services',
          party: 'XYZ Ltd'
        },
        {
          id: '4',
          date: '2024-01-12',
          description: 'Internet Bill',
          amount: 1500,
          type: 'expense',
          category: 'Utilities'
        },
        {
          id: '5',
          date: '2024-01-11',
          description: 'Consulting Fee - DEF Inc',
          amount: 75000,
          type: 'income',
          category: 'Consulting',
          party: 'DEF Inc'
        }
      ];
      
      setTransactions(mockTransactions);
    } catch (error) {
      console.error('Error loading transactions:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadTransactions();
    setRefreshing(false);
  };

  const filteredTransactions = transactions.filter(transaction => {
    if (selectedFilter === 'all') return true;
    return transaction.type === selectedFilter;
  });

  const renderTransaction = (transaction: Transaction) => (
    <View key={transaction.id} style={styles.transactionCard}>
      <View style={styles.transactionHeader}>
        <View style={styles.transactionInfo}>
          <Text style={styles.transactionDescription}>{transaction.description}</Text>
          <Text style={styles.transactionDate}>
            {new Date(transaction.date).toLocaleDateString()}
          </Text>
        </View>
        <View style={styles.transactionAmount}>
          <Text style={[
            styles.amountText,
            { color: transaction.type === 'income' ? '#2e7d32' : '#d32f2f' }
          ]}>
            {transaction.type === 'income' ? '+' : '-'}{formatCurrency(transaction.amount)}
          </Text>
        </View>
      </View>
      
      <View style={styles.transactionDetails}>
        <View style={styles.categoryContainer}>
          <Ionicons 
            name={transaction.type === 'income' ? 'trending-up' : 'trending-down'} 
            size={16} 
            color={transaction.type === 'income' ? '#2e7d32' : '#d32f2f'} 
          />
          <Text style={styles.categoryText}>{transaction.category}</Text>
        </View>
        {transaction.party && (
          <Text style={styles.partyText}>{transaction.party}</Text>
        )}
      </View>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#2e7d32" />
        <Text style={styles.loadingText}>Loading transactions...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Transactions</Text>
        
        <View style={styles.filterContainer}>
          <TouchableOpacity 
            style={[styles.filterButton, selectedFilter === 'all' && styles.filterButtonActive]}
            onPress={() => setSelectedFilter('all')}
          >
            <Text style={[styles.filterText, selectedFilter === 'all' && styles.filterTextActive]}>All</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.filterButton, selectedFilter === 'income' && styles.filterButtonActive]}
            onPress={() => setSelectedFilter('income')}
          >
            <Text style={[styles.filterText, selectedFilter === 'income' && styles.filterTextActive]}>Income</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.filterButton, selectedFilter === 'expense' && styles.filterButtonActive]}
            onPress={() => setSelectedFilter('expense')}
          >
            <Text style={[styles.filterText, selectedFilter === 'expense' && styles.filterTextActive]}>Expense</Text>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView 
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {filteredTransactions.length === 0 ? (
          <View style={styles.noDataContainer}>
            <Ionicons name="receipt-outline" size={48} color="#ccc" />
            <Text style={styles.noDataText}>No transactions found</Text>
          </View>
        ) : (
          filteredTransactions.map(renderTransaction)
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
  header: {
    backgroundColor: '#fff',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginBottom: 16,
  },
  filterContainer: {
    flexDirection: 'row',
    backgroundColor: '#f0f0f0',
    borderRadius: 8,
    padding: 4,
  },
  filterButton: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 6,
    alignItems: 'center',
  },
  filterButtonActive: {
    backgroundColor: '#2e7d32',
  },
  filterText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
  },
  filterTextActive: {
    color: '#fff',
  },
  content: {
    flex: 1,
    padding: 20,
  },
  transactionCard: {
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
  transactionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  transactionInfo: {
    flex: 1,
    marginRight: 12,
  },
  transactionDescription: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  transactionDate: {
    fontSize: 12,
    color: '#666',
  },
  transactionAmount: {
    alignItems: 'flex-end',
  },
  amountText: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  transactionDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  categoryContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  categoryText: {
    fontSize: 12,
    color: '#666',
    marginLeft: 4,
  },
  partyText: {
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
