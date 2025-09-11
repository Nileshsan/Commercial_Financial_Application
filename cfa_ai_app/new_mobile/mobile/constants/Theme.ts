export const Colors = {
  // Primary Colors
  primary: '#2e7d32',
  primaryLight: '#4caf50',
  primaryDark: '#1b5e20',
  
  // Secondary Colors
  secondary: '#388e3c',
  secondaryLight: '#66bb6a',
  secondaryDark: '#2e7d32',
  
  // Background Colors
  background: '#f8fff8',
  surface: '#ffffff',
  
  // Text Colors
  textPrimary: '#333333',
  textSecondary: '#666666',
  textLight: '#999999',
  
  // Status Colors
  success: '#4caf50',
  warning: '#ff9800',
  error: '#f44336',
  info: '#2196f3',
  
  // Gradient Colors
  gradients: {
    primary: ['#2e7d32', '#388e3c'],
    secondary: ['#4caf50', '#66bb6a'],
    background: ['#f8fff8', '#b7e4c7', '#40916c'],
  },
  
  // Chart Colors
  chart: {
    green: '#4caf50',
    blue: '#2196f3',
    orange: '#ff9800',
    purple: '#9c27b0',
    red: '#f44336',
    cyan: '#00bcd4',
  }
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const Typography = {
  h1: {
    fontSize: 32,
    fontWeight: 'bold' as const,
  },
  h2: {
    fontSize: 24,
    fontWeight: 'bold' as const,
  },
  h3: {
    fontSize: 20,
    fontWeight: '600' as const,
  },
  h4: {
    fontSize: 18,
    fontWeight: '600' as const,
  },
  body: {
    fontSize: 16,
    fontWeight: 'normal' as const,
  },
  bodySmall: {
    fontSize: 14,
    fontWeight: 'normal' as const,
  },
  caption: {
    fontSize: 12,
    fontWeight: 'normal' as const,
  },
};

export const Shadows = {
  small: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  medium: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 5,
  },
  large: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 16,
    elevation: 8,
  },
};

export const BorderRadius = {
  small: 8,
  medium: 12,
  large: 16,
  xl: 24,
  round: 50,
}; 