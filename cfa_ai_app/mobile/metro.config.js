const { getDefaultConfig } = require('expo/metro-config');

const config = (() => {
  const defaultConfig = getDefaultConfig(__dirname, {
    // Enable experimental features for Hermes
    experimentalImportSupport: false,
    inlineRequires: true,
  });
  const { transformer, resolver } = defaultConfig;

  return {
    ...defaultConfig,
    transformer: {
      ...transformer,
      babelTransformerPath: require.resolve('react-native-svg-transformer'),
      // Add this to ensure Hermes works properly
      getTransformOptions: async () => ({
        transform: {
          experimentalImportSupport: false,
          inlineRequires: true,
        },
      }),
    },
    resolver: {
      ...resolver,
      assetExts: resolver.assetExts.filter((ext) => ext !== 'svg').concat(['db', 'sqlite']),
      sourceExts: [...resolver.sourceExts, 'svg'],
      // Add these configurations for better module resolution
      resolverMainFields: ['react-native', 'browser', 'main'],
      useDependenciesExactly: true,
    },
  };
})();

module.exports = config;
