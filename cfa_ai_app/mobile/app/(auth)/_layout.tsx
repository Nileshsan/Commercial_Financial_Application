import React from 'react';
import { Stack } from 'expo-router';

export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: 'fade',
      }}
      initialRouteName="splash"
    >
      <Stack.Screen name="splash" options={{ headerShown: false, animation: 'none' }} />
      <Stack.Screen name="login" options={{ headerShown: false }} />
      <Stack.Screen name="api-token" options={{ headerShown: false }} />
      <Stack.Screen name="model-training" options={{ headerShown: false }} />
    </Stack>
  );
}
