"""Flex Message templates for LINE Messaging API."""

import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote


def create_question_message(card_id: str, front: str) -> Dict[str, Any]:
    """Create question display Flex Message.

    Args:
        card_id: Card ID for postback data.
        front: Question text (front of card).

    Returns:
        Flex Message JSON structure.
    """
    return {
        "type": "flex",
        "altText": "復習カード",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📚 復習カード",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#1DB446",
                    }
                ],
                "backgroundColor": "#F7F7F7",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": front,
                        "wrap": True,
                        "size": "md",
                        "weight": "bold",
                    }
                ],
                "paddingAll": "20px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "解答を見る",
                            "data": f"action=reveal&card_id={card_id}",
                        },
                        "style": "primary",
                        "color": "#1DB446",
                    }
                ],
            },
        },
    }


def create_answer_message(
    card_id: str,
    front: str,
    back: str,
) -> Dict[str, Any]:
    """Create answer display Flex Message with grade buttons.

    Args:
        card_id: Card ID for postback data.
        front: Question text.
        back: Answer text.

    Returns:
        Flex Message JSON structure.
    """
    grade_buttons = []
    grade_labels = [
        ("0", "忘れた"),
        ("1", "間違い"),
        ("2", "難しい"),
        ("3", "正解△"),
        ("4", "正解○"),
        ("5", "完璧"),
    ]

    for grade, label in grade_labels:
        grade_buttons.append(
            {
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": label,
                    "data": f"action=grade&card_id={card_id}&grade={grade}",
                },
                "style": "secondary",
                "height": "sm",
                "flex": 1,
            }
        )

    return {
        "type": "flex",
        "altText": "解答と成績入力",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📖 解答",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#1DB446",
                    }
                ],
                "backgroundColor": "#F7F7F7",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "問題",
                        "weight": "bold",
                        "size": "sm",
                        "color": "#888888",
                    },
                    {
                        "type": "text",
                        "text": front,
                        "wrap": True,
                        "size": "md",
                        "margin": "sm",
                    },
                    {
                        "type": "separator",
                        "margin": "lg",
                    },
                    {
                        "type": "text",
                        "text": "解答",
                        "weight": "bold",
                        "size": "sm",
                        "color": "#888888",
                        "margin": "lg",
                    },
                    {
                        "type": "text",
                        "text": back,
                        "wrap": True,
                        "size": "md",
                        "margin": "sm",
                        "weight": "bold",
                        "color": "#1DB446",
                    },
                ],
                "paddingAll": "20px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "覚え具合を選んでください",
                        "size": "xs",
                        "color": "#888888",
                        "align": "center",
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": grade_buttons[:3],
                        "margin": "md",
                        "spacing": "xs",
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": grade_buttons[3:],
                        "margin": "sm",
                        "spacing": "xs",
                    },
                ],
            },
        },
    }


def create_no_cards_message() -> Dict[str, Any]:
    """Create message for when there are no cards due.

    Returns:
        Text message JSON structure.
    """
    return {
        "type": "text",
        "text": "🎉 復習するカードはありません！\n\n素晴らしい！全てのカードが期限内です。",
    }


def create_completion_message(reviewed_count: int) -> Dict[str, Any]:
    """Create message for when review session is complete.

    Args:
        reviewed_count: Number of cards reviewed.

    Returns:
        Flex Message JSON structure.
    """
    return {
        "type": "flex",
        "altText": "復習完了！",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🎊 本日の復習が完了しました！",
                        "weight": "bold",
                        "size": "lg",
                        "align": "center",
                    },
                    {
                        "type": "text",
                        "text": f"{reviewed_count}枚のカードを復習しました",
                        "size": "md",
                        "align": "center",
                        "margin": "md",
                        "color": "#888888",
                    },
                ],
                "paddingAll": "20px",
            },
        },
    }


def create_link_required_message(liff_url: str) -> Dict[str, Any]:
    """Create message for when user needs to link account.

    Args:
        liff_url: LIFF app URL for account linking.

    Returns:
        Flex Message JSON structure.
    """
    return {
        "type": "flex",
        "altText": "アカウント連携が必要です",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📱 アカウント連携が必要です",
                        "weight": "bold",
                        "size": "lg",
                        "align": "center",
                    },
                    {
                        "type": "text",
                        "text": "LINEで復習を始めるには、アプリでアカウントを連携してください。",
                        "wrap": True,
                        "size": "sm",
                        "align": "center",
                        "margin": "md",
                        "color": "#888888",
                    },
                ],
                "paddingAll": "20px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "アプリを開く",
                            "uri": liff_url,
                        },
                        "style": "primary",
                        "color": "#1DB446",
                    }
                ],
            },
        },
    }


def create_error_message() -> Dict[str, Any]:
    """Create generic error message.

    Returns:
        Text message JSON structure.
    """
    return {
        "type": "text",
        "text": "申し訳ありません、エラーが発生しました。\n\nしばらくしてからもう一度お試しください。",
    }


