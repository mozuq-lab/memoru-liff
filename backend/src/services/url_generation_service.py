"""URL カード生成の本体ロジック (N-5).

LINE Webhook は API Gateway の 30 秒上限内に 200 を返す必要があるため、URL からの
カード生成（ページ取得 → chunk → Bedrock → 保存 → プレビュー push）という重い処理を
本モジュールへ切り出す。webhook の受付側（line_handler）はバリデーションと進捗 reply
だけを行い、本処理を SQS 経由でワーカー Lambda に非同期実行させる（インラインフォール
バックも可能）。

``generate_and_push_url_cards`` は reply token を一切使わず、結果・エラーはすべて
``push_message`` でユーザーに通知する。これにより、受付側で進捗メッセージ reply を
済ませた後でも（reply token は 1 回しか使えない）、本処理側から安全に通知できる。
"""

from __future__ import annotations

from aws_lambda_powertools import Logger, Tracer

from services.line_service import LineService
from services.flex_messages import (
    create_error_message,
    create_card_preview_carousel,
    create_url_generation_error_message,
)
from services.url_content_service import UrlContentService, ContentFetchError
from services.content_chunker import chunk_content
from services.ai_service import create_ai_service, AIServiceError
from services.url_cards_store import UrlCardsStore

logger = Logger()
tracer = Tracer()

# 共有サービスインスタンス（line_handler / worker の双方から利用される）。
line_service = LineService()
url_cards_store = UrlCardsStore()


@tracer.capture_method
def generate_and_push_url_cards(
    user_id: str,
    line_user_id: str,
    url: str,
) -> None:
    """URL から暗記カードを生成し、プレビューを push する（重い本処理）。

    呼び出し前に ``url`` は ``validate_url`` 済みであることを前提とする
    （受付側 line_handler でバリデーション済み）。進捗メッセージの reply も受付側で
    済ませているため、本関数は結果・エラーをすべて ``push_message`` で通知する。

    Args:
        user_id: システムユーザー ID。
        line_user_id: LINE ユーザー ID（push 宛先）。
        url: 生成元 URL（バリデーション済み）。
    """
    logger.info(f"Generating cards from URL for user: {user_id}, url: {url}")

    try:
        # ページ取得
        content_service = UrlContentService()
        page = content_service.fetch_content(url)

        # コンテンツを chunk 化
        chunks = chunk_content(page.text_content, page_title=page.title)
        chunk_texts = [c.text for c in chunks]

        if not chunk_texts:
            line_service.push_message(
                line_user_id,
                [create_url_generation_error_message(
                    "ページからテキストを抽出できませんでした。"
                )],
            )
            return

        # カード生成
        ai_service = create_ai_service()
        result = ai_service.generate_cards_from_chunks(
            chunks=chunk_texts,
            card_type="qa",
            target_count=10,
            difficulty="medium",
            language="ja",
            page_title=page.title,
        )

        if not result.cards:
            line_service.push_message(
                line_user_id,
                [create_url_generation_error_message(
                    "カードを生成できませんでした。"
                )],
            )
            return

        # カルーセル用のカードデータを構築
        cards_data = [
            {
                "front": card.front,
                "back": card.back,
                "suggested_tags": card.suggested_tags,
            }
            for card in result.cards
        ]

        # C-3: 生成済みカードを短い参照キーで永続化し、保存 postback が LINE の
        # 300 字制限内に収まるようにする（URL 自体は最大 2048 字）。また保存時に
        # 再取得／再生成しない（Bedrock 二重課金 + プレビュー／保存内容の不一致を回避）。
        ref_key = url_cards_store.store_pending_cards(
            cards=cards_data,
            page_url=page.url,
            page_title=page.title,
        )

        # プレビュー付きカルーセルを送信
        carousel = create_card_preview_carousel(
            cards=cards_data,
            page_title=page.title,
            page_url=page.url,
            user_id=user_id,
            ref_key=ref_key,
        )
        line_service.push_message(line_user_id, [carousel])

        logger.info(
            f"URL card generation complete: {len(result.cards)} cards, "
            f"url={url}"
        )

    except ContentFetchError as e:
        logger.warning(f"Content fetch error: {e}")
        line_service.push_message(
            line_user_id,
            [create_url_generation_error_message(str(e))],
        )
    except AIServiceError as e:
        logger.error(f"AI service error: {e}")
        line_service.push_message(
            line_user_id,
            [create_url_generation_error_message(
                "AI処理中にエラーが発生しました。"
            )],
        )
    except Exception as e:
        logger.error(f"Unexpected error in URL card generation: {e}")
        line_service.push_message(
            line_user_id,
            [create_error_message()],
        )
