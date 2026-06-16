import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Colors, Spacing, FontSizes, Radii } from '../constants/theme';
import * as geraldApi from '../services/geraldApi';
import { useConversationStore } from '../store/conversationStore';

interface Props {
  onApproved?: () => void;
  onRejected?: () => void;
}

export default function ApproveRejectBar({ onApproved, onRejected }: Props) {
  const [loading, setLoading] = useState<'approve' | 'reject' | null>(null);
  const { setStatus, baseUrl } = useConversationStore();

  async function handleApprove() {
    setLoading('approve');
    geraldApi.configure(baseUrl);
    try {
      await geraldApi.sendToClaudeCode();
      setStatus('executing');
      onApproved?.();
    } catch {
      Alert.alert('Error', 'Failed to send approval to Gerald.');
    } finally {
      setLoading(null);
    }
  }

  async function handleReject() {
    setLoading('reject');
    geraldApi.configure(baseUrl);
    try {
      await geraldApi.rejectPlan('Plan rejected by user');
      setStatus('idle');
      onRejected?.();
    } catch {
      Alert.alert('Error', 'Failed to send rejection to Gerald.');
    } finally {
      setLoading(null);
    }
  }

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={[styles.button, styles.approveButton]}
        onPress={handleApprove}
        disabled={loading !== null}
        activeOpacity={0.8}
      >
        {loading === 'approve' ? (
          <ActivityIndicator color={Colors.textPrimary} size="small" />
        ) : (
          <Text style={styles.buttonText}>APPROVE</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity
        style={[styles.button, styles.rejectButton]}
        onPress={handleReject}
        disabled={loading !== null}
        activeOpacity={0.8}
      >
        {loading === 'reject' ? (
          <ActivityIndicator color={Colors.textPrimary} size="small" />
        ) : (
          <Text style={styles.buttonText}>REJECT</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    marginTop: Spacing.md,
    gap: Spacing.sm,
  },
  button: {
    flex: 1,
    paddingVertical: Spacing.sm,
    borderRadius: Radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 40,
  },
  approveButton: {
    backgroundColor: Colors.approve,
  },
  rejectButton: {
    backgroundColor: Colors.reject,
  },
  buttonText: {
    color: Colors.textPrimary,
    fontSize: FontSizes.sm,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
});
