"""LINE webhook action handlers.

line_handler（Lambda 入口 + イベントルーティング）から、個々の postback / message
アクションの実処理を切り出したモジュール。レビューセッション操作（start / reveal / grade）と
URL カード生成・保存フロー（生成ディスパッチ / 保存 / レガシー保存）を担う。

サービス singleton は ``webhook.dependencies`` 経由で参照する（``deps.line_service`` 等）。
"""

import json
import os
from typing import Any, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer

from models.card import Reference
from services.ai_service import create_ai_service
from services.card_service import CardNotFoundError
from services.content_chunker import chunk_content
from services.flex_messages import (
    create_answer_message,
    create_error_message,
    create_no_cards_message,
    create_question_message,
    create_url_generation_error_message,
    create_url_generation_progress_message,
)
from services.line_service import LineApiError
from services.url_content_service import UrlContentService
from services.url_generation_service import generate_and_push_url_cards
from utils.url_validator import UrlValidationError, validate_url
from webhook import dependencies as deps

logger = Logger()
tracer = Tracer()

# N-5: URL カード生成の非同期化。
# 受付（webhook Lambda）は進捗 reply まで行い、重い生成本体は SQS へ enqueue して
# 即 return することで API Gateway の 30 秒上限による LINE 側タイムアウトを解消する。
# URL_GENERATE_QUEUE_URL が設定され、かつ URL_WORKER_MODE != "inline" のときのみ enqueue。
# それ以外（ローカル開発・テスト）はその場で同期実行する（インライン）。
# enqueue 失敗時はインライン同期実行へフォールバックしない（30 秒上限問題の再発を防ぐ）。
# 代わりにエラーをユーザーへ通知して即 200 を返す。
# NOTE(ローカル): sam local は SQS → Lambda トリガーを再現できないため、env.json で
# URL_WORKER_MODE="inline" を設定し、ローカルは常に同期実行する。
URL_GENERATE_QUEUE_URL = os.environ.get("URL_GENERATE_QUEUE_URL", "")
URL_WORKER_MODE = os.environ.get("URL_WORKER_MODE", "")

# Lazy 初期化（インラインのみの環境では SQS クライアントを生成しない）。
_sqs_client = None


def _get_sqs_client() -> Any:
    """SQS クライアントを遅延生成して返す。"""
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def _should_enqueue() -> bool:
    """URL カード生成を SQS ワーカーへ非同期ディスパッチすべきか判定する。

    Returns:
        True  — キュー URL があり、かつ inline モードでない（→ enqueue）。
        False — それ以外（→ その場で同期実行＝インライン）。
    """
    return bool(URL_GENERATE_QUEUE_URL) and URL_WORKER_MODE != "inline"


@tracer.capture_method
def handle_start_action(
    user_id: str,
    line_user_id: str,
    reply_token: str,
) -> None:
    """Handle 'start' postback action - begin review session.

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        reply_token: Reply token for response.
    """
    logger.info(f"Starting review session for user: {user_id}")

    # Get due cards
    due_response = deps.review_service.get_due_cards(user_id, limit=1)

    if not due_response.due_cards:
        # No cards due
        deps.line_service.reply_message(reply_token, [create_no_cards_message()])
        return

    # Send first card
    card = due_response.due_cards[0]
    message = create_question_message(card.card_id, card.front)
    deps.line_service.reply_message(reply_token, [message])


@tracer.capture_method
def handle_reveal_action(
    user_id: str,
    card_id: str,
    reply_token: str,
) -> None:
    """Handle 'reveal' postback action - show answer.

    Args:
        user_id: System user ID.
        card_id: Card ID to reveal.
        reply_token: Reply token for response.
    """
    logger.info(f"Revealing answer for card: {card_id}")

    try:
        card = deps.card_service.get_card(user_id, card_id)
        message = create_answer_message(card.card_id, card.front, card.back)
        deps.line_service.reply_message(reply_token, [message])
    except CardNotFoundError:
        logger.warning(f"Card not found: {card_id}")
        deps.line_service.reply_message(reply_token, [create_error_message()])


