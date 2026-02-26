import '@/styles/flip-card.css';

interface FlipCardProps {
  front: string;
  back: string;
  isFlipped: boolean;
  onFlip: () => void;
}

export const FlipCard = ({ front, back, isFlipped, onFlip }: FlipCardProps) => {
  return (
    <div
      className="flip-card w-full h-[240px] cursor-pointer"
      role="button"
      tabIndex={0}
      aria-label={isFlipped ? 'カード裏面を表示中。タップで表面に戻す' : 'カード表面を表示中。タップで裏面を見る'}
      onClick={onFlip}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onFlip();
        }
      }}
    >
      <div className={`flip-card-inner ${isFlipped ? 'flipped' : ''}`}>
        <div className="flip-card-front flex items-center justify-center p-6 bg-white rounded-xl shadow-md border border-gray-200">
          <p className="text-lg text-gray-800 text-center break-words whitespace-pre-wrap">
            {front}
          </p>
        </div>
        <div className="flip-card-back flex items-center justify-center p-6 bg-blue-50 rounded-xl shadow-md border border-blue-200">
          <p className="text-lg text-gray-800 text-center break-words whitespace-pre-wrap">
            {back}
          </p>
        </div>
      </div>
    </div>
  );
};
