import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  Text,
  Image,
  TouchableOpacity,
  PermissionsAndroid,
  Platform,
  Alert,
  Keyboard,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import * as Haptics from 'expo-haptics';
import {
  useConversationStore,
  AppStatus,
  Message,
} from '../store/conversationStore';
import MessageBubble from '../components/MessageBubble';
import PushToTalkButton, { PTTState } from '../components/PushToTalkButton';
import TextInputBar from '../components/TextInputBar';
import ProjectSelectorModal from '../components/ProjectSelectorModal';
import StatusIndicator from '../components/StatusIndicator';
import { Colors, FontSizes, Spacing } from '../constants/theme';
import * as geraldApi from '../services/geraldApi';
import {
  initVoice,
  startListening,
  stopListening,
  destroyVoice,
} from '../services/voice';

function mapBackendStatus(s: string): AppStatus {
  switch (s) {
    case 'working': return 'executing';
    case 'done': return 'idle';
    case 'error': return 'error';
    default: return 'idle';
  }
}

function detectIsPlan(text: string): boolean {
  const lower = text.toLowerCase();
  return (
    lower.includes('approve') ||
    lower.includes('shall i proceed') ||
    lower.includes("here is my plan") ||
    lower.includes("here's my plan") ||
    lower.includes('plan:') ||
    lower.includes('implementation plan')
  );
}

