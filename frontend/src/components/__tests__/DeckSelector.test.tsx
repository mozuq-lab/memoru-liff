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
});
