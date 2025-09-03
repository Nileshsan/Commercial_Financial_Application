import { DefaultTheme } from '@react-navigation/native';

export interface Theme {
  dark: boolean;
  colors: {
    primary: string;
    secondary: string;
    background: string;
    card: string;
    text: string;
    textSecondary: string;
    border: string;
    notification: string;
    error: string;
    success: string;
    buttonText: string;
  };
}

export const useTheme = (): Theme => ({
  dark: false,
  colors: {
    ...DefaultTheme.colors,
    primary: '#2196F3',
    secondary: '#5856D6',
    background: '#FFFFFF',
    card: '#FFFFFF',
    text: '#000000',
    textSecondary: '#666666',
    border: '#CCCCCC',
    notification: '#FF4444',
    error: '#FF0000',
    success: '#4CAF50',
    buttonText: '#FFFFFF',
  },
});
