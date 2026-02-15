/**
 * 【機能概要】: カード詳細・編集画面
 * 【実装方針】: カードの表示、編集、削除機能を提供
 * 【テスト対応】: TASK-0017 テストケース1〜9
 * 🟡 黄信号: user-stories.md 3.3より
 */
import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { CardForm } from '@/components/CardForm';
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import { cardsApi } from '@/services/api';
import type { Card } from '@/types';
import { formatDueDate, getDueStatus } from '@/utils/date';

/**
 * 【機能概要】: カード詳細ページコンポーネント
 */
export const CardDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [card, setCard] = useState<Card | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

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
