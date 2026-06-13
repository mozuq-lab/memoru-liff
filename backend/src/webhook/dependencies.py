"""Shared service singletons for the LINE webhook handlers.

line_handler（Lambda 入口 + ルーティング）と line_actions（アクションハンドラ）の双方が
同一のサービスインスタンスを参照できるよう、循環 import を避けて 1 箇所に集約する。

ハンドラ側は ``from webhook import dependencies as deps`` で取り込み、``deps.line_service``
のように呼び出し時に属性参照する。これにより ``patch("webhook.dependencies.line_service")``
がどのモジュールのハンドラからでも有効になる。
"""

from services.card_service import CardService
from services.line_service import LineService
from services.review_service import ReviewService
from services.url_cards_store import UrlCardsStore
from services.webhook_idempotency import WebhookIdempotencyService

line_service = LineService()
card_service = CardService()
review_service = ReviewService()
idempotency_service = WebhookIdempotencyService()
url_cards_store = UrlCardsStore()
