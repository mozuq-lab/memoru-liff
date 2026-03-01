/** 文字列を NFKC 正規化して小文字に変換（全角・半角・大小文字統一） */
export const normalize = (str: string): string =>
  str.normalize("NFKC").toLowerCase();
