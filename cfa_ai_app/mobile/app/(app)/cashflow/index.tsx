import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity, 
  Alert, 
  Dimensions,
  ActivityIndicator,
  RefreshControl
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { formatCurrency } from '../../../utils/formatters';
import { api } from '../../../services/api';
import { BankBalanceInput } from '../../../components/BankBalanceInput';
import { PaymentPredictionChart } from '../../../components/PaymentPredictionChart';
import { LineChart } from 'react-native-chart-kit';

interface CashflowPrediction {
  date: string;
  predicted_balance: number;
  min_balance: number;
  max_balance: number;
  receipts: Array<{
    date: string;
    amount: number;
    party: string;
    confidence: number;
  }>;
  expenses: Array<{
    date: string;
    amount: number;
    description: string;
  }>;
}

interface CashflowSummary {
  total_expected_receipts: number;
  total_expected_expenses: number;
  initial_balance: number;
  final_predicted_balance: number;
  days_forecast: number;
}

interface CashflowResponse {
  status: 'success' | 'error';
  data?: {
    predictions: CashflowPrediction[];
    summary: CashflowSummary;
    partyBalances?: PartyBalance[];
  };
  message?: string;
}

interface PartyBalance {
  party_name: string;
  current_balance: number;
  expected_payment_date: string | null;
  payment_probability: number;
  avg_payment_days?: number;
  confidence?: number;
  sample_size?: number;
}

interface UnpaidSale {
  id: number;
  date: string;
  amount: number;
  remaining_amount: number;
  party_name: string;
  voucher_number: string;
  predicted_payment_date: string | null;
  confidence: number;
  avg_delay_days: number;
}

interface PaymentAnalysisSummary {
  payment_patterns: {
    total_parties: number;
    parties_with_patterns: number;
    average_payment_delay: number;
  };
  unpaid_sales: {
    total_count: number;
    total_amount: number;
    average_amount: number;
  };
  payment_predictions: {
    total_predictions: number;
    high_confidence_predictions: number;
    total_predicted_amount: number;
    high_confidence_amount: number;
  };
  party_balances: {
    total_parties: number;
    total_outstanding: number;
    average_outstanding: number;
  };
  fixed_expenses: {
    total_expenses: number;
    total_monthly_amount: number;
  };
}

const { width } = Dimensions.get('window');

const styles = StyleSheet.create({
  periodSelector: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 8,
    padding: 4,
    marginTop: 16,
  },
  periodButton: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 6,
    alignItems: 'center',
  },
  periodButtonActive: {
    backgroundColor: '#fff',
  },
  periodText: {
    fontSize: 14,
    fontWeight: '600',
    color: 'rgba(255, 255, 255, 0.8)',
  },
  periodTextActive: {
    color: '#2e7d32',
  },
  errorContainer: {
    alignItems: 'center',
    padding: 40,
  },
  updateBalanceButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    margin: 20,
    padding: 16,
    borderRadius: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  updateBalanceText: {
    marginLeft: 8,
    fontSize: 16,
    color: '#2e7d32',
    fontWeight: '600',
  },
  partyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  partyAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#2e7d32',
  },
  partyDate: {
    fontSize: 14,
    color: '#666',
  },
  partyConfidence: {
    fontSize: 12,
    color: '#999',
  },
  summaryCard: {
    backgroundColor: '#fff',
    margin: 16,
    padding: 16,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  summaryTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginBottom: 12,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  summaryLabel: {
    fontSize: 14,
    color: '#666',
  },
  summaryValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#2e7d32',
  },
  unpaidSalesCard: {
    backgroundColor: '#fff',
    margin: 16,
    padding: 16,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  unpaidSaleItem: {
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
    paddingVertical: 12,
  },
  unpaidSaleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  unpaidSaleParty: {
    fontSize: 16,
    fontWeight: '600',
    color: '#2e7d32',
  },
  unpaidSaleAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#d32f2f',
  },
  unpaidSaleDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
  },
  unpaidSaleDate: {
    fontSize: 12,
    color: '#666',
  },
  unpaidSalePrediction: {
    fontSize: 12,
    color: '#2e7d32',
    fontWeight: '500',
  },
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#2e7d32',
    padding: 20,
    paddingTop: 60,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 8,
  },
  headerSubtitle: {
    fontSize: 16,
    color: '#fff',
    opacity: 0.8,
  },
  content: {
    flex: 1,
  },
  chartContainer: {
    backgroundColor: '#fff',
    margin: 16,
    padding: 16,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  chartTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginBottom: 16,
  },
  noDataContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  noDataText: {
    fontSize: 16,
    color: '#666',
    marginTop: 16,
    textAlign: 'center',
  },
  errorText: {
    fontSize: 16,
    color: '#f57c00',
    textAlign: 'center',
    fontWeight: 'bold',
  },
});

