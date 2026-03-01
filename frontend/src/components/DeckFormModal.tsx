import { useState, useEffect, useRef } from 'react';
import type { Deck, CreateDeckRequest, UpdateDeckRequest } from '@/types';

/** カラーパレットに表示するプリセットカラー一覧 */
const PRESET_COLORS = [
  '#3B82F6', // blue
  '#EF4444', // red
  '#10B981', // green
  '#F59E0B', // amber
  '#8B5CF6', // violet
  '#EC4899', // pink
  '#06B6D4', // cyan
  '#F97316', // orange
  '#6366F1', // indigo
  '#14B8A6', // teal
];

/** edit モード初期値スナップショット */
interface DeckFormInitialValues {
  name: string;
  description: string;
  color: string | null;
}

/**
 * DeckFormModal のプロパティ
 * @property mode - 'create'（新規作成）または 'edit'（編集）
 * @property deck - 編集対象のデッキ（edit モード時に使用）
 * @property isOpen - モーダルの表示状態
 * @property onClose - モーダルを閉じるコールバック
 * @property onSubmit - フォーム送信時のコールバック
 */
interface DeckFormModalProps {
  mode: 'create' | 'edit';
  deck?: Deck;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateDeckRequest | UpdateDeckRequest) => Promise<void>;
}

/**
 * デッキ作成・編集モーダルコンポーネント
 *
 * edit モードでは差分送信を行い、変更されたフィールドのみ payload に含める。
 * カラーの選択解除は null として送信し、バックエンドで REMOVE される。
 */
export const DeckFormModal = ({ mode, deck, isOpen, onClose, onSubmit }: DeckFormModalProps) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState<string | undefined>(undefined);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // edit モード: モーダルを開いた瞬間の値をスナップショットとして保持
  // deck prop が再レンダリングで変わっても、比較基準は起動時スナップショットを使う
  const initialValues = useRef<DeckFormInitialValues | null>(null);

  // フォーム初期化
  useEffect(() => {
    if (isOpen) {
      if (mode === 'edit' && deck) {
        const snapshot: DeckFormInitialValues = {
          name: deck.name,
          description: deck.description ?? '',
          color: deck.color ?? null,
        };
        initialValues.current = snapshot;
        setName(snapshot.name);
        setDescription(snapshot.description);
        setColor(snapshot.color ?? undefined);
      } else {
        initialValues.current = null;
        setName('');
        setDescription('');
        setColor(undefined);
      }
      setError(null);
    }
  }, [isOpen, mode, deck]);

  if (!isOpen) return null;

  /**
   * フォーム送信ハンドラ
   * create モードは全フィールドを送信、edit モードは初期値との差分のみ送信する。
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('デッキ名を入力してください');
      return;
    }
    if (trimmedName.length > 100) {
      setError('デッキ名は100文字以内で入力してください');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      if (mode === 'create') {
        const data: CreateDeckRequest = { name: trimmedName };
        if (description.trim()) data.description = description.trim();
        if (color) data.color = color;
        await onSubmit(data);
      } else {
        // edit モード: 差分送信ロジック
        // 初期値スナップショットと比較し、変更されたフィールドのみ payload に含める
        const initial = initialValues.current;
        const normalizedDescription = description.trim();
        // color: フォーム値 undefined は null に正規化（選択解除を null として比較）
        const normalizedColor: string | null = color ?? null;

        const payload: UpdateDeckRequest = {};

        if (trimmedName !== (initial?.name ?? '')) {
          payload.name = trimmedName;
        }
        if (normalizedDescription !== (initial?.description ?? '')) {
          // 空文字は null に変換（バックエンドで REMOVE）
          payload.description = normalizedDescription === '' ? null : normalizedDescription;
        }
        if (normalizedColor !== (initial?.color ?? null)) {
          // 選択解除（undefined → null）はそのまま null として送信（バックエンドで REMOVE）
          payload.color = normalizedColor;
        }

        await onSubmit(payload);
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'エラーが発生しました');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      data-testid="deck-form-modal-overlay"
    >
      <div className="bg-white rounded-xl w-full max-w-md shadow-xl" data-testid="deck-form-modal">
        {/* ヘッダー */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-bold text-gray-800">
            {mode === 'create' ? 'デッキを作成' : 'デッキを編集'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
            aria-label="閉じる"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* フォーム */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* エラー表示 */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm" data-testid="deck-form-error">
              {error}
            </div>
          )}

          {/* デッキ名 */}
          <div>
            <label htmlFor="deck-name" className="block text-sm font-medium text-gray-700 mb-1">
              デッキ名 <span className="text-red-500">*</span>
            </label>
            <input
              id="deck-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例: 英語、数学、プログラミング"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors"
              maxLength={100}
              autoFocus
              data-testid="deck-name-input"
            />
            <p className="mt-1 text-xs text-gray-500">{name.length}/100</p>
          </div>

          {/* 説明 */}
          <div>
            <label htmlFor="deck-description" className="block text-sm font-medium text-gray-700 mb-1">
              説明
            </label>
            <textarea
              id="deck-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="デッキの説明（任意）"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors resize-none"
              rows={3}
              maxLength={500}
              data-testid="deck-description-input"
            />
            <p className="mt-1 text-xs text-gray-500">{description.length}/500</p>
          </div>

          {/* カラー選択 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              カラー
            </label>
            <div className="flex flex-wrap gap-2" data-testid="deck-color-palette">
              {/* 「なし」オプション */}
              <button
                type="button"
                onClick={() => setColor(undefined)}
                className={`w-8 h-8 rounded-full border-2 transition-all flex items-center justify-center ${
                  !color ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-300'
                }`}
                aria-label="カラーなし"
                data-testid="deck-color-none"
              >
                <svg className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                </svg>
              </button>
              {PRESET_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={`w-8 h-8 rounded-full border-2 transition-all ${
                    color === c ? 'border-gray-800 ring-2 ring-gray-300 scale-110' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: c }}
                  aria-label={`カラー ${c}`}
                  data-testid={`deck-color-${c}`}
                />
              ))}
            </div>
          </div>

          {/* ボタン */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-3 px-4 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 active:bg-gray-100 transition-colors min-h-[44px] font-medium"
              disabled={isSubmitting}
            >
              キャンセル
            </button>
            <button
              type="submit"
              className="flex-1 py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 active:bg-blue-800 transition-colors min-h-[44px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isSubmitting || !name.trim()}
              data-testid="deck-form-submit"
            >
              {isSubmitting ? '保存中...' : mode === 'create' ? '作成' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
