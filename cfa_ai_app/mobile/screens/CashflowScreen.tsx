import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TextInput, 
  TouchableOpacity, 
  Alert, 
  Dimensions,
  ActivityIndicator,
  RefreshControl
} from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { useTheme } from '../hooks/useTheme';
import { formatCurrency } from '../lib/formatters';
import { CashflowPrediction, IPartyBalance } from '../lib/types';
import { api } from '../services/api';
import { RouteProp } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';

interface Prediction {
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

interface PartyBalance {
  party_name: string;
  current_balance: number;
  expected_payment_date: string;
  payment_probability: number;
}

interface ChartDataPoint {
  x: Date;
  y: number;
  yMin: number;
  yMax: number;
}

type RootStackParamList = {
  Cashflow: { companyId: number };
};

type CashflowScreenProps = {
  route: RouteProp<RootStackParamList, 'Cashflow'>;
  navigation: StackNavigationProp<RootStackParamList, 'Cashflow'>;
};

export default function CashflowScreen({ route, navigation }: CashflowScreenProps) {
  const { colors } = useTheme();
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState(false);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [partyBalances, setPartyBalances] = useState<IPartyBalance[]>([]);
  const [bankBalance, setBankBalance] = useState<string>('');
  const [days, setDays] = useState<number>(30);
  const companyId = route.params?.companyId;

  useEffect(() => {
    if (!companyId) {
      Alert.alert('Error', 'No company selected');
      navigation.goBack();
      return;
    }
  }, [companyId, navigation]);

  useEffect(() => {
    loadData();
  }, [days]);

  const loadData = async () => {
    if (!companyId) {
      return;
    }

    try {
      setLoading(true);
      // Get cashflow predictions
      const predictionsRes = await api.getCashflowPredictions(companyId, days);
      if (predictionsRes?.data?.data?.predictions) {
        setPredictions(predictionsRes.data.data.predictions);
      }

      // Get party balances from mobile app (used to compute receivables)
      const partyBalancesRes = await api.getPartyBalances(companyId);
      if (partyBalancesRes.status === 'success' && partyBalancesRes.data) {
        setPartyBalances(partyBalancesRes.data.party_balances);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to load cashflow data');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const fetchPredictions = async () => {
    if (!companyId) {
      Alert.alert('Error', 'Company ID is required');
      return;
    }

    try {
      setLoading(true);
      const response = await api.getCashflowPredictions(companyId, days);
      if (response.status === 'success' && response.data) {
        setPredictions(response.data.data.predictions);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to fetch predictions');
      console.error('Fetch predictions error:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateBankBalance = async () => {
    if (!companyId || !bankBalance) {
      Alert.alert('Error', 'Company ID and bank balance are required');
      return;
    }

    try {
      const response = await api.updateBankBalance(
        companyId,
        parseFloat(bankBalance)
      );
      
      if (response.status === 'success') {
        Alert.alert('Success', 'Bank balance updated successfully');
        fetchPredictions();
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to update bank balance');
      console.error('Update bank balance error:', error);
    }
  };

  const renderChart = () => {
    if (!predictions.length) return null;

    try {
      const chartData = {
      labels: predictions.map(p => new Date(p.date).toLocaleDateString([], { month: 'short', day: 'numeric' })),
      datasets: [
        {
          data: predictions.map(p => {
            const value = p.predicted_balance;
            return isNaN(value) || !isFinite(value) ? 0 : value;
          }),
          color: (opacity = 1) => colors.primary,
          strokeWidth: 2
        },
        {
          data: predictions.map(p => {
            const value = p.min_balance;
            return isNaN(value) || !isFinite(value) ? 0 : value;
          }),
          color: (opacity = 1) => `${colors.error}88`,  // 88 for opacity
          strokeWidth: 1
        },
        {
          data: predictions.map(p => {
            const value = p.max_balance;
            return isNaN(value) || !isFinite(value) ? 0 : value;
          }),
          color: (opacity = 1) => `${colors.success}88`,  // 88 for opacity
          strokeWidth: 1
        }
      ]
    };

    return (
      <View style={styles.chartContainer}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Cashflow Forecast</Text>
        <LineChart
          data={chartData}
          width={Dimensions.get('window').width - 32}
          height={220}
          chartConfig={{
            backgroundColor: colors.card,
            backgroundGradientFrom: colors.card,
            backgroundGradientTo: colors.card,
            decimalPlaces: 0,
            color: (opacity = 1) => colors.text,
            labelColor: (opacity = 1) => colors.text,
            style: {
              borderRadius: 16
            },
            propsForDots: {
              r: "4",
              strokeWidth: "1",
              stroke: colors.primary
            },
            formatYLabel: (value: string | number) => formatCurrency(Number(value))
          }}
          bezier
          style={{
            marginVertical: 8,
            borderRadius: 8
          }}
        />
      </View>
    );
    } catch (error) {
      console.error('Error rendering chart:', error);
      return (
        <View style={styles.errorContainer}>
          <Text style={[styles.errorText, { color: colors.error }]}>
            Failed to render chart. Please try again.
          </Text>
        </View>
      );
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  const totalDebtorBalance = partyBalances.reduce((sum, p) => sum + (p.current_balance || 0), 0);
  const upcomingPayments = partyBalances
    .filter(pb => pb.current_balance > 0)
    .sort((a, b) => {
      const dateA = a.expected_payment_date ? new Date(a.expected_payment_date).getTime() : Number.MAX_SAFE_INTEGER;
      const dateB = b.expected_payment_date ? new Date(b.expected_payment_date).getTime() : Number.MAX_SAFE_INTEGER;
      return dateA - dateB;
    });

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background }]}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      {/* Summary Cards */}
      <View style={styles.summaryContainer}>
        <View style={[styles.card, { backgroundColor: colors.primary }]}>
          <Text style={styles.cardLabel}>Current Bank Balance</Text>
          <Text style={styles.cardValue}>
            {formatCurrency(predictions[0]?.predicted_balance || 0)}
          </Text>
        </View>
        
        <View style={[styles.card, { backgroundColor: colors.secondary }]}>
          <Text style={styles.cardLabel}>Total Receivables</Text>
          <Text style={styles.cardValue}>
            {formatCurrency(totalDebtorBalance)}
          </Text>
        </View>
      </View>

      {/* Bank Balance Update */}
      <View style={[styles.inputContainer, { backgroundColor: colors.card }]}>
        <TextInput
          style={[styles.input, { color: colors.text, borderColor: colors.border }]}
          value={bankBalance}
          onChangeText={setBankBalance}
          placeholder="Enter current bank balance"
          placeholderTextColor={colors.textSecondary}
          keyboardType="numeric"
        />
        <TouchableOpacity
          style={[styles.button, { backgroundColor: colors.primary }]}
          onPress={updateBankBalance}
        >
          <Text style={[styles.buttonText, { color: colors.buttonText }]}>
            Update Balance
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.daysContainer}>
        {[7, 15, 30, 60].map(d => (
          <TouchableOpacity
            key={d}
            style={[
              styles.dayButton,
              { 
                backgroundColor: days === d ? colors.primary : colors.background,
                borderColor: colors.border
              }
            ]}
            onPress={() => setDays(d)}
          >
            <Text style={[
              styles.dayButtonText,
              { color: days === d ? colors.buttonText : colors.text }
            ]}>
              {d} Days
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {renderChart()}

      <View style={styles.predictionsContainer}>
        {predictions.map((prediction, index) => (
          <View key={index} style={[styles.predictionItem, { borderColor: colors.border }]}>
            <Text style={[styles.date, { color: colors.text }]}>
              {new Date(prediction.date).toLocaleDateString()}
            </Text>
            <Text style={[styles.balance, { color: colors.text }]}>
              {formatCurrency(prediction.predicted_balance)}
            </Text>
            <View style={styles.detailsContainer}>
              {prediction.receipts.map((receipt, i) => (
                <Text key={i} style={[styles.detail, { color: colors.success }]}>
                  + {formatCurrency(receipt.amount)} from {receipt.party}
                  {receipt.confidence > 0.7 ? ' ⭐' : ''}
                </Text>
              ))}
              {prediction.expenses.map((expense, i) => (
                <Text key={i} style={[styles.detail, { color: colors.error }]}>
                  - {formatCurrency(expense.amount)} for {expense.description}
                </Text>
              ))}
            </View>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  errorContainer: {
    padding: 16,
    alignItems: 'center',
  },
  errorText: {
    fontSize: 16,
    textAlign: 'center',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  date: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  balance: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 12,
  },
  summaryContainer: {
    flexDirection: 'row',
    padding: 16,
    gap: 16,
  },
  card: {
    flex: 1,
    padding: 16,
    borderRadius: 8,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  cardLabel: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '500',
  },
  cardValue: {
    color: '#fff',
    fontSize: 20,
    fontWeight: 'bold',
    marginTop: 8,
  },
  inputContainer: {
    padding: 16,
    margin: 16,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  daysContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 16,
  },
  chartContainer: {
    marginVertical: 16,
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  dayButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  dayButtonText: {
    fontSize: 12,
    fontWeight: '600',
  },
  input: {
    flex: 1,
    height: 40,
    borderWidth: 1,
    borderRadius: 4,
    paddingHorizontal: 12,
  },
  button: {
    padding: 12,
    borderRadius: 4,
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '500',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 16,
  },
  predictionsContainer: {
    padding: 16,
    margin: 16,
    borderRadius: 8,
  },
  predictionItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  paymentRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  partyName: {
    fontSize: 16,
    fontWeight: '500',
  },
  paymentDate: {
    fontSize: 12,
    color: '#666',
    marginTop: 4,
  },
  paymentAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    textAlign: 'right',
  },
  probability: {
    fontSize: 12,
    color: '#666',
    textAlign: 'right',
    marginTop: 4,
  },
  detailsContainer: {
    marginTop: 8,
  },
  detail: {
    fontSize: 14,
    marginBottom: 4,
  },
});
