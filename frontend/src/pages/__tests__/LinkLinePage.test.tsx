/**
 * 【テスト概要】: LINE連携画面のテスト
 * 【テスト対象】: LinkLinePage コンポーネント
 * 【テスト対応】: TASK-0019 テストケース1〜7
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { LinkLinePage } from '../LinkLinePage';
import type { User } from '@/types';

// Navigation モック
vi.mock('@/components/Navigation', () => ({
  Navigation: () => <nav data-testid="navigation">Navigation</nav>,
}));

// usersApi モック
const mockGetCurrentUser = vi.fn();
const mockUpdateUser = vi.fn();
const mockLinkLine = vi.fn();
const mockUnlinkLine = vi.fn();

vi.mock('@/services/api', () => ({
  usersApi: {
    getCurrentUser: () => mockGetCurrentUser(),
    updateUser: (...args: unknown[]) => mockUpdateUser(...args),
    linkLine: (...args: unknown[]) => mockLinkLine(...args),
    unlinkLine: () => mockUnlinkLine(),
  },
}));

// liff モック
const mockInitializeLiff = vi.fn();
const mockGetLiffProfile = vi.fn();
const mockIsInLiffClient = vi.fn();
const mockGetLiffIdToken = vi.fn();

vi.mock('@/services/liff', () => ({
  initializeLiff: () => mockInitializeLiff(),
  getLiffProfile: () => mockGetLiffProfile(),
  isInLiffClient: () => mockIsInLiffClient(),
  getLiffIdToken: () => mockGetLiffIdToken(),
}));

// useNavigate モック
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockUnlinkedUser: User = {
  user_id: 'user-1',
  display_name: 'テストユーザー',
  picture_url: null,
  line_linked: false,
  notification_time: '09:00',
  timezone: 'Asia/Tokyo',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockLinkedUser: User = {
  user_id: 'user-1',
  display_name: 'テストユーザー',
  picture_url: null,
  line_linked: true,
  notification_time: '09:00',
  timezone: 'Asia/Tokyo',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const renderLinkLinePage = () => {
  return render(
    <MemoryRouter>
      <LinkLinePage />
    </MemoryRouter>
  );
};

describe('LinkLinePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCurrentUser.mockResolvedValue(mockUnlinkedUser);
    mockUpdateUser.mockResolvedValue(mockUnlinkedUser);
    mockLinkLine.mockResolvedValue(mockLinkedUser);
    mockInitializeLiff.mockResolvedValue(undefined);
    mockGetLiffProfile.mockResolvedValue({
      userId: 'line-user-123',
      displayName: 'LINE表示名',
      pictureUrl: 'https://example.com/picture.jpg',
    });
    mockIsInLiffClient.mockReturnValue(true);
    mockGetLiffIdToken.mockReturnValue('test-liff-id-token');
  });

  describe('テストケース1: 連携状態の表示（連携済み）', () => {
    it('連携済みユーザーは「連携済み」と表示される', async () => {
      mockGetCurrentUser.mockResolvedValue(mockLinkedUser);
      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('link-status')).toHaveTextContent('連携済み');
      });
    });

    it('連携済みの場合は連携中テキストが表示される', async () => {
      mockGetCurrentUser.mockResolvedValue(mockLinkedUser);
      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('line-status-text')).toHaveTextContent('LINE連携中');
      });
    });

    it('連携済みの場合は解除ボタンが表示される', async () => {
      mockGetCurrentUser.mockResolvedValue(mockLinkedUser);
      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('unlink-button')).toBeInTheDocument();
      });
    });
  });

  describe('テストケース2: 連携状態の表示（未連携）', () => {
    it('未連携ユーザーは「未連携」と表示される', async () => {
      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('link-status')).toHaveTextContent('未連携');
      });
    });

    it('未連携の場合は連携ボタンが表示される', async () => {
      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('link-button')).toBeInTheDocument();
      });
    });
  });

  describe('テストケース3: LINE連携の実行', () => {
    it('連携ボタンクリックでLIFF SDK呼び出しとAPI連携が実行される', async () => {
      const user = userEvent.setup();
      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('link-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('link-button'));

      await waitFor(() => {
        expect(mockIsInLiffClient).toHaveBeenCalled();
        expect(mockInitializeLiff).toHaveBeenCalled();
        expect(mockGetLiffIdToken).toHaveBeenCalled();
        expect(mockLinkLine).toHaveBeenCalledWith({ id_token: 'test-liff-id-token' });
      });
    });
  });

  describe('テストケース4: LINE連携成功時のメッセージ', () => {
    it('連携成功時に成功メッセージが表示される', async () => {
      const user = userEvent.setup();
      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('link-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('link-button'));

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toHaveTextContent('LINE連携が完了しました');
      });
    });
  });

  describe('テストケース5: LINE連携の解除', () => {
    it('解除ボタンクリックで連携解除が実行される', async () => {
      const user = userEvent.setup();
      mockGetCurrentUser.mockResolvedValue(mockLinkedUser);
      mockUpdateUser.mockResolvedValue({ ...mockLinkedUser, line_linked: false });

      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('unlink-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('unlink-button'));

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toHaveTextContent('LINE連携を解除しました');
      });
    });
  });

  describe('テストケース6: LIFF外からのアクセス時のエラー', () => {
    it('LINEアプリ外からのアクセス時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockIsInLiffClient.mockReturnValue(false);

      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('link-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('link-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('LINEアプリからアクセスしてください');
      });
    });
  });

  describe('テストケース7: 連携エラー時の表示', () => {
    it('連携API失敗時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockLinkLine.mockRejectedValue(new Error('連携エラー'));

      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('link-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('link-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('LINE連携に失敗しました');
      });
    });

    it('解除API失敗時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockGetCurrentUser.mockResolvedValue(mockLinkedUser);
      mockUnlinkLine.mockRejectedValue(new Error('解除エラー'));

      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('unlink-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('unlink-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('LINE連携の解除に失敗しました');
      });
    });
  });

  describe('ローディング状態', () => {
    it('読み込み中はローディングが表示される', () => {
      mockGetCurrentUser.mockImplementation(() => new Promise(() => {}));

      renderLinkLinePage();

      expect(screen.getByText('読み込み中...')).toBeInTheDocument();
    });
  });

  describe('エラー状態', () => {
    it('取得エラー時はエラーメッセージが表示される', async () => {
      mockGetCurrentUser.mockRejectedValue(new Error('取得エラー'));

      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByText('LINE連携状態の取得に失敗しました')).toBeInTheDocument();
      });
    });

    it('エラー時に再試行ボタンが表示される', async () => {
      mockGetCurrentUser.mockRejectedValue(new Error('取得エラー'));

      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /再試行/ })).toBeInTheDocument();
      });
    });
  });

  describe('戻るボタン', () => {
    it('戻るボタンで履歴を戻る', async () => {
      const user = userEvent.setup();
      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('back-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('back-button'));

      expect(mockNavigate).toHaveBeenCalledWith(-1);
    });
  });

  /**
   * TASK-0045: TC-08 - LinkLinePage が unlinkLine を使用
   * 対応要件: EARS-045-015, EARS-045-016
   *
   * RED フェーズ失敗理由:
   *   LinkLinePage.tsx L101 の handleUnlinkLine が usersApi.updateUser() を呼んでいる。
   *   unlinkLine ではなく updateUser が呼ばれるため:
   *   - mockUnlinkLine.toHaveBeenCalledTimes(1) → FAIL (0回呼ばれる)
   *   - mockUpdateUser.not.toHaveBeenCalled() → FAIL (呼ばれている)
   */
  describe('TC-08: LinkLinePage が unlinkLine を使用', () => {
    beforeEach(() => {
      mockUnlinkLine.mockResolvedValue({
        user_id: 'user-1',
        display_name: 'テストユーザー',
        picture_url: null,
        line_linked: false,
        notification_time: '09:00',
        timezone: 'Asia/Tokyo',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      });
    });

    it('TC-08-01: LINE連携解除ボタンクリックで unlinkLine が呼ばれ updateUser が呼ばれないこと', async () => {
      /**
       * 【テスト目的】: handleUnlinkLine が updateUser ではなく unlinkLine を呼ぶことを検証
       * 【期待される動作】: unlinkLine が1回呼ばれ、updateUser は呼ばれない
       * 青 信頼性レベル: EARS-045-015
       */
      const linkedUser: User = {
        user_id: 'user-1',
        display_name: 'テストユーザー',
        picture_url: null,
        line_linked: true,
        notification_time: '09:00',
        timezone: 'Asia/Tokyo',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      mockGetCurrentUser.mockResolvedValue(linkedUser);

      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('unlink-button')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('unlink-button'));

      await waitFor(() => {
        // unlinkLine が呼ばれること
        expect(mockUnlinkLine).toHaveBeenCalledTimes(1);
        // updateUser が呼ばれないこと
        expect(mockUpdateUser).not.toHaveBeenCalled();
      });
    });

    it('TC-08-02: LINE連携解除成功後にサーバーレスポンスで状態更新されること', async () => {
      /**
       * 【テスト目的】: setUser がサーバーレスポンスをそのまま使用することを検証
       *                 手動で line_linked: false を上書きしていないことを確認
       * 青 信頼性レベル: EARS-045-016
       */
      const linkedUser: User = {
        user_id: 'user-1',
        display_name: 'テストユーザー',
        picture_url: null,
        line_linked: true,
        notification_time: '09:00',
        timezone: 'Asia/Tokyo',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      const serverResponse: User = {
        user_id: 'user-1',
        display_name: 'テストユーザー',
        picture_url: null,
        line_linked: false,
        notification_time: '09:00',
        timezone: 'Asia/Tokyo',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      mockGetCurrentUser.mockResolvedValue(linkedUser);
      mockUnlinkLine.mockResolvedValue(serverResponse);

      renderLinkLinePage();

      await waitFor(() => {
        expect(screen.getByTestId('unlink-button')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('unlink-button'));

      // 成功メッセージが表示されること
      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toHaveTextContent(
          'LINE連携を解除しました'
        );
      });

      // 状態が「未連携」に更新されること
      await waitFor(() => {
        expect(screen.getByTestId('link-status')).toHaveTextContent('未連携');
      });
    });
  });
});
