import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { Dimensions } from 'react-native';
import { formatCurrency } from '../lib/formatters';

const { width } = Dimensions.get('window');

interface PaymentPredictionData {
  date: string;
  total: number;
  parties: Array<{
    party_name: string;
    amount: number;
    confidence: number;
  }>;
}

interface PaymentPredictionProps {
  predictions: PaymentPredictionData[];
  initialBalance: number;
}

export const PaymentPredictionChart: React.FC<PaymentPredictionProps> = ({
  predictions,
  initialBalance,
}) => {
  // Check for empty predictions
  if (!predictions || predictions.length === 0) {
    return (
      <View style={styles.noDataContainer}>
        <Text style={styles.noDataText}>No prediction data available</Text>
      </View>
    );
  }

  // Calculate cumulative balances with NaN protection
  const cumulativeData = predictions.reduce((acc, prediction) => {
    const previousBalance = acc.length > 0 
      ? acc[acc.length - 1].balance 
      : initialBalance;
    
    // Ensure values are valid numbers
    const total = isNaN(prediction.total) || !isFinite(prediction.total) ? 0 : prediction.total;
    const balance = isNaN(previousBalance) || !isFinite(previousBalance) ? initialBalance : previousBalance;
    
    acc.push({
      date: prediction.date,
      balance: balance + total,
      total: total
    });
    
    return acc;
  }, [] as Array<{ date: string; balance: number; total: number }>);

  const chartData = {
    labels: cumulativeData.map(d => 
      new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    ),
    datasets: [
      {
        data: cumulativeData.map(d => {
          const value = d.balance;
          return isNaN(value) || !isFinite(value) ? 0 : value;
        }),
        color: (opacity = 1) => `rgba(46, 125, 50, ${opacity})`,
        strokeWidth: 2,
      },
    ],
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Predicted Cash Flow</Text>
      <LineChart
        data={chartData}
        width={width - 40}
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
          formatYLabel: (value: string | number) => {
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
        style={styles.chart}
      />
      
      <ScrollView style={styles.detailsContainer}>
        <Text style={styles.sectionTitle}>Daily Predictions</Text>
        {predictions.map((prediction) => {
          const key = prediction.date || JSON.stringify(prediction);
          const displayDate = prediction.date
            ? new Date(prediction.date).toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
              })
            : 'Unknown date';

          const parties = Array.isArray(prediction.parties) ? prediction.parties : [];

          return (
            <View key={key} style={styles.predictionItem}>
              <Text style={styles.date}>{displayDate}</Text>
              <Text style={styles.amount}>{formatCurrency(prediction.total)}</Text>
              <View style={styles.partiesContainer}>
                {parties.map((party, pIndex) => (
                  <Text
                    key={`${key}-${party.party_name ?? 'party'}-${pIndex}`}
                    style={styles.partyDetail}
                  >
                    {party.party_name}: {formatCurrency(party.amount)} ({Math.round((party.confidence || 0) * 100)}% confidence)
                  </Text>
                ))}
              </View>
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    margin: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginBottom: 16,
  },
  chart: {
    marginVertical: 8,
    borderRadius: 16,
  },
  noDataContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
    backgroundColor: '#fff',
    borderRadius: 12,
    margin: 16,
  },
  noDataText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
  },
  detailsContainer: {
    maxHeight: 300,
    marginTop: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  predictionItem: {
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
    paddingVertical: 12,
  },
  date: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  amount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#2e7d32',
    marginTop: 4,
  },
  partiesContainer: {
    marginTop: 8,
  },
  partyDetail: {
    fontSize: 12,
    color: '#666',
    marginTop: 2,
  },
});
