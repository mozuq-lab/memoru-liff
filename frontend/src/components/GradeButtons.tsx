interface GradeButtonsProps {
  onGrade: (grade: number) => void;
  onSkip: () => void;
  disabled: boolean;
}

const GRADE_CONFIGS = [
  { grade: 0, colorClass: 'bg-red-600 hover:bg-red-700 active:bg-red-800', description: '全く覚えていない' },
  { grade: 1, colorClass: 'bg-orange-600 hover:bg-orange-700 active:bg-orange-800', description: '間違えた' },
  { grade: 2, colorClass: 'bg-amber-500 hover:bg-amber-600 active:bg-amber-700', description: '間違えたが見覚えあり' },
  { grade: 3, colorClass: 'bg-yellow-500 hover:bg-yellow-600 active:bg-yellow-700', description: '難しかったが正解' },
  { grade: 4, colorClass: 'bg-lime-500 hover:bg-lime-600 active:bg-lime-700', description: 'やや迷ったが正解' },
  { grade: 5, colorClass: 'bg-green-600 hover:bg-green-700 active:bg-green-800', description: '完璧' },
] as const;

export const GradeButtons = ({ onGrade, onSkip, disabled }: GradeButtonsProps) => {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        {GRADE_CONFIGS.map(({ grade, colorClass, description }) => (
          <button
            key={grade}
            type="button"
            onClick={() => onGrade(grade)}
            disabled={disabled}
            aria-label={`${grade} - ${description}`}
            className={`flex flex-col items-center justify-center min-h-[44px] py-2 px-3 rounded-lg text-white font-bold text-lg transition-colors ${colorClass} ${
              disabled ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <span>{grade}</span>
            <span className="text-[10px] font-normal opacity-80">{description}</span>
          </button>
        ))}
      </div>
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
    </div>
  );
};
