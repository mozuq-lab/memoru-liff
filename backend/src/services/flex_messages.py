"""Flex Message templates for LINE Messaging API."""

from typing import Any, Dict, List, Optional


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