export default function CashflowScreen() {
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showBankBalanceModal, setShowBankBalanceModal] = useState(false);
  const [predictions, setPredictions] = useState<CashflowPrediction[]>([]);
  const [paymentPredictions, setPaymentPredictions] = useState<any>(null);
  const [summary, setSummary] = useState<CashflowSummary | null>(null);
  const [partyBalances, setPartyBalances] = useState<PartyBalance[]>([]);
  const [unpaidSales, setUnpaidSales] = useState<UnpaidSale[]>([]);
  const [analysisSummary, setAnalysisSummary] = useState<PaymentAnalysisSummary | null>(null);
  const [bankBalance, setBankBalance] = useState<number | null>(null);
  const [days, setDays] = useState<number>(30);
  const [companyId, setCompanyId] = useState<number>(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      await api.init(); // Initialize API client first
      initializeScreen();
    };
    init();
  }, []);

  useEffect(() => {
    if (companyId) {
      loadData();
    }
  }, [companyId, days]);

  const initializeScreen = async () => {
    try {
      const storedCompanyId = await AsyncStorage.getItem('companyId');
      if (storedCompanyId) {
        setCompanyId(parseInt(storedCompanyId, 10));
      }
      
      // Check if bank balance is set
      const response = await api.getCashflowPredictions(parseInt(storedCompanyId!, 10), days);
      if (response.status === 'success' && response.data?.data?.summary?.initial_balance) {
        setBankBalance(response.data.data.summary.initial_balance);
      } else {
        setShowBankBalanceModal(true);
      }
    } catch (error) {
      console.error('Error initializing screen:', error);
      setError('Failed to initialize. Please try again.');
    }
  };

  const loadData = async () => {
    let hasError = false;
    try {
      setLoading(true);
      setError(null);

      // Check if we have a valid token
      const hasToken = await api.hasValidToken();
      if (!hasToken) {
        console.log('No valid token found, redirecting to login');
        setError('Please log in to continue');
        return;
      }
      
      // Get cashflow predictions - this is our critical path
      const response = await api.getCashflowPredictions(companyId, days);
      console.log('API Response:', response);
      
      if (!response || response.status !== 'success' || !response.data) {
        console.error('Invalid response from cashflow predictions API:', response);
        throw new Error('Failed to fetch cashflow predictions. Please check your network connection and try again.');
      }

      // Log successful data for debugging
      console.log('Successfully fetched predictions:', {
        predictionCount: response.data?.data?.predictions?.length || 0,
        hasSummary: !!response.data?.data?.summary,
        summary: response.data?.data?.summary
      });

      // Get predictions from the correct path in the response
      const rawPredictions = response.data?.predictions || [];
      console.log('Raw predictions:', rawPredictions); // Debug log
      
      // Transform predictions to match the expected format
      const cleanPredictions = rawPredictions.map((prediction: any) => {
        const totalReceipts = prediction.receipts.reduce((sum: number, r: any) => sum + (r.amount || 0), 0);
        const totalExpenses = prediction.expenses.reduce((sum: number, e: any) => sum + (e.amount || 0), 0);
        
        const cleaned = {
          date: prediction.date,
          predicted_balance: prediction.predicted_balance || 0,
          min_balance: prediction.predicted_balance - (totalExpenses * 0.1) || 0, // 10% variance for min
          max_balance: prediction.predicted_balance + (totalReceipts * 0.1) || 0, // 10% variance for max
          receipts: prediction.receipts || [],
          expenses: prediction.expenses || []
        };
        console.log('Cleaned prediction:', cleaned); // Debug log
        return cleaned;
      });
      
      setPredictions(cleanPredictions);
      setPaymentPredictions(response.data); // Store the full response for other components
      
      const finalBalance = cleanPredictions.length > 0 ? cleanPredictions[cleanPredictions.length - 1].predicted_balance : 0;
      
      setSummary({
        total_expected_receipts: response.data?.insights?.total_expected_receipts || 0,
        total_expected_expenses: response.data?.insights?.total_expected_expenses || 0,
        initial_balance: response.data?.initial_balance || bankBalance || 0,
        final_predicted_balance: finalBalance,
        days_forecast: days
      });
      
      // Convert analyzed parties to party balances format
      const parties = response.data?.data?.predictions
        .filter((p: CashflowPrediction) => p.receipts && p.receipts.length > 0)
        .flatMap((p: CashflowPrediction) => p.receipts)
        .map((r: any) => ({
          party_name: r.party,
          current_balance: r.amount,
          expected_payment_date: r.date,
          payment_probability: r.confidence
        }));
      setPartyBalances(parties);

        // Load additional data in parallel with proper error handling
      let errors: string[] = [];
      const [
        unpaidSalesResponse,
        partyBalancesResponse,
        analysisSummaryResponse
      ] = await Promise.allSettled([
        api.getUnpaidSales(companyId),
        api.getPartyBalances(companyId),
        api.getPaymentAnalysisSummary(companyId)
      ]);

      // Payment predictions are already handled above

      // Handle unpaid sales
      if (unpaidSalesResponse.status === 'fulfilled' && 
          unpaidSalesResponse.value.status === 'success') {
        setUnpaidSales(unpaidSalesResponse.value.data.unpaid_sales);
      } else if (unpaidSalesResponse.status === 'rejected') {
        errors.push('Could not load unpaid sales');
      }

      // Handle party balances
      if (partyBalancesResponse.status === 'fulfilled' && 
          partyBalancesResponse.value.status === 'success') {
        setPartyBalances(partyBalancesResponse.value.data.party_balances);
      } else if (partyBalancesResponse.status === 'rejected') {
        errors.push('Could not load party balances');
      }

      // Handle analysis summary
      if (analysisSummaryResponse.status === 'fulfilled' && 
          analysisSummaryResponse.value.status === 'success') {
        setAnalysisSummary(analysisSummaryResponse.value.data);
      } else if (analysisSummaryResponse.status === 'rejected') {
        errors.push('Could not load analysis summary');
      }

      // Set error if any secondary data failed to load
      if (errors.length > 0) {
        setError(`Some data could not be loaded: ${errors.join(', ')}`);
      }
    } catch (error) {
      console.error('Error loading cashflow data:', error);
      // Clear all state on critical error
      setError('Failed to load cashflow data. Please try again.');
      setPredictions([]);
      setSummary(null);
      setPaymentPredictions(null);
      setPartyBalances([]);
      setUnpaidSales([]);
      setAnalysisSummary(null);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleBankBalanceSet = async () => {
    if (bankBalance) {
      await updateBankBalance();
      setShowBankBalanceModal(false);
    }
  };

  const updateBankBalance = async () => {
    if (!bankBalance || isNaN(Number(bankBalance))) {
      Alert.alert('Error', 'Please enter a valid balance');
      return;
    }

    try {
      setLoading(true);
      const response = await api.updateBankBalance(companyId, Number(bankBalance));
      console.log('Update bank balance response:', response); // Debug log
      
      if (response.status === 'success' && response.data?.status !== 'error') {
        Alert.alert('Success', 'Bank balance updated successfully');
        // Clear the input after successful update
        setBankBalance(null);
        // Reload data immediately
        await loadData();
      } else {
        const errorMessage = response.data?.message || response.message || 'Failed to update bank balance';
        Alert.alert('Error', errorMessage);
      }
    } catch (error) {
      console.error('Error updating bank balance:', error);
      Alert.alert('Error', 'Failed to update bank balance. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const renderChart = () => {
    if (error) {
      return (
        <View style={styles.noDataContainer}>
          <Ionicons name="warning-outline" size={48} color="#f57c00" />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      );
    }

    if (predictions.length === 0) {
      return (
        <View style={styles.noDataContainer}>
          <Ionicons name="analytics-outline" size={48} color="#ccc" />
          <Text style={styles.noDataText}>No prediction data available</Text>
        </View>
      );
    }

    // Get the visible range based on days selection
    const visibleDays = days === 7 ? 7 : (days === 30 ? 14 : 30);
    const visiblePredictions = predictions.slice(0, visibleDays);

    console.log('Preparing chart data for predictions:', visiblePredictions);
    
    const chartData = {
      labels: visiblePredictions.map(p => new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
      datasets: [
        {
          data: visiblePredictions.map(p => {
            const value = Number(p.predicted_balance);
            console.log(`Balance for ${p.date}:`, value);
            return isNaN(value) || !isFinite(value) ? 0 : value;
          }),
          color: (opacity = 1) => `rgba(46, 125, 50, ${opacity})`,
          strokeWidth: 2,
        },
        {
          data: visiblePredictions.map(p => {
            const value = Number(p.min_balance);
            return isNaN(value) || !isFinite(value) ? 0 : value;
          }),
          color: (opacity = 1) => `rgba(255, 152, 0, ${opacity})`,
          strokeWidth: 1,
        },
        {
          data: visiblePredictions.map(p => {
            const value = Number(p.max_balance);
            return isNaN(value) || !isFinite(value) ? 0 : value;
          }),
          color: (opacity = 1) => `rgba(33, 150, 243, ${opacity})`,
          strokeWidth: 1,
        },
      ],
    };

    return (
      <View style={styles.chartContainer}>
        <Text style={styles.chartTitle}>Cash Flow Prediction</Text>
        <LineChart
          data={chartData}
          width={width - 64}
          height={220}
          chartConfig={{
            backgroundColor: '#ffffff',
            backgroundGradientFrom: '#ffffff',
            backgroundGradientTo: '#ffffff',
            decimalPlaces: 0,
            color: (opacity = 1) => `rgba(46, 125, 50, ${opacity})`,
            labelColor: (opacity = 1) => `rgba(0, 0, 0, ${opacity})`,
            style: {
              borderRadius: 16,
            },
            propsForDots: {
              r: '4',
              strokeWidth: '2',
              stroke: '#2e7d32',
            },
            formatYLabel: (value) => {
              const numValue = Number(value);
              if (isNaN(numValue) || !isFinite(numValue)) {
                return '₹0';
              }
              return `₹${numValue.toLocaleString('en-IN', {
                maximumFractionDigits: 0,
              })}`;
            },
          }}
          bezier
          style={{
            marginVertical: 8,
            borderRadius: 16,
          }}
        />
      </View>
    );
  };

  const renderSummary = () => {
    if (!analysisSummary) return null;

    return (
      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Payment Analysis Summary</Text>
        
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Total Parties Analyzed</Text>
          <Text style={styles.summaryValue}>{analysisSummary.payment_patterns.total_parties}</Text>
        </View>
        
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Parties with Patterns</Text>
          <Text style={styles.summaryValue}>{analysisSummary.payment_patterns.parties_with_patterns}</Text>
        </View>
        
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Average Payment Delay</Text>
          <Text style={styles.summaryValue}>{analysisSummary.payment_patterns.average_payment_delay} days</Text>
        </View>
        
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Total Unpaid Sales</Text>
          <Text style={styles.summaryValue}>{formatCurrency(analysisSummary.unpaid_sales.total_amount)}</Text>
        </View>
        
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>High Confidence Predictions</Text>
          <Text style={styles.summaryValue}>{analysisSummary.payment_predictions.high_confidence_predictions}</Text>
        </View>
        
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Total Outstanding</Text>
          <Text style={styles.summaryValue}>{formatCurrency(analysisSummary.party_balances.total_outstanding)}</Text>
        </View>
      </View>
    );
  };

  const renderUnpaidSales = () => {
    if (!unpaidSales || unpaidSales.length === 0) return null;

    return (
      <View style={styles.unpaidSalesCard}>
        <Text style={styles.summaryTitle}>Unpaid Sales</Text>
        {unpaidSales.slice(0, 5).map((sale) => (
          <View key={sale.id} style={styles.unpaidSaleItem}>
            <View style={styles.unpaidSaleHeader}>
              <Text style={styles.unpaidSaleParty}>{sale.party_name}</Text>
              <Text style={styles.unpaidSaleAmount}>{formatCurrency(sale.remaining_amount)}</Text>
            </View>
            <View style={styles.unpaidSaleDetails}>
              <Text style={styles.unpaidSaleDate}>
                Sale Date: {new Date(sale.date).toLocaleDateString()}
              </Text>
              {sale.predicted_payment_date && (
                <Text style={styles.unpaidSalePrediction}>
                  Expected: {new Date(sale.predicted_payment_date).toLocaleDateString()} 
                  ({sale.confidence * 100}% confidence)
                </Text>
              )}
            </View>
          </View>
        ))}
        {unpaidSales.length > 5 && (
          <Text style={styles.summaryLabel}>
            +{unpaidSales.length - 5} more unpaid sales
          </Text>
        )}
      </View>
    );
  };

  const renderPartyBalances = () => {
    if (!partyBalances || partyBalances.length === 0) return null;

    return (
      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Party Balances</Text>
        {partyBalances.slice(0, 5).map((balance, index) => (
          <View key={index} style={styles.unpaidSaleItem}>
            <View style={styles.unpaidSaleHeader}>
              <Text style={styles.unpaidSaleParty}>{balance.party_name}</Text>
              <Text style={styles.unpaidSaleAmount}>{formatCurrency(balance.current_balance)}</Text>
            </View>
            <View style={styles.unpaidSaleDetails}>
              {balance.expected_payment_date && (
                <Text style={styles.unpaidSaleDate}>
                  Expected: {new Date(balance.expected_payment_date).toLocaleDateString()}
                </Text>
              )}
              <Text style={styles.unpaidSalePrediction}>
                {balance.payment_probability * 100}% probability
              </Text>
            </View>
          </View>
        ))}
        {partyBalances.length > 5 && (
          <Text style={styles.summaryLabel}>
            +{partyBalances.length - 5} more parties
          </Text>
        )}
      </View>
    );
  };

  if (loading) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Cash Flow</Text>
          <Text style={styles.headerSubtitle}>Payment Predictions & Analysis</Text>
        </View>
        <View style={styles.content}>
          <View style={styles.noDataContainer}>
            <ActivityIndicator size="large" color="#2e7d32" />
            <Text style={styles.noDataText}>Loading payment predictions...</Text>
          </View>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Cash Flow</Text>
        <Text style={styles.headerSubtitle}>Payment Predictions & Analysis</Text>
        <View style={styles.periodSelector}>
          <TouchableOpacity 
            style={[styles.periodButton, days === 7 && styles.periodButtonActive]}
            onPress={() => setDays(7)}
          >
            <Text style={[styles.periodText, days === 7 && styles.periodTextActive]}>7D</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.periodButton, days === 30 && styles.periodButtonActive]}
            onPress={() => setDays(30)}
          >
            <Text style={[styles.periodText, days === 30 && styles.periodTextActive]}>30D</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.periodButton, days === 90 && styles.periodButtonActive]}
            onPress={() => setDays(90)}
          >
            <Text style={[styles.periodText, days === 90 && styles.periodTextActive]}>90D</Text>
          </TouchableOpacity>
        </View>
      </View>
      
      <ScrollView 
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {renderChart()}
        {renderSummary()}
        {renderUnpaidSales()}
        {renderPartyBalances()}
      </ScrollView>

      {showBankBalanceModal && (
        <BankBalanceInput
          visible={showBankBalanceModal}
          onClose={() => setShowBankBalanceModal(false)}
          onConfirm={handleBankBalanceSet}
          balance={bankBalance}
          onBalanceChange={setBankBalance}
        />
      )}
    </View>
  );
}

