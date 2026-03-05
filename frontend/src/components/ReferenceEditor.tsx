/**
 * 【機能概要】: 参考情報の編集コンポーネント
 * 【実装方針】: 参考情報の追加・編集・削除を提供
 * 【テスト対応】: TASK-0159
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント仕様より
 */
import { useState } from 'react';
import type { Reference, ReferenceType } from '@/types/card';

interface ReferenceEditorProps {
  references: Reference[];
  onChange: (references: Reference[]) => void;
  maxItems?: number;
}

const TYPE_LABELS: Record<ReferenceType, string> = {
  url: 'URL',
  book: '書籍',
  note: 'メモ',
};

const TYPE_OPTIONS: { value: ReferenceType; label: string }[] = [
  { value: 'url', label: 'URL' },
  { value: 'book', label: '書籍' },
  { value: 'note', label: 'メモ' },
];

/**
 * 【機能概要】: 参考情報の編集コンポーネント
 * 【実装方針】: リスト表示 + 追加フォーム + インライン編集・削除
 */
export const ReferenceEditor = ({
  references,
  onChange,
  maxItems = 5,
}: ReferenceEditorProps) => {
  const [newType, setNewType] = useState<ReferenceType>('url');
  const [newValue, setNewValue] = useState('');
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editType, setEditType] = useState<ReferenceType>('url');
  const [editValue, setEditValue] = useState('');

  const isMaxReached = references.length >= maxItems;

  // 【追加ハンドラ】
  const handleAdd = () => {
    if (!newValue.trim()) return;
    const newRef: Reference = { type: newType, value: newValue.trim() };
    onChange([...references, newRef]);
    setNewValue('');
    setNewType('url');
  };

  // 【削除ハンドラ】
  const handleDelete = (index: number) => {
    const updated = references.filter((_, i) => i !== index);
    onChange(updated);
    if (editingIndex === index) {
      setEditingIndex(null);
    }
  };

  // 【編集開始ハンドラ】
  const handleEditStart = (index: number) => {
    setEditingIndex(index);
    setEditType(references[index].type);
    setEditValue(references[index].value);
  };

  // 【編集確定ハンドラ】
  const handleEditSave = () => {
    if (editingIndex === null || !editValue.trim()) return;
    const updated = references.map((ref, i) =>
      i === editingIndex ? { type: editType, value: editValue.trim() } : ref,
    );
    onChange(updated);
    setEditingIndex(null);
  };

  // 【編集キャンセルハンドラ】
  const handleEditCancel = () => {
    setEditingIndex(null);
  };

  // 【タイプアイコン取得】
  const getTypeIcon = (type: ReferenceType): string => {
    switch (type) {
      case 'url':
        return '🔗';
      case 'book':
        return '📖';
      case 'note':
        return '📝';
    }
  };

  return (
    <div data-testid="reference-editor" className="space-y-3">
      <h3 className="text-sm font-medium text-gray-700">参考情報</h3>

      {/* 既存の参考情報リスト */}
      {references.length > 0 && (
        <ul className="space-y-2" data-testid="reference-list">
          {references.map((ref, index) => (
            <li key={index} className="flex items-center gap-2">
              {editingIndex === index ? (
                /* インライン編集フォーム */
                <div className="flex-1 flex items-center gap-2" data-testid={`reference-edit-form-${index}`}>
                  <select
                    value={editType}
                    onChange={(e) => setEditType(e.target.value as ReferenceType)}
                    className="px-2 py-1 border border-gray-300 rounded text-sm min-h-[44px]"
                    data-testid={`reference-edit-type-${index}`}
                  >
                    {TYPE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm min-h-[44px]"
                    data-testid={`reference-edit-value-${index}`}
                  />
                  <button
                    type="button"
                    onClick={handleEditSave}
                    className="px-3 py-1 bg-blue-600 text-white rounded text-sm min-h-[44px] hover:bg-blue-700 transition-colors"
                    data-testid={`reference-edit-save-${index}`}
                  >
                    保存
                  </button>
                  <button
                    type="button"
                    onClick={handleEditCancel}
                    className="px-3 py-1 bg-gray-200 text-gray-700 rounded text-sm min-h-[44px] hover:bg-gray-300 transition-colors"
                    data-testid={`reference-edit-cancel-${index}`}
                  >
                    取消
                  </button>
                </div>
              ) : (
                /* 表示モード */
                <>
                  <span className="text-sm" aria-hidden="true">
                    {getTypeIcon(ref.type)}
                  </span>
                  <span
                    className={`text-sm font-medium px-2 py-0.5 rounded ${
                      ref.type === 'url'
                        ? 'bg-blue-100 text-blue-700'
                        : ref.type === 'book'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-green-100 text-green-700'
                    }`}
                  >
                    {TYPE_LABELS[ref.type]}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleEditStart(index)}
                    className="flex-1 text-left text-sm text-gray-800 truncate hover:text-blue-600 min-h-[44px] flex items-center"
                    data-testid={`reference-item-${index}`}
                  >
                    {ref.value}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(index)}
                    className="p-2 text-gray-400 hover:text-red-600 min-w-[44px] min-h-[44px] flex items-center justify-center transition-colors"
                    aria-label={`${ref.value}を削除`}
                    data-testid={`reference-delete-${index}`}
                  >
                    ✕
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* 追加フォーム */}
      {!isMaxReached && (
        <div className="flex items-center gap-2" data-testid="reference-add-form">
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as ReferenceType)}
            className="px-2 py-1 border border-gray-300 rounded text-sm min-h-[44px]"
            data-testid="reference-add-type"
          >
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="参考情報を入力..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm min-h-[44px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            data-testid="reference-add-value"
          />
          <button
            type="button"
            onClick={handleAdd}
            disabled={!newValue.trim()}
            className={`px-4 py-2 rounded text-sm min-h-[44px] transition-colors ${
              newValue.trim()
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
            data-testid="reference-add-button"
          >
            追加
          </button>
        </div>
      )}

      {/* 上限到達メッセージ */}
      {isMaxReached && (
        <p className="text-sm text-gray-500" data-testid="reference-max-message">
          参考情報の上限（{maxItems}件）に達しています
        </p>
      )}
    </div>
  );
};
