# infra-cdk-tests データフロー図

**作成日**: 2026-03-03
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/infra-cdk-tests/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 要件定義書・CDK ドキュメント・ユーザヒアリングを参考にした確実なフロー

---

## テスト実行フロー 🔵

**信頼性**: 🔵 *Jest + CDK assertions の標準動作より*

```mermaid
flowchart TD
    A[npm test] --> B[Jest 起動]
    B --> C[ts-jest で TypeScript コンパイル]
    C --> D[テストファイル読み込み]

    D --> E1[cognito-stack.test.ts]
    D --> E2[keycloak-stack.test.ts]
    D --> E3[liff-hosting-stack.test.ts]

    E1 --> F1[new CognitoStack で CDK synth]
    E2 --> F2[new KeycloakStack で CDK synth]
    E3 --> F3[new LiffHostingStack で CDK synth]

    F1 --> G1[Template.fromStack]
    F2 --> G2[Template.fromStack]
    F3 --> G3[Template.fromStack]

    G1 --> H[Snapshot 比較 + Fine-grained assertions]
    G2 --> H
    G3 --> H

    H --> I{全テスト Pass?}
    I -->|Yes| J[✅ 成功]
    I -->|No| K[❌ 失敗レポート]
```

## 各テスト種別のデータフロー 🔵

**信頼性**: 🔵 *CDK assertions API ドキュメントより*

### Snapshot テスト

```mermaid
sequenceDiagram
    participant T as テストコード
    participant S as CDK Stack
    participant Tpl as Template
    participant Snap as __snapshots__/

    T->>S: new XxxStack(app, 'Test', props)
    S-->>T: Stack インスタンス
    T->>Tpl: Template.fromStack(stack)
    Tpl-->>T: CloudFormation テンプレート (JSON)
    T->>Snap: toMatchSnapshot()
    alt 初回実行
        Snap-->>T: Snapshot 保存
    else 2回目以降
        Snap-->>T: 既存 Snapshot と比較
        alt 一致
            T-->>T: ✅ Pass
        else 不一致
            T-->>T: ❌ Fail (差分表示)
        end
    end
```

### Fine-grained assertions

```mermaid
sequenceDiagram
    participant T as テストコード
    participant Tpl as Template
    participant M as Match

    T->>Tpl: hasResourceProperties('AWS::RDS::DBInstance', {...})
    Tpl->>Tpl: テンプレート内を検索
    alt プロパティ一致
        Tpl-->>T: ✅ Pass
    else 不一致
        Tpl-->>T: ❌ Fail (期待値 vs 実際値)
    end
```

### Validation テスト

```mermaid
sequenceDiagram
    participant T as テストコード
    participant S as CDK Stack

    T->>S: new XxxStack(app, 'Test', invalidProps)
    S-->>T: throw new Error(...)
    T->>T: expect(...).toThrow(message)
    alt エラーメッセージ一致
        T-->>T: ✅ Pass
    else 不一致 or エラーなし
        T-->>T: ❌ Fail
    end
```

## dev/prod テスト生成パターン 🔵

**信頼性**: 🔵 *テスト戦略・既存コードの isProd パターンより*

```mermaid
flowchart LR
    subgraph "各テストファイル"
        Props_dev[dev Props] --> Stack_dev[Stack 生成 dev]
        Props_prod[prod Props] --> Stack_prod[Stack 生成 prod]

        Stack_dev --> Snap_dev[Snapshot dev]
        Stack_dev --> Assert_dev[Fine-grained dev]

        Stack_prod --> Snap_prod[Snapshot prod]
        Stack_prod --> Assert_prod[Fine-grained prod]
    end
```

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **要件定義**: [requirements.md](../../spec/infra-cdk-tests/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 4件 (100%)
- 🟡 黄信号: 0件 (0%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
