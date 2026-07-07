"""URL カード生成の本体ロジック (N-5).

LINE Webhook は API Gateway の 30 秒上限内に 200 を返す必要があるため、URL からの
カード生成（ページ取得 → chunk → Bedrock → 保存 → プレビュー push）という重い処理を
本モジュールへ切り出す。webhook の受付側（line_handler）はバリデーションと進捗 reply
だけを行い、本処理を SQS 経由でワーカー Lambda に非同期実行させる（インラインフォール
バックも可能）。

通知とリトライ判定の分離（R-2）:
  コア関数 ``generate_url_cards_core`` は例外を握りつぶさず、再試行可否で分類した
  型付き例外（``UrlGenerationPermanentError`` / ``UrlGenerationTransientError``）に
  変換して raise する。これにより SQS ワーカーは「ユーザー通知」と「SQS リトライ
  /DLQ 判定」を独立に制御できる（一時障害はサイレントリトライ、恒久障害は即通知
  して成功確定）。

  - permanent（再試行無意味）: テキスト抽出不可・空コンテンツ・カード 0 件など、
    同じ入力で再実行しても結果が変わらないもの。
  - transient（再試行で成功し得る）: ネットワーク／AI／DynamoDB の一過性障害や
    想定外例外。LLM 出力は非決定的なため、パース失敗 (AIParseError) も transient
    として扱う（再実行で成功し得る）。

``generate_and_push_url_cards`` は reply token を一切使わず、結果・エラーはすべて
``push_message`` でユーザーに通知する。これにより、受付側で進捗メッセージ reply を
済ませた後でも（reply token は 1 回しか使えない）、本処理側から安全に通知できる。
"""

from __future__ import annotations

from aws_lambda_powertools import Logger, Tracer
from botocore.exceptions import ClientError

from services.line_service import LineService
from services.flex_messages import (
    MAX_PREVIEW_CARDS,
    create_error_message,
    create_card_preview_carousel,
    create_url_generation_error_message,
)
from services.url_content_service import (
    UrlContentService,
    ContentFetchError,
    PageContent,
)
from services.content_chunker import chunk_content
from services.ai_service import (
    create_ai_service,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIProviderError,
    AIParseError,
    GenerationResult,
    CardType,
    DifficultyLevel,
    Language,
)
from services.url_cards_store import UrlCardsStore

logger = Logger()
tracer = Tracer()

# L-19: LineService を import 時に即時生成すると、webhook Lambda のコールドスタートで
# webhook/dependencies.py 側の LineService() と二重に
# _load_credentials_from_secrets_manager() が走り、同一シークレットへ Secrets Manager
# API コールが 2 回発生する。本モジュールは webhook Lambda では「インライン実行時のみ」
# line_service を必要とするため、遅延生成（_get_line_service）にして無駄な呼び出しを
# 避ける。テストは `monkeypatch.setattr(svc, "line_service", mock)` で差し替えるため、
# module グローバル `line_service` を参照する設計を維持する（差し替え済みなら再生成しない）。
line_service: LineService | None = None
url_cards_store = UrlCardsStore()


def _get_line_service() -> LineService:
    """共有 LineService を遅延生成して返す（コールドスタート時の二重シークレット読みを回避）。"""
    global line_service
    if line_service is None:
        line_service = LineService()
    return line_service


class UrlGenerationError(Exception):
    """URL カード生成エラーの基底クラス。

    ``user_message`` にユーザー向けの通知文を保持する（コア関数の呼び出し側が
    リトライ判定とは独立に通知を行えるようにするため）。
    """

    def __init__(self, message: str, user_message: str) -> None:
        super().__init__(message)
        self.user_message = user_message


class UrlGenerationPermanentError(UrlGenerationError):
    """再試行しても結果が変わらない恒久エラー（テキスト抽出不可・空コンテンツ等）。

    SQS ワーカーはこれを「成功確定（mark_processed）」として扱い、リトライしない。
    """


class UrlGenerationTransientError(UrlGenerationError):
    """再試行で成功し得る一時エラー（ネットワーク／AI／DynamoDB／想定外例外）。

    SQS ワーカーはこれを batchItemFailures に積み、SQS リトライ／DLQ に委ねる。
    """


class EmptyContentError(Exception):
    """ページからテキストを抽出できなかった（chunk 0 件）。

    fetch_and_generate_cards が raise する。「テキスト抽出不可」は再実行しても
    結果が変わらないため、呼び出し側は恒久エラー（HTTP 422 / permanent / 通知）
    として扱う。
    """


