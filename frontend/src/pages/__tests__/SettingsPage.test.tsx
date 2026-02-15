/**
 * 【テスト概要】: 設定画面のテスト
 * 【テスト対象】: SettingsPage コンポーネント
 * 【テスト対応】: TASK-0018 テストケース1〜7
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { SettingsPage } from '../SettingsPage';
import type { User } from '@/types';

// Navigation モック
vi.mock('@/components/Navigation', () => ({
  Navigation: () => <nav data-testid="navigation">Navigation</nav>,
}));

// usersApi モック
const mockGetCurrentUser = vi.fn();
const mockUpdateUser = vi.fn();

vi.mock('@/services/api', () => ({
  usersApi: {
    getCurrentUser: () => mockGetCurrentUser(),
    updateUser: (...args: unknown[]) => mockUpdateUser(...args),
  },
}));

// useAuth モック
const mockLogout = vi.fn();
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    logout: mockLogout,
    user: {
      access_token: 'test-token',
      expired: false,
      profile: {
        sub: 'user-1',
        email: 'test@example.com',
        name: 'テストユーザー',
      },
    },
    isAuthenticated: true,
    isLoading: false,
  }),
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

const mockUser: User = {
  user_id: 'user-1',
  display_name: 'テストユーザー',
  picture_url: null,
  line_linked: false,
  notification_time: '09:00',
  timezone: 'Asia/Tokyo',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const renderSettingsPage = () => {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>
  );
};

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCurrentUser.mockResolvedValue(mockUser);
    mockUpdateUser.mockResolvedValue(mockUser);
    mockLogout.mockResolvedValue(undefined);
  });

  describe('テストケース1: 現在の設定値の表示', () => {
    it('設定が読み込まれると現在の通知時間が選択状態で表示される', async () => {
      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('settings-title')).toBeInTheDocument();
      });

      const selectedOption = screen.getByTestId('time-option-09:00');
      expect(selectedOption).toHaveClass('border-blue-500');
    });

    it('ユーザー情報が表示される', async () => {
      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('user-email')).toHaveTextContent('test@example.com');
        expect(screen.getByTestId('user-name')).toHaveTextContent('テストユーザー');
      });
    });
  });

  describe('テストケース2: 通知時間の選択', () => {
    it('別の通知時間を選択するとハイライトが変わる', async () => {
      const user = userEvent.setup();
      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('settings-title')).toBeInTheDocument();
      });

      const newOption = screen.getByTestId('time-option-18:00');
      await user.click(newOption);

      expect(newOption).toHaveClass('border-blue-500');
      expect(screen.getByTestId('time-option-09:00')).not.toHaveClass('border-blue-500');
    });
  });

  describe('テストケース3: 設定の保存', () => {
    it('保存成功時に成功メッセージが表示される', async () => {
      const user = userEvent.setup();
      const updatedUser = { ...mockUser, notification_time: '18:00' };
      mockUpdateUser.mockResolvedValue(updatedUser);

      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('settings-title')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('time-option-18:00'));
      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toHaveTextContent('設定を保存しました');
      });

      expect(mockUpdateUser).toHaveBeenCalledWith({ notification_time: '18:00' });
    });
  });

  describe('テストケース4: 変更がない場合の保存ボタン無効化', () => {
    it('設定を変更していない場合は保存ボタンが無効', async () => {
      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeDisabled();
      });
    });

    it('設定を変更すると保存ボタンが有効になる', async () => {
      const user = userEvent.setup();
      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('settings-title')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('time-option-18:00'));

      expect(screen.getByTestId('save-button')).toBeEnabled();
    });
  });

  describe('テストケース5: 保存成功フィードバック', () => {
    it('保存成功メッセージが表示される', async () => {
      const user = userEvent.setup();
      const updatedUser = { ...mockUser, notification_time: '18:00' };
      mockUpdateUser.mockResolvedValue(updatedUser);

      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('settings-title')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('time-option-18:00'));
      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toHaveTextContent('設定を保存しました');
      });
    });
  });

  describe('テストケース6: 保存エラー時の表示', () => {
    it('保存失敗時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockUpdateUser.mockRejectedValue(new Error('保存エラー'));

      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('settings-title')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('time-option-18:00'));
      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('設定の保存に失敗しました');
      });
    });
  });

  describe('テストケース7: ログアウト処理', () => {
    it('ログアウトボタンをクリックするとログアウト処理が実行される', async () => {
      const user = userEvent.setup();
      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('logout-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('logout-button'));

      await waitFor(() => {
        expect(mockLogout).toHaveBeenCalled();
        expect(mockNavigate).toHaveBeenCalledWith('/');
      });
    });

    it('ログアウト失敗時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockLogout.mockRejectedValue(new Error('ログアウトエラー'));

      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('logout-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('logout-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('ログアウトに失敗しました');
      });
    });
  });

  describe('ローディング状態', () => {
    it('読み込み中はローディングが表示される', () => {
      mockGetCurrentUser.mockImplementation(() => new Promise(() => {}));

      renderSettingsPage();

      expect(screen.getByText('設定を読み込み中...')).toBeInTheDocument();
    });
  });

  describe('エラー状態', () => {
    it('取得エラー時はエラーメッセージが表示される', async () => {
      mockGetCurrentUser.mockRejectedValue(new Error('取得エラー'));

      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByText('設定の取得に失敗しました')).toBeInTheDocument();
      });
    });

    it('エラー時に再試行ボタンが表示される', async () => {
      mockGetCurrentUser.mockRejectedValue(new Error('取得エラー'));

      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /再試行/ })).toBeInTheDocument();
      });
    });
  });

  describe('LINE連携表示', () => {
    it('LINE連携済みの場合は連携済みと表示される', async () => {
      const linkedUser = { ...mockUser, line_linked: true };
      mockGetCurrentUser.mockResolvedValue(linkedUser);

      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('line-connected')).toHaveTextContent('連携済み');
      });
    });

    it('LINE連携設定へのリンクがある', async () => {
      renderSettingsPage();

      await waitFor(() => {
        expect(screen.getByTestId('line-link-button')).toHaveAttribute('href', '/link-line');
      });
    });
  });
});
