/**
 * 【テスト概要】: LinkLinePage の ID トークン送信テスト
 * 【テスト対象】: LinkLinePage コンポーネント - ID トークン検証フロー (TASK-0044)
 * 【テスト対応】: TC-14, TC-15, TC-16
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { LinkLinePage } from '../LinkLinePage';
import type { User } from '@/types';

// 【テスト前準備】: Navigation コンポーネントをモック
vi.mock('@/components/Navigation', () => ({
  Navigation: () => <nav data-testid="navigation">Navigation</nav>,
}));

// 【テスト前準備】: usersApi のモックを設定
// - getCurrentUser: ユーザー情報の取得
// - updateUser: ユーザー設定の更新
// - linkLine: LINE 連携の実行（id_token を受け取る）
const mockGetCurrentUser = vi.fn();
const mockUpdateUser = vi.fn();
const mockLinkLine = vi.fn();

vi.mock('@/services/api', () => ({
  usersApi: {
    getCurrentUser: () => mockGetCurrentUser(),
    updateUser: (...args: unknown[]) => mockUpdateUser(...args),
    linkLine: (...args: unknown[]) => mockLinkLine(...args),
  },
}));

// 【テスト前準備】: liff サービスのモックを設定
// TC-14〜TC-16 では getLiffIdToken が追加で必要
const mockInitializeLiff = vi.fn();
const mockGetLiffProfile = vi.fn();
const mockIsInLiffClient = vi.fn();
const mockGetLiffIdToken = vi.fn();  // 【重要】: TC-14〜16 で使用する新しいモック

vi.mock('@/services/liff', () => ({
  initializeLiff: () => mockInitializeLiff(),
  getLiffProfile: () => mockGetLiffProfile(),
  isInLiffClient: () => mockIsInLiffClient(),
  getLiffIdToken: () => mockGetLiffIdToken(),  // 新しい関数: TASK-0044 で追加予定
}));

// 【テスト前準備】: useNavigate のモックを設定
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// 【テストデータ準備】: 未連携ユーザーのモックデータ
const mockUnlinkedUser: User = {
  user_id: 'user-1',
  display_name: 'Test User',
  picture_url: null,
  line_linked: false,
  notification_time: '09:00',
  timezone: 'Asia/Tokyo',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

// 【テストデータ準備】: 連携済みユーザーのモックデータ
const mockLinkedUser: User = {
  ...mockUnlinkedUser,
  line_linked: true,
};

// 【テストヘルパー】: LinkLinePage をレンダリングするユーティリティ関数
const renderLinkLinePage = () => {
  return render(
    <MemoryRouter>
      <LinkLinePage />
    </MemoryRouter>
  );
};

describe('LinkLinePage - ID Token Tests (TASK-0044)', () => {
  // 【テスト前準備】: 各テスト実行前にモックをリセットし、デフォルト値を設定
  beforeEach(() => {
    vi.clearAllMocks();
    // デフォルト: 未連携ユーザー
    mockGetCurrentUser.mockResolvedValue(mockUnlinkedUser);
    mockLinkLine.mockResolvedValue(mockLinkedUser);
    mockInitializeLiff.mockResolvedValue(undefined);
    mockIsInLiffClient.mockReturnValue(true);
    // TC-14〜16: getLiffIdToken が有効なトークンを返すデフォルト設定
    mockGetLiffIdToken.mockReturnValue('test-liff-id-token-xyz');
  });

  it('TC-14: LINE連携ボタン押下時に id_token フィールドで API が呼ばれる', async () => {
    /**
     * 【テスト目的】: フロントエンドが liff.getIDToken() を使用し、
     *               id_token フィールドで linkLine API を呼ぶことを検証する
     * 【テスト内容】:
     *   1. mockGetLiffIdToken が有効なトークンを返すよう設定済み
     *   2. LinkLinePage をレンダリング
     *   3. 連携ボタンをクリック
     *   4. mockLinkLine が { id_token: "test-liff-id-token-xyz" } で呼ばれることを確認
     * 【期待される動作】: linkLine が id_token フィールドで呼ばれる
     * 🔵 信頼性レベル: 青信号 - REQ-V2-021 のフロントエンド送信要件に基づく
     */

    // 【テストデータ準備】: userEvent を初期化
    const user = userEvent.setup();

    // 【実際の処理実行】: ページをレンダリングしてボタンをクリック
    renderLinkLinePage();

    // 連携ボタンが表示されるまで待機
    await waitFor(() => {
      expect(screen.getByTestId('link-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('link-button'));

    // 【結果検証】: linkLine が id_token フィールドで呼ばれることを確認
    await waitFor(() => {
      expect(mockLinkLine).toHaveBeenCalledWith({
        id_token: 'test-liff-id-token-xyz',  // 【確認内容】: id_token フィールドが使用されている 🔵
      });
    });
  });

  it('TC-15: IDトークン取得失敗時（null）にエラーメッセージが表示される', async () => {
    /**
     * 【テスト目的】: liff.getIDToken() が null を返した場合に
     *               エラーメッセージが表示され、API が呼ばれないことを検証する
     * 【テスト内容】:
     *   1. mockGetLiffIdToken が null を返すよう設定
     *   2. 連携ボタンをクリック
     *   3. エラーメッセージが表示されることを確認
     *   4. linkLine API が呼ばれていないことを確認
     * 【期待される動作】: エラーメッセージが表示される
     * 🟡 信頼性レベル: 黄信号 - エラーメッセージの文言は設計文書に明確な定義なし
     */

    // 【初期条件設定】: getLiffIdToken が null を返すよう設定
    mockGetLiffIdToken.mockReturnValue(null);

    const user = userEvent.setup();

    // 【実際の処理実行】: ページをレンダリングしてボタンをクリック
    renderLinkLinePage();

    await waitFor(() => {
      expect(screen.getByTestId('link-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('link-button'));

    // 【結果検証】: エラーメッセージが表示されることを確認
    await waitFor(() => {
      const errorMessage = screen.getByTestId('error-message');
      expect(errorMessage).toBeInTheDocument();  // 【確認内容】: エラーメッセージ要素が存在する 🟡
      // エラーメッセージが何らかのテキストを持つことを確認
      // 具体的な文言は実装時に確定（"LINEの認証情報を取得できませんでした" などを想定）
      expect(errorMessage.textContent).toBeTruthy();  // 【確認内容】: エラーメッセージにテキストが存在する 🟡
    });

    // 【確認内容】: linkLine API は呼ばれていないことを確認（ID トークン未取得のため）
    expect(mockLinkLine).not.toHaveBeenCalled();  // 🔵
  });

  it('TC-16: linkLine 呼び出し時に line_user_id ではなく id_token が使用される', async () => {
    /**
     * 【テスト目的】: フロントエンドが line_user_id を直接送信せず、
     *               id_token を送信することを検証する（セキュリティ改善の確認）
     * 【テスト内容】:
     *   1. 連携ボタンをクリック
     *   2. mockLinkLine の呼び出し引数を検査
     *   3. id_token フィールドが存在することを確認
     *   4. line_user_id フィールドが存在しないことを確認
     * 【期待される動作】: id_token フィールドのみが使用される
     * 🔵 信頼性レベル: 青信号 - REQ-V2-021 の line_user_id 廃止要件に基づく
     */

    const user = userEvent.setup();

    // 【実際の処理実行】: ページをレンダリングしてボタンをクリック
    renderLinkLinePage();

    await waitFor(() => {
      expect(screen.getByTestId('link-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('link-button'));

    // 【結果検証】: linkLine の呼び出し引数を確認
    await waitFor(() => {
      expect(mockLinkLine).toHaveBeenCalled();

      const callArgs = mockLinkLine.mock.calls[0][0];

      // 【確認内容】: id_token フィールドが存在することを確認
      expect(callArgs).toHaveProperty('id_token');  // 🔵

      // 【確認内容】: line_user_id フィールドが存在しないことを確認（廃止された送信方法）
      expect(callArgs).not.toHaveProperty('line_user_id');  // 🔵
    });
  });
});
