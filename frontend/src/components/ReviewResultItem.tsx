import type { SessionCardResult } from '@/types';

interface ReviewResultItemProps {
  result: SessionCardResult;
  index: number;
  onUndo?: (index: number) => void;
  isUndoing?: boolean;
}

const GRADE_DISPLAY_CONFIGS: Record<number, { label: string; bgClass: string; textClass: string }> = {
  0: { label: '0', bgClass: 'bg-red-100', textClass: 'text-red-700' },
  1: { label: '1', bgClass: 'bg-orange-100', textClass: 'text-orange-700' },
  2: { label: '2', bgClass: 'bg-amber-100', textClass: 'text-amber-700' },
  3: { label: '3', bgClass: 'bg-yellow-100', textClass: 'text-yellow-700' },
  4: { label: '4', bgClass: 'bg-lime-100', textClass: 'text-lime-700' },
  5: { label: '5', bgClass: 'bg-green-100', textClass: 'text-green-700' },
};

export const ReviewResultItem = ({
  result,
  index,
  onUndo,
  isUndoing = false,
}: ReviewResultItemProps) => {
  const gradeConfig = result.grade !== undefined ? GRADE_DISPLAY_CONFIGS[result.grade] : null;

  return (
    <div className="flex items-center gap-3 py-3 px-4 bg-white rounded-lg border border-gray-200">
      {/* Grade badge or status */}
      <div className="shrink-0 w-10">
        {result.type === 'graded' && gradeConfig && (
          <span
            className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${gradeConfig.bgClass} ${gradeConfig.textClass}`}
          >
            {gradeConfig.label}
          </span>
        )}
        {result.type === 'skipped' && (
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
            —
          </span>
        )}
        {result.type === 'undone' && (
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-medium bg-blue-100 text-blue-500">
            ↩
          </span>
        )}
      </div>

      {/* Card front text */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-800 truncate">{result.front}</p>
        {result.type === 'graded' && result.nextReviewDate && (
          <p className="text-xs text-gray-500 mt-0.5">
            次回: {result.nextReviewDate}
          </p>
        )}
        {result.type === 'skipped' && (
          <p className="text-xs text-gray-400 mt-0.5">スキップ</p>
        )}
        {result.type === 'undone' && (
          <p className="text-xs text-blue-500 mt-0.5">取り消し済み</p>
        )}
      </div>

      {/* Undo button */}
      <div className="shrink-0">
        {(result.type === 'graded' || result.type === 'reconfirmed') && onUndo && (
          <button
            type="button"
            onClick={() => onUndo(index)}
            disabled={isUndoing}
            aria-label={`${result.front} の採点を取り消す`}
            className={`min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg text-sm text-gray-500 hover:bg-gray-100 active:bg-gray-200 transition-colors ${
              isUndoing ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {isUndoing ? (
              <svg className="animate-spin h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <span className="text-xs">取消</span>
            )}
          </button>
        )}
      </div>
    </div>
  );
};
