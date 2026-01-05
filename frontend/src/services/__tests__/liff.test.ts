import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// 【テスト目的】: LIFF SDK初期化とログイン処理の動作確認
// 【テスト内容】: initializeLiff()、getLiffProfile()、getLiffIdToken()の動作を検証
// 【期待される動作】: LIFF SDKが正しく初期化され、LINEログイン状態が管理される
// 🔵 青信号: 要件定義2.3データフロー・TASK-0012.mdに基づく

// liffモジュールのモック
vi.mock('@line/liff', () => ({
  default: {
    init: vi.fn(),
    isLoggedIn: vi.fn(),
    login: vi.fn(),
    getProfile: vi.fn(),
    getIDToken: vi.fn(),
    isInClient: vi.fn(),
  },
}));

describe('LIFF Service', () => {
  // 【テスト前準備】: 各テスト実行前にモックをリセット
  // 【環境初期化】: 前のテストの影響を排除
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('TC-002: LIFF SDK正常初期化', () => {
    it('LIFF SDKが正しいLIFF IDで初期化される', async () => {
      // 【テストデータ準備】: liffモックの設定
      // 【初期条件設定】: LIFF IDが設定され、ユーザーがログイン済みの状態
      const liff = (await import('@line/liff')).default;
      vi.mocked(liff.init).mockResolvedValue(undefined);
      vi.mocked(liff.isLoggedIn).mockReturnValue(true);

      // 【実際の処理実行】: initializeLiff()を呼び出す
      // 【処理内容】: LIFF SDKを初期化し、ログイン状態を確認
      const { initializeLiff } = await import('@/services/liff');
      await initializeLiff();

      // 【結果検証】: liff.init()が正しい引数で呼び出されたことを確認
      // 【期待値確認】: LIFF IDが正しく渡されている

      // 【検証項目】: init()が正しいLIFF IDで呼び出された
      // 🔵 青信号: LIFF SDK初期化の標準手順
      expect(liff.init).toHaveBeenCalledWith({
        liffId: expect.any(String),
      });

      // 【検証項目】: init()が1回だけ呼び出された
      // 🔵 青信号: 初期化は1回のみ実行される
      expect(liff.init).toHaveBeenCalledTimes(1);
    });
  });

  describe('TC-003: LIFF未ログイン時ログイン', () => {
    it('未ログイン時にliff.login()が呼び出される', async () => {
      // 【テストデータ準備】: 未ログイン状態のモック設定
      // 【初期条件設定】: isLoggedIn()がfalseを返す状態
      const liff = (await import('@line/liff')).default;
      vi.mocked(liff.init).mockResolvedValue(undefined);
      vi.mocked(liff.isLoggedIn).mockReturnValue(false);
      vi.mocked(liff.login).mockReturnValue(undefined);

      // 【実際の処理実行】: initializeLiff()を呼び出す
      // 【処理内容】: 未ログイン検出後にlogin()を呼び出す
      const { initializeLiff } = await import('@/services/liff');
      await initializeLiff();

      // 【結果検証】: login()が呼び出されたことを確認
      // 【期待値確認】: 未ログイン時の自動ログイン動作

      // 【検証項目】: isLoggedIn()で状態確認後、login()が呼び出された
      // 🔵 青信号: 要件定義の認証フロー仕様
      expect(liff.isLoggedIn).toHaveBeenCalled();
      expect(liff.login).toHaveBeenCalled();
    });

    it('ログイン済みの場合はliff.login()が呼び出されない', async () => {
      // 【テストデータ準備】: ログイン済み状態のモック設定
      // 【初期条件設定】: isLoggedIn()がtrueを返す状態
      const liff = (await import('@line/liff')).default;
      vi.mocked(liff.init).mockResolvedValue(undefined);
      vi.mocked(liff.isLoggedIn).mockReturnValue(true);

      // 【実際の処理実行】: initializeLiff()を呼び出す
      // 【処理内容】: ログイン済みの場合はlogin()をスキップ
      const { initializeLiff } = await import('@/services/liff');
      await initializeLiff();

      // 【結果検証】: login()が呼び出されないことを確認
      // 【期待値確認】: ログイン済みの場合の動作

      // 【検証項目】: login()が呼び出されていない
      // 🔵 青信号: 既存セッション維持の仕様
      expect(liff.login).not.toHaveBeenCalled();
    });
  });

  describe('TC-013: LIFF ID無効エラー', () => {
    it('無効なLIFF IDで初期化に失敗する', async () => {
      // 【テストデータ準備】: init()がエラーをスローするモック設定
      // 【初期条件設定】: 無効なLIFF IDが設定されている状態
      const liff = (await import('@line/liff')).default;
      vi.mocked(liff.init).mockRejectedValue(new Error('INIT_FAILED'));

      // 【実際の処理実行】: initializeLiff()がエラーをスローすることを確認
      // 【処理内容】: 無効なLIFF IDでの初期化失敗
      const { initializeLiff } = await import('@/services/liff');

      // 【結果検証】: エラーがスローされることを確認
      // 【期待値確認】: 初期化失敗時のエラーハンドリング

      // 【検証項目】: 適切なエラーがスローされる
      // 🟡 黄信号: エッジケースからの推測
      await expect(initializeLiff()).rejects.toThrow('INIT_FAILED');
    });
  });

  describe('TC-014: LINE WebView外アクセス', () => {
    it('LINE WebView外でのアクセスを検出できる', async () => {
      // 【テストデータ準備】: isInClient()がfalseを返すモック設定
      // 【初期条件設定】: 通常のWebブラウザからのアクセス
      const liff = (await import('@line/liff')).default;
      vi.mocked(liff.isInClient).mockReturnValue(false);

      // 【実際の処理実行】: isInClient()の結果を取得
      // 【処理内容】: LINE WebView内かどうかを判定
      const { isInLiffClient } = await import('@/services/liff');
      const result = isInLiffClient();

      // 【結果検証】: WebView外であることが正しく検出される
      // 【期待値確認】: 環境検出の正確性

      // 【検証項目】: isInClient()がfalseを返す
      // 🟡 黄信号: 開発環境での動作考慮
      expect(result).toBe(false);
    });
  });

  describe('getLiffProfile', () => {
    it('LINEプロファイル情報を取得できる', async () => {
      // 【テストデータ準備】: プロファイルモックデータ
      // 【初期条件設定】: ログイン済みでプロファイル取得可能な状態
      const mockProfile = {
        userId: 'U1234567890',
        displayName: 'Test User',
        pictureUrl: 'https://example.com/picture.jpg',
      };
      const liff = (await import('@line/liff')).default;
      vi.mocked(liff.getProfile).mockResolvedValue(mockProfile);

      // 【実際の処理実行】: getLiffProfile()を呼び出す
      // 【処理内容】: LINEプロファイル情報を取得
      const { getLiffProfile } = await import('@/services/liff');
      const profile = await getLiffProfile();

      // 【結果検証】: プロファイル情報が正しく取得される
      // 【期待値確認】: LINE APIからのレスポンス形式

      // 【検証項目】: プロファイルオブジェクトの内容
      // 🔵 青信号: LIFF SDK標準のプロファイル形式
      expect(profile).toEqual(mockProfile);
    });
  });

  describe('getLiffIdToken', () => {
    it('LIFF ID Tokenを取得できる', async () => {
      // 【テストデータ準備】: ID Tokenモック
      // 【初期条件設定】: ログイン済みでトークン取得可能な状態
      const mockIdToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';
      const liff = (await import('@line/liff')).default;
      vi.mocked(liff.getIDToken).mockReturnValue(mockIdToken);

      // 【実際の処理実行】: getLiffIdToken()を呼び出す
      // 【処理内容】: LIFF ID Tokenを取得
      const { getLiffIdToken } = await import('@/services/liff');
      const token = getLiffIdToken();

      // 【結果検証】: ID Tokenが正しく取得される
      // 【期待値確認】: JWT形式のトークン

      // 【検証項目】: ID Tokenの値
      // 🔵 青信号: LIFF SDK標準のトークン取得
      expect(token).toBe(mockIdToken);
    });
  });
});
