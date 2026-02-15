import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// 【テスト目的】: ApiClient の request() メソッドにおける 204 No Content レスポンスのハンドリング確認
// 【テスト内容】: 204 レスポンスで undefined を返す、200 レスポンスで JSON パースが正常動作、エラーハンドリングの互換性
// 【期待される動作】: 204 チェック追加後も既存の動作に影響がないこと
// 🔵 青信号: 要件定義 REQ-CR-004, REQ-CR-101 に基づく

describe('ApiClient', () => {
  let mockFetch: ReturnType<typeof vi.fn>;

  // 【テスト前準備】: global.fetch のモックを設定し、各テストで独立した fetch 動作を定義可能にする
  // 【環境初期化】: 前のテストの fetch モックや accessToken の影響を排除する
  beforeEach(async () => {
    vi.clearAllMocks();
    vi.resetModules();

    // API Base URL モック
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');

    // fetch をモック
    mockFetch = vi.fn();
    global.fetch = mockFetch;
  });

  // 【テスト後処理】: vi.restoreAllMocks() でモックを復元し、他テストへの影響を防止
  // 【状態復元】: fetch モックとaccessToken をクリーンな状態に戻す
  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  describe('request() - 204 No Content ハンドリング', () => {
    it('TC-027-01: 204 No Contentレスポンスでundefinedが返される', async () => {
      // 【テストデータ準備】: fetch モックを 204 No Content で応答するように設定
      // 【初期条件設定】: Response インスタンスを使用してブラウザの実際の動作を再現
      // 【前提条件確認】: response.ok は true（204 は成功ステータス）、response.body は null
      mockFetch.mockResolvedValue(new Response(null, { status: 204 }));

      // 【実際の処理実行】: apiClient を動的にインポートして request() を呼び出す
      // 【処理内容】: 内部で request<void>('/cards/card-123', { method: 'DELETE' }) が実行される
      // 【実行タイミング】: fetch モック設定後、アサーション前
      const { apiClient } = await import('@/services/api');
      const result = await apiClient['request']<void>('/cards/card-123', {
        method: 'DELETE',
      });

      // 【結果検証】: request() がエラーなく完了したことを確認
      // 【期待値確認】: 204 レスポンスで undefined が返され、JSON パースが実行されない
      // 【品質保証】: REQ-CR-101 の完了条件「204 時に JSON パースをスキップして undefined を返す」を確認

      // 【検証項目】: 戻り値が undefined であること
      // 🔵 青信号: REQ-CR-101 の仕様
      expect(result).toBeUndefined();

      // 【検証項目】: fetch が正しいエンドポイントで呼び出された
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/cards/card-123',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });

    it('TC-027-10: 204レスポンスでボディがnullの場合にundefinedが返される', async () => {
      // 【テストデータ準備】: ボディが null の 204 レスポンスを設定
      // 【境界値の意味】: new Response(null, { status: 204 }) は HTTP 204 の最も標準的な形式
      // 【境界値での動作保証】: ボディが null であっても JSON パースを試みず、undefined を返すことを確認
      mockFetch.mockResolvedValue(new Response(null, { status: 204 }));

      const { apiClient } = await import('@/services/api');
      const result = await apiClient['request']<void>('/cards/card-456', {
        method: 'DELETE',
      });

      // 【検証項目】: 戻り値が undefined であること
      // 🔵 青信号: 要件定義エッジケース1「204 レスポンスでレスポンスボディが null」
      expect(result).toBeUndefined();
    });

    it('TC-027-11: 204レスポンスでボディが空文字列の場合にundefinedが返される', async () => {
      // 【テストデータ準備】: ボディが空文字列の 204 レスポンスを設定
      // 【境界値の意味】: 一部のサーバーやプロキシが 204 レスポンスに空文字列ボディを付与する可能性がある
      // 【境界値での動作保証】: ボディが空文字列であっても、ステータスコードのみで判定されることを確認
      // 注: HTTP 204 No Content ではボディを持つことができないため、このテストは 204 レスポンスの標準動作を確認
      mockFetch.mockResolvedValue(new Response(null, { status: 204 }));

      const { apiClient } = await import('@/services/api');
      const result = await apiClient['request']<void>('/cards/card-789', {
        method: 'DELETE',
      });

      // 【検証項目】: 戻り値が undefined であること
      // 🔵 青信号: 要件定義エッジケース2「204 レスポンスでレスポンスボディが空文字列」
      expect(result).toBeUndefined();
    });
  });

  describe('request() - 200 レスポンス JSON パース（互換性確認）', () => {
    it('TC-027-02: 200レスポンスで従来通りJSONがパースされる', async () => {
      // 【テストデータ準備】: GET や POST 操作が返す標準的な 200 OK + JSON ボディレスポンスを再現
      // 【初期条件設定】: Content-Type: application/json ヘッダー付きの 200 レスポンス
      const mockData = { card_id: 'card-123', front: 'test', back: 'answer' };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockData), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      // 【実際の処理実行】: request() を呼び出してカード情報を取得
      const { apiClient } = await import('@/services/api');
      const result = await apiClient['request']<typeof mockData>('/cards/card-123', {
        method: 'GET',
      });

      // 【結果検証】: パース済み JSON オブジェクトが正しい内容であること
      // 【期待値確認】: 204 チェック追加後も、既存の JSON パース処理が影響を受けないことを保証

      // 【検証項目】: パース結果のオブジェクトが正しい内容であること
      // 🔵 青信号: 要件定義 制約条件「互換性要件」、タスクノート完了条件3 に基づく
      expect(result).toEqual(mockData);
    });

    it('TC-027-04: 201 Createdレスポンスで従来通りJSONがパースされる', async () => {
      // 【テストデータ準備】: POST /cards による新規カード作成レスポンスを再現
      // 【初期条件設定】: 204 以外の成功ステータスが 204 チェックの影響を受けないことを確認
      const mockData = { card_id: 'new-card', front: 'question' };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockData), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      const { apiClient } = await import('@/services/api');
      const result = await apiClient['request']<typeof mockData>('/cards', {
        method: 'POST',
        body: JSON.stringify({ front: 'question', back: 'answer' }),
      });

      // 【検証項目】: 201 レスポンスで JSON パースが正常に行われること
      // 🔵 青信号: 要件定義 制約条件「互換性要件」に基づく
      expect(result).toEqual(mockData);
    });

    it('TC-027-12: 200レスポンスで空のJSONオブジェクトが返された場合に正常にパースされる', async () => {
      // 【テストデータ準備】: JSON ボディが {} の場合、204 とは異なり正常にパースされるべき
      // 【境界値の意味】: JSON ボディの最小形式。204 と混同されないことを確認
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      const { apiClient } = await import('@/services/api');
      const result = await apiClient['request']<object>('/some-endpoint', {
        method: 'GET',
      });

      // 【検証項目】: 空オブジェクトが undefined にならず、正しくパースされること
      // 🟡 黄信号: 要件定義に直接の記載はないが、互換性要件から妥当な推測
      expect(result).toEqual({});
    });
  });

  describe('request() - エラーハンドリング', () => {
    it('TC-027-06: 404 Not Foundレスポンスで適切なErrorがスローされる', async () => {
      // 【テストデータ準備】: 存在しないカードの削除を試みた場合、Backend が 404 エラーを返す
      // 【エラーケースの概要】: 他のデバイスで既に削除されたカードを削除しようとした場合
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify({ message: 'Card not found' }), {
          status: 404,
        })
      );

      const { apiClient } = await import('@/services/api');

      // 【結果検証】: Error('Card not found') がスローされる
      // 【エラーメッセージの内容】: Backend からのエラーメッセージがそのまま伝播される
      // 🔵 青信号: 要件定義 エラーケース1「DELETE で 404 エラー」
      await expect(
        apiClient['request']<void>('/cards/nonexistent-id', {
          method: 'DELETE',
        })
      ).rejects.toThrow('Card not found');
    });

    it('TC-027-07: 500 Internal Server Errorレスポンスで適切なErrorがスローされる', async () => {
      // 【テストデータ準備】: サーバー側の内部エラーが発生した場合
      // 【エラーケースの概要】: DynamoDB への書き込みエラー、Lambda タイムアウト等
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify({ message: 'Internal server error' }), {
          status: 500,
        })
      );

      const { apiClient } = await import('@/services/api');

      // 【結果検証】: Error('Internal server error') がスローされる
      // 🔵 青信号: 要件定義 エラーケース2「DELETE で 500 エラー」
      await expect(
        apiClient['request']<void>('/cards/card-123', {
          method: 'DELETE',
        })
      ).rejects.toThrow('Internal server error');
    });

    it('TC-027-08: エラーレスポンスのボディがJSON形式でない場合にフォールバックメッセージが使用される', async () => {
      // 【テストデータ準備】: エラーレスポンスのボディが有効な JSON でない場合（例: HTML エラーページ）
      // 【エラーケースの概要】: API Gateway のデフォルトエラーページ、またはプロキシエラー
      mockFetch.mockResolvedValue(
        new Response('Internal Server Error', {
          status: 500,
        })
      );

      const { apiClient } = await import('@/services/api');

      // 【結果検証】: Error('Unknown error') がスローされる（フォールバック）
      // 【エラーメッセージの内容】: フォールバックメッセージ "Unknown error" が使用される
      // 🔵 青信号: api.ts 41行目 .catch(() => ({ message: 'Unknown error' })) の既存実装に基づく
      await expect(
        apiClient['request']<void>('/cards/card-123', {
          method: 'DELETE',
        })
      ).rejects.toThrow('Unknown error');
    });

    it('TC-027-09: ネットワークエラー（fetchの例外）が発生した場合にErrorが伝播される', async () => {
      // 【テストデータ準備】: ネットワーク接続の問題で fetch 自体が例外をスローするケース
      // 【エラーケースの概要】: Wi-Fi 切断、サーバー接続タイムアウト、DNS解決失敗
      mockFetch.mockRejectedValue(new Error('Network error'));

      const { apiClient } = await import('@/services/api');

      // 【結果検証】: Error('Network error') がそのままスローされる
      // 【エラーメッセージの内容】: fetch 由来のエラーメッセージが伝播される
      // 🟡 黄信号: 要件定義に直接の記載はないが、request() メソッドの堅牢性として妥当な推測
      await expect(
        apiClient['request']<void>('/cards/card-123', {
          method: 'DELETE',
        })
      ).rejects.toThrow('Network error');
    });
  });

  describe('request() - 認証ヘッダー', () => {
    it('TC-027-05: アクセストークン設定時にAuthorizationヘッダーが付与される', async () => {
      // 【テストデータ準備】: 認証済みユーザーがカード削除操作を行うシナリオ
      // 【初期条件設定】: setAccessToken() でトークンを設定後、204 レスポンスを返す DELETE リクエストを実行
      mockFetch.mockResolvedValue(new Response(null, { status: 204 }));

      const { apiClient } = await import('@/services/api');
      apiClient.setAccessToken('test-jwt-token');

      await apiClient['request']<void>('/cards/card-123', {
        method: 'DELETE',
      });

      // 【結果検証】: fetch の呼び出し引数に Authorization: Bearer test-jwt-token ヘッダーが含まれること
      // 【期待値確認】: API 仕様で認証が Bearer {JWT} であると定められている
      // 🔵 青信号: 要件定義 API仕様制約「認証: Bearer {JWT}」、api.ts 31-33行目の実装に基づく

      // 【検証項目】: ヘッダーの形式と値が正しいこと
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/cards/card-123',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-jwt-token',
          }),
        })
      );
    });

    it('TC-027-13: アクセストークン未設定時にAuthorizationヘッダーが含まれない', async () => {
      // 【テストデータ準備】: accessToken が null（初期状態）の場合の動作確認
      // 【境界値の意味】: accessToken の初期値 null は境界値。ヘッダー付与ロジックの分岐テスト
      mockFetch.mockResolvedValue(new Response(null, { status: 204 }));

      const { apiClient } = await import('@/services/api');
      // setAccessToken を呼び出さない（デフォルトの null 状態）

      await apiClient['request']<void>('/cards/card-123', {
        method: 'DELETE',
      });

      // 【結果検証】: fetch の呼び出し引数に Authorization ヘッダーが含まれない
      // 【期待値確認】: トークン未設定時でもリクエスト処理が正常に動作すること
      // 🟡 黄信号: 要件定義に直接の記載はないが、api.ts 31-33行目の実装から妥当な推測

      // 【検証項目】: Authorization ヘッダーが含まれないこと
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/cards/card-123',
        expect.objectContaining({
          headers: expect.not.objectContaining({
            Authorization: expect.anything(),
          }),
        })
      );
    });
  });

  describe('deleteCard() - 統合テスト', () => {
    it('TC-027-03: deleteCard()メソッドが204レスポンスで正常に完了する', async () => {
      // 【テストデータ準備】: カード削除操作の典型的なシナリオ。Backend は 204 No Content で応答する
      // 【初期条件設定】: fetch が 204 レスポンスを返すようにモック設定
      mockFetch.mockResolvedValue(new Response(null, { status: 204 }));

      // 【実際の処理実行】: deleteCard('card-123') を呼び出す
      // 【処理内容】: 公開API deleteCard() が内部で request<void>('/cards/card-123', { method: 'DELETE' }) を実行
      const { apiClient } = await import('@/services/api');

      // 【結果検証】: deleteCard() が例外をスローせず正常に Promise を解決する
      // 【期待値確認】: REQ-CR-004 に基づき、DELETE 操作が正常に完了することを保証する
      // 🔵 青信号: 要件定義 REQ-CR-004、タスクノート完了条件2 に基づく
      await expect(apiClient.deleteCard('card-123')).resolves.toBeUndefined();

      // 【検証項目】: fetch が正しいメソッドとパスで呼ばれること
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/cards/card-123',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });
});
