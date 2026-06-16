export const Colors = {
  background: '#0d0d0d',
  surface: '#1a1a1a',
  surfaceElevated: '#242424',
  userBubble: '#1e3a5f',
  geraldBubble: '#0f2b1a',
  accent: '#00c896',
  error: '#c0392b',
  approve: '#27ae60',
  reject: '#c0392b',
  textPrimary: '#f0f0f0',
  textSecondary: '#888888',
  textMuted: '#555555',
  border: '#2a2a2a',
  codeBg: '#141414',
  statusIdle: '#666666',
  statusPlanning: '#f39c12',
  statusAwaiting: '#3498db',
  statusExecuting: '#00c896',
  statusError: '#c0392b',
} as const;

export const FontSizes = {
  xs: 11,
  sm: 13,
  md: 15,
  lg: 17,
  xl: 20,
  mono: 12,
} as const;

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const Radii = {
  sm: 6,
  md: 12,
  lg: 18,
  full: 9999,
} as const;
