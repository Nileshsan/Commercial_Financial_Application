import React, { createContext, useContext, ReactNode } from 'react';
import { Linking } from 'react-native';
import { NavigationContainerRef, PathConfigMap } from '@react-navigation/native';

type LinkingConfiguration = {
  prefixes: string[];
  config: {
    screens: {
      [key: string]: string | { [key: string]: string };
    };
  };
};

type AuthStackParamList = {
  login: undefined;
  'api-token': undefined;
  'model-training': undefined;
};

type AppStackParamList = {
  dashboard: undefined;
  cashflow: undefined;
  transactions: undefined;
  clients: undefined;
  profile: undefined;
  settings: undefined;
};

type RootStackParamList = {
  index: undefined;
  '(auth)': undefined;
  '(app)': undefined;
};

interface LinkingContextType {
  url: string;
}

export const LinkingContext = createContext<LinkingContextType | undefined>(undefined);

interface LinkingProviderProps {
  children: ReactNode;
}

export function LinkingProvider({ children }: LinkingProviderProps) {
  const linking: LinkingConfiguration = {
    prefixes: ['cfa://', 'https://cfa.app'],
    config: {
      screens: {
        index: '',
        '(auth)': {
          login: 'login',
          'api-token': 'api-token',
          'model-training': 'model-training',
        },
        '(app)': {
          dashboard: 'dashboard',
          cashflow: 'cashflow',
          transactions: 'transactions',
          clients: 'clients',
          profile: 'profile',
          settings: 'settings',
        },
      },
    },
  };

  return (
    <LinkingContext.Provider value={{ url: '' }}>
      {children}
    </LinkingContext.Provider>
  );
}

export const useLinking = () => {
  const context = useContext(LinkingContext);
  if (!context) {
    throw new Error('useLinking must be used within a LinkingProvider');
  }
  return context;
};
