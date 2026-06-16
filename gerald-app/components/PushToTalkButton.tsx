import React, { useEffect, useRef } from 'react';
import {
  Animated,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  ActivityIndicator,
} from 'react-native';
import { Colors, FontSizes, Spacing } from '../constants/theme';

export type PTTState = 'idle' | 'recording' | 'processing';

interface Props {
  state: PTTState;
  onPressIn: () => void;
  onPressOut: () => void;
}

export default function PushToTalkButton({ state, onPressIn, onPressOut }: Props) {
  const pulseScale = useRef(new Animated.Value(1)).current;
  const pulseOpacity = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef<Animated.CompositeAnimation | null>(null);

  useEffect(() => {
    if (state === 'recording') {
      pulseOpacity.setValue(0.7);
      pulseAnim.current = Animated.loop(
        Animated.sequence([
          Animated.parallel([
            Animated.timing(pulseScale, {
              toValue: 1.6,
              duration: 700,
              useNativeDriver: true,
            }),
            Animated.timing(pulseOpacity, {
              toValue: 0,
              duration: 700,
              useNativeDriver: true,
            }),
          ]),
          Animated.parallel([
            Animated.timing(pulseScale, {
              toValue: 1,
              duration: 0,
              useNativeDriver: true,
            }),
            Animated.timing(pulseOpacity, {
              toValue: 0.7,
              duration: 0,
              useNativeDriver: true,
            }),
          ]),
        ])
      );
      pulseAnim.current.start();
    } else {
      pulseAnim.current?.stop();
      pulseScale.setValue(1);
      pulseOpacity.setValue(0);
    }

    return () => {
      pulseAnim.current?.stop();
    };
  }, [state]);

  const isRecording = state === 'recording';
  const isProcessing = state === 'processing';

  const buttonColor = isRecording
    ? Colors.error
    : isProcessing
    ? Colors.statusPlanning
    : Colors.accent;

  return (
    <View style={styles.wrapper}>
      {/* Animated pulse ring */}
      <Animated.View
        style={[
          styles.pulseRing,
          {
            borderColor: Colors.error,
            transform: [{ scale: pulseScale }],
            opacity: pulseOpacity,
          },
        ]}
      />

      <TouchableOpacity
        onPressIn={onPressIn}
        onPressOut={onPressOut}
        activeOpacity={0.85}
        disabled={isProcessing}
        style={[styles.button, { backgroundColor: buttonColor }]}
      >
        {isProcessing ? (
          <ActivityIndicator color={Colors.textPrimary} size="large" />
        ) : (
          <Text style={styles.icon}>{isRecording ? '⏹' : '🎤'}</Text>
        )}
      </TouchableOpacity>

      <Text style={styles.label}>
        {isProcessing ? 'Sending...' : isRecording ? 'Listening...' : 'Hold to talk'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  pulseRing: {
    position: 'absolute',
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 3,
  },
  button: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 4,
  },
  icon: {
    fontSize: 28,
  },
  label: {
    color: Colors.textSecondary,
    fontSize: FontSizes.xs,
    marginTop: Spacing.sm,
  },
});
