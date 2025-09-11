// Allow importing various file types and modules in TypeScript

declare module '@expo/vector-icons' {
  export * from '@expo/vector-icons';
}

declare module 'expo-network' {
  export * from 'expo-network';
}

declare module '*.png' {
  const value: any;
  export default value;
}

declare module '*.jpg' {
  const value: any;
  export default value;
}

declare module '*.jpeg' {
  const value: any;
  export default value;
}

declare module '*.gif' {
  const value: any;
  export default value;
}

declare module '*.svg' {
  const value: any;
  export default value;
}

// Ambient declarations for third-party modules without shipped types
declare module 'react-native-chart-kit';
declare module 'react-native-gesture-handler';
declare module 'react-native-reanimated';

