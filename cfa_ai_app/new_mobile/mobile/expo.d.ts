import { ViewProps } from 'react-native';
import React from 'react';

declare module 'react-native-gesture-handler' {
  import { ViewProps } from 'react-native';
  
  export interface GestureHandlerRootViewProps extends ViewProps {}
  
  export class GestureHandlerRootView extends React.Component<GestureHandlerRootViewProps> {}
  
  export * from 'react-native-gesture-handler/lib/typescript/index';
}

declare module 'expo-linear-gradient' {
  import { ViewProps } from 'react-native';
  
  export interface LinearGradientProps extends ViewProps {
    colors: string[];
    start?: { x: number; y: number };
    end?: { x: number; y: number };
    locations?: number[];
  }
  
  const LinearGradient: React.ComponentType<LinearGradientProps>;
  export default LinearGradient;
}

declare module 'expo-web-browser' {
  export interface WebBrowserResult {
    type: 'cancel' | 'dismiss' | 'opened';
  }

  export interface WebBrowserAuthSessionResult extends WebBrowserResult {
    url?: string;
  }

  export function openBrowserAsync(url: string): Promise<WebBrowserResult>;
  export function warmUpAsync(): Promise<void>;
  export function coolDownAsync(): Promise<void>;
  export function dismissBrowser(): Promise<void>;
  export function maybeCompleteAuthSession(): void;
  export function openAuthSessionAsync(
    url: string,
    redirectUrl?: string | null,
    options?: {
      showInRecents?: boolean;
      ephemeral?: boolean;
    }
  ): Promise<WebBrowserAuthSessionResult>;
}

declare module 'expo-auth-session' {
  export interface AuthRequestConfig {
    clientId: string;
    redirectUri: string;
    scopes?: string[];
    extraParams?: Record<string, string>;
    responseType?: string;
    usePKCE?: boolean;
  }

  export interface AuthSessionResult {
    type: string;
    params?: Record<string, string>;
    error?: Error;
    url?: string;
  }

  export class AuthRequest {
    constructor(config: AuthRequestConfig);
    promptAsync(options?: { useProxy?: boolean }): Promise<AuthSessionResult>;
  }

  export function makeRedirectUri(options?: { useProxy?: boolean }): string;
}
