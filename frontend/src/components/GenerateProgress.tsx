interface GenerateProgressProps {
  stage: 'fetching' | 'analyzing' | 'generating';
}

const STAGES = [
  { key: 'fetching', label: 'ページ取得中...', description: 'Web ページのコンテンツを取得しています' },
  { key: 'analyzing', label: 'コンテンツ解析中...', description: '重要なポイントを分析しています' },
  { key: 'generating', label: 'カード生成中...', description: 'AIがフラッシュカードを作成しています' },
] as const;

export const GenerateProgress = ({ stage }: GenerateProgressProps) => {
  const currentIndex = STAGES.findIndex(s => s.key === stage);

  return (
    <div className="bg-white rounded-lg p-4 shadow-sm" data-testid="generate-progress">
      <div className="space-y-3">
        {STAGES.map((s, index) => {
          const isComplete = index < currentIndex;
          const isCurrent = index === currentIndex;

          return (
            <div key={s.key} className="flex items-center gap-3">
              <div
                className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                  isComplete
                    ? 'bg-green-500 text-white'
                    : isCurrent
                    ? 'bg-blue-500 text-white animate-pulse'
                    : 'bg-gray-200 text-gray-400'
                }`}
              >
                {isComplete ? '✓' : index + 1}
              </div>
              <div className="flex-1">
                <p
                  className={`text-sm font-medium ${
                    isCurrent ? 'text-blue-700' : isComplete ? 'text-green-700' : 'text-gray-400'
                  }`}
                >
                  {s.label}
                </p>
                {isCurrent && (
                  <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="mt-4 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-500"
          style={{ width: `${((currentIndex + 0.5) / STAGES.length) * 100}%` }}
        />
      </div>
    </div>
  );
};
