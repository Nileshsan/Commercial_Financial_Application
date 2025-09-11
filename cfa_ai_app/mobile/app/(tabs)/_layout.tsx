import { Tabs } from 'expo-router';
import { BlurView } from 'expo-blur';
import { useTheme } from '@react-navigation/native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { ViewStyle, useColorScheme } from 'react-native';

export default function TabLayout() {
  const { colors } = useTheme();
  const colorScheme = useColorScheme();
  
  return (
    <Tabs
      screenOptions={{
        tabBarStyle: {
          backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#ffffff',
        } as ViewStyle,
        headerStyle: {
          backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#ffffff',
        } as ViewStyle,
        headerTintColor: colorScheme === 'dark' ? '#ffffff' : '#000000',
        tabBarActiveTintColor: '#40916c',
        tabBarInactiveTintColor: colorScheme === 'dark' ? '#888888' : '#666666',
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
