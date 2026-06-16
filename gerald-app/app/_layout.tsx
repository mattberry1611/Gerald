import React, { useEffect } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { MD3DarkTheme, PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Colors } from '../constants/theme';
import {
  requestPermissionsAndRegister,
  addNotificationResponseListener,
} from '../services/notifications';
import { useConversationStore } from '../store/conversationStore';

const paperTheme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    background: Colors.background,
    surface: Colors.surface,
    primary: Colors.accent,
    onPrimary: Colors.background,
    secondary: Colors.statusAwaiting,
    error: Colors.error,
  },
};

export default function RootLayout() {
  const { baseUrl, loadPersistedSettings } = useConversationStore();

  useEffect(() => {
    loadPersistedSettings().then(() => {
      requestPermissionsAndRegister(baseUrl);
    });

    const sub = addNotificationResponseListener((_response) => {
      // Notification tapped — app is already open; conversation is visible
    });

    return () => sub.remove();
  }, []);

  return (
    <SafeAreaProvider>
      <PaperProvider theme={paperTheme}>
        <StatusBar style="light" backgroundColor={Colors.background} />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: Colors.background },
            animation: 'slide_from_right',
          }}
        >
          <Stack.Screen name="index" />
          <Stack.Screen name="settings" />
        </Stack>
      </PaperProvider>
    </SafeAreaProvider>
  );
}
