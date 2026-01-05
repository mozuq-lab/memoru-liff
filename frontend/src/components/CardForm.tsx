/**
 * 【機能概要】: カード編集フォームコンポーネント
 * 【実装方針】: 表面・裏面の編集と保存・キャンセル機能を提供
 * 【テスト対応】: TASK-0017 テストケース2〜5
 * 🟡 黄信号: user-stories.md 3.3より
 */
import { useState } from 'react';

interface CardFormProps {
  initialFront: string;
  initialBack: string;
  onSave: (front: string, back: string) => Promise<void>;
  onCancel: () => void;
  isSaving: boolean;
}

/**
 * 【機能概要】: カード編集フォームコンポーネント
 * 【実装方針】: 変更があり、空でない場合のみ保存可能
 */
export const CardForm = ({
  initialFront,
  initialBack,
  onSave,
  onCancel,
  isSaving,
}: CardFormProps) => {
  const [front, setFront] = useState(initialFront);
  const [back, setBack] = useState(initialBack);

  // 【バリデーション】: 空でないかチェック
  const isValid = front.trim().length > 0 && back.trim().length > 0;
  // 【変更検知】: 初期値から変更があるかチェック
  const hasChanges = front !== initialFront || back !== initialBack;
  // 【保存可否】: 有効かつ変更があり、保存中でない場合のみ保存可能
  const canSave = isValid && hasChanges && !isSaving;

  // 【送信ハンドラ】
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSave) return;
    await onSave(front.trim(), back.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6" data-testid="card-form">
      <div className="mb-6">
        <label htmlFor="front" className="block text-sm font-medium text-gray-700 mb-2">
          表面（質問）
        </label>
        <textarea
          id="front"
          value={front}
          onChange={(e) => setFront(e.target.value)}
          placeholder="質問を入力..."
          className="w-full h-32 p-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          disabled={isSaving}
          data-testid="input-front"
        />
      </div>

      <div className="mb-6">
        <label htmlFor="back" className="block text-sm font-medium text-gray-700 mb-2">
          裏面（解答）
        </label>
        <textarea
          id="back"
          value={back}
          onChange={(e) => setBack(e.target.value)}
          placeholder="解答を入力..."
          className="w-full h-32 p-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          disabled={isSaving}
          data-testid="input-back"
        />
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSaving}
          className="flex-1 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 min-h-[44px] transition-colors"
          data-testid="cancel-button"
        >
          キャンセル
        </button>
        <button
          type="submit"
          disabled={!canSave}
          className={`flex-1 py-3 rounded-lg min-h-[44px] transition-colors ${
            canSave
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
          data-testid="save-button"
        >
          {isSaving ? '保存中...' : '保存'}
        </button>
      </div>
    </form>
  );
};
