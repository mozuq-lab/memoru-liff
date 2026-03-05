/**
 * 【機能概要】: 参考情報の表示コンポーネント
 * 【実装方針】: URL はリンク、書籍/メモはテキストとして表示
 * 【テスト対応】: TASK-0159
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント仕様より
 */
import type { Reference, ReferenceType } from '@/types/card';

interface ReferenceDisplayProps {
  references: Reference[];
}

/** 【タイプアイコン取得】 */
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

/**
 * 【機能概要】: 参考情報の表示コンポーネント
 * 【実装方針】: references が空なら null を返す。コンパクトな表示。
 */
export const ReferenceDisplay = ({ references }: ReferenceDisplayProps) => {
  if (references.length === 0) {
    return null;
  }

  return (
    <div data-testid="reference-display" className="mt-4">
      <h4 className="text-sm font-medium text-gray-600 mb-2">参考情報</h4>
      <ul className="space-y-1">
        {references.map((ref, index) => (
          <li
            key={index}
            className="flex items-center gap-2 text-sm"
            data-testid={`reference-display-item-${index}`}
          >
            <span aria-hidden="true">{getTypeIcon(ref.type)}</span>
            {ref.type === 'url' && /^https?:\/\//i.test(ref.value) ? (
              <a
                href={ref.value}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 hover:underline truncate"
                data-testid={`reference-display-link-${index}`}
              >
                {ref.value}
              </a>
            ) : (
              <span className="text-gray-800 truncate">
                {ref.value}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};
