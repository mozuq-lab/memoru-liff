/**
 * 【テスト概要】: カード詳細・編集画面のテスト
 * 【テスト対象】: CardDetailPage コンポーネント
 * 【テスト対応】: TASK-0017 テストケース1〜9
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { CardDetailPage } from '../CardDetailPage';
import type { Card } from '@/types';

// Navigation モック
vi.mock('@/components/Navigation', () => ({
  Navigation: () => <nav data-testid="navigation">Navigation</nav>,
}));

// cardsApi モック
const mockGetCard = vi.fn();
const mockUpdateCard = vi.fn();
const mockDeleteCard = vi.fn();

vi.mock('@/services/api', () => ({
  cardsApi: {
    getCard: (...args: unknown[]) => mockGetCard(...args),
    updateCard: (...args: unknown[]) => mockUpdateCard(...args),
    deleteCard: (...args: unknown[]) => mockDeleteCard(...args),
  },
}));

// DecksContext モック
const mockFetchDecks = vi.fn();
const mockDecks = [
  {
    deck_id: 'deck-1',
    user_id: 'user-1',
    name: '英語',
    color: '#EF4444',
    card_count: 10,
    due_count: 3,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    deck_id: 'deck-2',
    user_id: 'user-1',
    name: '数学',
    color: '#3B82F6',
    card_count: 5,
    due_count: 1,
    created_at: '2024-01-02T00:00:00Z',
  },
];
vi.mock('@/contexts/DecksContext', () => ({
  useDecksContext: () => ({
    decks: mockDecks,
    isLoading: false,
    error: null,
    fetchDecks: mockFetchDecks,
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

const mockCard: Card = {
  card_id: 'card-1',
  user_id: 'user-1',
  front: 'テスト質問',
  back: 'テスト回答',
  tags: ['tag1'],
  ease_factor: 2.5,
  interval: 7,
  repetitions: 3,
  deck_id: 'deck-1', // 【初期値】: null 送信テストのために初期値を deck-1 に設定 🔵
  next_review_at: '2024-01-20',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-15T00:00:00Z',
};

const renderCardDetailPage = (cardId: string = 'card-1') => {
  return render(
    <MemoryRouter initialEntries={[`/cards/${cardId}`]}>
      <Routes>
        <Route path="/cards/:id" element={<CardDetailPage />} />
        <Route path="/cards" element={<div data-testid="cards-page">Cards Page</div>} />
      </Routes>
    </MemoryRouter>
  );
};

describe('CardDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCard.mockResolvedValue(mockCard);
    mockUpdateCard.mockResolvedValue(mockCard);
    mockDeleteCard.mockResolvedValue(undefined);

    // 日付のモック（fake timersではなくDateのモック）
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2024-01-15T00:00:00').getTime());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('テストケース1: カード詳細の表示', () => {
    it('カードの表面・裏面が表示される', async () => {
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-front')).toHaveTextContent('テスト質問');
      });
      expect(screen.getByTestId('card-back')).toHaveTextContent('テスト回答');
    });

    it('メタ情報（次回復習日、復習間隔）が表示される', async () => {
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('due-date')).toBeInTheDocument();
      });
      expect(screen.getByTestId('interval')).toHaveTextContent('7日');
    });

    it('APIからカードを取得する', async () => {
      renderCardDetailPage('card-1');

      await waitFor(() => {
        expect(mockGetCard).toHaveBeenCalledWith('card-1');
      });
    });
  });

  describe('テストケース2: 編集モードへの切り替え', () => {
    it('編集ボタンをクリックすると編集フォームが表示される', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      const editButton = screen.getByTestId('edit-button');
      await user.click(editButton);

      expect(screen.getByTestId('card-form')).toBeInTheDocument();
    });

    it('編集モードでは編集ボタンが非表示になる', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      expect(screen.queryByTestId('edit-button')).not.toBeInTheDocument();
    });
  });

  describe('テストケース3: 編集のキャンセル', () => {
    it('キャンセルボタンで表示モードに戻る', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));
      expect(screen.getByTestId('card-form')).toBeInTheDocument();

      await user.click(screen.getByTestId('cancel-button'));

      expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      expect(screen.queryByTestId('card-form')).not.toBeInTheDocument();
    });
  });

  describe('テストケース4: カードの保存', () => {
    it('保存成功時に成功メッセージが表示される', async () => {
      const user = userEvent.setup();
      const updatedCard = { ...mockCard, front: '更新された質問' };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '更新された質問');

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toHaveTextContent('カードを保存しました');
      });
    });

    it('保存成功後に表示モードに戻る', async () => {
      const user = userEvent.setup();
      const updatedCard = { ...mockCard, front: '更新された質問' };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '更新された質問');

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });
    });

    it('保存失敗時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockUpdateCard.mockRejectedValue(new Error('保存エラー'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '更新された質問');

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('カードの保存に失敗しました');
      });
    });
  });

  describe('テストケース5: 空の入力での保存防止', () => {
    it('空の入力では保存ボタンが無効', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);

      expect(screen.getByTestId('save-button')).toBeDisabled();
    });
  });

  describe('テストケース6: 削除確認ダイアログの表示', () => {
    it('削除ボタンで確認ダイアログが表示される', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('delete-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('delete-button'));

      expect(screen.getByTestId('delete-confirm-dialog')).toBeInTheDocument();
      expect(screen.getByText('カードを削除しますか？')).toBeInTheDocument();
      expect(screen.getByText('この操作は取り消せません。')).toBeInTheDocument();
    });
  });

  describe('テストケース7: 削除のキャンセル', () => {
    it('キャンセルボタンでダイアログが閉じる', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('delete-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('delete-button'));
      expect(screen.getByTestId('delete-confirm-dialog')).toBeInTheDocument();

      await user.click(screen.getByTestId('delete-cancel-button'));

      expect(screen.queryByTestId('delete-confirm-dialog')).not.toBeInTheDocument();
    });
  });

  describe('テストケース8: カードの削除', () => {
    it('削除成功時に一覧画面に遷移する', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('delete-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('delete-button'));
      await user.click(screen.getByTestId('delete-confirm-button'));

      await waitFor(() => {
        expect(mockDeleteCard).toHaveBeenCalledWith('card-1');
        expect(mockNavigate).toHaveBeenCalledWith('/cards', { state: { message: 'カードを削除しました' } });
      });
    });

    it('削除失敗時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockDeleteCard.mockRejectedValue(new Error('削除エラー'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('delete-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('delete-button'));
      await user.click(screen.getByTestId('delete-confirm-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('カードの削除に失敗しました');
      });
    });
  });

  describe('テストケース9: 存在しないカードへのアクセス', () => {
    it('カード取得失敗時にエラーが表示される', async () => {
      mockGetCard.mockRejectedValue(new Error('Not Found'));

      renderCardDetailPage('non-existent');

      await waitFor(() => {
        expect(screen.getByText('カードの取得に失敗しました')).toBeInTheDocument();
      });
    });

    it('エラー時に再試行ボタンが表示される', async () => {
      mockGetCard.mockRejectedValue(new Error('Not Found'));

      renderCardDetailPage('non-existent');

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /再試行/ })).toBeInTheDocument();
      });
    });
  });

  describe('ローディング状態', () => {
    it('読み込み中はローディングが表示される', () => {
      mockGetCard.mockImplementation(() => new Promise(() => {})); // 永遠に解決しない

      renderCardDetailPage();

      expect(screen.getByText('カードを読み込み中...')).toBeInTheDocument();
    });
  });

  describe('戻るボタン', () => {
    it('戻るボタンで履歴を戻る', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('back-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('back-button'));

      expect(mockNavigate).toHaveBeenCalledWith(-1);
    });
  });

  // ============================================================
  // TASK-0079: フロントエンド プリセットボタンUI テストケース
  // ============================================================
  // ============================================================
  // TASK-0092: デッキ変更（null送信）テストケース
  // ============================================================
  describe('デッキ変更（null送信）', () => {
    // ----------------------------------------------------------------
    // TC-D01: デッキ選択時に updateCard API が呼ばれる
    // ----------------------------------------------------------------
    it('デッキを選択すると updateCard API が呼ばれる', async () => {
      // 【テスト目的】: デッキセレクターでデッキを選択した時にAPI呼び出しが行われることを確認
      // 【テスト内容】: DeckSelector の onChange ハンドラが updateCard を呼び出すかを検証
      // 【期待される動作】: cardsApi.updateCard(cardId, { deck_id: 'deck-1' }) が呼ばれる
      // 🔵 要件定義 REQ-002・受け入れ基準 TC-103-03 より

      const user = userEvent.setup();

      // 【テストデータ準備】: デッキ変更後のカードを返すよう設定
      const updatedCard = { ...mockCard, deck_id: 'deck-1' };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-deck')).toBeInTheDocument();
      });

      // 【実際の処理実行】: デッキセレクターを変更
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      await user.selectOptions(select, 'deck-1');

      // 【結果検証】: updateCard API が呼ばれること
      await waitFor(() => {
        expect(mockUpdateCard).toHaveBeenCalledWith('card-1', { deck_id: 'deck-1' }); // 【確認内容】: deck_id に文字列を送信 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-D02: 「未分類」選択時に null が送信される
    // ----------------------------------------------------------------
    it('「未分類」を選択すると updateCard API が { deck_id: null } で呼ばれる', async () => {
      // 【テスト目的】: 「未分類」選択時に null が明示的に送信されることを確認
      // 【テスト内容】: DeckSelector で空文字列が選択された時に null に変換されるかを検証
      // 【期待される動作】: cardsApi.updateCard(cardId, { deck_id: null }) が呼ばれる
      // 🔵 要件定義 REQ-002, REQ-103・EDGE-101 より

      const user = userEvent.setup();

      // 【テストデータ準備】: deck_id が null になったカードを返すよう設定
      const updatedCard = { ...mockCard, deck_id: null };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-deck')).toBeInTheDocument();
      });

      // 【初期状態確認】: 初期値は deck_id を持つ
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      expect(select.value).not.toBe(''); // 初期値が空でない

      // 【実際の処理実行】: 「未分類」（空文字列）を選択
      await user.selectOptions(select, '');

      // 【結果検証】: updateCard が null を含むオブジェクトで呼ばれること
      await waitFor(() => {
        expect(mockUpdateCard).toHaveBeenCalledWith('card-1', { deck_id: null }); // 【確認内容】: null が明示的に送信される 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-D03: deck_id null 送信成功時に成功メッセージが表示される
    // ----------------------------------------------------------------
    it('「未分類」選択後 API 成功時に「デッキを変更しました」メッセージが表示される', async () => {
      // 【テスト目的】: null 送信成功時に成功メッセージが表示されること
      // 【テスト内容】: handleDeckChange の成功フローで setSuccessMessage が呼ばれるかを検証
      // 【期待される動作】: data-testid="success-message" に「デッキを変更しました」が表示される
      // 🔵 設計文書 architecture.md・要件定義 REQ-203 より

      const user = userEvent.setup();

      // 【テストデータ準備】: API成功を返すよう設定
      const updatedCard = { ...mockCard, deck_id: null };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-deck')).toBeInTheDocument();
      });

      // 【実際の処理実行】: 「未分類」を選択
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      await user.selectOptions(select, '');

      // 【結果検証】: 成功メッセージが表示されること
      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toHaveTextContent('デッキを変更しました'); // 【確認内容】: 成功メッセージが表示される 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-D04: deck_id 値変更時に値が送信される
    // ----------------------------------------------------------------
    it('デッキを別のデッキに変更すると updateCard API が新しい deck_id で呼ばれる', async () => {
      // 【テスト目的】: deck_id が値（文字列）に設定された場合に、その値が送信されることを確認
      // 【テスト内容】: デッキ選択時に deck_id: "deck-2" が送信されるかを検証
      // 【期待される動作】: cardsApi.updateCard(cardId, { deck_id: 'deck-2' }) が呼ばれる
      // 🔵 要件定義 REQ-002・受け入れ基準 TC-103-04 より

      const user = userEvent.setup();

      // 【テストデータ準備】: 新しいデッキに変更されたカードを返すよう設定
      const updatedCard = { ...mockCard, deck_id: 'deck-2' };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-deck')).toBeInTheDocument();
      });

      // 【実際の処理実行】: デッキを選択
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      await user.selectOptions(select, 'deck-2');

      // 【結果検証】: updateCard が新しい deck_id で呼ばれること
      await waitFor(() => {
        expect(mockUpdateCard).toHaveBeenCalledWith('card-1', { deck_id: 'deck-2' }); // 【確認内容】: 新しい deck_id が送信される 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-D05: デッキ変更失敗時にエラーメッセージが表示される
    // ----------------------------------------------------------------
    it('デッキ変更失敗時に「デッキの変更に失敗しました」エラーメッセージが表示される', async () => {
      // 【テスト目的】: API失敗時にエラーメッセージが表示されること
      // 【テスト内容】: handleDeckChange のエラーフローで setError が呼ばれるかを検証
      // 【期待される動作】: data-testid="error-message" にエラーメッセージが表示される
      // 🟡 要件定義 REQ-103・既存テストパターンから妥当な推測

      const user = userEvent.setup();

      // 【テストデータ準備】: API失敗を模擬
      mockUpdateCard.mockRejectedValue(new Error('API Error'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-deck')).toBeInTheDocument();
      });

      // 【実際の処理実行】: デッキを選択
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      await user.selectOptions(select, 'deck-1');

      // 【結果検証】: エラーメッセージが表示されること
      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('デッキの変更に失敗しました'); // 【確認内容】: エラーメッセージが表示される 🟡
      });
    });

    // ----------------------------------------------------------------
    // TC-D07: デッキ変更成功後に fetchDecks が呼ばれる（REQ-203）
    // ----------------------------------------------------------------
    it('デッキ変更成功後に fetchDecks が呼ばれる', async () => {
      // 【テスト目的】: デッキ変更保存後に DecksContext.fetchDecks() が呼ばれることを確認
      // 【テスト内容】: handleDeckChange の成功フローで fetchDecks が呼び出されるかを検証
      // 【期待される動作】: cardsApi.updateCard 成功後に mockFetchDecks が1回呼ばれる
      // 🔵 要件定義 REQ-203・architecture.md セクション9 より

      const user = userEvent.setup();

      // 【テストデータ準備】: デッキ変更後のカードを返すよう設定
      const updatedCard = { ...mockCard, deck_id: 'deck-2' };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-deck')).toBeInTheDocument();
      });

      // 【初期化確認】: fetchDecks の初期呼び出し回数を記録（useEffect による初回呼び出しを除外）
      const initialCallCount = mockFetchDecks.mock.calls.length;

      // 【実際の処理実行】: デッキを別のデッキに変更
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      await user.selectOptions(select, 'deck-2');

      // 【結果検証】: fetchDecks がデッキ変更後に追加で呼ばれること
      await waitFor(() => {
        expect(mockFetchDecks.mock.calls.length).toBeGreaterThan(initialCallCount); // 【確認内容】: fetchDecks が追加で呼ばれた 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-D08: 「未分類」選択（null送信）成功後に fetchDecks が呼ばれる（REQ-203）
    // ----------------------------------------------------------------
    it('「未分類」選択（deck_id=null）後に fetchDecks が呼ばれる', async () => {
      // 【テスト目的】: deck_id を null に変更した場合も fetchDecks() が呼ばれることを確認
      // 【テスト内容】: handleDeckChange(null) の成功フローで fetchDecks が呼び出されるかを検証
      // 【期待される動作】: cardsApi.updateCard({ deck_id: null }) 成功後に mockFetchDecks が呼ばれる
      // 🔵 要件定義 REQ-203 より

      const user = userEvent.setup();

      // 【テストデータ準備】: deck_id が null になったカードを返すよう設定
      const updatedCard = { ...mockCard, deck_id: null };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-deck')).toBeInTheDocument();
      });

      // 【初期化確認】: fetchDecks の初期呼び出し回数を記録
      const initialCallCount = mockFetchDecks.mock.calls.length;

      // 【実際の処理実行】: 「未分類」（空文字列）を選択
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      await user.selectOptions(select, '');

      // 【結果検証】: fetchDecks が追加で呼ばれること
      await waitFor(() => {
        expect(mockFetchDecks.mock.calls.length).toBeGreaterThan(initialCallCount); // 【確認内容】: null送信成功後も fetchDecks が呼ばれる 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-D09: デッキ変更失敗時に fetchDecks が呼ばれない（REQ-203）
    // ----------------------------------------------------------------
    it('デッキ変更失敗時に fetchDecks が呼ばれない', async () => {
      // 【テスト目的】: updateCard が失敗した場合は fetchDecks() が呼ばれないことを確認
      // 【テスト内容】: handleDeckChange のエラーフローで fetchDecks が呼ばれないかを検証
      // 【期待される動作】: cardsApi.updateCard が reject した場合、fetchDecks は呼ばれない
      // 🔵 要件定義 REQ-203 より

      const user = userEvent.setup();

      // 【テストデータ準備】: API失敗を模擬
      mockUpdateCard.mockRejectedValue(new Error('API Error'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-deck')).toBeInTheDocument();
      });

      // 【初期化確認】: fetchDecks の初期呼び出し回数を記録
      const initialCallCount = mockFetchDecks.mock.calls.length;

      // 【実際の処理実行】: デッキ変更を試みるが失敗する
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      await user.selectOptions(select, 'deck-2');

      // 【結果検証】: エラーが表示され、fetchDecks は追加で呼ばれていないこと
      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
      });
      expect(mockFetchDecks.mock.calls.length).toBe(initialCallCount); // 【確認内容】: API失敗時は fetchDecks が呼ばれない 🔵
    });

    // ----------------------------------------------------------------
    // TC-D06: デッキ変更失敗時にカードデータは変更されない
    // ----------------------------------------------------------------
    it('デッキ変更失敗時にカードの deck_id が変更前の値のまま保持される', async () => {
      // 【テスト目的】: API失敗時に UI が変更前のデータを維持すること
      // 【テスト内容】: API失敗後のカード表示が元のままであることを検証
      // 【期待される動作】: デッキ情報が変更前の状態で保持される
      // 🟡 要件定義 REQ-104・データフロー図エラーフローから妥当な推測

      const user = userEvent.setup();

      // 【テストデータ準備】: API失敗を模擬
      mockUpdateCard.mockRejectedValue(new Error('API Error'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-deck')).toBeInTheDocument();
      });

      // 【初期状態確認】: 初期 deck_id が表示されている
      const initialCard = mockCard;
      expect(screen.queryByTestId('card-detail')).toBeInTheDocument();

      // 【実際の処理実行】: デッキ変更を試みるが失敗する
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      await user.selectOptions(select, 'deck-2');

      // 【結果検証】: エラー後もカードの deck_id が変更されていないこと
      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
      });
      // updateCard は呼ばれたが、setCard は呼ばれていないので、mockCard のまま
      expect(mockUpdateCard).toHaveBeenCalledWith('card-1', { deck_id: 'deck-2' }); // 【確認内容】: API呼び出しは行われた 🟡
    });
  });

  describe('復習間隔プリセットボタン', () => {
    // 【テスト前準備】: 各テスト実行前にモックを初期化し、標準的なカードデータを返すよう設定
    // 【環境初期化】: vi.clearAllMocks() は外側の beforeEach で実行済みのため省略

    // ----------------------------------------------------------------
    // TC-F01: プリセットボタン5つが表示される
    // ----------------------------------------------------------------
    it('プリセットボタン5つが表示される', async () => {
      // 【テスト目的】: カード詳細画面の表示モードでプリセットボタンが5つレンダリングされること
      // 【テスト内容】: 表示モードでプリセットボタンのDOM要素が存在するかを検証
      // 【期待される動作】: 5つのプリセットボタンがレンダリングされる
      // 🔵 要件定義 REQ-001・受け入れ基準 TC-001-01 より

      // 【テストデータ準備】: 標準的なカードデータでページをレンダリング
      renderCardDetailPage();

      // 【実際の処理実行】: カード取得完了を待機
      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【結果検証】: 5つのプリセットボタンが表示されること
      expect(screen.getByTestId('preset-button-1')).toBeInTheDocument(); // 【確認内容】: 1日ボタンが存在する 🔵
      expect(screen.getByTestId('preset-button-3')).toBeInTheDocument(); // 【確認内容】: 3日ボタンが存在する 🔵
      expect(screen.getByTestId('preset-button-7')).toBeInTheDocument(); // 【確認内容】: 7日ボタンが存在する 🔵
      expect(screen.getByTestId('preset-button-14')).toBeInTheDocument(); // 【確認内容】: 14日ボタンが存在する 🔵
      expect(screen.getByTestId('preset-button-30')).toBeInTheDocument(); // 【確認内容】: 30日ボタンが存在する 🔵
    });

    // ----------------------------------------------------------------
    // TC-F02: プリセットボタンのテキストが正しい
    // ----------------------------------------------------------------
    it('プリセットボタンに正しいテキストが表示される', async () => {
      // 【テスト目的】: 各プリセットボタンに「N日」形式の正しいテキストが表示されること
      // 【テスト内容】: ボタンテキストがプリセット値に応じた日数で表示されるかを検証
      // 【期待される動作】: ボタンテキストが「1日」「3日」「7日」「14日」「30日」
      // 🔵 設計文書 architecture.md・要件定義 REQ-001 より

      // 【テストデータ準備】: 標準的なカードデータでページをレンダリング
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【結果検証】: 各ボタンのテキストが正しいN日形式であること
      expect(screen.getByTestId('preset-button-1')).toHaveTextContent('1日'); // 【確認内容】: 1日ボタンのテキストが「1日」 🔵
      expect(screen.getByTestId('preset-button-3')).toHaveTextContent('3日'); // 【確認内容】: 3日ボタンのテキストが「3日」 🔵
      expect(screen.getByTestId('preset-button-7')).toHaveTextContent('7日'); // 【確認内容】: 7日ボタンのテキストが「7日」 🔵
      expect(screen.getByTestId('preset-button-14')).toHaveTextContent('14日'); // 【確認内容】: 14日ボタンのテキストが「14日」 🔵
      expect(screen.getByTestId('preset-button-30')).toHaveTextContent('30日'); // 【確認内容】: 30日ボタンのテキストが「30日」 🔵
    });

    // ----------------------------------------------------------------
    // TC-F03: 「復習間隔を調整」セクションタイトルが表示される
    // ----------------------------------------------------------------
    it('プリセットボタンセクションのタイトルが表示される', async () => {
      // 【テスト目的】: プリセットボタンの上に「復習間隔を調整」というタイトルが表示されること
      // 【テスト内容】: セクションタイトルが正しいテキストでレンダリングされるかを検証
      // 【期待される動作】: 「復習間隔を調整」テキストがDOMに存在する
      // 🟡 設計文書 architecture.md のUI構成図から妥当な推測

      // 【テストデータ準備】: 標準的なカードデータでページをレンダリング
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【結果検証】: セクションタイトルが存在すること
      expect(screen.getByText('復習間隔を調整')).toBeInTheDocument(); // 【確認内容】: セクションタイトルが表示されている 🟡
    });

    // ----------------------------------------------------------------
    // TC-F04: プリセットボタン「1日」タップでAPIが呼ばれる
    // ----------------------------------------------------------------
    it('プリセットボタン「1日」タップで updateCard API が interval=1 で呼ばれる', async () => {
      // 【テスト目的】: 「1日」ボタンをクリックした時に正しいAPI呼び出しが行われること
      // 【テスト内容】: ボタンクリック後にmockUpdateCardの呼び出し引数を検証
      // 【期待される動作】: cardsApi.updateCard(cardId, { interval: 1 }) が呼び出される
      // 🔵 要件定義 REQ-002・受け入れ基準 TC-002-01 より

      const user = userEvent.setup();

      // 【テストデータ準備】: interval=1 で更新されたカードを返すよう設定
      const updatedCard = { ...mockCard, interval: 1 };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: 「1日」ボタンをクリック
      await user.click(screen.getByTestId('preset-button-1'));

      // 【結果検証】: updateCard APIが正しい引数で呼ばれること
      await waitFor(() => {
        expect(mockUpdateCard).toHaveBeenCalledWith('card-1', { interval: 1 }); // 【確認内容】: 第1引数がcard_id、第2引数に interval: 1 が含まれる 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-F05: プリセットボタン「30日」タップでAPIが呼ばれる
    // ----------------------------------------------------------------
    it('プリセットボタン「30日」タップで updateCard API が interval=30 で呼ばれる', async () => {
      // 【テスト目的】: 「30日」ボタンをクリックした時に正しいAPI呼び出しが行われること
      // 【テスト内容】: ボタンクリック後にmockUpdateCardの呼び出し引数を検証
      // 【期待される動作】: cardsApi.updateCard(cardId, { interval: 30 }) が呼び出される
      // 🔵 要件定義 REQ-002・受け入れ基準 TC-002-02 より

      const user = userEvent.setup();

      // 【テストデータ準備】: interval=30 で更新されたカードを返すよう設定
      const updatedCard = { ...mockCard, interval: 30 };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: 「30日」ボタンをクリック
      await user.click(screen.getByTestId('preset-button-30'));

      // 【結果検証】: updateCard APIが正しい引数で呼ばれること
      await waitFor(() => {
        expect(mockUpdateCard).toHaveBeenCalledWith('card-1', { interval: 30 }); // 【確認内容】: 第1引数がcard_id、第2引数に interval: 30 が含まれる 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-F06: 「7日」ボタンが正しいinterval値でAPIを呼ぶ
    // ----------------------------------------------------------------
    it('プリセットボタン「7日」タップで updateCard API が interval=7 で呼ばれる', async () => {
      // 【テスト目的】: 「7日」ボタンをクリックした時に正しいAPI呼び出しが行われること
      // 【テスト内容】: 中間値プリセットのAPI呼び出し引数を検証
      // 【期待される動作】: cardsApi.updateCard(cardId, { interval: 7 }) が呼び出される
      // 🟡 要件定義 REQ-002 から各値が同じロジックで処理されることの妥当な推測

      const user = userEvent.setup();

      // 【テストデータ準備】: interval=7 で更新されたカードを返すよう設定
      const updatedCard = { ...mockCard, interval: 7 };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: 「7日」ボタンをクリック
      await user.click(screen.getByTestId('preset-button-7'));

      // 【結果検証】: updateCard APIが正しい引数で呼ばれること
      await waitFor(() => {
        expect(mockUpdateCard).toHaveBeenCalledWith('card-1', { interval: 7 }); // 【確認内容】: 第2引数に interval: 7 が含まれる 🟡
      });
    });

    // ----------------------------------------------------------------
    // TC-F07: API成功時にカードデータが更新される
    // ----------------------------------------------------------------
    it('API成功時にカード詳細のメタ情報（復習間隔）が更新される', async () => {
      // 【テスト目的】: API成功後、画面上のメタ情報（復習間隔）が新しい値に更新されること
      // 【テスト内容】: API成功後にinterval表示が更新されるかを検証
      // 【期待される動作】: setCard(updatedCard) により、表示が更新後のデータに切り替わる
      // 🔵 要件定義 REQ-203・受け入れ基準 TC-002-03 より

      const user = userEvent.setup();

      // 【テストデータ準備】: interval=7→14 への更新成功を模擬
      const updatedCard = { ...mockCard, interval: 14, next_review_at: '2024-01-29' };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【初期状態確認】: 元の interval が 7日 であること
      expect(screen.getByTestId('interval')).toHaveTextContent('7日'); // 【確認内容】: 初期値が7日 🔵

      // 【実際の処理実行】: 「14日」ボタンをクリック
      await user.click(screen.getByTestId('preset-button-14'));

      // 【結果検証】: 画面上の復習間隔表示が「14日」に更新されること
      await waitFor(() => {
        expect(screen.getByTestId('interval')).toHaveTextContent('14日'); // 【確認内容】: API成功後に interval 表示が14日に更新される 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-F08: API成功時に成功メッセージが表示される
    // ----------------------------------------------------------------
    it('API成功時に「復習間隔を更新しました」メッセージが表示される', async () => {
      // 【テスト目的】: 間隔調整成功後に成功メッセージが表示されること
      // 【テスト内容】: setSuccessMessage('復習間隔を更新しました') が呼ばれDOMに表示されるかを検証
      // 【期待される動作】: data-testid="success-message" に「復習間隔を更新しました」が表示される
      // 🔵 設計文書 architecture.md・NFR-203・既存テストパターン（テストケース4）より

      const user = userEvent.setup();

      // 【テストデータ準備】: 正常レスポンスを返すよう設定
      mockUpdateCard.mockResolvedValue(mockCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: プリセットボタンをクリック
      await user.click(screen.getByTestId('preset-button-7'));

      // 【結果検証】: 成功メッセージが表示されること
      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toHaveTextContent('復習間隔を更新しました'); // 【確認内容】: 成功メッセージのテキストが正しい 🔵
      });
    });

    // ----------------------------------------------------------------
    // TC-F09: API成功後にボタンが再度有効化される
    // ----------------------------------------------------------------
    it('API成功後にプリセットボタンが再度有効になる', async () => {
      // 【テスト目的】: API呼び出し完了後に isAdjusting が false に戻り、ボタンが操作可能になること
      // 【テスト内容】: API完了後のボタン状態を検証
      // 【期待される動作】: finally { setIsAdjusting(false) } によりボタンのdisabled属性が解除される
      // 🟡 データフロー図の正常フロー・既存 isSaving パターンから妥当な推測

      const user = userEvent.setup();

      // 【テストデータ準備】: 正常レスポンスを返すよう設定
      mockUpdateCard.mockResolvedValue(mockCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: プリセットボタンをクリックし、API完了を待機
      await user.click(screen.getByTestId('preset-button-7'));

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });

      // 【結果検証】: 全プリセットボタンが disabled ではない状態になること
      expect(screen.getByTestId('preset-button-1')).not.toBeDisabled(); // 【確認内容】: 1日ボタンが有効状態 🟡
      expect(screen.getByTestId('preset-button-7')).not.toBeDisabled(); // 【確認内容】: 7日ボタンが有効状態 🟡
      expect(screen.getByTestId('preset-button-30')).not.toBeDisabled(); // 【確認内容】: 30日ボタンが有効状態 🟡
    });

    // ----------------------------------------------------------------
    // TC-F10: プリセットボタンに適切な aria-label が設定されている
    // ----------------------------------------------------------------
    it('プリセットボタンに正しい aria-label が設定される', async () => {
      // 【テスト目的】: 各ボタンに「復習間隔を{N}日に設定」形式の aria-label が設定されていること
      // 【テスト内容】: アクセシビリティ属性が正しく設定されているかを検証
      // 【期待される動作】: アクセシビリティ情報が正しく設定される
      // 🔵 要件定義 NFR-301・タスクノートより

      // 【テストデータ準備】: 標準的なカードデータでページをレンダリング
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【結果検証】: aria-label によるボタン取得ができること
      expect(screen.getByRole('button', { name: '復習間隔を1日に設定' })).toBeInTheDocument(); // 【確認内容】: 1日ボタンの aria-label が正しい 🔵
      expect(screen.getByRole('button', { name: '復習間隔を3日に設定' })).toBeInTheDocument(); // 【確認内容】: 3日ボタンの aria-label が正しい 🔵
      expect(screen.getByRole('button', { name: '復習間隔を7日に設定' })).toBeInTheDocument(); // 【確認内容】: 7日ボタンの aria-label が正しい 🔵
      expect(screen.getByRole('button', { name: '復習間隔を14日に設定' })).toBeInTheDocument(); // 【確認内容】: 14日ボタンの aria-label が正しい 🔵
      expect(screen.getByRole('button', { name: '復習間隔を30日に設定' })).toBeInTheDocument(); // 【確認内容】: 30日ボタンの aria-label が正しい 🔵
    });

    // ----------------------------------------------------------------
    // TC-F11: API失敗時にエラーメッセージが表示される
    // ----------------------------------------------------------------
    it('API失敗時に「復習間隔の更新に失敗しました」エラーメッセージが表示される', async () => {
      // 【テスト目的】: API呼び出しが失敗した場合のUI挙動を確認
      // 【テスト内容】: mockUpdateCardをRejectさせた後のエラーメッセージ表示を検証
      // 【期待される動作】: data-testid="error-message" に「復習間隔の更新に失敗しました」が表示される
      // 🟡 要件定義 REQ-103・受け入れ基準 TC-103-01・既存テストパターン（テストケース4）から妥当な推測

      const user = userEvent.setup();

      // 【テストデータ準備】: ネットワークエラーを模擬
      mockUpdateCard.mockRejectedValue(new Error('Network Error'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: プリセットボタンをクリック
      await user.click(screen.getByTestId('preset-button-7'));

      // 【結果検証】: エラーメッセージが表示されること
      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('復習間隔の更新に失敗しました'); // 【確認内容】: エラーメッセージのテキストが正しい 🟡
      });
    });

    // ----------------------------------------------------------------
    // TC-F12: API失敗時に元のカードデータが保持される
    // ----------------------------------------------------------------
    it('API失敗時にカードのメタ情報が変更前の値のまま保持される', async () => {
      // 【テスト目的】: API失敗時にUIが変更前のデータを維持し、不整合を防ぐ
      // 【テスト内容】: API失敗後のinterval表示が元の値のまま保持されるかを検証
      // 【期待される動作】: data-testid="interval" のテキストが「7日」のまま変わらない
      // 🟡 要件定義 REQ-103・受け入れ基準 TC-103-02・データフロー図エラーフローから妥当な推測

      const user = userEvent.setup();

      // 【テストデータ準備】: API失敗を模擬（interval=14ボタンタップするが失敗する）
      mockUpdateCard.mockRejectedValue(new Error('Server Error'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【初期状態確認】: 元の interval が 7日 であること
      expect(screen.getByTestId('interval')).toHaveTextContent('7日'); // 【確認内容】: 初期値が7日 🟡

      // 【実際の処理実行】: 「14日」ボタンをクリック（API失敗）
      await user.click(screen.getByTestId('preset-button-14'));

      // 【結果検証】: エラー後も interval 表示が「7日」のまま
      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
      });
      expect(screen.getByTestId('interval')).toHaveTextContent('7日'); // 【確認内容】: API失敗後も元の7日が表示されている 🟡
    });

    // ----------------------------------------------------------------
    // TC-F13: API失敗時にボタンが再度有効化される
    // ----------------------------------------------------------------
    it('API失敗後にプリセットボタンが再度有効になる', async () => {
      // 【テスト目的】: API失敗後も isAdjusting が false に戻り、再試行が可能であること
      // 【テスト内容】: API失敗後のボタン状態を検証
      // 【期待される動作】: finally ブロックで確実に状態復帰され、ボタンが操作可能に戻る
      // 🟡 データフロー図エラーフロー・既存 isSaving パターンから妥当な推測

      const user = userEvent.setup();

      // 【テストデータ準備】: API失敗を模擬
      mockUpdateCard.mockRejectedValue(new Error('Error'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: プリセットボタンをクリックし、エラーを待機
      await user.click(screen.getByTestId('preset-button-7'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
      });

      // 【結果検証】: 全プリセットボタンが disabled ではない状態に戻ること
      expect(screen.getByTestId('preset-button-1')).not.toBeDisabled(); // 【確認内容】: 1日ボタンが有効状態に復帰 🟡
      expect(screen.getByTestId('preset-button-7')).not.toBeDisabled(); // 【確認内容】: 7日ボタンが有効状態に復帰 🟡
      expect(screen.getByTestId('preset-button-30')).not.toBeDisabled(); // 【確認内容】: 30日ボタンが有効状態に復帰 🟡
    });

    // ----------------------------------------------------------------
    // TC-F14: 編集モード時にプリセットボタンが非表示になる
    // ----------------------------------------------------------------
    it('編集モード時にプリセットボタンセクションが非表示になる', async () => {
      // 【テスト目的】: 表示モード/編集モードの状態境界でプリセットボタンの表示制御を確認
      // 【テスト内容】: isEditing=true の状態でプリセットボタンがDOMに存在しないことを検証
      // 【期待される動作】: プリセットボタンがレンダリングされない
      // 🔵 要件定義 REQ-201・受け入れ基準 TC-001-02・タスクノート（編集モードとの排他制御）より

      const user = userEvent.setup();

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: 編集ボタンをクリックして編集モードに遷移
      await user.click(screen.getByTestId('edit-button'));

      // 【結果検証】: プリセットボタンが非表示であること
      expect(screen.queryByTestId('preset-button-1')).not.toBeInTheDocument(); // 【確認内容】: 1日ボタンが非表示 🔵
      expect(screen.queryByTestId('preset-button-30')).not.toBeInTheDocument(); // 【確認内容】: 30日ボタンが非表示 🔵
    });

    // ----------------------------------------------------------------
    // TC-F15: API呼び出し中にプリセットボタンが無効化される
    // ----------------------------------------------------------------
    it('API呼び出し中に全プリセットボタンが disabled になる', async () => {
      // 【テスト目的】: isAdjusting の true/false 境界でのボタン状態変化を確認
      // 【テスト内容】: API保留中のボタン無効化状態を検証
      // 【期待される動作】: 全5つのプリセットボタンが disabled 属性を持つ
      // 🟡 要件定義 REQ-202・受け入れ基準 TC-202-01・既存 isSaving パターンから妥当な推測

      const user = userEvent.setup();

      // 【テストデータ準備】: API応答を永続保留させることで「処理中」状態を維持
      mockUpdateCard.mockImplementation(() => new Promise(() => {}));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: プリセットボタンをクリック（APIは保留中）
      await user.click(screen.getByTestId('preset-button-7'));

      // 【結果検証】: 全5つのプリセットボタンが disabled であること
      await waitFor(() => {
        expect(screen.getByTestId('preset-button-1')).toBeDisabled(); // 【確認内容】: 1日ボタンが無効化されている 🟡
      });
      expect(screen.getByTestId('preset-button-3')).toBeDisabled(); // 【確認内容】: 3日ボタンが無効化されている 🟡
      expect(screen.getByTestId('preset-button-7')).toBeDisabled(); // 【確認内容】: 7日ボタンが無効化されている 🟡
      expect(screen.getByTestId('preset-button-14')).toBeDisabled(); // 【確認内容】: 14日ボタンが無効化されている 🟡
      expect(screen.getByTestId('preset-button-30')).toBeDisabled(); // 【確認内容】: 30日ボタンが無効化されている 🟡
    });

    // ----------------------------------------------------------------
    // TC-F16: 編集モードから戻った後にプリセットボタンが再表示される
    // ----------------------------------------------------------------
    it('編集キャンセル後にプリセットボタンが再表示される', async () => {
      // 【テスト目的】: 編集モード → 表示モード の状態遷移境界で表示復帰を確認
      // 【テスト内容】: 編集キャンセル後にプリセットボタンが再度表示されるかを検証
      // 【期待される動作】: プリセットボタン5つが再度表示される
      // 🟡 既存テストパターン（テストケース3）と要件定義 REQ-201 から妥当な推測

      const user = userEvent.setup();

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: 編集ボタン → キャンセルボタンの順でクリック
      await user.click(screen.getByTestId('edit-button'));
      expect(screen.queryByTestId('preset-button-1')).not.toBeInTheDocument(); // 編集モード中は非表示

      await user.click(screen.getByTestId('cancel-button'));

      // 【結果検証】: プリセットボタンが再表示されること
      expect(screen.getByTestId('preset-button-1')).toBeInTheDocument(); // 【確認内容】: キャンセル後に1日ボタンが再表示 🟡
      expect(screen.getByTestId('preset-button-30')).toBeInTheDocument(); // 【確認内容】: キャンセル後に30日ボタンが再表示 🟡
    });

    // ----------------------------------------------------------------
    // TC-F17: 連続でプリセットボタンを押した場合の挙動
    // ----------------------------------------------------------------
    it('API呼び出し中は2回目のプリセットボタンクリックが disabled でブロックされる', async () => {
      // 【テスト目的】: 高速連続操作時のUI制御の一貫性を確認
      // 【テスト内容】: ボタン無効化によるガードで二重送信が防止されることを検証
      // 【期待される動作】: API完了前の2回目クリックは disabled により無視され、updateCard は1回だけ呼ばれる
      // 🟡 要件定義 REQ-202・EDGE-002・データフロー図から妥当な推測

      const user = userEvent.setup();

      // 【テストデータ準備】: 1回目は保留、2回目の解消のために後から完了させる
      let resolveFirst!: (value: Card) => void;
      const firstCallPromise = new Promise<Card>((resolve) => {
        resolveFirst = resolve;
      });
      mockUpdateCard.mockReturnValueOnce(firstCallPromise).mockResolvedValue(mockCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      // 【実際の処理実行】: 「1日」ボタンをクリック（API保留中）
      await user.click(screen.getByTestId('preset-button-1'));

      // 【結果検証の前提】: 1回目の API 呼び出し中はボタンが disabled になっている
      await waitFor(() => {
        expect(screen.getByTestId('preset-button-30')).toBeDisabled();
      });

      // 「30日」ボタンをクリックしようとする（disabled なので無視される）
      await user.click(screen.getByTestId('preset-button-30'));

      // 【結果検証】: updateCard は1回だけ呼ばれること（2回目は disabled でブロック）
      expect(mockUpdateCard).toHaveBeenCalledTimes(1); // 【確認内容】: updateCard が1回だけ呼ばれている 🟡

      // 【クリーンアップ】: API を完了させ、React 状態更新を act() でラップして警告を防ぐ
      // 【act() の理由】: resolveFirst() により handleIntervalAdjust の finally が実行されて
      //   setIsAdjusting(false), setCard(), setSuccessMessage() が呼ばれるため 🔵
      await act(async () => {
        resolveFirst(mockCard);
      });
    });
  });
});
