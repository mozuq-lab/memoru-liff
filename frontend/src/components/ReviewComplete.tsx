import { Link } from 'react-router-dom';
import type { SessionCardResult } from '@/types';
import { ReviewResultItem } from './ReviewResultItem';

interface ReviewCompleteProps {
  reviewedCount: number;
  results?: SessionCardResult[];
  onUndo?: (index: number) => void;
  isUndoing?: boolean;
  undoingIndex?: number | null;
}

export const ReviewComplete = ({
  reviewedCount,
  results = [],
  onUndo,
  isUndoing = false,
  undoingIndex = null,
}: ReviewCompleteProps) => {
  const gradedCount = results.filter((r) => r.type === 'graded').length;
  const displayCount = gradedCount > 0 ? gradedCount : reviewedCount;

  return (
    <div className="flex flex-col min-h-[60vh] px-4 py-6">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">
          復習完了!
        </h2>
        <p className="text-lg text-gray-600">
          {displayCount}枚のカードを復習しました
        </p>
      </div>

      {results.length > 0 && (
        <div className="flex-1 space-y-2 mb-6 overflow-y-auto max-h-[50vh]">
          {results.map((result, index) => (
            <ReviewResultItem
              key={`${result.cardId}-${index}`}
              result={result}
              index={index}
              onUndo={onUndo}
              isUndoing={isUndoing && undoingIndex === index}
            />
          ))}
        </div>
      )}

      <div className="text-center">
        <Link
          to="/"
          className="inline-block py-3 px-8 bg-blue-600 text-white rounded-lg font-medium min-h-[44px] hover:bg-blue-700 active:bg-blue-800 transition-colors"
        >
          ホームに戻る
        </Link>
      </div>
    </div>
  );
};
