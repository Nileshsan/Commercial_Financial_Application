import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface ErrorOverlayProps {
  message: string;
}

export const ErrorOverlay: React.FC<ErrorOverlayProps> = ({ message }) => {
  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <Ionicons name="warning" size={24} color="#ff4444" />
        <Text style={styles.errorText}>{message}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    backgroundColor: '#ff000088',
    padding: 10,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  errorText: {
    color: 'white',
    marginLeft: 10,
    flex: 1,
  },
});
