import '@testing-library/jest-dom';
import { vi } from 'vitest';

// 【テスト環境初期化】: グローバルなモックとセットアップを定義
// 【目的】: 一貫したテスト環境を提供し、外部依存をモック化

// localStorage モック
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// location モック
Object.defineProperty(window, 'location', {
  value: {
    origin: 'http://localhost:3000',
    href: 'http://localhost:3000',
    pathname: '/',
    search: '',
    hash: '',
    assign: vi.fn(),
    replace: vi.fn(),
    reload: vi.fn(),
  },
  writable: true,
});

// 環境変数モック
vi.stubEnv('VITE_KEYCLOAK_URL', 'https://keycloak.example.com');
vi.stubEnv('VITE_KEYCLOAK_REALM', 'memoru');
vi.stubEnv('VITE_KEYCLOAK_CLIENT_ID', 'memoru-liff');
vi.stubEnv('VITE_LIFF_ID', '1234567890-abcdefgh');
