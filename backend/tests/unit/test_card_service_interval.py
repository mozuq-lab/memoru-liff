"""Unit tests for CardService.update_card with interval parameter.

【テスト目的】: CardService.update_card の interval パラメータ拡張をテスト
【テスト内容】: interval 指定時の next_review_at 再計算、ease_factor/repetitions の不変性を検証
【期待される動作】: interval 指定時に next_review_at が正しく計算され、SRS パラメータが保持される
🔵 要件定義 REQ-002〜004, REQ-401〜403, 受け入れ基準 TC-003-01〜TC-004-02 より
"""

import pytest
from moto import mock_aws
import boto3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from services.card_service import (
    CardService,
    CardNotFoundError,
)


# 【テスト前準備】: モック DynamoDB テーブルを作成するフィクスチャ
# 【環境初期化】: 各テストが独立した DynamoDB 環境で動作するように設定
@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB tables (cards, users, reviews)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # 【カードテーブル作成】: GSI (user_id-due-index) を含むカードテーブルを作成
        cards_table = dynamodb.create_table(
            TableName="memoru-cards-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "card_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "card_id", "AttributeType": "S"},
                {"AttributeName": "next_review_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-due-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "next_review_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        cards_table.wait_until_exists()

        # 【ユーザーテーブル作成】: card_count 管理用のユーザーテーブルを作成
        users_table = dynamodb.create_table(
            TableName="memoru-users-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        users_table.wait_until_exists()

        # 【レビューテーブル作成】: TC-N07 での review_history 非記録確認用
        reviews_table = dynamodb.create_table(
            TableName="memoru-reviews-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "card_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "card_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        reviews_table.wait_until_exists()

        yield dynamodb


@pytest.fixture
def card_service(dynamodb_table):
    """Create CardService with mock DynamoDB.

    【テスト前準備】: CardService インスタンスを作成し、transact_write_items をモックする
    【実装詳細】: moto の transact_write_items にバグがあるためカスタムモックを使用
    """
    service = CardService(
        table_name="memoru-cards-test",
        users_table_name="memoru-users-test",
        reviews_table_name="memoru-reviews-test",
        dynamodb_resource=dynamodb_table,
    )

    # 【transact_write_items モック】: moto のバグを回避するカスタムモック
    users_table = dynamodb_table.Table("memoru-users-test")
    cards_table = dynamodb_table.Table("memoru-cards-test")
    reviews_table = dynamodb_table.Table("memoru-reviews-test")

    def mock_transact_write_items(TransactItems, **kwargs):
        from boto3.dynamodb.types import TypeDeserializer
        from botocore.exceptions import ClientError

        deserializer = TypeDeserializer()

        for item in TransactItems:
            if 'Update' in item:
                update = item['Update']
                table_name = update['TableName']
                table = users_table if 'users' in table_name else cards_table

                key_dict = {k: deserializer.deserialize(v) for k, v in update['Key'].items()}

                if 'users' in table_name:
                    try:
                        response = table.get_item(Key=key_dict)
                        if 'Item' not in response:
                            table.put_item(Item={**key_dict, 'card_count': 0})
                    except Exception:
                        pass

                if 'ConditionExpression' in update:
                    response = table.get_item(Key=key_dict)
                    current_item = response.get('Item', {})
                    expr_values = update.get('ExpressionAttributeValues', {})
                    card_count = int(current_item.get('card_count', 0))

                    if ':limit' in expr_values:
                        limit = int(expr_values[':limit']['N'])
                        if not (card_count < limit):
                            raise ClientError(
                                {
                                    "Error": {
                                        "Code": "TransactionCanceledException",
                                        "Message": "Transaction cancelled",
                                    },
                                    "CancellationReasons": [{"Code": "ConditionalCheckFailed"}],
                                },
                                "TransactWriteItems",
                            )

                all_expr_values = {k: deserializer.deserialize(v) for k, v in update.get('ExpressionAttributeValues', {}).items()}
                update_expr = update['UpdateExpression']

                used_values = {}
                for key in all_expr_values:
                    if key in update_expr:
                        used_values[key] = all_expr_values[key]

                expr_names = update.get('ExpressionAttributeNames', {})

                update_item_kwargs = {
                    "Key": key_dict,
                    "UpdateExpression": update_expr,
                }
                if used_values:
                    update_item_kwargs["ExpressionAttributeValues"] = used_values
                if expr_names:
                    update_item_kwargs["ExpressionAttributeNames"] = expr_names

                table.update_item(**update_item_kwargs)

            elif 'Put' in item:
                put = item['Put']
                table_name = put['TableName']
                table = cards_table if 'cards' in table_name else users_table
                item_dict = {k: deserializer.deserialize(v) for k, v in put['Item'].items()}
                table.put_item(Item=item_dict)

            elif 'Delete' in item:
                delete = item['Delete']
                table_name = delete['TableName']
                if 'cards' in table_name:
                    table = cards_table
                elif 'reviews' in table_name:
                    table = reviews_table
                else:
                    table = users_table

                key_dict = {k: deserializer.deserialize(v) for k, v in delete['Key'].items()}
                table.delete_item(Key=key_dict)

        return {}

    service._client.transact_write_items = mock_transact_write_items
    return service


class TestCardServiceUpdateInterval:
    """Tests for CardService.update_card with interval parameter.

    【テストクラス目的】: TASK-0078 で追加される interval パラメータのサービス層テスト
    【テスト対象】: backend/src/services/card_service.py の update_card メソッド
    🔵 要件定義 REQ-002〜004, REQ-401〜403 より
    """

    # 【固定日時】: datetime.now() のモックに使用する固定日時
    # 【選択理由】: 再現可能なテストのために固定日時を使用する
    FIXED_NOW = datetime(2026, 2, 28, 10, 0, 0, tzinfo=timezone.utc)

    def test_update_card_interval_only(self, card_service):
        """TC-N01: interval のみ指定してカード更新が成功する。

        【テスト目的】: card_service.update_card に interval=7 を指定した場合に、
                       interval と next_review_at が正しく更新されることを確認
        【テスト内容】: interval=7 で update_card を呼び出し、返却された Card を検証
        【期待される動作】: interval=7, next_review_at=現在日時+7日 が設定される
        🔵 信頼性レベル: 要件定義 REQ-003, 受け入れ基準 TC-003-01 より
        """
        # 【テストデータ準備】: interval 更新テスト用のカードを作成する
        # 【初期条件設定】: 典型的な復習データを持つカードを用意
        created = card_service.create_card(
            user_id="test-user-id",
            front="問題文",
            back="答え",
        )

        # 【実際の処理実行】: card_service.update_card に interval=7 を渡して更新を実行
        # 【処理内容】: interval + next_review_at の再計算と DynamoDB 更新
        # 【実行タイミング】: datetime.now をモックして固定日時で検証
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            updated = card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=7,
            )

        # 【結果検証】: 返却された Card オブジェクトの各フィールドを検証
        # 【期待値確認】: interval=7, next_review_at=固定日時+7日

        # 【検証項目】: interval が指定した値に更新されていること
        assert updated.interval == 7  # 【確認内容】: interval が 7 に更新されていること 🔵

        # 【検証項目】: next_review_at が正しく再計算されていること
        expected_next_review = self.FIXED_NOW + timedelta(days=7)
        assert updated.next_review_at is not None  # 【確認内容】: next_review_at が None でないこと 🔵
        assert updated.next_review_at.replace(tzinfo=timezone.utc) == expected_next_review  # 【確認内容】: next_review_at が 7 日後になること 🔵

        # 【検証項目】: updated_at が自動付与されていること
        assert updated.updated_at is not None  # 【確認内容】: updated_at が自動付与されること 🔵

    def test_update_card_interval_ease_factor_unchanged(self, card_service):
        """TC-N02: interval 指定時に ease_factor が変更されない。

        【テスト目的】: interval を更新した後、既存の ease_factor が保持されることを確認
        【テスト内容】: ease_factor=2.8 のカードに interval=14 で更新し、ease_factor を検証
        【期待される動作】: ease_factor は UpdateExpression に含まれず、元の値がそのまま残る
        🔵 信頼性レベル: 要件定義 REQ-004, 受け入れ基準 TC-004-01 より
        """
        # 【テストデータ準備】: ease_factor=2.8 のカードを作成する
        # 【前提条件確認】: SM-2 で ease_factor が変化したカードへの interval 調整を再現
        created = card_service.create_card(
            user_id="test-user-id",
            front="問題文",
            back="答え",
        )

        # 【初期条件設定】: ease_factor=2.8, repetitions=3 の復習データを設定
        # 【実装詳細】: update_review_data を使用して SRS パラメータを設定
        # 【注意】: update_review_data は quality パラメータを受け取らない
        card_service.update_review_data(
            user_id="test-user-id",
            card_id=created.card_id,
            ease_factor=2.8,
            interval=3,
            repetitions=3,
            next_review_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
        )

        # 【実際の処理実行】: interval=14 で update_card を呼び出す
        # 【処理内容】: interval のみを更新し、ease_factor は変更しない
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            updated = card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=14,
            )

        # 【結果検証】: ease_factor が元の値のまま保持されることを確認
        # 【品質保証】: SRS パラメータの不変性を保証
        assert updated.ease_factor == 2.8  # 【確認内容】: ease_factor が元の値 2.8 のまま保持されること 🔵
        assert updated.interval == 14  # 【確認内容】: interval が 14 に更新されていること 🔵

    def test_update_card_interval_repetitions_unchanged(self, card_service):
        """TC-N03: interval 指定時に repetitions が変更されない。

        【テスト目的】: interval を更新した後、既存の repetitions が保持されることを確認
        【テスト内容】: repetitions=5 のカードに interval=30 で更新し、repetitions を検証
        【期待される動作】: repetitions は UpdateExpression に含まれず、元の値がそのまま残る
        🔵 信頼性レベル: 要件定義 REQ-004, 受け入れ基準 TC-004-02 より
        """
        # 【テストデータ準備】: repetitions=5 のカードを作成する
        # 【前提条件確認】: 復習回数が蓄積されたカードへの interval 調整を再現
        created = card_service.create_card(
            user_id="test-user-id",
            front="問題文",
            back="答え",
        )

        # 【初期条件設定】: repetitions=5 の復習データを設定
        # 【注意】: update_review_data は quality パラメータを受け取らない
        card_service.update_review_data(
            user_id="test-user-id",
            card_id=created.card_id,
            ease_factor=2.5,
            interval=10,
            repetitions=5,
            next_review_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
        )

        # 【実際の処理実行】: interval=30 で update_card を呼び出す
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            updated = card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=30,
            )

        # 【結果検証】: repetitions が元の値のまま保持されることを確認
        assert updated.repetitions == 5  # 【確認内容】: repetitions が元の値 5 のまま保持されること 🔵
        assert updated.interval == 30  # 【確認内容】: interval が 30 に更新されていること 🔵

    def test_update_card_interval_and_front_simultaneously(self, card_service):
        """TC-N04: interval と front を同時に指定して更新が成功する。

        【テスト目的】: interval と front/back を同時に指定した場合、全フィールドが
                       1 つの UpdateExpression でまとめて更新されることを確認
        【テスト内容】: front="新しい問題文" と interval=14 を同時に指定して update_card を呼び出す
        【期待される動作】: front の更新と interval/next_review_at の更新が同時に反映される
        🔵 信頼性レベル: 設計文書 architecture.md 技術的制約セクションより
        """
        # 【テストデータ準備】: 同時更新テスト用のカードを作成する
        created = card_service.create_card(
            user_id="test-user-id",
            front="古い問題文",
            back="答え",
        )

        # 【実際の処理実行】: front と interval を同時に指定して update_card を呼び出す
        # 【処理内容】: 1 つの UpdateExpression で front と interval/next_review_at を同時更新
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            updated = card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                front="新しい問題文",
                interval=14,
            )

        # 【結果検証】: 両フィールドが正しく更新されることを確認
        assert updated.front == "新しい問題文"  # 【確認内容】: front が正しく更新されること 🔵
        assert updated.interval == 14  # 【確認内容】: interval が 14 に更新されること 🔵
        expected_next_review = self.FIXED_NOW + timedelta(days=14)
        assert updated.next_review_at is not None  # 【確認内容】: next_review_at が設定されること 🔵
        assert updated.next_review_at.replace(tzinfo=timezone.utc) == expected_next_review  # 【確認内容】: next_review_at が 14 日後になること 🔵

    def test_update_card_without_interval_does_not_change_interval(self, card_service):
        """TC-N05: interval 未指定時に interval/next_review_at が変更されない。

        【テスト目的】: interval を指定せずに front のみ更新した場合、interval と next_review_at は
                       元の値のまま保持されることを確認
        【テスト内容】: front のみを指定して update_card を呼び出し、interval と next_review_at を検証
        【期待される動作】: interval 関連のフィールドが UpdateExpression に含まれない（後方互換性）
        🔵 信頼性レベル: 要件定義 REQ-401, REQ-402 より
        """
        # 【テストデータ準備】: interval が設定されたカードを作成する
        created = card_service.create_card(
            user_id="test-user-id",
            front="古い問題文",
            back="答え",
        )

        # 【初期条件設定】: interval=7 の復習データを設定して元の値を記録
        # 【注意】: update_review_data は quality パラメータを受け取らない
        original_next_review = datetime(2026, 3, 7, tzinfo=timezone.utc)
        card_service.update_review_data(
            user_id="test-user-id",
            card_id=created.card_id,
            ease_factor=2.5,
            interval=7,
            repetitions=2,
            next_review_at=original_next_review,
        )

        # 【元の値を確認】: 更新前の interval と next_review_at を取得
        original_card = card_service.get_card("test-user-id", created.card_id)
        original_interval = original_card.interval
        original_next_review_at = original_card.next_review_at

        # 【実際の処理実行】: front のみを指定して update_card を呼び出す（interval 未指定）
        # 【処理内容】: interval 関連フィールドは UpdateExpression に含まれない
        updated = card_service.update_card(
            user_id="test-user-id",
            card_id=created.card_id,
            front="更新された問題文",
        )

        # 【結果検証】: interval と next_review_at が元の値のまま保持されることを確認
        assert updated.front == "更新された問題文"  # 【確認内容】: front が正しく更新されること 🔵
        assert updated.interval == original_interval  # 【確認内容】: interval が変更されていないこと 🔵
        assert updated.next_review_at == original_next_review_at  # 【確認内容】: next_review_at が変更されていないこと 🔵

    def test_update_card_interval_not_recorded_in_review_history(self, card_service, dynamodb_table):
        """TC-N07: interval 更新が review_history に記録されない。

        【テスト目的】: interval 更新が復習操作ではないため、review_history テーブルに
                       レコードが追加されないことを確認
        【テスト内容】: interval=7 で update_card を実行後、reviews テーブルを確認
        【期待される動作】: reviews テーブルにレコードが追加されていない
        🟡 信頼性レベル: 要件定義 REQ-403 より（「記録してはならない」の明示的検証）
        """
        # 【テストデータ準備】: review_history 確認用のカードを作成する
        created = card_service.create_card(
            user_id="test-user-id",
            front="問題文",
            back="答え",
        )

        # 【実際の処理実行】: interval=7 で update_card を呼び出す
        # 【処理内容】: review_service は呼び出されず、review_history には記録されない
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=7,
            )

        # 【結果検証】: reviews テーブルにレコードが追加されていないことを確認
        reviews_table = dynamodb_table.Table("memoru-reviews-test")
        result = reviews_table.scan()
        assert result["Count"] == 0  # 【確認内容】: reviews テーブルにレコードが 0 件であること 🟡

    def test_update_card_interval_not_found_raises_error(self, card_service):
        """TC-E06: 存在しないカードの interval 更新で CardNotFoundError が発生する。

        【テスト目的】: 存在しない card_id に対する interval 更新が適切にエラーとなることを確認
        【テスト内容】: 存在しない card_id で interval=7 を指定して update_card を呼び出す
        【期待される動作】: CardNotFoundError が発生する
        🔵 信頼性レベル: 既存テスト test_update_card_not_found と同パターン
        """
        # 【テストデータ準備】: 存在しない card_id
        # 【初期条件設定】: DynamoDB に該当カードは存在しない
        with pytest.raises(CardNotFoundError):
            card_service.update_card(
                user_id="test-user-id",
                card_id="non-existent-card",
                interval=7,
            )
        # 【確認内容】: CardNotFoundError が発生すること 🔵

    def test_update_card_interval_boundary_min(self, card_service):
        """TC-B01: interval=1（最小値）で正常に更新できる。

        【テスト目的】: ge=1 制約の下限値 1 でサービス層が正常動作することを確認
        【テスト内容】: interval=1 で update_card を呼び出し、翌日の next_review_at を検証
        【期待される動作】: interval=1, next_review_at=現在日時+1日 が設定される
        🔵 信頼性レベル: 要件定義 EDGE-101, TC-101-B01, TC-003-02 より
        """
        # 【テストデータ準備】: 下限境界値テスト用のカードを作成する
        created = card_service.create_card(
            user_id="test-user-id",
            front="問題文",
            back="答え",
        )

        # 【実際の処理実行】: interval=1 で update_card を呼び出す
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            updated = card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=1,
            )

        # 【結果検証】: interval=1, next_review_at=翌日 であることを確認
        assert updated.interval == 1  # 【確認内容】: interval が 1 に更新されていること 🔵
        expected_next_review = self.FIXED_NOW + timedelta(days=1)
        assert updated.next_review_at is not None  # 【確認内容】: next_review_at が設定されること 🔵
        assert updated.next_review_at.replace(tzinfo=timezone.utc) == expected_next_review  # 【確認内容】: next_review_at が翌日になること 🔵

    def test_update_card_interval_boundary_max(self, card_service):
        """TC-B02: interval=365（最大値）で正常に更新できる。

        【テスト目的】: le=365 制約の上限値 365 でサービス層が正常動作することを確認
        【テスト内容】: interval=365 で update_card を呼び出し、365日後の next_review_at を検証
        【期待される動作】: interval=365, next_review_at=現在日時+365日 が設定される
        🔵 信頼性レベル: 要件定義 EDGE-102, TC-102-B01 より
        """
        # 【テストデータ準備】: 上限境界値テスト用のカードを作成する
        created = card_service.create_card(
            user_id="test-user-id",
            front="問題文",
            back="答え",
        )

        # 【実際の処理実行】: interval=365 で update_card を呼び出す
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            updated = card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=365,
            )

        # 【結果検証】: interval=365, next_review_at=365日後 であることを確認
        assert updated.interval == 365  # 【確認内容】: interval が 365 に更新されていること 🔵
        expected_next_review = self.FIXED_NOW + timedelta(days=365)
        assert updated.next_review_at is not None  # 【確認内容】: next_review_at が設定されること 🔵
        assert updated.next_review_at.replace(tzinfo=timezone.utc) == expected_next_review  # 【確認内容】: next_review_at が 365 日後になること 🔵

    def test_update_card_interval_on_fresh_card(self, card_service):
        """TC-B03: 未復習カード（repetitions=0, interval=0）に interval 調整ができる。

        【テスト目的】: カード作成直後の初期状態にも interval 調整が可能であることを確認
        【テスト内容】: 新規カード（repetitions=0, interval=0）に interval=7 で更新する
        【期待される動作】: interval=7, next_review_at=現在日時+7日, repetitions=0 が設定される
        🟡 信頼性レベル: 要件定義 EDGE-103 より（初期状態カードへの操作として妥当な推測）
        """
        # 【テストデータ準備】: 未復習カード（作成直後）を用意する
        # 【初期条件設定】: 作成直後のカードは repetitions=0, interval=0 の初期状態
        created = card_service.create_card(
            user_id="test-user-id",
            front="問題文",
            back="答え",
        )

        # 【前提条件確認】: カードが初期状態であることを確認
        assert created.repetitions == 0  # 【確認内容】: 未復習状態 (repetitions=0) であること 🟡

        # 【実際の処理実行】: 未復習カードに interval=7 で update_card を呼び出す
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            updated = card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=7,
            )

        # 【結果検証】: interval が更新され、repetitions が 0 のまま保持されることを確認
        assert updated.interval == 7  # 【確認内容】: interval が 7 に更新されていること 🟡
        assert updated.repetitions == 0  # 【確認内容】: repetitions が 0 のまま保持されること 🟡
        expected_next_review = self.FIXED_NOW + timedelta(days=7)
        assert updated.next_review_at is not None  # 【確認内容】: next_review_at が設定されること 🟡
        assert updated.next_review_at.replace(tzinfo=timezone.utc) == expected_next_review  # 【確認内容】: next_review_at が 7 日後になること 🟡

    def test_update_card_interval_next_review_at_format(self, card_service, dynamodb_table):
        """TC-N06: next_review_at が ISO 8601 形式 (UTC) で DynamoDB に保存される。

        【テスト目的】: interval 更新後の next_review_at が DynamoDB に ISO 8601 形式で保存され、
                       GSI ソートキーとして正しく機能することを確認
        【テスト内容】: interval=7 で update_card を実行後、DynamoDB から直接 next_review_at を取得
        【期待される動作】: DynamoDB 上の next_review_at が ISO 8601 形式（UTC）で保存される
        🟡 信頼性レベル: 設計文書 architecture.md, note.md の技術的制約から妥当な推測
        """
        # 【テストデータ準備】: ISO 8601 形式確認用のカードを作成する
        created = card_service.create_card(
            user_id="test-user-id",
            front="問題文",
            back="答え",
        )

        # 【実際の処理実行】: interval=7 で update_card を呼び出す（固定日時でモック）
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = self.FIXED_NOW
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=7,
            )

        # 【結果検証】: DynamoDB から直接 next_review_at を取得して形式を確認
        cards_table = dynamodb_table.Table("memoru-cards-test")
        response = cards_table.get_item(
            Key={"user_id": "test-user-id", "card_id": created.card_id}
        )
        item = response["Item"]

        # 【確認内容】: next_review_at が文字列として保存されていること
        assert isinstance(item["next_review_at"], str)  # 【確認内容】: next_review_at が文字列型であること 🟡

        # 【確認内容】: ISO 8601 形式でパース可能であること
        parsed = datetime.fromisoformat(item["next_review_at"])
        assert parsed is not None  # 【確認内容】: fromisoformat() でパース可能であること 🟡

        # 【確認内容】: 期待される日時と一致すること
        expected = self.FIXED_NOW + timedelta(days=7)
        assert parsed.replace(tzinfo=timezone.utc) == expected  # 【確認内容】: 7 日後の正確な日時であること 🟡


