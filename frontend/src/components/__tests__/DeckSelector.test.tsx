/**
 * 【テスト概要】: DeckSelector コンポーネントのテスト
 * 【テスト対象】: DeckSelector コンポーネント
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DeckSelector } from '../DeckSelector';
import type { Deck } from '@/types';

// DecksContext モック
const mockDecks: Deck[] = [
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

const mockDecksContext = {
  decks: mockDecks,
  isLoading: false,
  error: null,
  fetchDecks: vi.fn(),
  createDeck: vi.fn(),
  updateDeck: vi.fn(),
  deleteDeck: vi.fn(),
};

vi.mock('@/contexts/DecksContext', () => ({
  useDecksContext: () => mockDecksContext,
}));

const renderDeckSelector = (props: {
  value?: string | null;
  onChange: (deckId: string | null) => void;
  disabled?: boolean;
}) => {
  return render(
    <MemoryRouter>
      <DeckSelector {...props} />
    </MemoryRouter>
  );
};

describe('DeckSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDecksContext.decks = mockDecks;
  });

  describe('表示テスト', () => {
    it('「未分類」オプションが表示される', () => {
      const onChange = vi.fn();
      renderDeckSelector({ value: null, onChange });

      const select = screen.getByRole('combobox');
      expect(select).toBeInTheDocument();

      const options = screen.getAllByRole('option');
      expect(options[0]).toHaveTextContent('未分類');
    });

    it('デッキ一覧がオプションとして表示される', () => {
      const onChange = vi.fn();
      renderDeckSelector({ value: null, onChange });

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(3); // 未分類 + 2デッキ
      expect(options[1]).toHaveTextContent('英語');
      expect(options[2]).toHaveTextContent('数学');
    });

    it('「unassigned」疑似デッキはオプションから除外される', () => {
      mockDecksContext.decks = [
        ...mockDecks,
        {
          deck_id: 'unassigned',
          user_id: 'user-1',
          name: '未分類',
          color: '#9CA3AF',
          card_count: 2,
          due_count: 0,
          created_at: '2024-01-01T00:00:00Z',
        },
      ];

      const onChange = vi.fn();
      renderDeckSelector({ value: null, onChange });

      const options = screen.getAllByRole('option');
      // 未分類 (select option) + 英語 + 数学 = 3 (unassigned pseudo-deck excluded)
      expect(options).toHaveLength(3);
    });
  });

  describe('選択テスト', () => {
    it('デッキを選択すると onChange が呼ばれる', () => {
      const onChange = vi.fn();
      renderDeckSelector({ value: null, onChange });

      const select = screen.getByRole('combobox');
      fireEvent.change(select, { target: { value: 'deck-1' } });

      expect(onChange).toHaveBeenCalledWith('deck-1');
    });

    it('「未分類」を選択すると onChange が null で呼ばれる', () => {
      const onChange = vi.fn();
      renderDeckSelector({ value: 'deck-1', onChange });

      const select = screen.getByRole('combobox');
      fireEvent.change(select, { target: { value: '' } });

      expect(onChange).toHaveBeenCalledWith(null);
    });

    it('value が指定されている場合、対応するオプションが選択される', () => {
      const onChange = vi.fn();
      renderDeckSelector({ value: 'deck-2', onChange });

      const select = screen.getByRole('combobox') as HTMLSelectElement;
      expect(select.value).toBe('deck-2');
    });
  });

  describe('無効化テスト', () => {
    it('disabled=true の場合、select が無効化される', () => {
      const onChange = vi.fn();
      renderDeckSelector({ value: null, onChange, disabled: true });

      const select = screen.getByRole('combobox');
      expect(select).toBeDisabled();
    });
  });

  // ============================================================
  // TASK-0092: null値ハンドリングテスト
  // ============================================================
  describe('null値ハンドリング', () => {
    // ----------------------------------------------------------------
    // TC-N01: value が null の場合、「未分類」が選択状態になる
    // ----------------------------------------------------------------
    it('value=null の場合、「未分類」（空文字列）が選択される', () => {
      // 【テスト目的】: null 値が正しく空文字列の option にマッピングされることを確認
      // 【テスト内容】: value={null} を指定した時に select 要素の value が '' になるかを検証
      // 【期待される動作】: select.value === ''
      // 🔵 要件定義 REQ-002・受け入れ基準 TC-103-05 より

      const onChange = vi.fn();
      renderDeckSelector({ value: null, onChange });

      const select = screen.getByRole('combobox') as HTMLSelectElement;
      expect(select.value).toBe(''); // 【確認内容】: null が空文字列にマッピングされている 🔵
    });

    // ----------------------------------------------------------------
    // TC-N02: value が undefined の場合、「未分類」が選択状態になる
    // ----------------------------------------------------------------
    it('value=undefined の場合、「未分類」（空文字列）が選択される', () => {
      // 【テスト目的】: undefined 値が正しく空文字列の option にマッピングされることを確認
      // 【テスト内容】: value={undefined} を指定した時に select 要素の value が '' になるかを検証
      // 【期待される動作】: select.value === ''
      // 🔵 要件定義 REQ-104・受け入れ基準 TC-104-01 より

      const onChange = vi.fn();
      renderDeckSelector({ value: undefined, onChange });

      const select = screen.getByRole('combobox') as HTMLSelectElement;
      expect(select.value).toBe(''); // 【確認内容】: undefined が空文字列にマッピングされている 🔵
    });

    // ----------------------------------------------------------------
    // TC-N03: 「未分類」から通常デッキへの変更で値が送信される
    // ----------------------------------------------------------------
    it('「未分類」から通常デッキに変更すると onChange が deck_id で呼ばれる', () => {
      // 【テスト目的】: null 値から deck_id 文字列への変更が正しく handleChange に反映されること
      // 【テスト内容】: 「未分類」→「英語」への変更時に onChange('deck-1') が呼ばれるかを検証
      // 【期待される動作】: onChange が deck_id 値で呼ばれる
      // 🔵 要件定義 REQ-002・受け入れ基準 TC-103-06 より

      const onChange = vi.fn();
      renderDeckSelector({ value: null, onChange });

      const select = screen.getByRole('combobox');
      fireEvent.change(select, { target: { value: 'deck-1' } });

      expect(onChange).toHaveBeenCalledWith('deck-1'); // 【確認内容】: deck_id が送信される 🔵
    });

    // ----------------------------------------------------------------
    // TC-N04: 通常デッキから「未分類」への変更で null が送信される
    // ----------------------------------------------------------------
    it('通常デッキから「未分類」に変更すると onChange が null で呼ばれる', () => {
      // 【テスト目的】: deck_id 値から null への明示的な変更が handleChange に反映されること
      // 【テスト内容】: 「英語」→「未分類」への変更時に onChange(null) が呼ばれるかを検証
      // 【期待される動作】: onChange が null で呼ばれる
      // 🔵 要件定義 REQ-002・EDGE-101 より

      const onChange = vi.fn();
      renderDeckSelector({ value: 'deck-1', onChange });

      const select = screen.getByRole('combobox');
      fireEvent.change(select, { target: { value: '' } });

      expect(onChange).toHaveBeenCalledWith(null); // 【確認内容】: null が明示的に送信される 🔵
    });
  });
});
