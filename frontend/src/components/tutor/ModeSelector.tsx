import type { LearningMode } from "@/types";

interface ModeSelectorProps {
  onSelect: (mode: LearningMode) => void;
  disabled?: boolean;
}

const modes: {
  key: LearningMode;
  label: string;
  description: string;
  icon: string;
}[] = [
  {
    key: "free_talk",
    label: "Free Talk",
    description: "デッキの内容について自由に質問できます",
    icon: "💬",
  },
  {
    key: "quiz",
    label: "Quiz",
    description: "AIがカード内容からクイズを出題します",
    icon: "❓",
  },
  {
    key: "weak_point",
    label: "Weak Point Focus",
    description: "苦手なカードを重点的に学習します",
    icon: "🎯",
  },
];

export const ModeSelector = ({ onSelect, disabled }: ModeSelectorProps) => {
  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-gray-700 mb-4">
        学習モードを選択
      </h2>
      {modes.map((mode) => (
        <button
          key={mode.key}
          onClick={() => onSelect(mode.key)}
          disabled={disabled}
          className="w-full text-left p-4 bg-white rounded-lg shadow hover:bg-gray-50 active:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-start gap-3">
            <span className="text-2xl" aria-hidden="true">
              {mode.icon}
            </span>
            <div>
              <h3 className="font-medium text-gray-800">{mode.label}</h3>
              <p className="text-sm text-gray-500 mt-1">{mode.description}</p>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
};