@tracer.capture_method
def handle_grade_action(
    user_id: str,
    card_id: str,
    grade: int,
    reply_token: str,
) -> None:
    """Handle 'grade' postback action - record review result.

    Args:
        user_id: System user ID.
        card_id: Card ID being reviewed.
        grade: Review grade (0-5).
        reply_token: Reply token for response.
    """
    logger.info(f"Recording grade {grade} for card: {card_id}")

    try:
        # Submit review
        deps.review_service.submit_review(user_id, card_id, grade)

        # Get next due card
        due_response = deps.review_service.get_due_cards(user_id, limit=1)

        if due_response.due_cards:
            # Send next card
            next_card = due_response.due_cards[0]
            message = create_question_message(next_card.card_id, next_card.front)
            deps.line_service.reply_message(reply_token, [message])
        else:
            # No more cards - session complete
            # Use due_response.total_due_count as a proxy for reviewed count
            # since we don't track session-level review count
            deps.line_service.reply_message(
                reply_token,
                [{"type": "text", "text": "🎊 本日の復習が完了しました！お疲れさまです！"}],
            )

    except CardNotFoundError:
        logger.warning(f"Card not found: {card_id}")
        deps.line_service.reply_message(reply_token, [create_error_message()])
    except Exception as e:
        logger.error(f"Error processing grade: {e}")
        deps.line_service.reply_message(reply_token, [create_error_message()])


@tracer.capture_method
def handle_url_card_generation(
    user_id: str,
    line_user_id: str,
    url: str,
    reply_token: str,
    webhook_event_id: Optional[str] = None,
) -> None:
    """Handle URL card generation from LINE chat (N-5: receive + dispatch).

    受付側の責務はバリデーション → 進捗 reply → ディスパッチに簡素化されている。
    重い生成本体（取得 → chunk → Bedrock → 保存 → push）は
    ``services.url_generation_service`` に切り出され、SQS ワーカーで非同期実行される
    （queue 未設定 / inline モード時のみその場で同期実行）。enqueue 失敗時はインライン
    へフォールバックせず、エラーを通知して 200 を返す。

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        url: URL to generate cards from.
        reply_token: Reply token for response (進捗メッセージでここで消費する)。
        webhook_event_id: ワーカー側冪等に使う LINE webhookEventId（enqueue 時に同梱）。
    """
    logger.info(f"Dispatching URL card generation for user: {user_id}, url: {url}")

    # Validate URL before processing (M-1: SSRF prevention)
    try:
        url = validate_url(url)
    except UrlValidationError as e:
        logger.warning(f"URL validation failed: {e}")
        deps.line_service.reply_message(
            reply_token,
            [create_url_generation_error_message(
                f"無効なURLです: {e}"
            )],
        )
        return

    # Send progress message first (reply token はここで消費される)。
    try:
        deps.line_service.reply_message(
            reply_token,
            [create_url_generation_progress_message(url)],
        )
    except LineApiError:
        logger.warning("Failed to send progress message")

    # ディスパッチ: 非同期（SQS）かインライン（同期）か。
    if _should_enqueue():
        try:
            _enqueue_url_generation(
                user_id=user_id,
                line_user_id=line_user_id,
                url=url,
                webhook_event_id=webhook_event_id or "",
            )
        except Exception as e:
            # enqueue 失敗時にインライン同期実行へフォールバックすると 30 秒上限問題が
            # 再発するため、フォールバックは廃止。error ログを残し、best-effort で
            # ユーザーにエラーを通知して受付は 200 で返す（受付は決して落とさない）。
            logger.error(f"Failed to enqueue URL generation: {e}")
            try:
                deps.line_service.push_message(
                    line_user_id,
                    [create_url_generation_error_message(
                        "エラーが発生しました。しばらくしてからもう一度 URL を送信してください。"
                    )],
                )
            except Exception as push_err:
                logger.warning(
                    f"Failed to push enqueue-failure notification: {push_err}"
                )
        return

    # インライン同期実行（_should_enqueue() == False の場合のみ：
    # queue 未設定 or URL_WORKER_MODE=inline）。ローカル開発・テスト相当。
    generate_and_push_url_cards(
        user_id=user_id,
        line_user_id=line_user_id,
        url=url,
    )


def _enqueue_url_generation(
    user_id: str,
    line_user_id: str,
    url: str,
    webhook_event_id: str,
) -> None:
    """URL カード生成リクエストを SQS ワーカーキューへ送信する。

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        url: 生成元 URL（バリデーション済み）。
        webhook_event_id: ワーカー側冪等用の LINE webhookEventId。
    """
    payload = {
        "user_id": user_id,
        "line_user_id": line_user_id,
        "url": url,
        "webhook_event_id": webhook_event_id,
    }
    _get_sqs_client().send_message(
        QueueUrl=URL_GENERATE_QUEUE_URL,
        MessageBody=json.dumps(payload, ensure_ascii=False),
    )
    logger.info(
        "Enqueued URL card generation",
        extra={"user_id": user_id, "webhook_event_id": webhook_event_id},
    )


