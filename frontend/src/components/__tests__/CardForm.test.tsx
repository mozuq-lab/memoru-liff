/**
 * 【テスト概要】: カード編集フォームコンポーネントのテスト
 * 【テスト対象】: CardForm コンポーネント
 * 【テスト対応】: TASK-0017 テストケース2〜5, TASK-0141 AI補足機能
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CardForm } from '../CardForm';
import { REFINE_AI_TIMEOUT_MS } from '@/constants/refine';

// cardsApi モック（CardForm が import する ApiError も同モジュールから提供する）
vi.mock('@/services/api', () => {
  class ApiError extends Error {
    readonly status: number;
    readonly code?: string;

    constructor(message: string, status: number, code?: string) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.code = code;
    }
  }
  return {
    cardsApi: {
      refineCard: vi.fn(),
    },
    ApiError,
  };
});

// モック関数を取得
const getRefineCardMock = async () => {
  const { cardsApi } = await import('@/services/api');
  return cardsApi.refineCard as ReturnType<typeof vi.fn>;
};

// モックモジュールの ApiError クラスを取得（instanceof 判定を成立させるため）
const getApiError = async () => {
  const { ApiError } = await import('@/services/api');
  return ApiError;
};

const defaultProps = {
  initialFront: '元の質問',
  initialBack: '元の回答',
  onSave: vi.fn(),
  onCancel: vi.fn(),
  isSaving: false,
};

const renderCardForm = (props = {}) => {
  return render(<CardForm {...defaultProps} {...props} />);
};

describe('CardForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('初期表示', () => {
    it('初期値が表示される', () => {
      renderCardForm();

      expect(screen.getByTestId('input-front')).toHaveValue('元の質問');
      expect(screen.getByTestId('input-back')).toHaveValue('元の回答');
    });

    it('フォームが表示される', () => {
      renderCardForm();

      expect(screen.getByTestId('card-form')).toBeInTheDocument();
    });

    it('ラベルが表示される', () => {
      renderCardForm();

      expect(screen.getByLabelText('表面（質問）')).toBeInTheDocument();
      expect(screen.getByLabelText('裏面（解答）')).toBeInTheDocument();
    });

    it('AI で補足ボタンが表示される', () => {
      renderCardForm();

      expect(screen.getByTestId('refine-button')).toBeInTheDocument();
      expect(screen.getByTestId('refine-button')).toHaveTextContent('AI で補足');
    });
  });

  describe('バリデーション', () => {
    it('変更がない場合、保存ボタンは無効', () => {
      renderCardForm();

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeDisabled();
    });

    it('表面が空の場合、保存ボタンは無効', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeDisabled();
    });

    it('裏面が空の場合、保存ボタンは無効', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const backInput = screen.getByTestId('input-back');
      await user.clear(backInput);

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeDisabled();
    });

    it('両方が空白のみの場合、保存ボタンは無効', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const frontInput = screen.getByTestId('input-front');
      const backInput = screen.getByTestId('input-back');

      await user.clear(frontInput);
      await user.type(frontInput, '   ');
      await user.clear(backInput);
      await user.type(backInput, '   ');

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeDisabled();
    });

    it('変更があり両方に値がある場合、保存ボタンは有効', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '新しい質問');

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeEnabled();
    });
  });

  describe('保存', () => {
    it('保存ボタンクリックでonSaveが呼ばれる', async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);
      renderCardForm({ onSave });

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '新しい質問');

      const saveButton = screen.getByTestId('save-button');
      await user.click(saveButton);

      expect(onSave).toHaveBeenCalledWith('新しい質問', '元の回答', []);
    });

    it('保存中はボタンに「保存中...」と表示される', () => {
      renderCardForm({ isSaving: true });

      expect(screen.getByTestId('save-button')).toHaveTextContent('保存中...');
    });

    it('保存中は入力フィールドが無効化される', () => {
      renderCardForm({ isSaving: true });

      expect(screen.getByTestId('input-front')).toBeDisabled();
      expect(screen.getByTestId('input-back')).toBeDisabled();
    });

    it('保存中はキャンセルボタンが無効化される', () => {
      renderCardForm({ isSaving: true });

      expect(screen.getByTestId('cancel-button')).toBeDisabled();
    });

    it('値の前後の空白はトリムされる', async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);
      renderCardForm({ onSave });

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '  新しい質問  ');

      const saveButton = screen.getByTestId('save-button');
      await user.click(saveButton);

      expect(onSave).toHaveBeenCalledWith('新しい質問', '元の回答', []);
    });
  });

  describe('キャンセル', () => {
    it('キャンセルボタンクリックでonCancelが呼ばれる', async () => {
      const user = userEvent.setup();
      const onCancel = vi.fn();
      renderCardForm({ onCancel });

      const cancelButton = screen.getByTestId('cancel-button');
      await user.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
    });
  });

  describe('入力操作', () => {
    it('表面のテキストを変更できる', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, 'テスト質問');

      expect(frontInput).toHaveValue('テスト質問');
    });

    it('裏面のテキストを変更できる', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const backInput = screen.getByTestId('input-back');
      await user.clear(backInput);
      await user.type(backInput, 'テスト回答');

      expect(backInput).toHaveValue('テスト回答');
    });
  });

  describe('AI で補足', () => {
    it('AI で補足ボタンが有効（表面・裏面に値がある場合）', () => {
      renderCardForm();

      expect(screen.getByTestId('refine-button')).toBeEnabled();
    });

    it('表面・裏面の両方が空の場合、AI で補足ボタンは無効', () => {
      renderCardForm({ initialFront: '', initialBack: '' });

      expect(screen.getByTestId('refine-button')).toBeDisabled();
    });

    it('表面のみ入力があればAI で補足ボタンは有効', () => {
      renderCardForm({ initialFront: 'テスト', initialBack: '' });

      expect(screen.getByTestId('refine-button')).toBeEnabled();
    });

    it('裏面のみ入力があればAI で補足ボタンは有効', () => {
      renderCardForm({ initialFront: '', initialBack: 'テスト' });

      expect(screen.getByTestId('refine-button')).toBeEnabled();
    });

    it('保存中はAI で補足ボタンが無効', () => {
      renderCardForm({ isSaving: true });

      expect(screen.getByTestId('refine-button')).toBeDisabled();
    });

    it('AI で補足成功時にテキストエリアが更新される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      mockRefineCard.mockResolvedValue({
        refined_front: '改善された質問',
        refined_back: '改善された回答',
        model_used: 'test-model',
        processing_time_ms: 500,
      });

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('input-front')).toHaveValue('改善された質問');
        expect(screen.getByTestId('input-back')).toHaveValue('改善された回答');
      });
    });

    it('AI で補足中はボタンに「AI 処理中...」と表示される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      let resolvePromise: (value: unknown) => void;
      mockRefineCard.mockReturnValue(new Promise((resolve) => { resolvePromise = resolve; }));

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      expect(screen.getByTestId('refine-button')).toHaveTextContent('AI 処理中...');
      expect(screen.getByTestId('refine-button')).toBeDisabled();

      resolvePromise!({
        refined_front: '改善', refined_back: '改善',
        model_used: 'test', processing_time_ms: 100,
      });
    });

    it('AI で補足中は入力フィールドが無効化される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      let resolvePromise: (value: unknown) => void;
      mockRefineCard.mockReturnValue(new Promise((resolve) => { resolvePromise = resolve; }));

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      expect(screen.getByTestId('input-front')).toBeDisabled();
      expect(screen.getByTestId('input-back')).toBeDisabled();

      resolvePromise!({
        refined_front: '改善', refined_back: '改善',
        model_used: 'test', processing_time_ms: 100,
      });
    });

    it('AI で補足エラー時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      mockRefineCard.mockRejectedValue(new Error('HTTP 500'));

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toBeInTheDocument();
      });
    });

    it('AI で補足エラー時に元のテキストが維持される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      mockRefineCard.mockRejectedValue(new Error('HTTP 500'));

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toBeInTheDocument();
      });

      expect(screen.getByTestId('input-front')).toHaveValue('元の質問');
      expect(screen.getByTestId('input-back')).toHaveValue('元の回答');
    });

    // バックエンドの実レスポンスは {"error": "AI service unavailable"} のように
    // ステータスコードの数字を含まないため、ApiError の status で分類されることを検証する
    it('タイムアウトエラー（504）時に適切なメッセージが表示される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      const ApiError = await getApiError();
      mockRefineCard.mockRejectedValue(
        new ApiError('AI processing timed out', 504),
      );

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toHaveTextContent(
          'AIの処理がタイムアウトしました。再度お試しください'
        );
      });
    });

    it('レート制限エラー（429）時に適切なメッセージが表示される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      const ApiError = await getApiError();
      mockRefineCard.mockRejectedValue(
        new ApiError('Rate limit exceeded', 429),
      );

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toHaveTextContent(
          'リクエスト制限に達しました。しばらくお待ちください'
        );
      });
    });

    it('AIサービス障害（503）時に適切なメッセージが表示される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      const ApiError = await getApiError();
      mockRefineCard.mockRejectedValue(
        new ApiError('AI service unavailable', 503),
      );

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toHaveTextContent(
          'AIサービスが一時的に利用できません'
        );
      });
    });

    it('入力エラー（400）時に適切なメッセージが表示される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      const ApiError = await getApiError();
      mockRefineCard.mockRejectedValue(new ApiError('Invalid input', 400));

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toHaveTextContent(
          '入力内容を確認してください'
        );
      });
    });

    it('その他の ApiError（500）は汎用メッセージが表示される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      const ApiError = await getApiError();
      mockRefineCard.mockRejectedValue(
        new ApiError('Internal server error', 500),
      );

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toHaveTextContent(
          'AI補足に失敗しました。再度お試しください'
        );
      });
    });

    it('ApiError でないエラー（ネットワークエラー等）は汎用メッセージが表示される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      mockRefineCard.mockRejectedValue(new Error('Network error'));

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toHaveTextContent(
          'AI補足に失敗しました。再度お試しください'
        );
      });
    });

    it('タイムアウト経過で abort されタイムアウトメッセージが表示される', async () => {
      // 【テスト内容】: handleRefine のタイムアウト（REFINE_AI_TIMEOUT_MS）経過で
      //               リクエストが中断され、処理中状態が解除されてメッセージが出ること
      // fake timers と userEvent の相性問題を避けるため fireEvent.click を使用する
      vi.useFakeTimers();
      try {
        const mockRefineCard = await getRefineCardMock();
        mockRefineCard.mockImplementation(
          (_req: unknown, opts: { signal: AbortSignal }) =>
            new Promise((_resolve, reject) => {
              opts.signal.addEventListener('abort', () =>
                reject(opts.signal.reason),
              );
            }),
        );

        renderCardForm();

        fireEvent.click(screen.getByTestId('refine-button'));
        expect(screen.getByTestId('refine-button')).toHaveTextContent(
          'AI 処理中...'
        );

        await act(async () => {
          vi.advanceTimersByTime(REFINE_AI_TIMEOUT_MS);
        });

        expect(screen.getByTestId('refine-error')).toHaveTextContent(
          'AIの処理がタイムアウトしました。再度お試しください'
        );
        // 処理中のまま固まらないこと
        expect(screen.getByTestId('refine-button')).toHaveTextContent(
          'AI で補足'
        );
      } finally {
        vi.useRealTimers();
      }
    });

    it('APIレイヤーのタイムアウト（TimeoutError）でもタイムアウトメッセージが表示される', async () => {
      // 【テスト内容】: request() 側のタイムアウト合成（timeoutMs）による
      //               TimeoutError もタイムアウトとして分類されること
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      mockRefineCard.mockRejectedValue(
        new DOMException('The operation timed out.', 'TimeoutError'),
      );

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toHaveTextContent(
          'AIの処理がタイムアウトしました。再度お試しください'
        );
      });
    });

    it('AI で補足リクエストに正しいパラメータが渡される', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      mockRefineCard.mockResolvedValue({
        refined_front: '改善', refined_back: '改善',
        model_used: 'test', processing_time_ms: 100,
      });

      renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      await waitFor(() => {
        expect(mockRefineCard).toHaveBeenCalledWith(
          { front: '元の質問', back: '元の回答' },
          { signal: expect.any(AbortSignal), timeoutMs: REFINE_AI_TIMEOUT_MS },
        );
      });
    });

    it('アンマウント時に進行中のリクエストがキャンセルされる', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      let capturedSignal: AbortSignal | undefined;
      mockRefineCard.mockImplementation((_req: unknown, opts: { signal: AbortSignal }) => {
        capturedSignal = opts.signal;
        return new Promise(() => {}); // 永遠に解決しない
      });

      const { unmount } = renderCardForm();

      await user.click(screen.getByTestId('refine-button'));

      // signal が渡されていることを確認
      await waitFor(() => {
        expect(capturedSignal).toBeDefined();
      });
      expect(capturedSignal!.aborted).toBe(false);

      // アンマウント
      unmount();

      // abort が呼ばれたことを確認
      expect(capturedSignal!.aborted).toBe(true);
    });

    it('再試行時にエラーメッセージがクリアされる', async () => {
      const user = userEvent.setup();
      const mockRefineCard = await getRefineCardMock();
      mockRefineCard.mockRejectedValueOnce(new Error('HTTP 500'));
      mockRefineCard.mockResolvedValueOnce({
        refined_front: '改善', refined_back: '改善',
        model_used: 'test', processing_time_ms: 100,
      });

      renderCardForm();

      // 1回目: エラー
      await user.click(screen.getByTestId('refine-button'));
      await waitFor(() => {
        expect(screen.getByTestId('refine-error')).toBeInTheDocument();
      });

      // 2回目: 成功
      await user.click(screen.getByTestId('refine-button'));
      await waitFor(() => {
        expect(screen.queryByTestId('refine-error')).not.toBeInTheDocument();
      });
    });
  });

  describe('参考情報（ReferenceEditor 統合）', () => {
    it('ReferenceEditor が表示される', () => {
      renderCardForm();

      expect(screen.getByTestId('reference-editor')).toBeInTheDocument();
    });

    it('initialReferences が設定されると ReferenceEditor に反映される', () => {
      const refs = [
        { type: 'url' as const, value: 'https://example.com' },
        { type: 'book' as const, value: '参考書籍' },
      ];
      renderCardForm({ initialReferences: refs });

      expect(screen.getByTestId('reference-list')).toBeInTheDocument();
      expect(screen.getByTestId('reference-item-0')).toHaveTextContent('https://example.com');
      expect(screen.getByTestId('reference-item-1')).toHaveTextContent('参考書籍');
    });

    it('initialReferences なしの場合は空の状態で表示される', () => {
      renderCardForm();

      expect(screen.getByTestId('reference-editor')).toBeInTheDocument();
      expect(screen.queryByTestId('reference-list')).not.toBeInTheDocument();
    });

    it('参考情報を追加してフォーム送信すると onSave に references が含まれる', async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);
      renderCardForm({ onSave });

      // 参考情報を追加
      const addInput = screen.getByTestId('reference-add-value');
      await user.type(addInput, 'https://example.com');
      await user.click(screen.getByTestId('reference-add-button'));

      // テキストも変更（hasChanges 条件のため）
      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '新しい質問');

      await user.click(screen.getByTestId('save-button'));

      expect(onSave).toHaveBeenCalledWith('新しい質問', '元の回答', [
        { type: 'url', value: 'https://example.com' },
      ]);
    });

    it('参考情報の変更のみでも保存ボタンが有効になる', async () => {
      const user = userEvent.setup();
      renderCardForm();

      // 参考情報を追加（front/back は変更しない）
      const addInput = screen.getByTestId('reference-add-value');
      await user.type(addInput, 'https://example.com');
      await user.click(screen.getByTestId('reference-add-button'));

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeEnabled();
    });
  });
});
