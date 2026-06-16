import Voice, {
  SpeechResultsEvent,
  SpeechErrorEvent,
  SpeechStartEvent,
  SpeechEndEvent,
} from '@react-native-voice/voice';

export type VoiceCallbacks = {
  onResult: (text: string) => void;
  onError: (error: string) => void;
  onStart?: () => void;
  onEnd?: () => void;
};

let isInitialized = false;

export function initVoice(callbacks: VoiceCallbacks): void {
  Voice.onSpeechStart = (_e: SpeechStartEvent) => {
    callbacks.onStart?.();
  };

  Voice.onSpeechEnd = (_e: SpeechEndEvent) => {
    callbacks.onEnd?.();
  };

  Voice.onSpeechResults = (e: SpeechResultsEvent) => {
    const text = e.value?.[0] ?? '';
    if (text.trim()) {
      callbacks.onResult(text.trim());
    } else {
      callbacks.onError('No speech detected');
    }
  };

  Voice.onSpeechError = (e: SpeechErrorEvent) => {
    const msg = e.error?.message ?? 'Speech recognition error';
    callbacks.onError(msg);
  };

  isInitialized = true;
}

export async function startListening(): Promise<void> {
  if (!isInitialized) throw new Error('Voice not initialized');
  await Voice.start('en-US');
}

export async function stopListening(): Promise<void> {
  try {
    await Voice.stop();
  } catch {
    // ignore — may already be stopped
  }
}

export async function destroyVoice(): Promise<void> {
  try {
    await Voice.destroy();
    Voice.removeAllListeners();
    isInitialized = false;
  } catch {
    // ignore
  }
}

export async function isVoiceAvailable(): Promise<boolean> {
  try {
    const available = await Voice.isAvailable();
    return !!available;
  } catch {
    return false;
  }
}
