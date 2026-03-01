/**
 * 【機能概要】: カード詳細・編集画面
 * 【実装方針】: カードの表示、編集、削除機能を提供
 * 【テスト対応】: TASK-0017 テストケース1〜9
 * 🟡 黄信号: user-stories.md 3.3より
 */
import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { CardForm } from '@/components/CardForm';
import { DeckSelector } from '@/components/DeckSelector';
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import { cardsApi } from '@/services/api';
import { useDecksContext } from '@/contexts/DecksContext';
import type { Card } from '@/types';
import { formatDueDate, getDueStatus } from '@/utils/date';

/**
 * 【設定定数】: 復習間隔のプリセット値（日数）
 * 【調整可能性】: 要件変更時はこの定数を変更するだけでUIに反映される
 * 🔵 青信号: タスクノートのUI設計・要件定義 REQ-001 に明記されたプリセット値
 */
const INTERVAL_PRESET_DAYS = [1, 3, 7, 14, 30] as const;

/**
 * 【機能概要】: カード詳細ページコンポーネント
 */
export const CardDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { decks, fetchDecks } = useDecksContext();
  const [card, setCard] = useState<Card | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  // 【状態追加】: 復習間隔調整APIの呼び出し中かどうかを管理する。プリセットボタンの disabled 制御に使用 🔵
  const [isAdjusting, setIsAdjusting] = useState(false);

  // デッキ一覧を取得
  useEffect(() => {
    fetchDecks();
  }, [fetchDecks]);

  // 【カード取得】
  const fetchCard = useCallback(async () => {
    if (!id) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await cardsApi.getCard(id);
      setCard(data);
    } catch (err) {
      setError('カードの取得に失敗しました');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchCard();
  }, [fetchCard]);

  // 【成功メッセージの自動非表示】
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // 【保存ハンドラ】
  const handleSave = async (front: string, back: string) => {
    if (!id) return;

    setIsSaving(true);
    setError(null);

    try {
      const updatedCard = await cardsApi.updateCard(id, { front, back });
      setCard(updatedCard);
      setIsEditing(false);
      setSuccessMessage('カードを保存しました');
    } catch (err) {
      setError('カードの保存に失敗しました');
    } finally {
      setIsSaving(false);
    }
  };

  // 【削除ハンドラ】
  const handleDelete = async () => {
    if (!id) return;

    setIsDeleting(true);
    setError(null);

    try {
      await cardsApi.deleteCard(id);
      navigate('/cards', { state: { message: 'カードを削除しました' } });
    } catch (err) {
      setError('カードの削除に失敗しました');
      setShowDeleteConfirm(false);
    } finally {
      setIsDeleting(false);
    }
  };

  /**
   * 【機能概要】: 復習間隔プリセットボタンのタップハンドラ
   * 【改善内容】: useCallback でメモ化し、不要な再生成を防止
   * 【実装方針】: 既存の handleSave パターンに倣い、isAdjusting で処理中状態を管理する
   * 【保守性】: INTERVAL_PRESET_DAYS 定数と合わせて、プリセット値の管理を一元化
   * 🔵 青信号: タスクノートの「データフロー（正常系）」「データフロー（エラー系）」に基づく実装
   * @param interval - 設定する復習間隔（日数）。INTERVAL_PRESET_DAYS の値から呼び出される
   */
  const handleIntervalAdjust = useCallback(async (interval: number) => {
    // 【ガード処理】: カードIDが取得できない場合は処理を中断する
    if (!id) return;

    // 【処理開始】: API呼び出し中状態に設定し、前回のエラーをクリアする 🔵
    setIsAdjusting(true);
    setError(null);

    try {
      // 【API呼び出し】: interval フィールドのみを送信してカードを更新する 🔵
      const updatedCard = await cardsApi.updateCard(id, { interval });
      // 【成功処理】: 更新後のカードデータで画面を更新し、成功メッセージを表示する 🔵
      setCard(updatedCard);
      setSuccessMessage('復習間隔を更新しました');
    } catch (_err) {
      // 【エラー処理】: 更新失敗時はカードデータを変更せず、エラーメッセージのみ表示する 🔵
      setError('復習間隔の更新に失敗しました');
    } finally {
      // 【状態復帰】: 成功・失敗いずれの場合も isAdjusting を false に戻してボタンを再有効化する 🔵
      setIsAdjusting(false);
    }
  }, [id]);

  // 【デッキ変更ハンドラ】
  // 【修正内容】: TASK-0092 で null 送信に対応。deckId が null の場合は明示的に null を送信し、
  // バックエンド TASK-0085 の Sentinel パターン（deck_id を REMOVE）と連携する 🔵
  // 【追加】: TASK-0097（REQ-203）デッキ変更成功後に fetchDecks() を呼び出し、
  // DecksPage / DeckSummary の card_count / due_count を最新化する 🔵
  const handleDeckChange = useCallback(async (deckId: string | null) => {
    if (!id) return;

    setError(null);
    try {
      // 【送信ロジック】: deckId=null の場合は { deck_id: null } を送信（明示的クリア）
      // deckId=undefined なら送信しない（変更なし）、deckId='xxx' なら { deck_id: 'xxx' } を送信
      const updatePayload = deckId === undefined ? {} : { deck_id: deckId };
      const updatedCard = await cardsApi.updateCard(id, updatePayload);
      setCard(updatedCard);
      setSuccessMessage('デッキを変更しました');
      // 【REQ-203】: デッキの card_count / due_count を更新するため fetchDecks を呼び出す 🔵
      fetchDecks();
    } catch (_err) {
      setError('デッキの変更に失敗しました');
    }
  }, [id, fetchDecks]);

  // 【戻るハンドラ】
  const handleBack = () => {
    navigate(-1);
  };

  // 【ローディング表示】
  if (isLoading) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center">
          <Loading message="カードを読み込み中..." />
        </div>
        <Navigation />
      </div>
    );
  }

  // 【エラー表示（カード取得失敗）】
  if (error && !card) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center p-4">
          <Error message={error} onRetry={fetchCard} />
        </div>
        <Navigation />
      </div>
    );
  }

  // 【カード未存在】
  if (!card) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center p-4">
          <Error message="カードが見つかりません" />
        </div>
        <Navigation />
      </div>
    );
  }

  const dueStatus = card.next_review_at ? getDueStatus(card.next_review_at) : null;

  return (
    <div className="flex flex-col min-h-screen pb-20">
      <header className="bg-white shadow-sm p-4 mb-4">
        <div className="flex items-center justify-between">
          <button
            onClick={handleBack}
            className="flex items-center text-gray-600 hover:text-gray-800 min-w-[44px] min-h-[44px]"
            data-testid="back-button"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            <span className="ml-1">戻る</span>
          </button>
          {!isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="text-blue-600 hover:text-blue-800 min-w-[44px] min-h-[44px] flex items-center"
              data-testid="edit-button"
            >
              <svg className="w-5 h-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              編集
            </button>
          )}
        </div>
      </header>

      <main className="flex-1 px-4">
        {/* 成功メッセージ */}
        {successMessage && (
          <div
            className="mb-4 p-3 bg-green-100 border border-green-300 text-green-700 rounded-lg"
            data-testid="success-message"
          >
            {successMessage}
          </div>
        )}

        {/* エラーメッセージ */}
        {error && (
          <div
            className="mb-4 p-3 bg-red-100 border border-red-300 text-red-700 rounded-lg"
            data-testid="error-message"
          >
            {error}
          </div>
        )}

        {isEditing ? (
          /* 編集モード */
          <CardForm
            initialFront={card.front}
            initialBack={card.back}
            onSave={handleSave}
            onCancel={() => setIsEditing(false)}
            isSaving={isSaving}
          />
        ) : (
          /* 表示モード */
          <>
            <div className="bg-white rounded-lg shadow p-6 mb-4" data-testid="card-detail">
              <div className="mb-6">
                <span className="text-xs font-medium text-gray-500 uppercase">表面（質問）</span>
                <p className="text-lg text-gray-800 mt-2 whitespace-pre-wrap" data-testid="card-front">
                  {card.front}
                </p>
              </div>

              <div className="border-t pt-6">
                <span className="text-xs font-medium text-gray-500 uppercase">裏面（解答）</span>
                <p className="text-lg text-gray-800 mt-2 whitespace-pre-wrap" data-testid="card-back">
                  {card.back}
                </p>
              </div>
            </div>

            {/* メタ情報 */}
            <div className="bg-white rounded-lg shadow p-4 mb-6" data-testid="card-meta">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">次回復習日</span>
                <span
                  className={`text-sm font-medium ${
                    dueStatus?.status === 'overdue'
                      ? 'text-red-600'
                      : dueStatus?.status === 'today'
                      ? 'text-orange-600'
                      : 'text-gray-800'
                  }`}
                  data-testid="due-date"
                >
                  {card.next_review_at ? formatDueDate(card.next_review_at) : '-'}
                </span>
              </div>
              <div className="flex justify-between items-center mt-2">
                <span className="text-sm text-gray-600">復習間隔</span>
                <span className="text-sm text-gray-800" data-testid="interval">
                  {card.interval}日
                </span>
              </div>
            </div>

            {/* デッキ変更 */}
            <div className="bg-white rounded-lg shadow p-4 mb-4" data-testid="card-deck">
              <p className="text-sm text-gray-600 mb-2">デッキ</p>
              <DeckSelector
                value={card.deck_id}
                onChange={handleDeckChange}
              />
              {card.deck_id && (
                <div className="mt-2 flex items-center">
                  <div
                    className="w-2 h-2 rounded-full mr-2"
                    style={{
                      backgroundColor:
                        decks.find((d) => d.deck_id === card.deck_id)?.color || '#6B7280',
                    }}
                  />
                  <span className="text-xs text-gray-500">
                    {decks.find((d) => d.deck_id === card.deck_id)?.name || card.deck_id}
                  </span>
                </div>
              )}
            </div>

            {/* 復習間隔プリセットボタンセクション */}
            {/* 【配置理由】: タスクノートのUI設計に従い card-meta の下、削除ボタンの上に配置 🔵 */}
            <div className="bg-white rounded-lg shadow p-4 mb-4">
              {/* 【セクションタイトル】: TC-F03 が期待する「復習間隔を調整」テキスト 🟡 */}
              <p className="text-sm text-gray-600 mb-3">復習間隔を調整</p>
              <div className="flex gap-2 flex-wrap">
                {/* 【プリセットボタン】: INTERVAL_PRESET_DAYS 定数から生成。TC-F01〜F02, TC-F04〜F17 が期待するボタン 🔵 */}
                {INTERVAL_PRESET_DAYS.map((days) => (
                  <button
                    key={days}
                    onClick={() => handleIntervalAdjust(days)}
                    // 【無効化制御】: isAdjusting=true の間は全ボタンを disabled にして二重送信を防ぐ 🔵
                    disabled={isAdjusting}
                    // 【アクセシビリティ】: TC-F10 が期待する「復習間隔を{N}日に設定」形式の aria-label 🔵
                    aria-label={`復習間隔を${days}日に設定`}
                    // 【テスト識別子】: TC-F01〜F17 がボタンを特定するための data-testid 🔵
                    data-testid={`preset-button-${days}`}
                    className="flex-1 min-h-[44px] py-2 px-3 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {/* 【ボタンテキスト】: TC-F02 が期待する「{N}日」形式 🔵 */}
                    {days}日
                  </button>
                ))}
              </div>
            </div>

            {/* 削除ボタン */}
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="w-full py-3 text-red-600 border border-red-600 rounded-lg hover:bg-red-50 min-h-[44px] transition-colors"
              data-testid="delete-button"
            >
              カードを削除
            </button>
          </>
        )}
      </main>

      {/* 削除確認ダイアログ */}
      {showDeleteConfirm && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          data-testid="delete-confirm-dialog"
        >
          <div className="bg-white rounded-lg p-6 max-w-sm w-full">
            <h3 className="text-lg font-semibold text-gray-800 mb-2">
              カードを削除しますか？
            </h3>
            <p className="text-gray-600 mb-6">
              この操作は取り消せません。
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isDeleting}
                className="flex-1 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 min-h-[44px] transition-colors"
                data-testid="delete-cancel-button"
              >
                キャンセル
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="flex-1 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 min-h-[44px] transition-colors"
                data-testid="delete-confirm-button"
              >
                {isDeleting ? '削除中...' : '削除'}
              </button>
            </div>
          </div>
        </div>
      )}

      <Navigation />
    </div>
  );
};
