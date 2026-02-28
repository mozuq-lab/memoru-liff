/**
 * 【機能概要】: キーワードハイライトコンポーネント
 * 【実装方針】: テキストを分割して <mark> タグで囲む。dangerouslySetInnerHTML 不使用
 * 【テスト対応】: HT-001〜HT-006
 */

interface HighlightTextProps {
  /** 表示する元テキスト */
  text: string;
  /** ハイライトするキーワード（空文字 = ハイライトなし） */
  query: string;
  /** テキスト全体に適用する CSS クラス */
  className?: string;
}

/**
 * 文字列を NFKC 正規化して小文字に変換する（全角・半角・大小文字を統一）
 */
const normalize = (str: string): string => str.normalize('NFKC').toLowerCase();

/**
 * テキストを検索キーワードで分割し、マッチ箇所を <mark> タグで囲んで表示する。
 * XSS 安全: React の JSX レンダリングを使用するため innerHTML は不使用。
 */
export const HighlightText = ({ text, query, className }: HighlightTextProps) => {
  if (!query) {
    return <span className={className}>{text}</span>;
  }

  const normalizedQuery = normalize(query);
  const normalizedText = normalize(text);

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  let index = normalizedText.indexOf(normalizedQuery, lastIndex);
  while (index !== -1) {
    // マッチ前のテキスト
    if (index > lastIndex) {
      parts.push(text.slice(lastIndex, index));
    }
    // マッチ部分を <mark> で囲む（元テキストの文字を使用）
    parts.push(
      <mark key={index} className="bg-yellow-200 text-inherit rounded-sm">
        {text.slice(index, index + query.length)}
      </mark>
    );
    lastIndex = index + normalizedQuery.length;
    index = normalizedText.indexOf(normalizedQuery, lastIndex);
  }

  // 残りのテキスト
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return <span className={className}>{parts}</span>;
};
