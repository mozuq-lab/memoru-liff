/**
 * 【テスト概要】: AIカード生成画面のテスト
 * 【テスト対象】: GeneratePage コンポーネント
 * 【テスト対応】: TASK-0015 テストケース1〜9
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { GeneratePage } from '../GeneratePage';

// react-router-domのuseNavigateをモック
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// cardsApiのモック
const mockGenerateCards = vi.fn();
const mockCreateCard = vi.fn();
vi.mock('@/services/api', () => ({
  cardsApi: {
    generateCards: (...args: unknown[]) => mockGenerateCards(...args),
    createCard: (...args: unknown[]) => mockCreateCard(...args),
  },
}));

const renderGeneratePage = () => {
  return render(
    <MemoryRouter>
      <GeneratePage />
    </MemoryRouter>
  );
};

describe('GeneratePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGenerateCards.mockReset();
    mockCreateCard.mockReset();
  });

  describe('テストケース1: 文字数制限のバリデーション', () => {
    it('2000文字を超えるとエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      renderGeneratePage();

      const textarea = screen.getByTestId('input-text');
      const longText = 'a'.repeat(2001);
      await user.type(textarea, longText);

      expect(screen.getByTestId('over-limit-error')).toHaveTextContent('文字数制限を超えています');
    });

    it('2000文字を超えると生成ボタンが無効化される', async () => {
      const user = userEvent.setup();
      renderGeneratePage();

      const textarea = screen.getByTestId('input-text');
      const longText = 'a'.repeat(2001);
      await user.type(textarea, longText);

      const generateButton = screen.getByTestId('generate-button');
      expect(generateButton).toBeDisabled();
    });
  });

  describe('テストケース2: 文字数カウンター表示', () => {
    it('入力した文字数と上限が表示される', async () => {
      const user = userEvent.setup();
      renderGeneratePage();

      const textarea = screen.getByTestId('input-text');
      await user.type(textarea, 'テスト文字列');

      expect(screen.getByTestId('char-count')).toHaveTextContent('6 / 2000文字');
    });

    it('初期状態では0文字と表示される', () => {
      renderGeneratePage();
      expect(screen.getByTestId('char-count')).toHaveTextContent('0 / 2000文字');
    });
  });

  describe('テストケース3: 生成中のUI状態', () => {
    it('生成中は「生成中...」と表示される', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockImplementation(() => new Promise(() => {})); // 保留状態

      renderGeneratePage();

      const textarea = screen.getByTestId('input-text');
      await user.type(textarea, 'テストテキスト');

      const generateButton = screen.getByTestId('generate-button');
      await user.click(generateButton);

      expect(generateButton).toHaveTextContent('生成中...');
    });

    it('生成中はローディング表示が出る', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockImplementation(() => new Promise(() => {}));

      renderGeneratePage();

      const textarea = screen.getByTestId('input-text');
      await user.type(textarea, 'テストテキスト');

      await user.click(screen.getByTestId('generate-button'));

      expect(screen.getByTestId('loading')).toBeInTheDocument();
    });
  });

  describe('テストケース5: カード候補の表示', () => {
    it('生成成功時にカード候補が表示される', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockResolvedValue({
        generated_cards: [
          { front: '質問1', back: '回答1', suggested_tags: [] },
          { front: '質問2', back: '回答2', suggested_tags: [] },
        ],
        generation_info: { input_length: 10, model_used: 'test', processing_time_ms: 100 },
      });

      renderGeneratePage();

      const textarea = screen.getByTestId('input-text');
      await user.type(textarea, 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
        expect(screen.getByText('質問2')).toBeInTheDocument();
      });
    });

    it('生成されたカード数が表示される', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockResolvedValue({
        generated_cards: [
          { front: '質問1', back: '回答1', suggested_tags: [] },
          { front: '質問2', back: '回答2', suggested_tags: [] },
        ],
        generation_info: { input_length: 10, model_used: 'test', processing_time_ms: 100 },
      });

      renderGeneratePage();

      await user.type(screen.getByTestId('input-text'), 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByText('生成されたカード (2枚)')).toBeInTheDocument();
      });
    });

    it('デフォルトで全てのカードが選択されている', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockResolvedValue({
        generated_cards: [
          { front: '質問1', back: '回答1', suggested_tags: [] },
          { front: '質問2', back: '回答2', suggested_tags: [] },
        ],
        generation_info: { input_length: 10, model_used: 'test', processing_time_ms: 100 },
      });

      renderGeneratePage();

      await user.type(screen.getByTestId('input-text'), 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByTestId('selected-count')).toHaveTextContent('2枚選択中');
      });
    });
  });

  describe('テストケース6: カードの選択/解除', () => {
    it('カードの選択を解除できる', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockResolvedValue({
        generated_cards: [
          { front: '質問1', back: '回答1', suggested_tags: [] },
        ],
        generation_info: { input_length: 10, model_used: 'test', processing_time_ms: 100 },
      });

      renderGeneratePage();

      await user.type(screen.getByTestId('input-text'), 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByTestId('selected-count')).toHaveTextContent('1枚選択中');
      });

      const toggleButton = screen.getByTestId('toggle-select');
      await user.click(toggleButton);

      expect(screen.getByTestId('selected-count')).toHaveTextContent('0枚選択中');
    });
  });

  describe('テストケース7: カードの編集', () => {
    it('編集ボタンをクリックすると編集モードになる', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockResolvedValue({
        generated_cards: [
          { front: '質問1', back: '回答1', suggested_tags: [] },
        ],
        generation_info: { input_length: 10, model_used: 'test', processing_time_ms: 100 },
      });

      renderGeneratePage();

      await user.type(screen.getByTestId('input-text'), 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      expect(screen.getByTestId('edit-front')).toBeInTheDocument();
      expect(screen.getByTestId('edit-back')).toBeInTheDocument();
    });

    it('編集を保存できる', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockResolvedValue({
        generated_cards: [
          { front: '質問1', back: '回答1', suggested_tags: [] },
        ],
        generation_info: { input_length: 10, model_used: 'test', processing_time_ms: 100 },
      });

      renderGeneratePage();

      await user.type(screen.getByTestId('input-text'), 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('edit-front');
      await user.clear(frontInput);
      await user.type(frontInput, '編集後の質問');

      await user.click(screen.getByTestId('save-edit'));

      expect(screen.getByText('編集後の質問')).toBeInTheDocument();
    });
  });

  describe('テストケース8: カードの保存', () => {
    it('選択したカードを保存できる', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockResolvedValue({
        generated_cards: [
          { front: '質問1', back: '回答1', suggested_tags: ['tag1'] },
        ],
        generation_info: { input_length: 10, model_used: 'test', processing_time_ms: 100 },
      });
      mockCreateCard.mockResolvedValue({});

      renderGeneratePage();

      await user.type(screen.getByTestId('input-text'), 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(mockCreateCard).toHaveBeenCalledWith({
          front: '質問1',
          back: '回答1',
          tags: ['tag1'],
        });
        expect(mockNavigate).toHaveBeenCalledWith('/cards', expect.any(Object));
      });
    });

    it('選択がない場合は保存ボタンが無効', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockResolvedValue({
        generated_cards: [
          { front: '質問1', back: '回答1', suggested_tags: [] },
        ],
        generation_info: { input_length: 10, model_used: 'test', processing_time_ms: 100 },
      });

      renderGeneratePage();

      await user.type(screen.getByTestId('input-text'), 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByTestId('toggle-select')).toBeInTheDocument();
      });

      // 選択を解除
      await user.click(screen.getByTestId('toggle-select'));

      expect(screen.getByTestId('save-button')).toBeDisabled();
    });
  });

  describe('テストケース9: エラー表示', () => {
    it('生成エラー時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockRejectedValue(new Error('API Error'));

      renderGeneratePage();

      await user.type(screen.getByTestId('input-text'), 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error')).toBeInTheDocument();
        expect(screen.getByText('カードの生成に失敗しました。もう一度お試しください。')).toBeInTheDocument();
      });
    });

    it('保存エラー時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockGenerateCards.mockResolvedValue({
        generated_cards: [
          { front: '質問1', back: '回答1', suggested_tags: [] },
        ],
        generation_info: { input_length: 10, model_used: 'test', processing_time_ms: 100 },
      });
      mockCreateCard.mockRejectedValue(new Error('Save Error'));

      renderGeneratePage();

      await user.type(screen.getByTestId('input-text'), 'テストテキスト');
      await user.click(screen.getByTestId('generate-button'));

      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByText('カードの保存に失敗しました。もう一度お試しください。')).toBeInTheDocument();
      });
    });
  });

  describe('空入力の場合', () => {
    it('空白のみの場合は生成ボタンが無効', () => {
      renderGeneratePage();
      expect(screen.getByTestId('generate-button')).toBeDisabled();
    });
  });
});
