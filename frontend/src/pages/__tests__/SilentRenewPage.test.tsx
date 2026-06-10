import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { StrictMode } from 'react';

// 【テスト目的】: サイレントリニュー iframe コールバックページの動作確認 (S-2)
// 【テスト内容】: signinSilentCallback の委譲・StrictMode 二重実行ガード・エラー耐性

// vi.mock は hoist されるため、factory から参照する変数は vi.hoisted で定義する
const { mockHandleSilentCallback } = vi.hoisted(() => ({
  mockHandleSilentCallback: vi.fn(),
}));

vi.mock('@/services/auth', () => ({
  authService: {
    handleSilentCallback: mockHandleSilentCallback,
  },
}));

import { SilentRenewPage } from '../SilentRenewPage';

describe('SilentRenewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('マウント時に handleSilentCallback を呼び出す', () => {
    mockHandleSilentCallback.mockResolvedValue(undefined);

    const { container } = render(<SilentRenewPage />);

    // 【検証項目】: 親ウィンドウへの認証応答引き渡しが実行される
    expect(mockHandleSilentCallback).toHaveBeenCalledTimes(1);
    // 【検証項目】: iframe 内で不可視のため UI は描画しない
    expect(container.firstChild).toBeNull();
  });

  it('StrictMode の effect 二重実行でもコールバック処理は1回のみ', () => {
    mockHandleSilentCallback.mockResolvedValue(undefined);

    render(
      <StrictMode>
        <SilentRenewPage />
      </StrictMode>,
    );

    // 【検証項目】: ref ガードにより二重実行されない
    expect(mockHandleSilentCallback).toHaveBeenCalledTimes(1);
  });

  it('コールバック処理が失敗しても例外を投げない', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockHandleSilentCallback.mockRejectedValue(new Error('renew failed'));

    expect(() => render(<SilentRenewPage />)).not.toThrow();

    // 【検証項目】: エラーはログに記録される（リカバリは 401 リトライ経路に委譲）
    await vi.waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled();
    });
    consoleSpy.mockRestore();
  });
});
