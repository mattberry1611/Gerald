import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { Message } from '../store/conversationStore';
import { Colors, FontSizes, Spacing, Radii } from '../constants/theme';
import ApproveRejectBar from './ApproveRejectBar';

interface Props {
  message: Message;
}

function renderContent(text: string) {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts.map((part, i) => {
    if (part.startsWith('```') && part.endsWith('```')) {
      const inner = part.slice(3, -3).replace(/^[a-z]+\n/, '');
      return (
        <View key={i} style={styles.codeBlock}>
          <Text style={styles.codeText} selectable>
            {inner}
          </Text>
        </View>
      );
    }
    return (
      <Text key={i} style={styles.messageText} selectable>
        {part}
      </Text>
    );
  });
}

export default function MessageBubble({ message }: Props) {
  const [showTimestamp, setShowTimestamp] = useState(false);
  const isUser = message.role === 'user';

  const bubbleStyle = isUser ? styles.userBubble : styles.geraldBubble;
  const containerStyle = isUser ? styles.userContainer : styles.geraldContainer;

  function formatTime(d: Date) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  return (
    <View style={containerStyle}>
      <TouchableOpacity
        onLongPress={() => setShowTimestamp((v) => !v)}
        activeOpacity={0.9}
        style={[styles.bubble, bubbleStyle]}
      >
        {message.isLoading ? (
          <View style={styles.loadingRow}>
            <ActivityIndicator color={Colors.accent} size="small" />
            <Text style={[styles.messageText, styles.loadingText]}>
              Gerald is thinking...
            </Text>
          </View>
        ) : (
          renderContent(message.content)
        )}

        {message.isPlan && !message.isLoading && (
          <ApproveRejectBar />
        )}

        {showTimestamp && (
          <Text style={styles.timestamp}>
            {formatTime(message.timestamp)}
          </Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  userContainer: {
    alignSelf: 'flex-end',
    maxWidth: '80%',
    marginVertical: Spacing.xs,
    marginRight: Spacing.md,
    marginLeft: Spacing.xl,
  },
  geraldContainer: {
    alignSelf: 'flex-start',
    maxWidth: '80%',
    marginVertical: Spacing.xs,
    marginLeft: Spacing.md,
    marginRight: Spacing.xl,
  },
  bubble: {
    padding: Spacing.md,
    borderRadius: Radii.lg,
  },
  userBubble: {
    backgroundColor: Colors.userBubble,
    borderBottomRightRadius: Radii.sm,
  },
  geraldBubble: {
    backgroundColor: Colors.geraldBubble,
    borderBottomLeftRadius: Radii.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  messageText: {
    color: Colors.textPrimary,
    fontSize: FontSizes.md,
    lineHeight: 22,
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  loadingText: {
    color: Colors.textSecondary,
    fontStyle: 'italic',
  },
  codeBlock: {
    backgroundColor: Colors.codeBg,
    borderRadius: Radii.sm,
    padding: Spacing.sm,
    marginVertical: Spacing.xs,
    borderLeftWidth: 2,
    borderLeftColor: Colors.accent,
  },
  codeText: {
    color: Colors.accent,
    fontSize: FontSizes.mono,
    fontFamily: 'monospace',
    lineHeight: 18,
  },
  timestamp: {
    color: Colors.textMuted,
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
    textAlign: 'right',
  },
});
