import type { TutorMessage } from "@/types";

interface ChatMessageProps {
  message: TutorMessage;
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Detect quiz feedback markers in assistant messages.
 * Returns "correct" if ✅ is near the start, "incorrect" if ❌ is near the start, else null.
 */
function detectQuizFeedback(
  content: string,
): "correct" | "incorrect" | null {
  const trimmed = content.trimStart().slice(0, 30);
  if (trimmed.includes("✅")) return "correct";
  if (trimmed.includes("❌")) return "incorrect";
  return null;
}

export const ChatMessage = ({ message }: ChatMessageProps) => {
  const isUser = message.role === "user";
  const feedback = !isUser ? detectQuizFeedback(message.content) : null;

  // Determine bubble style: quiz feedback overrides default assistant styling
  let bubbleClass: string;
  if (isUser) {
    bubbleClass = "bg-blue-600 text-white rounded-br-sm";
  } else if (feedback === "correct") {
    bubbleClass = "bg-green-50 border border-green-300 text-gray-800 rounded-bl-sm";
  } else if (feedback === "incorrect") {
    bubbleClass = "bg-red-50 border border-red-300 text-gray-800 rounded-bl-sm";
  } else {
    bubbleClass = "bg-gray-100 text-gray-800 rounded-bl-sm";
  }

  let timestampClass: string;
  if (isUser) {
    timestampClass = "text-blue-200";
  } else if (feedback === "correct") {
    timestampClass = "text-green-400";
  } else if (feedback === "incorrect") {
    timestampClass = "text-red-400";
  } else {
    timestampClass = "text-gray-400";
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div className={`max-w-[80%] rounded-2xl px-4 py-2 ${bubbleClass}`}>
        <p className="text-sm whitespace-pre-wrap break-words">
          {message.content}
        </p>
        <p className={`text-xs mt-1 ${timestampClass}`}>
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  );
};
