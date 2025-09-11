const fs = require('fs');
const path = require('path');

const hasNativeProject = fs.existsSync('./android') || fs.existsSync('./ios');

// Default configuration
const defaultConfig = {
  API_URL: 'https://10.0.2.2:8000',
  scheme: 'cfa',
  name: 'CFA',
  slug: 'cfa',
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  splash: {
    image: './assets/splash.png',
    resizeMode: 'contain',
    backgroundColor: '#ffffff'
  },
  android: {
    package: 'com.nileshsan.cfa',
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#ffffff'
    }
  },
  ios: {
    bundleIdentifier: 'com.nileshsan.cfa',
    supportsTablet: true
  },
};

// Load .env file if it exists
let envConfig = {};
const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
  require('dotenv').config({ path: envPath });
  envConfig = {
    API_URL: process.env.API_URL || defaultConfig.API_URL,
  };
}

const nativeConfig = hasNativeProject
  ? {
      scheme: 'cfa',
      orientation: 'portrait',
      icon: './assets/icon.png',
      splash: {
        image: './assets/splash.png',
        resizeMode: 'contain',
        backgroundColor: '#ffffff'
      },
      jsEngine: 'hermes',
      plugins: [
        'expo-router'
      ],
      experiments: {
        tsconfigPaths: true
      },
      ios: {
        jsEngine: 'hermes',
        supportsTablet: true,
        bundleIdentifier: 'com.cfa.mobile'
      },
      android: {
        jsEngine: 'hermes',
        package: 'com.cfa.mobile',
        hermes: true
      }
    }
  : {
      orientation: 'portrait',
      icon: './assets/icon.png',
      scheme: 'cfa-mobile',
      userInterfaceStyle: 'light',
      jsEngine: 'hermes',
      splash: {
        image: './assets/splash.png',
        resizeMode: 'contain',
        backgroundColor: '#ffffff'
      },
      ios: {
        jsEngine: 'hermes',
        supportsTablet: true,
        bundleIdentifier: 'com.cfa.mobile'
      },
      android: {
        jsEngine: 'hermes',
        adaptiveIcon: {
          foregroundImage: './assets/adaptive-icon.png',
          backgroundColor: '#ffffff'
        },
        package: 'com.cfa.mobile'
      },
      plugins: [
        'expo-router',
        [
          'expo-build-properties',
          {
            ios: {
              enableHermes: true
            },
            android: {
              enableHermes: true
            }
          }
        ],
        'react-native-reanimated'
      ]
    };

const finalConfig = {
  name: 'CFA Mobile',
  slug: 'cfa-mobile',
  version: '1.0.0',
  extra: {
    ...envConfig,
    eas: {
      projectId: 'e866f211-9f36-4c8a-9b5e-9c48d8c37eb4'
    }
  },
  ...nativeConfig,
  plugins: [
    'expo-router',
    'expo-font',
    'expo-web-browser',
    [
      'expo-build-properties',
      {
        ios: {
          enableHermes: true
        },
        android: {
          enableHermes: true
        }
      }
    ],
    'react-native-reanimated'
  ],
  assetBundlePatterns: [
    'assets/*',
    '**/*',
  ],
  web: {
    favicon: './assets/favicon.png',
    build: {
      babel: {
        include: ['@expo/vector-icons', 'react-native-svg']
      }
    }
  },
  experiments: {
    tsconfigPaths: true
  }
};
