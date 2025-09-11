import { registerRootComponent } from 'expo';
import { AppRegistry, Platform } from 'react-native';
import App from './App';

if (Platform.OS === 'web') {
  // Register the app for web platform
  AppRegistry.registerComponent('main', () => App);
} else {
  // Register the app for native platforms using Expo's helper
  registerRootComponent(App);
}
