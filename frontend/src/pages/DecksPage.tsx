import { useEffect, useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useDecksContext } from '@/contexts/DecksContext';
import { useCardsContext } from '@/contexts/CardsContext';
import { Navigation } from '@/components/Navigation';
import { DeckFormModal } from '@/components/DeckFormModal';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import type { Deck, CreateDeckRequest, UpdateDeckRequest } from '@/types';

/**
 * デッキ管理ページ
 * デッキの一覧表示・作成・編集・削除を行う。
 * 削除時はカードを未分類に移動し、カード一覧を再取得する。
 */
export const DecksPage = () => {
  const navigate = useNavigate();
  const { decks, isLoading, error, fetchDecks, createDeck, updateDeck, deleteDeck } = useDecksContext();
  const { cards, fetchCards } = useCardsContext();

  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [editingDeck, setEditingDeck] = useState<Deck | undefined>(undefined);
  const [deletingDeckId, setDeletingDeckId] = useState<string | null>(null);

  /** マウント時にデッキ一覧とカード一覧を取得する */
  useEffect(() => {
    fetchDecks();
    fetchCards();
  }, [fetchDecks, fetchCards]);

  /** deck_id を持たないカード（未分類）の件数 */
  const uncategorizedCount = cards.filter((c) => !c.deck_id).length;

  /** デッキ作成モーダルを開く */
  const handleCreate = useCallback(() => {
    setModalMode('create');
    setEditingDeck(undefined);
    setModalOpen(true);
  }, []);

  /**
   * デッキ編集モーダルを開く
   * @param deck - 編集対象のデッキ
   */
  const handleEdit = useCallback((deck: Deck) => {
    setModalMode('edit');
    setEditingDeck(deck);
    setModalOpen(true);
  }, []);

  /**
   * モーダルのフォーム送信ハンドラ
   * modalMode に応じて createDeck または updateDeck を呼び出す。
   */
  const handleFormSubmit = useCallback(
    async (data: CreateDeckRequest | UpdateDeckRequest) => {
      if (modalMode === 'create') {
        await createDeck(data as CreateDeckRequest);
      } else if (editingDeck) {
        await updateDeck(editingDeck.deck_id, data as UpdateDeckRequest);
      }
    },
    [modalMode, editingDeck, createDeck, updateDeck]
  );

  /**
   * デッキ削除を確定する
   * 削除後にカード一覧を再取得して deck_id が null に更新されたカードを反映する。
   */
  const handleDeleteConfirm = useCallback(async () => {
    if (!deletingDeckId) return;
    try {
      await deleteDeck(deletingDeckId);
      await fetchCards(); // カード一覧を再取得（deck_idがnullに更新されるため）
    } catch {
      // エラーは Context で処理
    }
    setDeletingDeckId(null);
  }, [deletingDeckId, deleteDeck, fetchCards]);

  // ローディング表示
  if (isLoading && decks.length === 0) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center">
          <Loading message="デッキを読み込み中..." />
        </div>
        <Navigation />
      </div>
    );
  }

  // エラー表示
  if (error) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center p-4">
          <Error message="デッキの取得に失敗しました" onRetry={fetchDecks} />
        </div>
        <Navigation />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen pb-20">
      {/* ヘッダー */}
      <header className="bg-white shadow-sm p-4 mb-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-800" data-testid="decks-title">デッキ</h1>
            <p className="text-sm text-gray-600" data-testid="deck-count">
              {decks.length}個のデッキ
            </p>
          </div>
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 active:bg-blue-800 transition-colors min-h-[44px]"
            data-testid="create-deck-button"
          >
            + 新規作成
          </button>
        </div>
      </header>

      <main className="flex-1 px-4 mt-4">
        {decks.length === 0 ? (
          /* 空状態 */
          <div className="text-center py-12" data-testid="empty-state">
            <svg
              className="mx-auto h-16 w-16 text-gray-400 mb-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              />
            </svg>
            <p className="text-gray-600 mb-4">
              デッキを作成して学習を整理しましょう
            </p>
            <button
              onClick={handleCreate}
              className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 min-h-[44px] transition-colors font-medium"
            >
              最初のデッキを作成
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {/* デッキ一覧 */}
            {decks.map((deck) => (
              <div
                key={deck.deck_id}
                className="bg-white rounded-lg shadow p-4"
                data-testid={`deck-card-${deck.deck_id}`}
              >
                <div className="flex items-start gap-3">
                  {/* カラーインジケーター */}
                  <div
                    className="w-3 h-full min-h-[60px] rounded-full flex-shrink-0 mt-0.5"
                    style={{ backgroundColor: deck.color ?? '#D1D5DB' }}
                    aria-hidden="true"
                  />

                  {/* メイン情報 */}
                  <div className="flex-1 min-w-0">
                    <button
                      onClick={() => navigate(`/cards?deck_id=${deck.deck_id}`)}
                      className="text-left w-full"
                    >
                      <h3 className="text-base font-semibold text-gray-800 truncate">
                        {deck.name}
                      </h3>
                      {deck.description && (
                        <p className="text-sm text-gray-500 mt-0.5 line-clamp-2">
                          {deck.description}
                        </p>
                      )}
                    </button>

                    {/* カード数・due 数バッジ */}
                    <div className="flex items-center gap-3 mt-2">
                      <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                        {deck.card_count}枚
                      </span>
                      {deck.due_count > 0 && (
                        <span className="text-xs text-orange-700 bg-orange-100 px-2 py-0.5 rounded-full font-medium">
                          復習 {deck.due_count}枚
                        </span>
                      )}
                    </div>
                  </div>

                  {/* アクションボタン */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {/* 復習ボタン */}
                    {deck.due_count > 0 && (
                      <Link
                        to={`/review?deck_id=${deck.deck_id}`}
                        className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
                        aria-label={`${deck.name}を復習`}
                        data-testid={`review-deck-${deck.deck_id}`}
                      >
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </Link>
                    )}
                    {/* 編集ボタン */}
                    <button
                      onClick={() => handleEdit(deck)}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded-lg transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
                      aria-label={`${deck.name}を編集`}
                      data-testid={`edit-deck-${deck.deck_id}`}
                    >
                      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    {/* 削除ボタン */}
                    <button
                      onClick={() => setDeletingDeckId(deck.deck_id)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
                      aria-label={`${deck.name}を削除`}
                      data-testid={`delete-deck-${deck.deck_id}`}
                    >
                      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {/* 未分類セクション */}
            <div
              className="bg-gray-50 rounded-lg border border-gray-200 p-4"
              data-testid="uncategorized-section"
            >
              <button
                onClick={() => navigate('/cards')}
                className="flex items-center justify-between w-full text-left"
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-3 min-h-[40px] rounded-full bg-gray-300 flex-shrink-0"
                    aria-hidden="true"
                  />
                  <div>
                    <h3 className="text-base font-medium text-gray-600">未分類</h3>
                    <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded-full">
                      {uncategorizedCount}枚
                    </span>
                  </div>
                </div>
                <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </main>

      {/* デッキ作成・編集モーダル */}
      <DeckFormModal
        mode={modalMode}
        deck={editingDeck}
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleFormSubmit}
      />

      {/* 削除確認ダイアログ */}
      {deletingDeckId && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setDeletingDeckId(null); }}
          data-testid="delete-confirm-overlay"
        >
          <div className="bg-white rounded-xl w-full max-w-sm shadow-xl p-6" data-testid="delete-confirm-dialog">
            <h3 className="text-lg font-bold text-gray-800 mb-2">デッキを削除</h3>
            <p className="text-sm text-gray-600 mb-1">
              「{decks.find((d) => d.deck_id === deletingDeckId)?.name}」を削除しますか？
            </p>
            <p className="text-xs text-gray-500 mb-6">
              デッキ内のカードは削除されず、未分類に移動します。
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeletingDeckId(null)}
                className="flex-1 py-3 px-4 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 active:bg-gray-100 transition-colors min-h-[44px] font-medium"
              >
                キャンセル
              </button>
              <button
                onClick={handleDeleteConfirm}
                className="flex-1 py-3 px-4 bg-red-600 text-white rounded-lg hover:bg-red-700 active:bg-red-800 transition-colors min-h-[44px] font-medium"
                data-testid="delete-confirm-button"
              >
                削除
              </button>
            </div>
          </div>
        </div>
      )}

      <Navigation />
    </div>
  );
};
