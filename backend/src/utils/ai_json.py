"""AI モデルレスポンスからの JSON 抽出ユーティリティ。

Strands / Bedrock の各パーサーで重複していた
「Markdown ```json コードブロック または素の JSON 文字列を抽出して
json.loads する」ロジックを一元化する。
"""

import json
import re
from typing import Any

# Markdown コードブロック ```json ... ``` を検出する正規表現。
_JSON_BLOCK_RE = re.compile(r"```json\s*([\s\S]*?)\s*```")


def extract_json_from_text(response_text: str) -> Any:
    """AI レスポンステキストから JSON をパースして返す。

    以下の 2 種類のフォーマットに対応する:
    1. プレーン JSON 文字列: ``{"cards": [...]}``
    2. Markdown コードブロック: ````json\n{...}\n```

    Args:
        response_text: モデルから返されたレスポンステキスト。

    Returns:
        パース済みの JSON オブジェクト（通常は dict）。

    Raises:
        json.JSONDecodeError: JSON のパースに失敗した場合。呼び出し側で
            サービス固有の例外に変換することを想定する。
    """
    json_match = _JSON_BLOCK_RE.search(response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text.strip()

    return json.loads(json_str)
