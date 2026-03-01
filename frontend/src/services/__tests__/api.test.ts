import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { User } from '@/types';

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
    (globalThis as Record<string, unknown>).fetch = mockFetch;
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

  // ---------------------------------------------------------------------------
  // TASK-0042: API ルート統一 - パス検証
  // 対応要件: REQ-V2-001, REQ-V2-002, REQ-V2-003, REQ-V2-004
  // TDD Red フェーズ: 現在の不正なパスに対してテストが FAIL することを確認する
  // ---------------------------------------------------------------------------

  describe('TASK-0042: API ルート統一 - パス検証', () => {
    // TC-042-11: REQ-V2-004 - linkLine() パス検証
    it('TC-042-11: linkLine()が/users/link-lineにPOSTリクエストを送信する', async () => {
      // 【テスト目的】: REQ-V2-004 - linkLine() が正しいパス /users/link-line に送信することを確認
      // 【期待動作】: 修正前は /users/me/link-line を使用するため FAIL。修正後に PASS。
      // Given
      const mockUser = { user_id: 'test-user', line_user_id: 'U123' };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      // When
      const { apiClient } = await import('@/services/api');
      await apiClient.linkLine({ id_token: 'U123' });

      // Then: fetch が正しいパスに POST で呼ばれること
      // 🔵 青信号: REQ-V2-004 に基づく
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/users/link-line',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    // TC-042-12: REQ-V2-004 - linkLine() リクエストボディ検証
    it('TC-042-12: linkLine()のリクエストボディが正しくシリアライズされる', async () => {
      // 【テスト目的】: linkLine() のリクエストボディが JSON.stringify されて送信されること
      // 【期待動作】: パスの正否に関わらず body は正しくシリアライズされる（既存実装で PASS）
      // Given
      const mockUser = { user_id: 'test-user', line_user_id: 'U1234567890abcdef' };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      // When
      const { apiClient } = await import('@/services/api');
      await apiClient.linkLine({ id_token: 'U1234567890abcdef' });

      // Then: fetch の body が正しくシリアライズされていること
      // 🔵 青信号: REQ-V2-004 に基づく
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({ id_token: 'U1234567890abcdef' }),
        })
      );
    });

    // TC-042-13: REQ-V2-001 - updateUser() パス検証
    it('TC-042-13: updateUser()が/users/me/settingsにPUTリクエストを送信する', async () => {
      // 【テスト目的】: REQ-V2-001 - updateUser() が正しいパス /users/me/settings に送信することを確認
      // 【期待動作】: 修正前は /users/me を使用するため FAIL。修正後に PASS。
      // Given
      const mockUser = { user_id: 'test-user', settings: { notification_time: '21:00' } };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      // When
      const { apiClient } = await import('@/services/api');
      await apiClient.updateUser({ notification_time: '21:00' });

      // Then: fetch が /users/me/settings に PUT で呼ばれること
      // 🔵 青信号: REQ-V2-001 に基づく
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/users/me/settings',
        expect.objectContaining({
          method: 'PUT',
        })
      );
    });

    // TC-042-14: REQ-V2-002 - submitReview() パス検証
    it('TC-042-14: submitReview()が/reviews/{cardId}にPOSTリクエストを送信する', async () => {
      // 【テスト目的】: REQ-V2-002 - submitReview() が正しいパス /reviews/{cardId} に送信することを確認
      // 【期待動作】: 現在のフロントエンド実装は既に /reviews/${cardId} を使用しているため PASS（回帰テスト）
      // Given
      const mockResponse = { success: true };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      // When
      const { apiClient } = await import('@/services/api');
      await apiClient.submitReview('card-abc-123', 4);

      // Then: fetch が /reviews/card-abc-123 に POST で呼ばれ、body が正しいこと
      // 🔵 青信号: REQ-V2-002 に基づく
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/reviews/card-abc-123',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ grade: 4 }),
        })
      );
    });

    // TC-042-15: REQ-V2-001 - updateUser() リクエストボディ検証
    it('TC-042-15: updateUser()のリクエストボディが正しくシリアライズされる', async () => {
      // 【テスト目的】: updateUser() のリクエストボディが正しく JSON シリアライズされること
      // 【期待動作】: パスの正否に関わらず body は正しくシリアライズされる（既存実装で PASS）
      // Given
      const mockUser = { user_id: 'test-user' };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      // When
      const requestData = { notification_time: '18:00', timezone: 'America/New_York' };
      const { apiClient } = await import('@/services/api');
      await apiClient.updateUser(requestData);

      // Then: fetch の body が正しくシリアライズされていること
      // 🔵 青信号: REQ-V2-001 に基づく
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify(requestData),
        })
      );
    });

    // TC-042-16: REQ-V2-004 - linkLine() レスポンス型検証
    it('TC-042-16: linkLine()のレスポンスがUser型として返却される', async () => {
      // 【テスト目的】: linkLine() のレスポンスが User 型として正しく返却されること
      // 【期待動作】: パスが正しければレスポンスが User 型で返る（修正後に PASS）
      // Given
      const mockUser = {
        user_id: 'test-user',
        line_user_id: 'U123',
        settings: { notification_time: '09:00', timezone: 'Asia/Tokyo' },
        created_at: '2026-01-01T00:00:00Z',
      };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      // When
      const { apiClient } = await import('@/services/api');
      const result = await apiClient.linkLine({ id_token: 'U123' });

      // Then: 戻り値が User 型のオブジェクトであること
      // 🔵 青信号: REQ-V2-004 に基づく
      expect(result).toEqual(mockUser);
      expect(result.user_id).toBe('test-user');
    });

    // TC-042-35: REQ-V2-004 - 旧パス /users/me/link-line が使用されていないこと
    it('TC-042-35: linkLine()が旧パス/users/me/link-lineを使用していないこと', async () => {
      // 【テスト目的】: REQ-V2-004 - linkLine() が旧パス /users/me/link-line を使用していないことを確認
      // 【期待動作】: 修正前は /users/me/link-line を使用するため FAIL。修正後に PASS。
      // Given
      const mockUser = { user_id: 'test-user', line_user_id: 'U123' };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      // When
      const { apiClient } = await import('@/services/api');
      await apiClient.linkLine({ id_token: 'U123' });

      // Then: 旧パスが使用されておらず、新パスが使用されていること
      // 🔵 青信号: REQ-V2-004 に基づく
      const fetchUrl = mockFetch.mock.calls[0][0] as string;
      expect(fetchUrl).not.toContain('/users/me/link-line');
      expect(fetchUrl).toContain('/users/link-line');
    });

    // TC-042-36: REQ-V2-001 - 旧パス PUT /users/me が使用されていないこと
    it('TC-042-36: updateUser()が/users/me/settingsを使用し旧パス/users/meのみでないこと', async () => {
      // 【テスト目的】: REQ-V2-001 - updateUser() が旧パス /users/me のみでなく
      //   /users/me/settings を使用することを確認
      // 【期待動作】: 修正前は /users/me で FAIL。修正後に PASS。
      // Given
      const mockUser = { user_id: 'test-user' };
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      // When
      const { apiClient } = await import('@/services/api');
      await apiClient.updateUser({ notification_time: '10:00' });

      // Then: URL が /users/me/settings であること（/users/me のみではない）
      // 🔵 青信号: REQ-V2-001 に基づく
      const fetchUrl = mockFetch.mock.calls[0][0] as string;
      expect(fetchUrl).toBe('https://api.example.com/users/me/settings');
    });
  });

  describe('request() - 401 Unauthorized トークンリフレッシュ', () => {
    it('TC-037-01: 401レスポンスでトークンリフレッシュが呼ばれる', async () => {
      // 【テストデータ準備】: アクセストークンが期限切れの場合、401 Unauthorized が返される
      // 【初期条件設定】: 1回目のリクエストで 401、リフレッシュ後の2回目で 200 を返す
      // 【テスト目的】: REQ-CR-007「401エラー時にトークンリフレッシュを試行」を確認
      const mockData = { card_id: 'card-123', front: 'test' };
      mockFetch
        .mockResolvedValueOnce(new Response(null, { status: 401 }))
        .mockResolvedValueOnce(
          new Response(JSON.stringify(mockData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        );

      // authService.refreshToken のモック
      const mockRefreshToken = vi.fn().mockResolvedValue(undefined);
      const { authService } = await import('@/services/auth');
      vi.spyOn(authService, 'refreshToken').mockImplementation(mockRefreshToken);

      const { apiClient } = await import('@/services/api');
      apiClient.setAccessToken('expired-token');

      // 【実際の処理実行】: 401 レスポンスが返される request を実行
      const result = await apiClient['request']<typeof mockData>('/cards/card-123', {
        method: 'GET',
      });

      // 【結果検証】: refreshToken が1回呼ばれ、リトライで成功すること
      // 🟡 黄信号: TASK-0037 に基づく
      expect(mockRefreshToken).toHaveBeenCalledTimes(1);
      expect(result).toEqual(mockData);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('TC-037-02: リフレッシュ成功後にリトライが行われる', async () => {
      // 【テストデータ準備】: トークンリフレッシュ後に元のリクエストが再実行される
      // 【初期条件設定】: 1回目 401、2回目 200 で成功
      // 【テスト目的】: REQ-CR-102「リフレッシュ成功後に元のリクエストを再実行」を確認
      const mockData = { cards: [{ card_id: 'card-1', front: 'Q1' }] };
      mockFetch
        .mockResolvedValueOnce(new Response(null, { status: 401 }))
        .mockResolvedValueOnce(
          new Response(JSON.stringify(mockData), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        );

      const mockRefreshToken = vi.fn().mockResolvedValue(undefined);
      const { authService } = await import('@/services/auth');
      vi.spyOn(authService, 'refreshToken').mockImplementation(mockRefreshToken);

      const { apiClient } = await import('@/services/api');
      apiClient.setAccessToken('expired-token');

      // 【実際の処理実行】: getCards() を呼び出し
      const result = await apiClient.getCards();

      // 【結果検証】: リトライ後に正常なレスポンスが返される
      // 🟡 黄信号: TASK-0037 に基づく
      expect(result).toEqual(mockData.cards);
      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(mockRefreshToken).toHaveBeenCalledTimes(1);
    });

    it('TC-037-03: 並行リクエストでリフレッシュが1回のみ実行される', async () => {
      // 【テストデータ準備】: 複数の並行リクエストが同時に 401 を受け取る
      // 【初期条件設定】: 両リクエストとも 1回目 401、2回目 200
      // 【テスト目的】: EDGE-CR-003「並行リクエスト時にリフレッシュを1回に制限」を確認
      const mockData1 = { card_id: 'card-1', front: 'Q1' };
      const mockData2 = { card_id: 'card-2', front: 'Q2' };

      mockFetch
        .mockResolvedValueOnce(new Response(null, { status: 401 }))
        .mockResolvedValueOnce(new Response(null, { status: 401 }))
        .mockResolvedValueOnce(
          new Response(JSON.stringify(mockData1), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify(mockData2), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        );

      const mockRefreshToken = vi.fn().mockResolvedValue(undefined);
      const { authService } = await import('@/services/auth');
      vi.spyOn(authService, 'refreshToken').mockImplementation(mockRefreshToken);

      const { apiClient } = await import('@/services/api');
      apiClient.setAccessToken('expired-token');

      // 【実際の処理実行】: 並行して2つのリクエストを実行
      const [result1, result2] = await Promise.all([
        apiClient['request']<typeof mockData1>('/cards/card-1', { method: 'GET' }),
        apiClient['request']<typeof mockData2>('/cards/card-2', { method: 'GET' }),
      ]);

      // 【結果検証】: refreshToken が1回のみ呼ばれ、両リクエストが成功すること
      // 🟡 黄信号: EDGE-CR-003 に基づく
      expect(mockRefreshToken).toHaveBeenCalledTimes(1);
      expect(result1).toEqual(mockData1);
      expect(result2).toEqual(mockData2);
      expect(mockFetch).toHaveBeenCalledTimes(4); // 401 x2 + 200 x2
    });

    it('TC-037-04: リフレッシュ失敗時にlogin()が呼ばれる', async () => {
      // 【テストデータ準備】: トークンリフレッシュが失敗する（リフレッシュトークンも期限切れ）
      // 【初期条件設定】: 401 レスポンス、refreshToken() が失敗
      // 【テスト目的】: REQ-CR-103「リフレッシュ失敗時にログイン画面にリダイレクト」を確認
      mockFetch.mockResolvedValue(new Response(null, { status: 401 }));

      const mockRefreshToken = vi.fn().mockRejectedValue(new Error('Refresh token expired'));
      const mockLogin = vi.fn().mockResolvedValue(undefined);
      const { authService } = await import('@/services/auth');
      vi.spyOn(authService, 'refreshToken').mockImplementation(mockRefreshToken);
      vi.spyOn(authService, 'login').mockImplementation(mockLogin);

      const { apiClient } = await import('@/services/api');
      apiClient.setAccessToken('expired-token');

      // 【実際の処理実行】: 401 レスポンスが返されリフレッシュが失敗
      await expect(
        apiClient['request']<void>('/cards/card-123', { method: 'GET' })
      ).rejects.toThrow();

      // 【結果検証】: login() が呼ばれること
      // 🟡 黄信号: TASK-0037 に基づく
      expect(mockRefreshToken).toHaveBeenCalledTimes(1);
      expect(mockLogin).toHaveBeenCalledTimes(1);
    });

    it('TC-037-06: リトライ後も401の場合はlogin()が呼ばれエラーがスローされる', async () => {
      // 【テストデータ準備】: トークンリフレッシュは成功するが、リトライ後のリクエストも 401 を返す
      // 【初期条件設定】: 1回目 401 → リフレッシュ成功 → 2回目 401
      // 【テスト目的】: REQ-014「リトライを1回に制限し、無限再帰を防止」を確認
      mockFetch
        .mockResolvedValueOnce(new Response(null, { status: 401 }))
        .mockResolvedValueOnce(new Response(null, { status: 401 }));

      const mockRefreshToken = vi.fn().mockResolvedValue(undefined);
      const mockLogin = vi.fn().mockResolvedValue(undefined);
      const { authService } = await import('@/services/auth');
      vi.spyOn(authService, 'refreshToken').mockImplementation(mockRefreshToken);
      vi.spyOn(authService, 'login').mockImplementation(mockLogin);

      const { apiClient } = await import('@/services/api');
      apiClient.setAccessToken('expired-token');

      // 【実際の処理実行】: リトライ後も 401 が返される
      await expect(
        apiClient['request']<void>('/cards/card-123', { method: 'GET' })
      ).rejects.toThrow('Session expired');

      // 【結果検証】: リフレッシュは1回、login() が呼ばれ、fetch は2回（再帰は1回のみ）
      // 🔵 青信号: REQ-014 に基づく
      expect(mockRefreshToken).toHaveBeenCalledTimes(1);
      expect(mockLogin).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledTimes(2); // 初回 + リトライ1回のみ
    });

    it('TC-037-05: 401以外のエラーではリフレッシュが呼ばれない', async () => {
      // 【テストデータ準備】: 404 Not Found など、401以外のエラーレスポンス
      // 【初期条件設定】: 404 エラーレスポンスを返す
      // 【テスト目的】: 401以外のエラーでは通常のエラーハンドリングが行われることを確認
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify({ message: 'Not found' }), {
          status: 404,
        })
      );

      const mockRefreshToken = vi.fn();
      const { authService } = await import('@/services/auth');
      vi.spyOn(authService, 'refreshToken').mockImplementation(mockRefreshToken);

      const { apiClient } = await import('@/services/api');
      apiClient.setAccessToken('valid-token');

      // 【実際の処理実行】: 404 エラーが返される
      await expect(
        apiClient['request']<void>('/cards/nonexistent', { method: 'GET' })
      ).rejects.toThrow('Not found');

      // 【結果検証】: refreshToken が呼ばれないこと
      // 🟡 黄信号: 既存のエラーハンドリングとの互換性確認
      expect(mockRefreshToken).not.toHaveBeenCalled();
    });
  });

  // ---------------------------------------------------------------------------
  // TASK-0045: レスポンスDTO統一 + unlinkLine API使用
  // TC-07: unlinkLine API メソッドが POST /users/me/unlink-line を呼び出す
  // TC-10: linkLine レスポンスが User 型として正しくパースされる
  // 対応要件: EARS-045-011~014, EARS-045-010, EARS-045-026
  // TDD RED フェーズ: unlinkLine メソッドが api.ts に存在しないため FAIL することを確認する
  // ---------------------------------------------------------------------------

  describe('TC-07: unlinkLine API メソッド', () => {
    it('TC-07-01: unlinkLine が POST /users/me/unlink-line を呼び出すこと', async () => {
      /**
       * 【テスト目的】: unlinkLine メソッドが正しいエンドポイントと HTTP メソッドを使用することを検証
       * 【期待される動作】: POST /users/me/unlink-line が呼ばれ、リクエストボディがない
       * 青 信頼性レベル: EARS-045-011, EARS-045-013, EARS-045-014
       *
       * RED フェーズ失敗理由:
       *   api.ts の ApiClient クラスに unlinkLine メソッドが存在しないため、
       *   apiClient.unlinkLine() 呼び出し時に TypeError が発生する。
       */
      const mockResponse: User = {
        user_id: 'test-user-id',
        display_name: 'テストユーザー',
        picture_url: null,
        line_linked: false,
        notification_time: '09:00',
        timezone: 'Asia/Tokyo',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      const { apiClient } = await import('@/services/api');
      apiClient.setAccessToken('test-token');

      // unlinkLine メソッドが存在し呼び出せること (存在しない場合は TypeError)
      const result = await (apiClient as unknown as { unlinkLine: () => Promise<User> }).unlinkLine();

      // fetch が正しいエンドポイントで呼ばれたか
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me/unlink-line'),
        expect.objectContaining({
          method: 'POST',
        })
      );

      // リクエストボディがないこと
      const fetchCall = mockFetch.mock.calls[0][1] as RequestInit;
      expect(fetchCall.body).toBeUndefined();

      // Authorization ヘッダーが含まれること
      expect(fetchCall.headers).toHaveProperty('Authorization', 'Bearer test-token');

      // 戻り値が User 型であること
      expect(result).toEqual(mockResponse);
      expect(result.line_linked).toBe(false);
    });

    it('TC-07-02: usersApi.unlinkLine が apiClient.unlinkLine に委譲すること', async () => {
      /**
       * 【テスト目的】: usersApi エクスポートに unlinkLine が含まれることを検証
       * 青 信頼性レベル: EARS-045-012
       *
       * RED フェーズ失敗理由:
       *   usersApi オブジェクトに unlinkLine プロパティが存在しないため FAIL する。
       */
      const { usersApi } = await import('@/services/api');

      expect(usersApi).toHaveProperty('unlinkLine');
      expect(typeof (usersApi as unknown as Record<string, unknown>).unlinkLine).toBe('function');
    });
  });

  describe('TC-10: linkLine レスポンスの User 型パース', () => {
    it('TC-10-01: linkLine が User 型のレスポンスを返すこと', async () => {
      /**
       * 【テスト目的】: linkLine の戻り値が User 型として正しくパースされることを検証
       * 【期待される動作】: レスポンスが User 型の全フィールドを持つ
       * 青 信頼性レベル: EARS-045-010
       *
       * 注意: バックエンドのレスポンス形式変更 ({success, data} ラッパー) に応じて
       *       フロントエンド側のパース処理を調整する必要がある (EARS-045-026 黄)
       *
       * RED フェーズ状態:
       *   現在の linkLine は直接 User フィールドを含むオブジェクトを返す想定。
       *   timezone フィールドが含まれていることを検証する。
       *   バックエンドが {success, data: User} ラッパーで返す場合は GREEN フェーズで調整。
       */
      const mockServerResponse: User = {
        user_id: 'test-user-id',
        display_name: 'テストユーザー',
        picture_url: null,
        line_linked: true,
        notification_time: '09:00',
        timezone: 'Asia/Tokyo',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      mockFetch.mockResolvedValue(
        new Response(JSON.stringify(mockServerResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );

      const { apiClient } = await import('@/services/api');
      apiClient.setAccessToken('test-token');
      const result = await apiClient.linkLine({ id_token: 'valid-token' });

      // User 型の全フィールドが存在すること
      expect(result).toHaveProperty('user_id');
      expect(result).toHaveProperty('line_linked');
      expect(result).toHaveProperty('timezone');
      expect(result).toHaveProperty('notification_time');
      expect(result).toHaveProperty('created_at');
      expect(result).toHaveProperty('updated_at');

      // 値の検証
      expect(result.line_linked).toBe(true);
      expect(result.timezone).toBe('Asia/Tokyo');
      expect(typeof result.user_id).toBe('string');
    });
  });
});
