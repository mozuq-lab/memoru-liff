/**
 * カード生成オプション - カードタイプ、生成枚数、難易度の選択
 */
import type { CardType } from '@/types';

type Difficulty = 'easy' | 'medium' | 'hard';

interface GenerateOptionsProps {
  cardType: CardType;
  targetCount: number;
  difficulty: Difficulty;
  onCardTypeChange: (type: CardType) => void;
  onTargetCountChange: (count: number) => void;
  onDifficultyChange: (difficulty: Difficulty) => void;
  disabled: boolean;
}

const CARD_TYPES: { value: CardType; label: string; description: string }[] = [
  { value: 'qa', label: 'Q&A', description: '質問と回答' },
  { value: 'definition', label: '用語定義', description: '用語と定義' },
  { value: 'cloze', label: '穴埋め', description: '穴埋め形式' },
];

const DIFFICULTIES: { value: Difficulty; label: string }[] = [
  { value: 'easy', label: '易しい' },
  { value: 'medium', label: '普通' },
  { value: 'hard', label: '難しい' },
];

export const GenerateOptions = ({
  cardType,
  targetCount,
  difficulty,
  onCardTypeChange,
  onTargetCountChange,
  onDifficultyChange,
  disabled,
}: GenerateOptionsProps) => {
  return (
    <div className="space-y-4">
      {/* カードタイプ選択 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          カードタイプ
        </label>
        <div className="flex gap-2">
          {CARD_TYPES.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => onCardTypeChange(value)}
              disabled={disabled}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                cardType === value
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              data-testid={`card-type-${value}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* 生成枚数スライダー */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          生成枚数: <span data-testid="target-count-display">{targetCount}</span>枚
        </label>
        <input
          type="range"
          min={5}
          max={30}
          step={5}
          value={targetCount}
          onChange={(e) => onTargetCountChange(Number(e.target.value))}
          disabled={disabled}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
          data-testid="target-count-slider"
        />
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>5</span>
          <span>30</span>
        </div>
      </div>

      {/* 難易度選択 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          難易度
        </label>
        <div className="flex gap-2">
          {DIFFICULTIES.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => onDifficultyChange(value)}
              disabled={disabled}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                difficulty === value
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              data-testid={`difficulty-${value}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