def fetch_and_generate_cards(
    url: str,
    *,
    card_type: CardType = "qa",
    target_count: int = 10,
    difficulty: DifficultyLevel = "medium",
    language: Language = "ja",
    content_service: UrlContentService | None = None,
    profile_id: str | None = None,
) -> tuple[PageContent, list[str], GenerationResult]:
    """URL からページを取得し、chunk 化して AI カードを生成する共通パイプライン。

    fetch → chunk →（空チェック）→ generate という「ハッピーパス」を一元化する。
    REST ハンドラー（HTTP レスポンス）・SQS ワーカー（型付き例外）・レガシー保存
    （LINE 通知）でエラーの表現方法が異なるため、本関数はエラー変換を行わず素の
    例外をそのまま伝播させる。カード 0 件の扱いも呼び出し側の責務とする
    （REST=422 / worker=permanent など方針が異なるため）。

    既定の生成パラメータ（qa / 10 / medium / ja）は、生成オプション UI を持たない
    LINE チャットフローの仕様。LIFF（REST）経路は呼び出し側が明示的に上書きする。

    Args:
        url: 生成元 URL（fetch_content 内で SSRF バリデーションされる）。
        card_type: カードタイプ（qa/definition/cloze）。
        target_count: 目標生成枚数。
        difficulty: 難易度。
        language: 出力言語。
        content_service: 使用する UrlContentService。None の場合は既定生成
            （REST は BrowserService を注入したインスタンスを渡す）。
        profile_id: 認証付きページ取得用のブラウザプロファイル ID。

    Returns:
        (ページ内容, chunk テキスト列, 生成結果) のタプル。

    Raises:
        ContentFetchError: ページ取得・抽出に失敗。
        EmptyContentError: テキストを抽出できなかった（chunk 0 件）。
        AIServiceError（サブクラス含む）: AI 生成に失敗。
    """
    svc = content_service or UrlContentService()
    page = svc.fetch_content(url, profile_id=profile_id)

    chunks = chunk_content(page.text_content, page_title=page.title)
    chunk_texts = [c.text for c in chunks]
    if not chunk_texts:
        raise EmptyContentError("No text extracted from page")

    ai_service = create_ai_service()
    result = ai_service.generate_cards_from_chunks(
        chunks=chunk_texts,
        card_type=card_type,
        target_count=target_count,
        difficulty=difficulty,
        language=language,
        page_title=page.title,
    )
    return page, chunk_texts, result


