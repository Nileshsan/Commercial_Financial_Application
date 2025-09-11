/// <reference types="react" />

declare module '*.png';
declare module '*.jpg';
declare module '*.jpeg';
declare module '*.gif';
declare module '*.svg';

// Add React Native specific type declarations
declare module 'react-native' {
  export interface ViewStyle {
    elevation?: number;
  }
}

// Add environment variables type declarations
declare module '@env' {
  export const API_URL: string;
  export const ENV: 'development' | 'production';
}
