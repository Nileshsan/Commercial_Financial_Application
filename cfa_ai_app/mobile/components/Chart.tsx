import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

const { width } = Dimensions.get('window');

interface ChartData {
  label: string;
  value: number;
  color: string;
}

export function Chart() {
  const data: ChartData[] = [
    { label: 'Jan', value: 65, color: '#4caf50' },
    { label: 'Feb', value: 80, color: '#2196f3' },
    { label: 'Mar', value: 45, color: '#ff9800' },
    { label: 'Apr', value: 90, color: '#9c27b0' },
    { label: 'May', value: 75, color: '#f44336' },
    { label: 'Jun', value: 85, color: '#00bcd4' },
  ];

  const maxValue = Math.max(...data.map(item => item.value));

  const renderBar = (item: ChartData, index: number) => {
    const barHeight = (item.value / maxValue) * 120; // Max height 120px
    
    return (
      <View key={index} style={styles.barContainer}>
        <View style={styles.barWrapper}>
          <LinearGradient
            colors={[item.color, item.color + '80']}
            style={[styles.bar, { height: barHeight }]}
          />
        </View>
        <Text style={styles.barLabel}>{item.label}</Text>
        <Text style={styles.barValue}>{item.value}%</Text>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.chartContainer}>
        {data.map((item, index) => renderBar(item, index))}
      </View>
      
      {/* Chart Legend */}
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#4caf50' }]} />
          <Text style={styles.legendText}>Income</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: '#f44336' }]} />
          <Text style={styles.legendText}>Expenses</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  chartContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-around',
    height: 140,
    paddingHorizontal: 10,
  },
  barContainer: {
    alignItems: 'center',
    flex: 1,
  },
  barWrapper: {
    width: 20,
    height: 120,
    justifyContent: 'flex-end',
    marginBottom: 8,
  },
  bar: {
    width: '100%',
    borderRadius: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  barLabel: {
    fontSize: 12,
    color: '#666',
    fontWeight: '500',
  },
  barValue: {
    fontSize: 10,
    color: '#999',
    marginTop: 2,
  },
  legend: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 16,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 12,
  },
  legendDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 6,
  },
  legendText: {
    fontSize: 12,
    color: '#666',
  },
});
