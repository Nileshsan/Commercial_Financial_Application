module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      ['babel-preset-expo', {
        jsxRuntime: 'automatic',
        lazyImports: true,
      }],
    ],
    plugins: [
      ['@babel/plugin-transform-runtime', {
        helpers: true,
        regenerator: true,
      }],
      [
        'module-resolver',
        {
          root: ['.'],
          extensions: ['.ios.js', '.android.js', '.js', '.ts', '.tsx', '.json'],
          alias: {
            '@': '.',
            'services': './services',
            'components': './app/components'
          },
        },
      ],
      'react-native-worklets/plugin',
    ],
    env: {
      production: {
        plugins: ['transform-remove-console']
      }
    }
  };
};