def create_reminder_message(due_count: int) -> Dict[str, Any]:
    """Create review reminder push message.

    Args:
        due_count: Number of cards due for review.

    Returns:
        Flex Message JSON structure.
    """
    return {
        "type": "flex",
        "altText": "復習リマインド",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📚 復習の時間です！",
                        "weight": "bold",
                        "size": "lg",
                        "align": "center",
                        "color": "#1DB446",
                    },
                    {
                        "type": "text",
                        "text": f"{due_count}枚のカードが復習を待っています",
                        "wrap": True,
                        "size": "md",
                        "align": "center",
                        "margin": "md",
                        "color": "#666666",
                    },
                ],
                "paddingAll": "20px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "復習を始める",
                            "data": "action=start",
                        },
                        "style": "primary",
                        "color": "#1DB446",
                    }
                ],
            },
        },
    }


# ============================================================
# URL Card Generation Messages
# ============================================================


def create_url_generation_progress_message(url: str) -> Dict[str, Any]:
    """Create progress message for URL card generation.

    Args:
        url: The URL being processed.

    Returns:
        Text message JSON structure.
    """
    # Extract domain for display
    from urllib.parse import urlparse

    domain = urlparse(url).netloc or url
    return {
        "type": "text",
        "text": f"🔄 {domain} からカードを生成中です...\n\nしばらくお待ちください。",
    }


def create_card_preview_carousel(
    cards: List[Dict[str, Any]],
    page_title: str,
    page_url: str,
    user_id: str,
) -> Dict[str, Any]:
    """Create card preview carousel Flex Message.

    Shows generated cards in a carousel format with save button.
    LINE carousel supports max 10 bubbles.

    Args:
        cards: List of generated card dicts with front/back/tags.
        page_title: Title of the source page.
        page_url: URL of the source page.
        user_id: System user ID for save postback.

    Returns:
        Flex Message JSON structure.
    """
    if not cards:
        return {
            "type": "text",
            "text": "カードを生成できませんでした。別のURLでお試しください。",
        }

    # LINE carousel max is 10 bubbles; reserve 1 for summary
    max_card_bubbles = 9
    display_cards = cards[:max_card_bubbles]

    bubbles: List[Dict[str, Any]] = []

    for i, card in enumerate(display_cards):
        front = str(card.get("front", ""))
        back = str(card.get("back", ""))

        # Truncate long text for display
        if len(front) > 100:
            front = front[:97] + "..."
        if len(back) > 100:
            back = back[:97] + "..."

        bubble: Dict[str, Any] = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"カード {i + 1}/{len(display_cards)}",
                        "size": "xs",
                        "color": "#888888",
                    }
                ],
                "paddingBottom": "0px",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "問題",
                        "size": "xs",
                        "color": "#888888",
                        "weight": "bold",
                    },
                    {
                        "type": "text",
                        "text": front,
                        "wrap": True,
                        "size": "sm",
                        "margin": "xs",
                    },
                    {
                        "type": "separator",
                        "margin": "md",
                    },
                    {
                        "type": "text",
                        "text": "解答",
                        "size": "xs",
                        "color": "#888888",
                        "weight": "bold",
                        "margin": "md",
                    },
                    {
                        "type": "text",
                        "text": back,
                        "wrap": True,
                        "size": "sm",
                        "margin": "xs",
                        "color": "#1DB446",
                    },
                ],
                "paddingAll": "16px",
            },
        }
        bubbles.append(bubble)

    # Summary bubble with save button
    cards_json = json.dumps(
        [{"front": c["front"], "back": c["back"], "tags": c.get("tags", [])} for c in display_cards],
        ensure_ascii=False,
    )
    # Postback data has 300 char limit, so we use a reference key
    postback_data = f"action=save_url_cards&user_id={user_id}&count={len(display_cards)}&url={quote(page_url, safe='')}"

    summary_bubble: Dict[str, Any] = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"📄 {page_title}" if page_title else "📄 Webページ",
                    "weight": "bold",
                    "size": "sm",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": f"{len(display_cards)}枚のカードを生成しました",
                    "size": "sm",
                    "color": "#888888",
                    "margin": "md",
                },
            ],
            "paddingAll": "16px",
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": f"全{len(display_cards)}枚を保存",
                        "data": postback_data,
                    },
                    "style": "primary",
                    "color": "#1DB446",
                },
            ],
        },
    }
    bubbles.append(summary_bubble)

    return {
        "type": "flex",
        "altText": f"URLから{len(display_cards)}枚のカードを生成しました",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }


def create_url_generation_error_message(error: str) -> Dict[str, Any]:
    """Create error message for URL card generation failure.

    Args:
        error: Error description.

    Returns:
        Text message JSON structure.
    """
    return {
        "type": "text",
        "text": f"⚠️ カード生成エラー\n\n{error}\n\n別のURLでお試しください。",
    }
