import { describe, it, expect, vi, beforeEach } from 'vitest';

/**
 * 【テスト目的】: main.tsx でアプリ起動前に validateOidcConfig() が呼ばれることを確認
 * 【テスト内容】: validateOidcConfig が起動時に実行されること
 * 【期待される動作】: OIDC環境変数の不備を早期検出できる
 * 🔵 青信号: TASK-0029 要件に基づく
 */

describe('main.tsx', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  describe('TC-MAIN-001: 起動時のOIDC設定バリデーション', () => {
    it('アプリ起動前に validateOidcConfig が呼ばれること', async () => {
      // 【テスト準備】: validateOidcConfig をモック化
      const mockValidateOidcConfig = vi.fn();

      // 【モック設定】: oidc.ts の validateOidcConfig をモック
      vi.doMock('@/config/oidc', () => ({
        validateOidcConfig: mockValidateOidcConfig,
        oidcConfig: {
          authority: 'https://keycloak.example.com/realms/memoru',
          client_id: 'liff-client',
          redirect_uri: 'http://localhost:3000/callback',
          response_type: 'code',
          scope: 'openid profile email',
          automaticSilentRenew: true,
        },
      }));

      // 【DOM準備】: root要素を作成
      document.body.innerHTML = '<div id="root"></div>';

      // 【実際の処理実行】: main.tsx をインポート（これにより初期化コードが実行される）
      await import('../main');

      // 【結果検証】: validateOidcConfig が呼ばれたことを確認
      expect(mockValidateOidcConfig).toHaveBeenCalledTimes(1);
    });
  });

  describe('TC-MAIN-002: 環境変数不備時のエラー検出', () => {
    it('環境変数が不備の場合にエラーがスローされること', async () => {
      // 【テスト準備】: エラーをスローする validateOidcConfig をモック化
      const mockValidateOidcConfig = vi.fn(() => {
        throw new Error('環境変数 VITE_KEYCLOAK_URL が設定されていません');
      });

      // 【モック設定】: oidc.ts の validateOidcConfig をモック
      vi.doMock('@/config/oidc', () => ({
        validateOidcConfig: mockValidateOidcConfig,
        oidcConfig: {
          authority: '',
          client_id: '',
          redirect_uri: 'http://localhost:3000/callback',
          response_type: 'code',
          scope: 'openid profile email',
          automaticSilentRenew: true,
        },
      }));

      // 【DOM準備】: root要素を作成
      document.body.innerHTML = '<div id="root"></div>';

      // 【実際の処理実行】: main.tsx インポート時にエラーがスローされることを確認
      await expect(async () => {
        await import('../main');
      }).rejects.toThrow('環境変数 VITE_KEYCLOAK_URL が設定されていません');
    });
  });
});
