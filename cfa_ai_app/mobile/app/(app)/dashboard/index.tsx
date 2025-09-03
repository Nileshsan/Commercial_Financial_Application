import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  RefreshControl,
  Animated,
  StatusBar,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Chart } from '../../../components/Chart';
import { api } from '../../../services/api';

const { width } = Dimensions.get('window');

interface StatCard {
  title: string;
  value: string;
  change?: string;
  isPositive: boolean;
  icon: string;
  color: string;
}

interface DashboardData {
  totalRevenue: number;
  cashFlow: number;
  expenses: number;
  profitMargin: number; // percent
}

export default function DashboardScreen() {
  const [refreshing, setRefreshing] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState<'week' | 'month' | 'year'>('month');
  const [fadeAnim] = useState(new Animated.Value(0));

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 500,
      useNativeDriver: true,
    }).start();

    fetchDashboard();
  }, []);

  const statsFromData = (d: DashboardData | null): StatCard[] => {
    if (!d) return [];
    return [
      {
        title: 'Total Revenue',
        value: `₹${Math.round(d.totalRevenue).toLocaleString()}`,
        isPositive: true,
        icon: 'trending-up',
        color: '#4caf50',
      },
      {
        title: 'Cash Flow',
        value: `₹${Math.round(d.cashFlow).toLocaleString()}`,
        isPositive: d.cashFlow >= 0,
        icon: 'cash',
        color: '#2196f3',
      },
      {
        title: 'Expenses',
        value: `₹${Math.round(d.expenses).toLocaleString()}`,
        isPositive: false,
        icon: 'trending-down',
        color: '#ff9800',
      },
      {
        title: 'Profit Margin',
        value: `${d.profitMargin.toFixed(1)}%`,
        isPositive: d.profitMargin >= 0,
        icon: 'analytics',
        color: '#9c27b0',
      },
    ];
  };

  const renderStatCard = (stat: StatCard, index: number) => (
    <Animated.View
      key={index}
      style={[
        styles.statCard,
        {
          opacity: fadeAnim,
          transform: [
            {
              translateY: fadeAnim.interpolate({
                inputRange: [0, 1],
                outputRange: [20, 0],
              }),
            },
          ],
        },
      ]}
    >
      <LinearGradient colors={[stat.color + '20', stat.color + '10']} style={styles.statGradient}>
        <View style={styles.statHeader}>
          <Ionicons name={stat.icon as any} size={22} color={stat.color} />
          <Text style={[styles.changeText, { color: stat.isPositive ? '#4caf50' : '#f44336' }]}>
            {stat.change ?? ''}
          </Text>
        </View>
        <Text style={styles.statValue}>{stat.value}</Text>
        <Text style={styles.statTitle}>{stat.title}</Text>
      </LinearGradient>
    </Animated.View>
  );

  const renderQuickAction = (title: string, icon: string, color: string, onPress: () => void) => (
    <TouchableOpacity style={styles.quickAction} onPress={onPress}>
      <LinearGradient colors={[color + '20', color + '10']} style={styles.actionGradient}>
        <Ionicons name={icon as any} size={28} color={color} />
        <Text style={styles.actionTitle}>{title}</Text>
      </LinearGradient>
    </TouchableOpacity>
  );

  const fetchDashboard = useCallback(async () => {
    setRefreshing(true);
    setLoading(true);
    setError(null);

    try {
      const rawCid = await AsyncStorage.getItem('companyId');
      const companyId = rawCid ? Number(rawCid) : undefined;

      const [predRes, unpaidRes, balancesRes, summaryRes] = await Promise.allSettled([
        api.getCashflowPredictions(companyId, 30),
        api.getUnpaidSales(companyId as number),
        api.getPartyBalances(companyId as number),
        api.getPaymentAnalysisSummary(companyId as number),
      ]);

      const predictions = predRes.status === 'fulfilled' ? (predRes.value?.data ?? predRes.value) : null;
      const unpaid = unpaidRes.status === 'fulfilled' ? (unpaidRes.value?.data ?? unpaidRes.value) : null;
      const balances = balancesRes.status === 'fulfilled' ? (balancesRes.value?.data ?? balancesRes.value) : null;
      const summary = summaryRes.status === 'fulfilled' ? (summaryRes.value?.data ?? summaryRes.value) : null;

      const totalRevenue = Number(summary?.total_revenue ?? 0) || (predictions?.reduce ? predictions.reduce((s: number, p: any) => s + (p.type === 'receipt' ? p.amount : 0), 0) : 0);
      const expenses = Number(summary?.total_expenses ?? 0) || (predictions?.reduce ? predictions.reduce((s: number, p: any) => s + (p.type === 'payment' ? p.amount : 0), 0) : 0);
      const balancesSum = balances?.reduce ? balances.reduce((s: number, b: any) => s + (b.current_balance ?? 0), 0) : 0;
      const balancePrediction = predictions?.reduce ? predictions.reduce((s: number, p: any) => s + (p.type === 'balance' ? p.amount : 0), 0) : 0;
      const cashFlow = balancesSum + balancePrediction;
      const profitMargin = totalRevenue > 0 ? ((totalRevenue - expenses) / totalRevenue) * 100 : 0;

      setData({ totalRevenue, cashFlow, expenses, profitMargin });
    } catch (err: any) {
      setError(err?.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const onRefresh = useCallback(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#2e7d32" />

      <LinearGradient colors={['#2e7d32', '#4caf50', '#81c784']} style={styles.header}>
        <View style={styles.headerContent}>
          <Text style={styles.headerTitle}>Dashboard</Text>
          <Text style={styles.headerSubtitle}>Welcome back!</Text>
        </View>
      </LinearGradient>

      <ScrollView style={styles.content} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
        <View style={styles.periodSelector}>
          <TouchableOpacity style={[styles.periodBtn, selectedPeriod === 'week' && styles.periodBtnActive]} onPress={() => setSelectedPeriod('week')}>
            <Text style={[styles.periodText, selectedPeriod === 'week' && styles.periodTextActive]}>Week</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.periodBtn, selectedPeriod === 'month' && styles.periodBtnActive]} onPress={() => setSelectedPeriod('month')}>
            <Text style={[styles.periodText, selectedPeriod === 'month' && styles.periodTextActive]}>Month</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.periodBtn, selectedPeriod === 'year' && styles.periodBtnActive]} onPress={() => setSelectedPeriod('year')}>
            <Text style={[styles.periodText, selectedPeriod === 'year' && styles.periodTextActive]}>Year</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.statsGrid}>
          {loading && !data ? (
            <Text style={{ padding: 16 }}>Loading...</Text>
          ) : error ? (
            <Text style={{ padding: 16, color: 'red' }}>{error}</Text>
          ) : (
            statsFromData(data).map((stat, index) => renderStatCard(stat, index))
          )}
        </View>

        <View style={styles.chartSection}>
          <Text style={styles.sectionTitle}>Revenue Overview</Text>
          <View style={styles.chartContainer}>
            <Chart />
          </View>
        </View>

        <View style={styles.quickActions}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          <View style={styles.actionsGrid}>
            {renderQuickAction('Add Transaction', 'add-circle', '#4caf50', () => {})}
            {renderQuickAction('View Reports', 'document-text', '#2196f3', () => {})}
            {renderQuickAction('Manage Clients', 'people', '#ff9800', () => {})}
            {renderQuickAction('Settings', 'settings', '#9c27b0', () => {})}
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    paddingTop: 60,
    paddingBottom: 20,
    paddingHorizontal: 20,
  },
  headerContent: {
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.8)',
  },
  content: {
    flex: 1,
    paddingHorizontal: 20,
  },
  periodSelector: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 4,
    marginVertical: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  periodBtn: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: 8,
  },
  periodBtnActive: {
    backgroundColor: '#2e7d32',
  },
  periodText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
  },
  periodTextActive: {
    color: '#fff',
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  statCard: {
    width: (width - 60) / 2,
    marginBottom: 16,
  },
  statGradient: {
    padding: 16,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  statHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  statValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  statTitle: {
    fontSize: 12,
    color: '#666',
  },
  changeText: {
    fontSize: 12,
    fontWeight: '600',
  },
  chartSection: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 16,
  },
  chartContainer: {
    height: 200,
  },
  quickActions: {
    marginBottom: 20,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  quickAction: {
    width: (width - 60) / 2,
    marginBottom: 16,
  },
  actionGradient: {
    padding: 20,
    borderRadius: 12,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  actionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginTop: 8,
    textAlign: 'center',
  },
});

