import { AppRegistry, LogBox } from 'react-native';
import App from './App';

// Ignore specific warnings
LogBox.ignoreLogs([
  'Exception in HostObject::get for prop',
  'registerScreenCaptureObserver',
  'Permission Denial',
]);

// Register the app
AppRegistry.registerComponent('main', () => App);
