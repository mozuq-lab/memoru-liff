/**
 * 【テスト概要】: DecksContext のテスト
 * 【テスト対象】: DecksProvider, useDecksContext
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { DecksProvider, useDecksContext } from '@/contexts/DecksContext';
import { decksApi } from '@/services/api';
import type { Deck } from '@/types';
import type { ReactNode } from 'react';

// Mock the decksApi
vi.mock('@/services/api', () => ({
  decksApi: {
    getDecks: vi.fn(),
    createDeck: vi.fn(),
    updateDeck: vi.fn(),
    deleteDeck: vi.fn(),
  },
}));

const mockDeck: Deck = {
  deck_id: 'deck-1',
  user_id: 'user-1',
  name: 'テストデッキ',
  description: 'テスト説明',
  color: '#FF5733',
  card_count: 10,
  due_count: 3,
  created_at: '2024-01-01T00:00:00Z',
};

describe('DecksContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // getDecks returns Deck[] (api.ts extracts response.decks internally)
    vi.mocked(decksApi.getDecks).mockResolvedValue([mockDeck]);
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <DecksProvider>{children}</DecksProvider>
  );

  describe('Context 値の提供', () => {
    it('Context が正しい値を提供すること', () => {
      const { result } = renderHook(() => useDecksContext(), { wrapper });

      expect(result.current).toHaveProperty('decks');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('fetchDecks');
      expect(result.current).toHaveProperty('createDeck');
      expect(result.current).toHaveProperty('updateDeck');
      expect(result.current).toHaveProperty('deleteDeck');
    });

    it('Provider の外で使われた場合にエラーをスローすること', () => {
      expect(() => {
        renderHook(() => useDecksContext());
      }).toThrow('useDecksContext must be used within a DecksProvider');
    });
  });

  describe('fetchDecks', () => {
    it('デッキ一覧を取得できること', async () => {
      const { result } = renderHook(() => useDecksContext(), { wrapper });

      await act(async () => {
        await result.current.fetchDecks();
      });

      await waitFor(() => {
        expect(result.current.decks).toEqual([mockDeck]);
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('取得エラー時に error がセットされること', async () => {
      vi.mocked(decksApi.getDecks).mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useDecksContext(), { wrapper });

      await act(async () => {
        await result.current.fetchDecks();
      });

      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('createDeck', () => {
    it('デッキを作成できること', async () => {
      const newDeck: Deck = { ...mockDeck, deck_id: 'deck-new', name: '新デッキ' };
      vi.mocked(decksApi.createDeck).mockResolvedValueOnce(newDeck);

      const { result } = renderHook(() => useDecksContext(), { wrapper });

      await act(async () => {
        const created = await result.current.createDeck({ name: '新デッキ' });
        expect(created.name).toBe('新デッキ');
      });

      // 作成後に fetchDecks が再呼出しされている
      expect(decksApi.getDecks).toHaveBeenCalled();
    });

    it('作成エラー時に例外がスローされること', async () => {
      vi.mocked(decksApi.createDeck).mockRejectedValueOnce(new Error('Create failed'));

      const { result } = renderHook(() => useDecksContext(), { wrapper });

      await expect(
        act(async () => {
          await result.current.createDeck({ name: 'テスト' });
        })
      ).rejects.toThrow('Create failed');
    });
  });

  describe('updateDeck', () => {
    it('デッキを更新できること', async () => {
      const updatedDeck: Deck = { ...mockDeck, name: '更新名' };
      vi.mocked(decksApi.updateDeck).mockResolvedValueOnce(updatedDeck);

      const { result } = renderHook(() => useDecksContext(), { wrapper });

      await act(async () => {
        const updated = await result.current.updateDeck('deck-1', { name: '更新名' });
        expect(updated.name).toBe('更新名');
      });

      expect(decksApi.getDecks).toHaveBeenCalled();
    });

    it('更新エラー時に例外がスローされること', async () => {
      vi.mocked(decksApi.updateDeck).mockRejectedValueOnce(new Error('Update failed'));

      const { result } = renderHook(() => useDecksContext(), { wrapper });

      await expect(
        act(async () => {
          await result.current.updateDeck('deck-1', { name: '更新' });
        })
      ).rejects.toThrow('Update failed');
    });
  });

  describe('deleteDeck', () => {
    it('デッキを削除できること', async () => {
      vi.mocked(decksApi.deleteDeck).mockResolvedValueOnce(undefined);

      const { result } = renderHook(() => useDecksContext(), { wrapper });

      await act(async () => {
        await result.current.deleteDeck('deck-1');
      });

      expect(decksApi.deleteDeck).toHaveBeenCalledWith('deck-1');
      expect(decksApi.getDecks).toHaveBeenCalled();
    });

    it('削除エラー時に例外がスローされること', async () => {
      vi.mocked(decksApi.deleteDeck).mockRejectedValueOnce(new Error('Delete failed'));

      const { result } = renderHook(() => useDecksContext(), { wrapper });

      await expect(
        act(async () => {
          await result.current.deleteDeck('deck-1');
        })
      ).rejects.toThrow('Delete failed');
    });
  });

  describe('関数のメモ化', () => {
    it('fetchDecks が useCallback でメモ化されていること', () => {
      const { result, rerender } = renderHook(() => useDecksContext(), { wrapper });
      const first = result.current.fetchDecks;
      rerender();
      expect(result.current.fetchDecks).toBe(first);
    });
  });
});