export default function ConversationScreen() {
  const {
    messages,
    status,
    project,
    baseUrl,
    showTextInput,
    addMessage,
    updateLastGeraldMessage,
    setStatus,
    setShowTextInput,
    loadPersistedSettings,
  } = useConversationStore();

  const flatListRef = useRef<FlatList<Message>>(null);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [pttState, setPttState] = useState<PTTState>('idle');
  const statusPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isSendingRef = useRef(false);

  // Keep a stable ref to sendPrompt so voice callbacks don't go stale
  const sendPromptRef = useRef<((text: string) => Promise<void>) | null>(null);

  // Load persisted settings on mount
  useEffect(() => {
    loadPersistedSettings();
  }, []);

  // Show welcome message on first load
  useEffect(() => {
    if (messages.length === 0) {
      addMessage({
        role: 'gerald',
        content:
          "Hello! I'm Gerald, your coding supervisor. Hold the button to give me a task by voice, or tap ⌨ to type.",
      });
    }
  }, []);

  // Initialize voice recognition once (stable callbacks via ref)
  useEffect(() => {
    initVoice({
      onResult: async (text: string) => {
        setPttState('processing');
        await sendPromptRef.current?.(text);
        setPttState('idle');
      },
      onError: (_error: string) => {
        setPttState('idle');
        Alert.alert('Voice', "Didn't catch that — try again");
      },
      onEnd: () => {
        setPttState((prev) => (prev === 'recording' ? 'idle' : prev));
      },
    });

    return () => { destroyVoice(); };
  }, []);

  // Poll Gerald status every 3 seconds
  useEffect(() => {
    statusPollRef.current = setInterval(async () => {
      try {
        const { baseUrl: url } = useConversationStore.getState();
        geraldApi.configure(url);
        const data = await geraldApi.getStatus();
        if (data?.status) setStatus(mapBackendStatus(data.status));
      } catch {
        // Silent — backend may not be reachable yet
      }
    }, 3000);

    return () => {
      if (statusPollRef.current) clearInterval(statusPollRef.current);
    };
  }, []);

  async function requestMicPermission(): Promise<boolean> {
    if (Platform.OS !== 'android') return true;
    try {
      const granted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
        {
          title: 'Microphone Permission',
          message: 'Gerald needs microphone access for push-to-talk.',
          buttonPositive: 'Allow',
        }
      );
      return granted === PermissionsAndroid.RESULTS.GRANTED;
    } catch {
      return false;
    }
  }

  async function handlePTTPressIn() {
    if (isSendingRef.current || pttState !== 'idle') return;
    const hasPermission = await requestMicPermission();
    if (!hasPermission) {
      Alert.alert('Permission Required', 'Microphone access is needed for push-to-talk.');
      return;
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    Keyboard.dismiss();
    setPttState('recording');
    try {
      await startListening();
    } catch {
      setPttState('idle');
      Alert.alert('Voice Error', 'Could not start voice recognition. Try the keyboard instead.');
    }
  }

  async function handlePTTPressOut() {
    if (pttState !== 'recording') return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    try {
      await stopListening();
    } catch {
      // ignore — voice may already have stopped
    }
  }

  // Read project/baseUrl from store at call-time to avoid stale closures
  const sendPrompt = useCallback(async (text: string) => {
    if (!text.trim() || isSendingRef.current) return;
    isSendingRef.current = true;

    const { project: currentProject, baseUrl: currentUrl } =
      useConversationStore.getState();
    geraldApi.configure(currentUrl);

    addMessage({ role: 'user', content: text.trim() });
    addMessage({ role: 'gerald', content: '...', isLoading: true });

    scrollToBottom();

    try {
      setStatus('planning');
      const data = await geraldApi.askGerald(text.trim(), currentProject);
      const response =
        (data as { output?: string }).output ||
        (data as { message?: string }).message ||
        JSON.stringify(data);
      const isPlan = detectIsPlan(response);
      updateLastGeraldMessage(response, { isPlan });
      setStatus(isPlan ? 'awaiting' : 'idle');
    } catch {
      updateLastGeraldMessage(
        'Error connecting to Gerald. Check that the backend is running and verify the URL in Settings.',
        { isError: true }
      );
      setStatus('error');
    } finally {
      isSendingRef.current = false;
      scrollToBottom();
    }
  }, []); // Empty deps: project/baseUrl read from store directly at call-time

  // Keep ref current so voice callback always calls the latest version
  sendPromptRef.current = sendPrompt;

  function scrollToBottom() {
    setTimeout(() => {
      flatListRef.current?.scrollToEnd({ animated: true });
    }, 80);
  }

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLogoSection}>
          <Image
            source={require('../assets/gerald_logo.png')}
            style={styles.headerLogo}
            resizeMode="contain"
          />
          <Text style={styles.headerTitle}>Gerald</Text>
        </View>

        <TouchableOpacity
          onPress={() => setShowProjectModal(true)}
          style={styles.projectButton}
          activeOpacity={0.7}
        >
          <Text style={styles.projectName} numberOfLines={1}>
            {project || 'No project ▾'}
          </Text>
        </TouchableOpacity>

        <View style={styles.headerRight}>
          <StatusIndicator status={status} />
          <TouchableOpacity
            onPress={() => router.push('/settings')}
            style={styles.settingsButton}
          >
            <Text style={styles.settingsIcon}>⚙</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Message list */}
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <MessageBubble message={item} />}
        style={styles.messageList}
        contentContainerStyle={styles.messageListContent}
        onContentSizeChange={scrollToBottom}
        showsVerticalScrollIndicator={false}
      />

      {/* Text input (toggled by keyboard icon) */}
      {showTextInput && (
        <TextInputBar
          onSend={(text) => {
            setShowTextInput(false);
            sendPrompt(text);
          }}
          disabled={isSendingRef.current || pttState !== 'idle'}
        />
      )}

      {/* Bottom bar */}
      <View style={styles.bottomBar}>
        <TouchableOpacity
          onPress={() => {
            setShowTextInput(!showTextInput);
            if (!showTextInput) Keyboard.dismiss();
          }}
          style={styles.iconButton}
          activeOpacity={0.7}
        >
          <Text style={[styles.iconText, showTextInput && styles.iconTextActive]}>
            ⌨
          </Text>
        </TouchableOpacity>

        <PushToTalkButton
          state={pttState}
          onPressIn={handlePTTPressIn}
          onPressOut={handlePTTPressOut}
        />

        {/* Spacer to balance layout */}
        <View style={styles.iconButton} />
      </View>

      <ProjectSelectorModal
        visible={showProjectModal}
        onClose={() => setShowProjectModal(false)}
      />
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
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  headerLogoSection: {
    flexDirection: 'row',
    alignItems: 'center',
    width: 90,
    gap: Spacing.xs,
  },
  headerLogo: {
    width: 22,
    height: 22,
  },
  headerTitle: {
    color: Colors.accent,
    fontSize: FontSizes.lg,
    fontWeight: '800',
    letterSpacing: 1,
  },
  projectButton: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: Spacing.sm,
  },
  projectName: {
    color: Colors.textSecondary,
    fontSize: FontSizes.sm,
    textDecorationLine: 'underline',
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    width: 70,
    justifyContent: 'flex-end',
    gap: Spacing.xs,
  },
  settingsButton: {
    padding: Spacing.xs,
  },
  settingsIcon: {
    color: Colors.textSecondary,
    fontSize: FontSizes.lg,
  },
  messageList: {
    flex: 1,
  },
  messageListContent: {
    paddingVertical: Spacing.md,
    flexGrow: 1,
  },
  bottomBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.lg,
    paddingBottom: Spacing.xl,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  iconButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconText: {
    color: Colors.textSecondary,
    fontSize: 22,
  },
  iconTextActive: {
    color: Colors.accent,
  },
});