class TestCardServiceUpdateIntervalDayBoundary:
    """Tests for day boundary normalization in update_card (TASK-0105).

    Verifies that interval update normalizes next_review_at to user's day boundary
    when user_timezone and day_start_hour are provided.
    """

    def test_interval_update_with_timezone_normalizes(self, card_service):
        """Test that interval update with timezone/day_start_hour normalizes next_review_at."""
        created = card_service.create_card(
            user_id="test-user-id",
            front="Q",
            back="A",
        )

        # Mock srs.datetime to control boundary calculation
        mock_now = datetime(2024, 6, 15, 1, 0, 0, tzinfo=timezone.utc)  # 10:00 JST
        with patch("services.srs.datetime") as mock_srs_dt, \
             patch("services.card_service.datetime") as mock_cs_dt:
            mock_srs_dt.now.return_value = mock_now
            mock_srs_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_cs_dt.now.return_value = mock_now
            mock_cs_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            updated = card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=7,
                user_timezone="Asia/Tokyo",
                day_start_hour=4,
            )

        # 10:00 JST (after boundary), effective_date = 2024-06-15
        # target_date = 2024-06-15 + 7 = 2024-06-22
        # boundary = 2024-06-22 04:00 JST = 2024-06-21 19:00 UTC
        assert updated.interval == 7
        assert updated.next_review_at is not None
        jst = updated.next_review_at.astimezone(ZoneInfo("Asia/Tokyo"))
        assert jst.hour == 4
        assert jst.day == 22
        assert jst.month == 6

    def test_interval_update_without_timezone_uses_raw_calculation(self, card_service):
        """Test that interval update without timezone uses raw datetime (backward compatibility)."""
        created = card_service.create_card(
            user_id="test-user-id",
            front="Q",
            back="A",
        )

        fixed_now = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        with patch("services.card_service.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            updated = card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=7,
            )

        # Without timezone params, should use raw calculation: now + 7 days
        expected = fixed_now + timedelta(days=7)
        assert updated.next_review_at.replace(tzinfo=timezone.utc) == expected

    def test_interval_update_normalized_stored_in_dynamodb(self, card_service, dynamodb_table):
        """Test that the normalized next_review_at is stored correctly in DynamoDB."""
        created = card_service.create_card(
            user_id="test-user-id",
            front="Q",
            back="A",
        )

        mock_now = datetime(2024, 6, 15, 1, 0, 0, tzinfo=timezone.utc)  # 10:00 JST
        with patch("services.srs.datetime") as mock_srs_dt, \
             patch("services.card_service.datetime") as mock_cs_dt:
            mock_srs_dt.now.return_value = mock_now
            mock_srs_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_cs_dt.now.return_value = mock_now
            mock_cs_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            card_service.update_card(
                user_id="test-user-id",
                card_id=created.card_id,
                interval=3,
                user_timezone="Asia/Tokyo",
                day_start_hour=4,
            )

        # Verify stored value
        cards_table = dynamodb_table.Table("memoru-cards-test")
        item = cards_table.get_item(
            Key={"user_id": "test-user-id", "card_id": created.card_id}
        )["Item"]
        stored = datetime.fromisoformat(item["next_review_at"])
        jst = stored.astimezone(ZoneInfo("Asia/Tokyo"))
        assert jst.hour == 4  # Should be at day boundary
