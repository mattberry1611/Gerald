import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type MessageRole = 'user' | 'gerald';
export type AppStatus = 'idle' | 'planning' | 'awaiting' | 'executing' | 'error';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  isPlan?: boolean;
  isLoading?: boolean;
  isError?: boolean;
}

interface ConversationState {
  messages: Message[];
  status: AppStatus;
  project: string;
  baseUrl: string;
  showTextInput: boolean;

  addMessage: (msg: Omit<Message, 'id' | 'timestamp'>) => void;
  updateLastGeraldMessage: (
    content: string,
    opts?: { isPlan?: boolean; isError?: boolean }
  ) => void;
  setStatus: (status: AppStatus) => void;
  setProject: (project: string) => void;
  setBaseUrl: (url: string) => void;
  setShowTextInput: (show: boolean) => void;
  clearMessages: () => void;
  loadPersistedSettings: () => Promise<void>;
}

function makeId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

export const useConversationStore = create<ConversationState>((set) => ({
  messages: [],
  status: 'idle',
  project: '',
  baseUrl: 'http://192.168.1.100:8000',
  showTextInput: false,

  addMessage: (msg) =>
    set((state) => ({
      messages: [
        ...state.messages,
        { ...msg, id: makeId(), timestamp: new Date() },
      ],
    })),

  updateLastGeraldMessage: (content, opts = {}) =>
    set((state) => {
      const messages = [...state.messages];
      let lastIdx = -1;
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === 'gerald') {
          lastIdx = i;
          break;
        }
      }
      if (lastIdx === -1) return {};
      messages[lastIdx] = {
        ...messages[lastIdx],
        content,
        isLoading: false,
        ...opts,
      };
      return { messages };
    }),

  setStatus: (status) => set({ status }),

  setProject: (project) => {
    set({ project });
    AsyncStorage.setItem('@gerald_project', project);
  },

  setBaseUrl: (baseUrl) => {
    set({ baseUrl });
    AsyncStorage.setItem('@gerald_base_url', baseUrl);
  },

  setShowTextInput: (showTextInput) => set({ showTextInput }),

  clearMessages: () => set({ messages: [] }),

  loadPersistedSettings: async () => {
    const [project, baseUrl] = await Promise.all([
      AsyncStorage.getItem('@gerald_project'),
      AsyncStorage.getItem('@gerald_base_url'),
    ]);
    const updates: Partial<ConversationState> = {};
    if (project) updates.project = project;
    if (baseUrl) updates.baseUrl = baseUrl;
    set(updates);
  },
}));
