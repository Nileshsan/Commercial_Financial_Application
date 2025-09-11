import { Stack } from 'expo-router';
import { useEffect } from 'react';
import { useFonts } from 'expo-font';
import { useColorScheme } from 'react-native';
import { ThemeProvider } from '@/providers/ThemeProvider';
import { LinkingProvider } from '@/providers/LinkingProvider';

export default function RootLayout() {
  const colorScheme = useColorScheme();

  const [loaded] = useFonts({
    // Add your custom fonts here if needed
  });

  if (!loaded) {
    return null;
  }

  return (
    <ThemeProvider>
      <LinkingProvider>
        <Stack
          screenOptions={{
            headerShown: false,
          }}
          initialRouteName="(auth)"
        >
          <Stack.Screen 
            name="(auth)" 
            options={{ 
              headerShown: false,
              animation: 'none' 
            }} 
          />
          <Stack.Screen name="(app)" options={{ headerShown: false }} />
        </Stack>
      </LinkingProvider>
    </ThemeProvider>
  );

  if (!loaded) {
    return null;
  }

  return (
    <LinkingProvider>
      <ThemeProvider>
        <Stack 
          screenOptions={{
            headerShown: false,
          }}
        >
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen 
            name="(auth)" 
            options={{ 
              headerShown: false,
              gestureEnabled: false 
            }} 
          />
          <Stack.Screen 
            name="(app)" 
            options={{ 
              headerShown: false,
              gestureEnabled: false 
            }} 
          />
        </Stack>
      </ThemeProvider>
    </LinkingProvider>
  );
}
