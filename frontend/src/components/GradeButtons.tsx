interface GradeButtonsProps {
  onGrade: (grade: number) => void;
  onSkip?: () => void;
  disabled: boolean;
}

const GRADE_CONFIGS = [
  { grade: 0, bgClass: 'bg-red-50 hover:bg-red-100 active:bg-red-200 border-red-300', textClass: 'text-red-700', descClass: 'text-red-600', description: '全く覚えていない' },
  { grade: 1, bgClass: 'bg-orange-50 hover:bg-orange-100 active:bg-orange-200 border-orange-300', textClass: 'text-orange-700', descClass: 'text-orange-600', description: '間違えた' },
  { grade: 2, bgClass: 'bg-amber-50 hover:bg-amber-100 active:bg-amber-200 border-amber-300', textClass: 'text-amber-700', descClass: 'text-amber-600', description: '間違えたが見覚えあり' },
  { grade: 3, bgClass: 'bg-yellow-50 hover:bg-yellow-100 active:bg-yellow-200 border-yellow-300', textClass: 'text-yellow-700', descClass: 'text-yellow-600', description: '難しかったが正解' },
  { grade: 4, bgClass: 'bg-lime-50 hover:bg-lime-100 active:bg-lime-200 border-lime-300', textClass: 'text-lime-700', descClass: 'text-lime-600', description: 'やや迷ったが正解' },
  { grade: 5, bgClass: 'bg-green-50 hover:bg-green-100 active:bg-green-200 border-green-300', textClass: 'text-green-700', descClass: 'text-green-600', description: '完璧' },
] as const;

export const GradeButtons = ({ onGrade, onSkip, disabled }: GradeButtonsProps) => {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        {GRADE_CONFIGS.map(({ grade, bgClass, textClass, descClass, description }) => (
          <button
            key={grade}
            type="button"
            onClick={() => onGrade(grade)}
            disabled={disabled}
            aria-label={`${grade} - ${description}`}
            className={`flex flex-col items-center justify-center min-h-[44px] py-2 px-3 rounded-lg border transition-colors ${bgClass} ${
              disabled ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <span className={`font-bold text-lg ${textClass}`}>{grade}</span>
            <span className={`text-[10px] font-medium ${descClass}`}>{description}</span>
          </button>
        ))}
      </div>
      {onSkip && (
        <button
          type="button"
          onClick={onSkip}
          disabled={disabled}
          aria-label="スキップ"
          className={`w-full min-h-[44px] py-2 px-4 rounded-lg border border-gray-300 text-gray-600 text-sm font-medium transition-colors hover:bg-gray-100 active:bg-gray-200 ${
            disabled ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          スキップ
        </button>
      )}
    </div>
  );
};
