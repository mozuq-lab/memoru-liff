import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { cardsApi } from "@/services/api";

interface RelatedCardChipProps {
  cardId: string;
}

export const RelatedCardChip = ({ cardId }: RelatedCardChipProps) => {
  const navigate = useNavigate();
  const [frontText, setFrontText] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    cardsApi
      .getCard(cardId)
      .then((card) => {
        if (!cancelled) {
          setFrontText(card.front);
        }
      })
      .catch(() => {
        // Card may have been deleted; show ID as fallback
        if (!cancelled) {
          setFrontText(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [cardId]);

  const label = frontText ?? cardId;

  return (
    <button
      type="button"
      onClick={() => navigate(`/cards/${cardId}`)}
      className="inline-flex items-center gap-1 px-3 py-1 bg-blue-50 text-blue-700 text-xs rounded-full border border-blue-200 hover:bg-blue-100 transition-colors max-w-50 truncate"
      title={label}
    >
      <svg
        className="w-3 h-3 shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        role="img"
        aria-label="カード"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
        />
      </svg>
      <span className="truncate">{label}</span>
    </button>
  );
};
