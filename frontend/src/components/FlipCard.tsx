import "@/styles/flip-card.css";
import { SpeechButton } from "./SpeechButton";

export interface FlipCardSpeechProps {
  speechState: {
    isSpeaking: boolean;
    isSupported: boolean;
  };
  onSpeakFront: () => void;
  onSpeakBack: () => void;
}

interface FlipCardProps {
  front: string;
  back: string;
  isFlipped: boolean;
  onFlip: () => void;
  /** 読み上げ機能の統合（省略時は後方互換で非表示） */
  speechProps?: FlipCardSpeechProps;
}

export const FlipCard = ({
  front,
  back,
  isFlipped,
  onFlip,
  speechProps,
}: FlipCardProps) => {
  const showSpeech = speechProps?.speechState.isSupported ?? false;

  return (
    <div
      className="flip-card w-full h-[240px] cursor-pointer"
      role="button"
      tabIndex={0}
      aria-label={
        isFlipped
          ? "カード裏面を表示中。タップで表面に戻す"
          : "カード表面を表示中。タップで裏面を見る"
      }
      onClick={onFlip}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onFlip();
        }
      }}
    >
      <div className={`flip-card-inner ${isFlipped ? "flipped" : ""}`}>
        <div className="flip-card-front relative flex items-center justify-center p-6 bg-white rounded-xl shadow-md border border-gray-200">
          <p className="text-lg text-gray-800 text-center break-words whitespace-pre-wrap">
            {front}
          </p>
          {showSpeech && !isFlipped && speechProps && (
            <div
              className="absolute bottom-2 right-2"
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
            >
              <SpeechButton
                text={front}
                isSpeaking={speechProps.speechState.isSpeaking}
                onClick={speechProps.onSpeakFront}
                disabled={!front}
                label="表面"
              />
            </div>
          )}
        </div>
        <div className="flip-card-back relative flex items-center justify-center p-6 bg-blue-50 rounded-xl shadow-md border border-blue-200">
          <p className="text-lg text-gray-800 text-center break-words whitespace-pre-wrap">
            {back}
          </p>
          {showSpeech && isFlipped && speechProps && (
            <div
              className="absolute bottom-2 right-2"
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
            >
              <SpeechButton
                text={back}
                isSpeaking={speechProps.speechState.isSpeaking}
                onClick={speechProps.onSpeakBack}
                disabled={!back}
                label="裏面"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
