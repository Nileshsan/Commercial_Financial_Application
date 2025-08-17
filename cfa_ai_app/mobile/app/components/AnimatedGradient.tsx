import React, { useRef, useEffect } from 'react';
import { Animated, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

const AnimatedGradient: React.FC = () => {
  const colorAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(colorAnim, {
          toValue: 1,
          duration: 4000,
          useNativeDriver: false,
        }),
        Animated.timing(colorAnim, {
          toValue: 0,
          duration: 4000,
          useNativeDriver: false,
        }),
      ])
    ).start();
  }, []);

  const backgroundColors = colorAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [
      'rgba(210,236,248,1)', // Light blue
      'rgba(210,248,212,1)', // Light green
    ],
  });

  return (
    <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: backgroundColors }]}/>
  );
};

export default AnimatedGradient;
