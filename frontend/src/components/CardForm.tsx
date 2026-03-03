/**
 * 【機能概要】: カード編集フォームコンポーネント
 * 【実装方針】: 表面・裏面の編集と保存・キャンセル機能を提供
 * 【テスト対応】: TASK-0017 テストケース2〜5, TASK-0141 AI補足機能
 * 🟡 黄信号: user-stories.md 3.3より
 */
import { useRef, useState } from 'react';
import { cardsApi } from '@/services/api';

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
  const [isRefining, setIsRefining] = useState(false);
  const [refineError, setRefineError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 【バリデーション】: 空でないかチェック
  const isValid = front.trim().length > 0 && back.trim().length > 0;
  // 【変更検知】: 初期値から変更があるかチェック
  const hasChanges = front !== initialFront || back !== initialBack;
  // 【保存可否】: 有効かつ変更があり、保存中でない場合のみ保存可能
  const canSave = isValid && hasChanges && !isSaving && !isRefining;
  // 【AI補足可否】: 表面または裏面に入力があり、処理中でない場合のみ
  const canRefine = !isRefining && !isSaving && (front.trim().length > 0 || back.trim().length > 0);

  // 【送信ハンドラ】
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSave) return;
    await onSave(front.trim(), back.trim());
  };

  // 【AI補足ハンドラ】
  const handleRefine = async () => {
    if (!canRefine) return;

    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsRefining(true);
    setRefineError(null);

    try {
      const result = await cardsApi.refineCard(
        { front, back },
        { signal: controller.signal },
      );
      if (!controller.signal.aborted) {
        setFront(result.refined_front);
        setBack(result.refined_back);
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      const message = err instanceof Error ? err.message : '';
      if (message.includes('504') || message.toLowerCase().includes('timeout')) {
        setRefineError('AIの処理がタイムアウトしました。再度お試しください');
      } else if (message.includes('429') || message.toLowerCase().includes('rate')) {
        setRefineError('リクエスト制限に達しました。しばらくお待ちください');
      } else if (message.includes('503')) {
        setRefineError('AIサービスが一時的に利用できません');
      } else if (message.includes('400')) {
        setRefineError('入力内容を確認してください');
      } else {
        setRefineError('AI補足に失敗しました。再度お試しください');
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsRefining(false);
      }
    }
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
          disabled={isSaving || isRefining}
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
          disabled={isSaving || isRefining}
          data-testid="input-back"
        />
      </div>

      {refineError && (
        <div
          className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg"
          data-testid="refine-error"
        >
          {refineError}
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSaving || isRefining}
          className="flex-1 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 min-h-[44px] transition-colors"
          data-testid="cancel-button"
        >
          キャンセル
        </button>
        <button
          type="button"
          onClick={handleRefine}
          disabled={!canRefine}
          className={`flex-1 py-3 rounded-lg min-h-[44px] transition-colors ${
            canRefine
              ? 'bg-purple-600 text-white hover:bg-purple-700'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
          data-testid="refine-button"
        >
          {isRefining ? 'AI 処理中...' : 'AI で補足'}
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
