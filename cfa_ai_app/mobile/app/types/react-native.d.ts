/// <reference types="react" />

export {};

declare module 'react-native' {
  export interface NativeEventSubscription {
    remove(): void;
  }
}

declare module '@react-navigation/native' {
  export interface NavigationState {
    index: number;
    routes: Array<{
      key: string;
      name: string;
      params?: object;
    }>;
  }
}
