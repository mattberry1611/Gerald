import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { AppStatus } from '../store/conversationStore';
import { Colors, Spacing, FontSizes } from '../constants/theme';

const STATUS_COLORS: Record<AppStatus, string> = {
  idle: Colors.statusIdle,
  planning: Colors.statusPlanning,
  awaiting: Colors.statusAwaiting,
  executing: Colors.statusExecuting,
  error: Colors.statusError,
};

const STATUS_LABELS: Record<AppStatus, string> = {
  idle: 'Idle',
  planning: 'Planning',
  awaiting: 'Awaiting Approval',
  executing: 'Executing',
  error: 'Error',
};

interface Props {
  status: AppStatus;
}

export default function StatusIndicator({ status }: Props) {
  const [showLabel, setShowLabel] = useState(false);
  const color = STATUS_COLORS[status];

  return (
    <TouchableOpacity
      onLongPress={() => setShowLabel((v) => !v)}
      onPress={() => setShowLabel(false)}
      activeOpacity={0.7}
      style={styles.container}
    >
      <View style={[styles.dot, { backgroundColor: color }]} />
      {showLabel && (
        <View style={styles.labelContainer}>
          <Text style={[styles.label, { color }]}>{STATUS_LABELS[status]}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.sm,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  labelContainer: {
    position: 'absolute',
    top: 20,
    right: 0,
    backgroundColor: Colors.surface,
    borderRadius: 6,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderWidth: 1,
    borderColor: Colors.border,
    zIndex: 10,
  },
  label: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
});
