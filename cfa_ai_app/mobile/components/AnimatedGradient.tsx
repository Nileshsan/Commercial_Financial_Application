import React, { useEffect } from 'react';
import { StyleSheet, Animated } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

export function AnimatedGradient() {
  const animatedValue = new Animated.Value(0);

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(animatedValue, {
          toValue: 1,
          duration: 10000,
          useNativeDriver: true,
        }),
        Animated.timing(animatedValue, {
          toValue: 0,
          duration: 10000,
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, []);

  const rotate = animatedValue.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  const AnimatedGradient = Animated.createAnimatedComponent(LinearGradient);

  return (
    <Animated.View style={[StyleSheet.absoluteFill, { transform: [{ rotate }] }]}>
      <AnimatedGradient
        colors={['rgba(46, 125, 50, 0.1)', 'rgba(210, 236, 248, 0.2)', 'rgba(46, 125, 50, 0.1)']}
        style={StyleSheet.absoluteFill}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
      />
    </Animated.View>
  );
}