@tracer.capture_method
def generate_url_cards_core(
    user_id: str,
    line_user_id: str,
    url: str,
) -> None:
    """URL から暗記カードを生成し、プレビューを push する（コア処理）。

    例外を握りつぶさず、再試行可否で分類した型付き例外に変換して raise する。
    成功時のみ最後に push まで実施する。

    Args:
        user_id: システムユーザー ID。
        line_user_id: LINE ユーザー ID（push 宛先）。
        url: 生成元 URL（バリデーション済み）。

    Raises:
        UrlGenerationPermanentError: 再試行無意味な恒久エラー。
        UrlGenerationTransientError: 再試行で成功し得る一時エラー。
    """
    logger.info(f"Generating cards from URL for user: {user_id}, url: {url}")

    # --- 取得 → chunk → 生成（共通パイプライン）---
    # エラーは再試行可否で分類した型付き例外へ変換する。
    try:
        page, _chunk_texts, result = fetch_and_generate_cards(url)
    except ContentFetchError as e:
        # ネットワーク／タイムアウト等は再試行で成功し得る → transient。
        logger.warning(f"Content fetch error: {e}")
        raise UrlGenerationTransientError(
            f"Content fetch failed: {e}",
            user_message=str(e),
        ) from e
    except EmptyContentError as e:
        # テキストを抽出できない＝再実行しても同じ → permanent。
        raise UrlGenerationPermanentError(
            "No text extracted from page",
            user_message="ページからテキストを抽出できませんでした。",
        ) from e
    except (
        AITimeoutError,
        AIRateLimitError,
        AIProviderError,
        # LLM 出力は非決定的なため、パース失敗も再実行で成功し得る → transient。
        AIParseError,
    ) as e:
        logger.error(f"AI service transient error: {e}")
        raise UrlGenerationTransientError(
            f"AI service error: {e}",
            user_message="AI処理中にエラーが発生しました。",
        ) from e
    except AIServiceError as e:
        # その他の AIServiceError（AIInternalError 等）も一過性の可能性があるため
        # transient に倒す（再試行を許可しつつ、最終的に DLQ で可視化する）。
        logger.error(f"AI service error: {e}")
        raise UrlGenerationTransientError(
            f"AI service error: {e}",
            user_message="AI処理中にエラーが発生しました。",
        ) from e

    if not result.cards:
        # カードが 1 枚も生成されなかった＝抽出結果が薄い等 → permanent。
        raise UrlGenerationPermanentError(
            "No cards generated",
            user_message="カードを生成できませんでした。",
        )

    # カルーセル用のカードデータを構築。
    # カルーセルに表示できるのは MAX_PREVIEW_CARDS 件のみのため、保存対象も
    # ここで同じ枚数に切り詰める（「保存できるのはプレビューされたカードのみ」
    # の不変条件。切り詰めずに store すると、ユーザーが一度も確認していない
    # カードが保存時に紛れ込む）。
    cards_data = [
        {
            "front": card.front,
            "back": card.back,
            "suggested_tags": card.suggested_tags,
        }
        for card in result.cards[:MAX_PREVIEW_CARDS]
    ]

    # --- 永続化 ---
    # C-3: 生成済みカードを短い参照キーで永続化し、保存 postback が LINE の
    # 300 字制限内に収まるようにする（URL 自体は最大 2048 字）。また保存時に
    # 再取得／再生成しない（Bedrock 二重課金 + プレビュー／保存内容の不一致を回避）。
    try:
        ref_key = url_cards_store.store_pending_cards(
            cards=cards_data,
            page_url=page.url,
            page_title=page.title,
        )
    except ClientError as e:
        # DynamoDB の一過性障害（スロットリング等）は再試行で成功し得る → transient。
        logger.error(f"Failed to store pending cards: {e}")
        raise UrlGenerationTransientError(
            f"DynamoDB error: {e}",
            user_message="保存処理中にエラーが発生しました。",
        ) from e

    # --- プレビュー push（成功時のみ） ---
    carousel = create_card_preview_carousel(
        cards=cards_data,
        page_title=page.title,
        page_url=page.url,
        user_id=user_id,
        ref_key=ref_key,
    )
    _get_line_service().push_message(line_user_id, [carousel])

    logger.info(
        f"URL card generation complete: {len(cards_data)} cards "
        f"(generated={len(result.cards)}), url={url}"
    )


def notify_generation_failure(line_user_id: str, message: str) -> None:
    """ユーザーに生成失敗を push 通知する（リトライ判定とは独立したヘルパー）。

    通知自体の失敗はログのみとし、呼び出し側のリトライ判定に影響させない。

    Args:
        line_user_id: LINE ユーザー ID（push 宛先）。
        message: ユーザー向けエラーメッセージ。空文字の場合は汎用エラーを送る。
    """
    try:
        svc = _get_line_service()
        if message:
            svc.push_message(
                line_user_id,
                [create_url_generation_error_message(message)],
            )
        else:
            svc.push_message(line_user_id, [create_error_message()])
    except Exception as e:  # pragma: no cover - 通知失敗は判定に影響させない
        logger.error(f"Failed to push generation-failure notification: {e}")


@tracer.capture_method
def generate_and_push_url_cards(
    user_id: str,
    line_user_id: str,
    url: str,
) -> None:
    """URL から暗記カードを生成し、プレビューを push する（インライン経路用ラッパー）。

    Webhook のインライン同期実行経路向けに、コア処理を呼び、例外時はユーザーへ通知
    して正常 return する（＝従来挙動を完全維持）。SQS ワーカーは本ラッパーではなく
    ``generate_url_cards_core`` を直接呼び、通知とリトライ判定を分離する。

    呼び出し前に ``url`` は ``validate_url`` 済みであることを前提とする
    （受付側 line_handler でバリデーション済み）。

    Args:
        user_id: システムユーザー ID。
        line_user_id: LINE ユーザー ID（push 宛先）。
        url: 生成元 URL（バリデーション済み）。
    """
    try:
        generate_url_cards_core(
            user_id=user_id,
            line_user_id=line_user_id,
            url=url,
        )
    except UrlGenerationError as e:
        # permanent / transient いずれもインライン経路ではユーザーに通知して
        # 正常 return する（リトライ機構が無いため、従来どおり 1 回で完結させる）。
        notify_generation_failure(line_user_id, e.user_message)
    except Exception as e:
        # 想定外例外もインライン経路では握りつぶし、汎用エラーを通知する。
        logger.error(f"Unexpected error in URL card generation: {e}")
        notify_generation_failure(line_user_id, "")
