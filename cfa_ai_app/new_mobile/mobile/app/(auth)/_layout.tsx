import React from 'react';
import { View } from 'react-native';
import { Stack } from 'expo-router';

export default function AuthLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="api-token" />
      <Stack.Screen name="model-training" />
    </Stack>
  );
}
