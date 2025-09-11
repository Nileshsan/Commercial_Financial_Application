import { Redirect } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';
import { View, StyleSheet, Text, ActivityIndicator } from 'react-native';

export default function Index() {
  const [isLoading, setIsLoading] = useState(true);
  const [initialRoute, setInitialRoute] = useState<string | null>(null);

  useEffect(() => {
    async function checkAuthState() {
      try {
        const token = await AsyncStorage.getItem('sessionToken');
        setInitialRoute(token ? '/(app)/dashboard/index' : '/(auth)/login');
      } catch (error) {
        setInitialRoute('/(auth)/login');
      } finally {
        setIsLoading(false);
      }
    }
    checkAuthState();
  }, []);

  if (isLoading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color="#2e7d32" />
      </View>
    );
  }

  return initialRoute ? <Redirect href={initialRoute} /> : null;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
  },
});