@tracer.capture_method
def handle_save_url_cards(
    user_id: str,
    line_user_id: str,
    ref_key: str,
    reply_token: str,
) -> None:
    """Handle save URL cards postback action (C-3 reference-key flow).

    Loads the previously-generated cards from UrlCardsStore by ref_key and
    saves them as-is — WITHOUT re-fetching the URL or re-invoking Bedrock.
    This keeps the saved cards identical to the preview and avoids double
    AI cost. user_id is resolved from the webhook event, not the postback.

    Args:
        user_id: System user ID (resolved from the LINE user in handle_postback).
        line_user_id: LINE user ID.
        ref_key: Reference key into UrlCardsStore.
        reply_token: Reply token for response.
    """
    logger.info(f"Saving URL cards for user: {user_id}, ref_key: {ref_key}")

    pending = deps.url_cards_store.get_pending_cards(ref_key)
    if not pending or not pending.get("cards"):
        # Record missing or TTL-expired.
        deps.line_service.reply_message(
            reply_token,
            [{
                "type": "text",
                "text": "有効期限が切れました。もう一度 URL を送信してください。",
            }],
        )
        return

    # Two-tap / double-save guard: only the first tap proceeds.
    if not deps.url_cards_store.mark_saved(ref_key):
        logger.info(f"URL cards already saved for ref_key: {ref_key}")
        deps.line_service.reply_message(
            reply_token,
            [{"type": "text", "text": "このカードは既に保存済みです。"}],
        )
        return

    page_url = pending.get("page_url", "")
    cards = pending.get("cards", [])

    references = [Reference(type="url", value=page_url)] if page_url else []

    saved_count = 0
    for card in cards:
        front = str(card.get("front", "")).strip()
        back = str(card.get("back", "")).strip()
        if not front or not back:
            continue
        tags = card.get("suggested_tags") or card.get("tags") or []
        try:
            deps.card_service.create_card(
                user_id=user_id,
                front=front,
                back=back,
                tags=tags,
                references=references,
            )
            saved_count += 1
        except Exception as e:
            logger.warning(f"Failed to save card: {e}")

    deps.line_service.reply_message(
        reply_token,
        [{"type": "text", "text": f"✅ {saved_count}枚のカードを保存しました！"}],
    )


@tracer.capture_method
def handle_save_url_cards_legacy(
    user_id: str,
    line_user_id: str,
    url: str,
    count: int,
    reply_token: str,
) -> None:
    """Legacy save flow for old-format postbacks (``url=`` param).

    Pre-C-3 carousels embedded the URL in the postback and re-generated cards
    on save. Such postbacks may still arrive across a deploy boundary, so this
    fallback re-fetches + re-generates as before.

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        url: Source URL.
        count: Number of cards to save.
        reply_token: Reply token for response.
    """
    logger.info(f"Saving URL cards (legacy) for user: {user_id}, url: {url}")

    # Validate URL before processing (C-2: SSRF prevention)
    try:
        url = validate_url(url)
    except UrlValidationError as e:
        logger.warning(f"URL validation failed in save_url_cards: {e}")
        deps.line_service.reply_message(
            reply_token,
            [create_url_generation_error_message(f"無効なURLです: {e}")],
        )
        return

    try:
        # Re-fetch and generate
        content_service = UrlContentService()
        page = content_service.fetch_content(url)

        chunks = chunk_content(page.text_content, page_title=page.title)
        chunk_texts = [c.text for c in chunks]

        if not chunk_texts:
            deps.line_service.reply_message(
                reply_token,
                [create_url_generation_error_message("テキストを抽出できませんでした。")],
            )
            return

        ai_service = create_ai_service()
        result = ai_service.generate_cards_from_chunks(
            chunks=chunk_texts,
            card_type="qa",
            target_count=count,
            difficulty="medium",
            language="ja",
            page_title=page.title,
        )

        # Save each card
        saved_count = 0
        for card in result.cards[:count]:
            try:
                deps.card_service.create_card(
                    user_id=user_id,
                    front=card.front,
                    back=card.back,
                    tags=card.suggested_tags,
                    references=[Reference(type="url", value=page.url)],
                )
                saved_count += 1
            except Exception as e:
                logger.warning(f"Failed to save card: {e}")

        deps.line_service.reply_message(
            reply_token,
            [{"type": "text", "text": f"✅ {saved_count}枚のカードを保存しました！"}],
        )

    except Exception as e:
        logger.error(f"Error saving URL cards: {e}")
        deps.line_service.reply_message(
            reply_token,
            [create_error_message()],
        )
