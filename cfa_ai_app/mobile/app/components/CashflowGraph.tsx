import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { formatCurrency } from '../../utils/formatters';

interface CashflowDataPoint {
  date: string;
  projectedBalance: number;
  actualBalance?: number;
  receivables?: number;
  payables?: number;
}

interface CashflowGraphProps {
  data: CashflowDataPoint[];
  showReceivables?: boolean;
  showPayables?: boolean;
}

const CashflowGraphComponent: React.FC<CashflowGraphProps> = ({ 
  data,
  showReceivables = true,
  showPayables = true
}) => {
  const screenWidth = Dimensions.get('window').width;

  const renderNoData = (message: string) => (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Cashflow Projection</Text>
      </View>
      <View style={styles.noDataContainer}>
        <Text style={styles.noDataText}>{message}</Text>
      </View>
    </View>
  );

  // Handle invalid data scenarios
  if (!data) {
    return renderNoData('No data available');
  }

  if (!Array.isArray(data)) {
    return renderNoData('Invalid data format');
  }

  if (data.length === 0) {
    return renderNoData('No prediction data available');
  }

    // Transform and validate data points
    const transformedData = data.map(point => {
    try {
      const date = new Date(point.date);
      if (isNaN(date.getTime())) {
        throw new Error('Invalid date');
      }
      return {
        ...point,
        formattedDate: `${date.getDate()}/${date.getMonth() + 1}`,
        projectedBalance: Number(point.projectedBalance) || 0,
        actualBalance: point.actualBalance ? Number(point.actualBalance) : null,
        receivables: point.receivables ? Number(point.receivables) : 0,
        payables: point.payables ? Number(point.payables) : 0
      } as const;
    } catch (error) {
      console.error('Error processing data point:', error);
      return null;
    }
  }).filter((point): point is NonNullable<typeof point> => point !== null);

  // Use transformed data consistently
  const chartData = {
    labels: transformedData.map(point => point.formattedDate),
    datasets: [
      {
        data: transformedData.map(point => point.projectedBalance),
        color: (opacity = 1) => `rgba(46, 125, 50, ${opacity})`, // Green
        strokeWidth: 2
      },
      {
        data: transformedData.map(point => point.actualBalance ?? point.projectedBalance),
        color: (opacity = 1) => `rgba(25, 118, 210, ${opacity})`, // Blue
        strokeWidth: 2
      },
      ...(showReceivables ? [{
        data: transformedData.map(point => point.receivables),
        color: (opacity = 1) => `rgba(56, 142, 60, ${opacity * 0.5})`, // Light green
        strokeWidth: 1
      }] : []),
      ...(showPayables ? [{
        data: transformedData.map(point => point.payables),
        color: (opacity = 1) => `rgba(211, 47, 47, ${opacity * 0.5})`, // Light red
        strokeWidth: 1
      }] : [])
    ]
  };

  const chartConfig = {
    backgroundColor: '#ffffff',
    backgroundGradientFrom: '#ffffff',
    backgroundGradientTo: '#ffffff',
    decimalPlaces: 0,
    color: (opacity = 1) => `rgba(0, 0, 0, ${opacity})`,
    labelColor: (opacity = 1) => `rgba(0, 0, 0, ${opacity})`,
    style: {
      borderRadius: 16
    },
    propsForDots: {
      r: '4',
      strokeWidth: '1',
    },
    formatYLabel: (value: string) => formatCurrency(parseFloat(value))
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Cashflow Projection</Text>
      </View>
      
      <LineChart
        data={chartData}
        width={screenWidth - 32}
        height={220}
        chartConfig={chartConfig}
        bezier
        style={styles.chart}
        withVerticalLabels
        withHorizontalLabels
        withDots
        withInnerLines
        withOuterLines
        withShadow
      />
      
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#2e7d32' }]} />
          <Text style={styles.legendText}>Projected</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#1976d2' }]} />
          <Text style={styles.legendText}>Actual</Text>
        </View>
        {showReceivables && (
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: '#388e3c80' }]} />
            <Text style={styles.legendText}>Receivables</Text>
          </View>
        )}
        {showPayables && (
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: '#d32f2f80' }]} />
            <Text style={styles.legendText}>Payables</Text>
          </View>
        )}
      </View>
    </View>
  );
};

export default CashflowGraphComponent;

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 16,
    marginBottom: 16,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  noDataContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  noDataText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
  },
  header: {
    marginBottom: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#000',
  },
  chart: {
    marginVertical: 8,
    borderRadius: 16,
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    marginTop: 16,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 16,
    marginBottom: 8,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  legendText: {
    fontSize: 12,
    color: '#666',
  },
});
