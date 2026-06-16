import axios from 'axios';

const api = axios.create({
  baseURL: 'http://192.168.1.100:8000',
  timeout: 120000,
});

export function configure(baseURL: string) {
  api.defaults.baseURL = baseURL.replace(/\/$/, '');
}

export interface Project {
  name: string;
  path: string;
}

export interface GeraldStatus {
  status: string;
  detail: string;
  updated: string;
}

export async function askGerald(
  prompt: string,
  project: string
): Promise<{ output?: string; message?: string; [key: string]: unknown }> {
  const res = await api.post('/ask', { prompt, project });
  return res.data;
}

export async function getStatus(): Promise<GeraldStatus> {
  const res = await api.get('/status', { timeout: 5000 });
  return res.data;
}

export async function getProjects(): Promise<Project[]> {
  const res = await api.get('/projects', { timeout: 5000 });
  return res.data;
}

export async function sendToClaudeCode(message?: string): Promise<unknown> {
  const res = await api.post('/send-to-claude-code', { message }, { timeout: 15000 });
  return res.data;
}

export async function rejectPlan(reason: string): Promise<unknown> {
  const res = await api.post('/reject', { reason }, { timeout: 10000 });
  return res.data;
}

export async function registerDevice(token: string): Promise<unknown> {
  const res = await api.post('/register-device', { token }, { timeout: 5000 });
  return res.data;
}
