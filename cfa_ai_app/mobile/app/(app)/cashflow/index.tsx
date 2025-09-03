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
  // party balances removed from UI; unpaid sales will show pending receipts
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

      // Support two response shapes: response.data.data (new) or response.data (legacy)
      const dataRoot = response.data?.data || response.data || {};

      // Log successful data for debugging
      console.log('Successfully fetched predictions:', {
        predictionCount: (dataRoot.predictions && dataRoot.predictions.length) || 0,
        hasSummary: !!dataRoot.summary,
        summary: dataRoot.summary || null,
      });

      // Get predictions from the normalized root
      const rawPredictions = dataRoot.predictions || [];
      console.log('Raw predictions:', rawPredictions); // Debug log
      
      // Transform predictions to match the expected format
      const cleanPredictions = rawPredictions.map((prediction: any) => {
        const receiptsArr = Array.isArray(prediction.receipts) ? prediction.receipts : [];
        const expensesArr = Array.isArray(prediction.expenses) ? prediction.expenses : [];

        const totalReceipts = receiptsArr.reduce((sum: number, r: any) => sum + (r?.amount || 0), 0);
        const totalExpenses = expensesArr.reduce((sum: number, e: any) => sum + (e?.amount || 0), 0);
        
        const cleaned = {
          date: prediction.date,
          predicted_balance: prediction.predicted_balance || 0,
          min_balance: (prediction.predicted_balance || 0) - (totalExpenses * 0.1), // 10% variance for min
          max_balance: (prediction.predicted_balance || 0) + (totalReceipts * 0.1), // 10% variance for max
          receipts: receiptsArr,
          expenses: expensesArr,
        };
        console.log('Cleaned prediction:', cleaned); // Debug log
        return cleaned;
      });
      
      setPredictions(cleanPredictions);
      setPaymentPredictions(dataRoot); // Store the normalized root for other components

      const finalBalance = cleanPredictions.length > 0 ? cleanPredictions[cleanPredictions.length - 1].predicted_balance : 0;

      setSummary({
        total_expected_receipts: dataRoot?.insights?.total_expected_receipts || 0,
        total_expected_expenses: dataRoot?.insights?.total_expected_expenses || 0,
        initial_balance: dataRoot?.initial_balance || bankBalance || 0,
        final_predicted_balance: finalBalance,
        days_forecast: days,
      });

  // party balances removed - unpaid sales will show pending receipts and remaining amounts

        // Load additional data in parallel with proper error handling
      let errors: string[] = [];
      const [
        unpaidSalesResponse,
        analysisSummaryResponse
      ] = await Promise.allSettled([
        api.getUnpaidSales(companyId),
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

  // party balances intentionally not loaded here per UI decision

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
    // Build defensive date parser
    const parseDate = (d: any): Date | null => {
      if (!d) return null;
      try {
        const dt = new Date(d);
        if (isNaN(dt.getTime())) return null;
        return dt;
      } catch (e) {
        return null;
      }
    };

    // Extract predicted receipts from the payment predictions (paymentPredictions.predictions)
    const predictedFromApi: Array<any> = [];
    try {
      const root = paymentPredictions || {};
      const preds = Array.isArray(root.predictions) ? root.predictions : [];
      preds.forEach((p: any) => {
        const receipts = Array.isArray(p.receipts) ? p.receipts : [];
        receipts.forEach((r: any) => {
          // normalized shape expected from API logs: { amount, confidence, party, reference, type }
          predictedFromApi.push({
            party: r.party || r.party_name || 'Unknown',
            amount: Number(r.amount) || 0,
            confidence: Number(r.confidence) || 0,
            reference: r.reference || r.voucher_number || null,
            predicted_payment_date: p.date || r.date || null,
            raw: r,
          });
        });
      });
    } catch (e) {
      console.warn('Failed to parse paymentPredictions for predicted receipts', e);
    }

    // Merge predicted receipts with unpaid sales (prefer matching by voucher/reference, else by party+amount)
    const mergedPredicted: UnpaidSale[] = predictedFromApi.map((pred, idx) => {
      // Try to find a matching unpaid sale
      const match = (Array.isArray(unpaidSales) ? unpaidSales : []).find((s: any) => {
        if (pred.reference && s.voucher_number && String(pred.reference) === String(s.voucher_number)) return true;
        if (s.party_name && pred.party && s.party_name.trim().toLowerCase() === String(pred.party).trim().toLowerCase()) {
          // fuzzy amount match (remaining_amount should be >= predicted amount or close)
          const rem = Number(s.remaining_amount || 0);
          if (!isNaN(rem) && rem >= (pred.amount * 0.5)) return true;
        }
        return false;
      });

      const id = match?.id ?? -(idx + 1);
      const remaining_amount = match ? Number(match.remaining_amount || pred.amount) : Number(pred.amount || 0);
      const saleDate = match?.date ?? null;

      return {
        id,
        date: saleDate,
        amount: Number(pred.amount || 0),
        remaining_amount,
        party_name: pred.party,
        voucher_number: pred.reference || '',
        predicted_payment_date: pred.predicted_payment_date,
        confidence: Number(pred.confidence || 0),
        avg_delay_days: match?.avg_delay_days || 0,
      } as UnpaidSale;
    });

    // Filter out zero amounts and only keep those within expected forecast or high value
    const now = new Date();
    const endDate = new Date(now.getTime() + (days || 30) * 24 * 60 * 60 * 1000);

    const validPredicted = mergedPredicted.filter(s => Number(s.remaining_amount) > 0 && s.predicted_payment_date);

    const highValue = [...validPredicted].sort((a, b) => Number(b.remaining_amount) - Number(a.remaining_amount)).slice(0, 5);

    const expectedSoon = validPredicted.filter(s => {
      const pd = parseDate(s.predicted_payment_date);
      return pd && pd >= now && pd <= endDate;
    }).sort((a, b) => (parseDate(a.predicted_payment_date)?.getTime() || 0) - (parseDate(b.predicted_payment_date)?.getTime() || 0));

    return (
      <View style={styles.unpaidSalesCard}>
        <Text style={styles.summaryTitle}>Unpaid Sales</Text>

        {/* High value unpaid sales (from predictions) */}
        {highValue.length > 0 && (
          <View style={{ marginBottom: 8 }}>
            <Text style={[styles.summaryLabel, { marginBottom: 6 }]}>High value unpaid sales</Text>
            {highValue.map(sale => (
              <View key={`high-${sale.id ?? JSON.stringify(sale)}`} style={styles.unpaidSaleItem}>
                <View style={styles.unpaidSaleHeader}>
                  <Text style={styles.unpaidSaleParty}>{sale.party_name}</Text>
                  <Text style={styles.unpaidSaleAmount}>{formatCurrency(sale.remaining_amount)}</Text>
                </View>
                <View style={styles.unpaidSaleDetails}>
                  <Text style={styles.unpaidSaleDate}>Sale Date: {parseDate(sale.date)?.toLocaleDateString() ?? 'Unknown'}</Text>
                  {sale.predicted_payment_date && (
                    <Text style={styles.unpaidSalePrediction}>
                      Expected: {parseDate(sale.predicted_payment_date)?.toLocaleDateString() ?? 'Unknown'} ({Math.round((sale.confidence || 0) * 100)}% confidence)
                    </Text>
                  )}
                </View>
                {sale.voucher_number ? <Text style={styles.partyConfidence}>Ref: {sale.voucher_number}</Text> : null}
              </View>
            ))}
          </View>
        )}

        {/* Expected within forecast window */}
        {expectedSoon.length > 0 && (
          <View style={{ marginTop: 6 }}>
            <Text style={[styles.summaryLabel, { marginBottom: 6 }]}>Expected in next {days} days</Text>
            {expectedSoon.map(sale => (
              <View key={`exp-${sale.id ?? JSON.stringify(sale)}`} style={styles.unpaidSaleItem}>
                <View style={styles.unpaidSaleHeader}>
                  <Text style={styles.unpaidSaleParty}>{sale.party_name}</Text>
                  <Text style={styles.unpaidSaleAmount}>{formatCurrency(sale.remaining_amount)}</Text>
                </View>
                <View style={styles.unpaidSaleDetails}>
                  <Text style={styles.unpaidSaleDate}>Due: {parseDate(sale.predicted_payment_date)?.toLocaleDateString() ?? 'Unknown'}</Text>
                  <Text style={styles.unpaidSalePrediction}>{Math.round((sale.confidence || 0) * 100)}% probability</Text>
                </View>
                {sale.voucher_number ? <Text style={styles.partyConfidence}>Ref: {sale.voucher_number}</Text> : null}
              </View>
            ))}
          </View>
        )}

        {/* If no predicted unpaid sales, show helpful message */}
        {(highValue.length === 0 && expectedSoon.length === 0) && (
          <View style={styles.noDataContainer}>
            <Text style={styles.noDataText}>No predicted unpaid sales found for the selected period.</Text>
          </View>
        )}

        {/* Show total predicted count if more exist */}
        {validPredicted.length > 5 && (
          <Text style={styles.summaryLabel}>+{validPredicted.length - 5} more predicted unpaid sales</Text>
        )}
      </View>
    );
  };

  // party balances UI removed per product decision

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

