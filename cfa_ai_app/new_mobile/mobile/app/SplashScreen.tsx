import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated, Easing, Dimensions, Image } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import LogoImage from '../assets/images/converted-image.png';
import { api } from '../services/api';

const { width, height } = Dimensions.get('window');

// Light palette
const GREEN = '#b7e4c7';
const DARK_GREEN = '#40916c';
const BEIGE = '#f5f5dc';
const WHITE = '#fff';

export default function SplashScreen() {
  const router = useRouter();

  // Animation values
  const logoScale = useRef(new Animated.Value(0)).current;
  const logoOpacity = useRef(new Animated.Value(0)).current;
  const logoRotate = useRef(new Animated.Value(0)).current;
  const titleOpacity = useRef(new Animated.Value(0)).current;
  const titleTranslateY = useRef(new Animated.Value(50)).current;
  const subtitleOpacity = useRef(new Animated.Value(0)).current;
  const subtitleTranslateY = useRef(new Animated.Value(30)).current;
  const shimmerAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Check authentication status
    const checkAuth = async () => {
      try {
  // Check for authentication token first
  const authToken = await AsyncStorage.getItem('sessionToken');
        const apiToken = await AsyncStorage.getItem('apiToken');
        const modelTrained = await AsyncStorage.getItem('modelTrained');

        // After animations, navigate based on auth state
        setTimeout(() => {
          if (!authToken) {
            // No auth token, need to login
            router.replace('/(auth)/login');
          } else if (!apiToken) {
            // Logged in but no API token
            router.replace('/(auth)/api-token');
          } else if (!modelTrained || modelTrained !== 'true') {
            // Has tokens but model not trained
            router.replace('/(auth)/model-training');
          } else {
            // All set, go to main app
            router.replace('/(app)');
          }
        }, 3000); // Wait for animations to complete
      } catch (error) {
        console.error('Error checking auth status:', error);
        router.replace('/(auth)/login');
      }
    };

    // Start animations sequence and check auth
    const animationSequence = Animated.sequence([
      Animated.parallel([
        Animated.timing(logoScale, {
          toValue: 1,
          duration: 1200,
          easing: Easing.elastic(1.2),
          useNativeDriver: true,
        }),
        Animated.timing(logoOpacity, {
          toValue: 1,
          duration: 800,
          useNativeDriver: true,
        }),
        Animated.timing(logoRotate, {
          toValue: 1,
          duration: 1200,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),
      Animated.parallel([
        Animated.timing(titleOpacity, {
          toValue: 1,
          duration: 600,
          useNativeDriver: true,
        }),
        Animated.timing(titleTranslateY, {
          toValue: 0,
          duration: 600,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),
      Animated.parallel([
        Animated.timing(subtitleOpacity, {
          toValue: 1,
          duration: 500,
          useNativeDriver: true,
        }),
        Animated.timing(subtitleTranslateY, {
          toValue: 0,
          duration: 500,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),
    ]);

    // Continuous shimmer animation
    const shimmerAnimation = Animated.loop(
      Animated.timing(shimmerAnim, {
        toValue: 1,
        duration: 2000,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    );

    animationSequence.start();
    shimmerAnimation.start();

    const timer = setTimeout(() => {
      router.replace('/login');
    }, 3000);

    return () => {
      clearTimeout(timer);
      shimmerAnimation.stop();
    };
  }, []);

  // Animation interpolations
  const logoRotateInterpolate = logoRotate.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  const shimmerTranslate = shimmerAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [-width, width],
  });

  return (
    <View style={styles.container}>
      {/* White-Green Gradient with Light Beige */}
      <LinearGradient
        colors={[WHITE, GREEN, BEIGE]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={StyleSheet.absoluteFill}
      />

      {/* Main Content Container */}
      <View style={styles.contentContainer}>
        {/* Logo Container with Glow Effect */}
        <Animated.View
          style={[
            styles.logoContainer,
            {
              opacity: logoOpacity,
              transform: [
                { scale: logoScale },
                { rotate: logoRotateInterpolate },
              ],
            },
          ]}
        >
          {/* Glow Effect */}
          <View style={styles.glowEffect} />

          {/* Logo Background Circle */}
          <LinearGradient
            colors={[WHITE, GREEN, BEIGE]}
            style={styles.logoBackground}
          >
            {/* CFA Logo Image */}
            <Image
              source={LogoImage}
              style={styles.logoImage}
              resizeMode="contain"
            />
          </LinearGradient>

          {/* Shimmer Effect */}
          <Animated.View
            style={[
              styles.shimmer,
              {
                transform: [{ translateX: shimmerTranslate }],
              },
            ]}
          />
        </Animated.View>

        {/* App Title */}
        <Animated.View
          style={[
            styles.titleContainer,
            {
              opacity: titleOpacity,
              transform: [{ translateY: titleTranslateY }],
            },
          ]}
        >
          <Text style={styles.appTitle}>CFA AI</Text>
          <LinearGradient
            colors={[GREEN, BEIGE]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.titleUnderline}
          />
        </Animated.View>

        {/* Subtitle */}
        <Animated.View
          style={[
            styles.subtitleContainer,
            {
              opacity: subtitleOpacity,
              transform: [{ translateY: subtitleTranslateY }],
            },
          ]}
        >
          <Text style={styles.subtitle}>Smart Cash Flow Analytics</Text>
          <Text style={styles.tagline}>Powered by Artificial Intelligence</Text>
        </Animated.View>
      </View>

      {/* Loading Indicator */}
      <Animated.View
        style={[
          styles.loadingContainer,
          {
            opacity: subtitleOpacity,
          },
        ]}
      >
        <View style={styles.loadingBar}>
          <Animated.View
            style={[
              styles.loadingProgress,
              {
                transform: [{ scaleX: shimmerAnim }],
              },
            ]}
          />
        </View>
        <Text style={styles.loadingText}>Initializing AI Engine...</Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  contentContainer: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 36,
    position: 'relative',
  },
  glowEffect: {
    position: 'absolute',
    width: 160,
    height: 160,
    borderRadius: 80,
    backgroundColor: 'rgba(183,228,199,0.13)',
    shadowColor: '#b7e4c7',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.6,
    shadowRadius: 30,
    elevation: 18,
  },
  logoBackground: {
    width: 110,
    height: 110,
    borderRadius: 55,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#b7e4c7',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.13,
    shadowRadius: 16,
    elevation: 10,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.18)',
    backgroundColor: '#fff',
  },
  logoImage: {
    width: 80,
    height: 80,
    borderRadius: 40,
  },
  shimmer: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(255,255,255,0.18)',
    width: 28,
    borderRadius: 55,
    transform: [{ skewX: '-20deg' }],
  },
  titleContainer: {
    alignItems: 'center',
    marginBottom: 18,
  },
  appTitle: {
    fontSize: 34,
    fontWeight: '900',
    color: '#40916c',
    letterSpacing: 2,
    textAlign: 'center',
    textShadowColor: 'rgba(0,0,0,0.10)',
    textShadowOffset: { width: 2, height: 2 },
    textShadowRadius: 8,
  },
  titleUnderline: {
    height: 4,
    width: 60,
    borderRadius: 2,
    marginTop: 8,
  },
  subtitleContainer: {
    alignItems: 'center',
    marginBottom: 24,
  },
  subtitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#40916c',
    textAlign: 'center',
    marginBottom: 6,
    letterSpacing: 1,
  },
  tagline: {
    fontSize: 13,
    fontWeight: '400',
    color: '#b7e4c7',
    textAlign: 'center',
    fontStyle: 'italic',
  },
  loadingContainer: {
    position: 'absolute',
    bottom: 70,
    alignItems: 'center',
    width: '100%',
  },
  loadingBar: {
    width: 150,
    height: 3,
    backgroundColor: 'rgba(183,228,199,0.18)',
    borderRadius: 2,
    overflow: 'hidden',
    marginBottom: 10,
  },
  loadingProgress: {
    height: '100%',
    backgroundColor: '#b7e4c7',
    borderRadius: 2,
    transformOrigin: 'left',
  },
  loadingText: {
    fontSize: 12,
    color: '#40916c',
    fontWeight: '500',
    letterSpacing: 0.5,
  },
});