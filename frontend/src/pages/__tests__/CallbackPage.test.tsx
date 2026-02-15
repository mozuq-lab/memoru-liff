/**
 * 【テスト概要】: OIDCコールバック画面のテスト
 * 【テスト対象】: CallbackPage コンポーネント
 * 【テスト対応】: TASK-0025 テストケース1〜3
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CallbackPage } from '../CallbackPage';

// authService モック
const mockHandleCallback = vi.fn();

vi.mock('@/services/auth', () => ({
  authService: {
    handleCallback: () => mockHandleCallback(),
  },
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

const renderCallbackPage = () => {
  return render(
    <MemoryRouter initialEntries={['/callback']}>
      <CallbackPage />
    </MemoryRouter>
  );
};

describe('CallbackPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHandleCallback.mockResolvedValue({ access_token: 'test-token' });
  });

  describe('テストケース1: handleCallback成功時のリダイレクト', () => {
    it('authService.handleCallback()が呼ばれる', async () => {
      renderCallbackPage();

      await waitFor(() => {
        expect(mockHandleCallback).toHaveBeenCalledTimes(1);
      });
    });

    it('成功時にホーム画面にリダイレクトされる', async () => {
      renderCallbackPage();

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
      });
    });
  });

  describe('テストケース2: handleCallback失敗時のエラー表示', () => {
    it('エラー時にエラーメッセージが表示される', async () => {
      mockHandleCallback.mockRejectedValue(new Error('認証エラー'));

      renderCallbackPage();

      await waitFor(() => {
        expect(screen.getByText('認証に失敗しました')).toBeInTheDocument();
      });
    });

    it('エラー時にリダイレクトされない', async () => {
      mockHandleCallback.mockRejectedValue(new Error('認証エラー'));

      renderCallbackPage();

      await waitFor(() => {
        expect(screen.getByText('認証に失敗しました')).toBeInTheDocument();
      });

      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  describe('テストケース3: ローディング状態', () => {
    it('処理中はローディングメッセージが表示される', () => {
      mockHandleCallback.mockImplementation(() => new Promise(() => {}));

      renderCallbackPage();

      expect(screen.getByText('認証処理中...')).toBeInTheDocument();
    });
  });
});
