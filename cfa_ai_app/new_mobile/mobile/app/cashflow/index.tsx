import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export default function CashflowScreen() {
  return (
    <View style={styles.container}>
      <Text>Cashflow Analytics</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
  },
});
