/**
 * 【機能概要】: キーワードハイライトコンポーネント
 * 【実装方針】: テキストを分割して <mark> タグで囲む。dangerouslySetInnerHTML 不使用
 * 【テスト対応】: HT-001〜HT-008
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
 * H-3 fix: 元テキスト ⇔ 正規化テキストのインデックスマッピングを構築する。
 * NFKC 正規化で文字数が変わるケース（例: ㌔→キロ, ﬁ→fi）に対応。
 * normalizedToOriginal[i] = 正規化後のインデックス i に対応する元テキストの文字位置
 */
const buildNormalizedToOriginalMap = (original: string): number[] => {
  const map: number[] = [];
  for (let i = 0; i < original.length; i++) {
    const charNormalized = original[i].normalize('NFKC').toLowerCase();
    for (let j = 0; j < charNormalized.length; j++) {
      map.push(i);
    }
  }
  return map;
};

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
  const indexMap = buildNormalizedToOriginalMap(text);

  const parts: React.ReactNode[] = [];
  let lastOrigIndex = 0;

  let nIdx = normalizedText.indexOf(normalizedQuery, 0);
  let searchFrom = 0;
  while (nIdx !== -1) {
    // 正規化後インデックスを元テキストインデックスに変換
    const origStart = indexMap[nIdx];
    const nEnd = nIdx + normalizedQuery.length;
    // nEnd が末尾を超える場合は元テキスト末尾まで
    const origEnd = nEnd < indexMap.length ? indexMap[nEnd] : text.length;

    // マッチ前のテキスト
    if (origStart > lastOrigIndex) {
      parts.push(text.slice(lastOrigIndex, origStart));
    }
    // マッチ部分を <mark> で囲む（元テキストの文字を使用）
    parts.push(
      <mark key={nIdx} className="bg-yellow-200 text-inherit rounded-sm">
        {text.slice(origStart, origEnd)}
      </mark>
    );
    lastOrigIndex = origEnd;
    searchFrom = nEnd;
    nIdx = normalizedText.indexOf(normalizedQuery, searchFrom);
  }

  // 残りのテキスト
  if (lastOrigIndex < text.length) {
    parts.push(text.slice(lastOrigIndex));
  }

  return <span className={className}>{parts}</span>;
};
