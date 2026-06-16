import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useConversationStore } from '../store/conversationStore';
import { Colors, FontSizes, Spacing, Radii } from '../constants/theme';
import Constants from 'expo-constants';

export default function SettingsScreen() {
  const { baseUrl, setBaseUrl, clearMessages } = useConversationStore();
  const [urlDraft, setUrlDraft] = useState(baseUrl);

  function handleSaveUrl() {
    const trimmed = urlDraft.trim();
    if (!trimmed) return;
    setBaseUrl(trimmed);
    Alert.alert('Saved', 'Backend URL updated.');
  }

  function handleClearHistory() {
    Alert.alert(
      'Clear Conversation',
      'This will remove all messages from this session. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: () => {
            clearMessages();
            router.back();
          },
        },
      ]
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Settings</Text>
        <View style={styles.backButton} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Backend URL */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Gerald Backend</Text>
          <Text style={styles.label}>Base URL</Text>
          <TextInput
            style={styles.input}
            value={urlDraft}
            onChangeText={setUrlDraft}
            placeholder="http://192.168.x.x:8000"
            placeholderTextColor={Colors.textMuted}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />
          <TouchableOpacity style={styles.saveButton} onPress={handleSaveUrl}>
            <Text style={styles.saveButtonText}>Save URL</Text>
          </TouchableOpacity>
        </View>

        {/* Conversation */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Conversation</Text>
          <TouchableOpacity style={styles.dangerButton} onPress={handleClearHistory}>
            <Text style={styles.dangerButtonText}>Clear Conversation History</Text>
          </TouchableOpacity>
        </View>

        {/* App info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>About</Text>
          <Text style={styles.infoText}>
            Gerald v{Constants.expoConfig?.version ?? '1.0.0'}
          </Text>
          <Text style={styles.infoText}>Voice-to-Claude coding supervisor</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  backButton: {
    width: 80,
  },
  backText: {
    color: Colors.accent,
    fontSize: FontSizes.md,
  },
  headerTitle: {
    color: Colors.textPrimary,
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  content: {
    padding: Spacing.lg,
    gap: Spacing.xl,
  },
  section: {
    gap: Spacing.sm,
  },
  sectionTitle: {
    color: Colors.accent,
    fontSize: FontSizes.sm,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: Spacing.xs,
  },
  label: {
    color: Colors.textSecondary,
    fontSize: FontSizes.sm,
  },
  input: {
    backgroundColor: Colors.surface,
    color: Colors.textPrimary,
    borderRadius: Radii.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    fontSize: FontSizes.md,
  },
  saveButton: {
    backgroundColor: Colors.accent,
    borderRadius: Radii.sm,
    paddingVertical: Spacing.sm,
    alignItems: 'center',
    marginTop: Spacing.xs,
  },
  saveButtonText: {
    color: Colors.background,
    fontWeight: '700',
    fontSize: FontSizes.md,
  },
  dangerButton: {
    backgroundColor: Colors.surface,
    borderRadius: Radii.sm,
    borderWidth: 1,
    borderColor: Colors.error,
    paddingVertical: Spacing.sm,
    alignItems: 'center',
  },
  dangerButtonText: {
    color: Colors.error,
    fontWeight: '600',
    fontSize: FontSizes.md,
  },
  infoText: {
    color: Colors.textSecondary,
    fontSize: FontSizes.sm,
  },
});
