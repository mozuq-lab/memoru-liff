/**
 * 【機能概要】: 生成されたカードのプレビューと編集機能を提供
 * 【実装方針】: 選択・編集モードを持つカードプレビューコンポーネント
 * 【テスト対応】: TASK-0015 テストケース6, 7
 * 🔵 青信号: user-stories.md 2.1より
 */
import { useState } from 'react';
import type { GeneratedCardWithId } from '@/types';

interface CardPreviewProps {
  card: GeneratedCardWithId;
  isSelected: boolean;
  onToggle: () => void;
  onEdit: (front: string, back: string) => void;
}

/**
 * 【機能概要】: カードプレビューコンポーネント
 * 【実装方針】: プレビューモードと編集モードを切り替え可能
 */
export const CardPreview = ({ card, isSelected, onToggle, onEdit }: CardPreviewProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editFront, setEditFront] = useState(card.front);
  const [editBack, setEditBack] = useState(card.back);

  // 【編集保存】: 編集内容を親に通知
  const handleSaveEdit = () => {
    onEdit(editFront, editBack);
    setIsEditing(false);
  };

  // 【編集キャンセル】: 編集内容を破棄
  const handleCancelEdit = () => {
    setEditFront(card.front);
    setEditBack(card.back);
    setIsEditing(false);
  };

  return (
    <div
      className={`bg-white rounded-lg shadow p-4 border-2 transition-colors ${
        isSelected ? 'border-blue-500' : 'border-transparent'
      }`}
      data-testid={`card-preview-${card.tempId}`}
    >
      {isEditing ? (
        /* 編集モード */
        <div className="space-y-3">
          <div>
            <label htmlFor={`card-front-${card.tempId}`} className="block text-sm font-medium text-gray-600 mb-1">
              表面（質問）
            </label>
            <textarea
              id={`card-front-${card.tempId}`}
              value={editFront}
              onChange={(e) => setEditFront(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded resize-none h-20"
              data-testid="edit-front"
            />
          </div>
          <div>
            <label htmlFor={`card-back-${card.tempId}`} className="block text-sm font-medium text-gray-600 mb-1">
              裏面（解答）
            </label>
            <textarea
              id={`card-back-${card.tempId}`}
              value={editBack}
              onChange={(e) => setEditBack(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded resize-none h-20"
              data-testid="edit-back"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSaveEdit}
              className="flex-1 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 min-h-[44px]"
              data-testid="save-edit"
            >
              保存
            </button>
            <button
              onClick={handleCancelEdit}
              className="flex-1 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 min-h-[44px]"
              data-testid="cancel-edit"
            >
              キャンセル
            </button>
          </div>
        </div>
      ) : (
        /* プレビューモード */
        <div>
          <div className="flex justify-between items-start mb-3">
            <button
              onClick={onToggle}
              className={`flex items-center justify-center w-6 h-6 rounded border-2 ${
                isSelected
                  ? 'bg-blue-500 border-blue-500 text-white'
                  : 'border-gray-300'
              }`}
              aria-label={isSelected ? 'カードの選択を解除' : 'カードを選択'}
              data-testid="toggle-select"
            >
              {isSelected && (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </button>
            <button
              onClick={() => setIsEditing(true)}
              className="text-gray-500 hover:text-gray-700 p-1 min-w-[44px] min-h-[44px] flex items-center justify-center"
              aria-label="カードを編集"
              data-testid="edit-button"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
          </div>

          <div className="mb-3">
            <span className="text-xs font-medium text-gray-500">表面</span>
            <p className="text-gray-800 mt-1" data-testid="card-front">{card.front}</p>
          </div>

          <div className="border-t pt-3">
            <span className="text-xs font-medium text-gray-500">裏面</span>
            <p className="text-gray-800 mt-1" data-testid="card-back">{card.back}</p>
          </div>
        </div>
      )}
    </div>
  );
};
