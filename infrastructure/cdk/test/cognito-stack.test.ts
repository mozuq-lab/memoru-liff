import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { CognitoStack, type CognitoStackProps } from '../lib/cognito-stack';

const devProps: CognitoStackProps = {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev-test',
  callbackUrls: ['http://localhost:3000/callback'],
  logoutUrls: ['http://localhost:3000/'],
};

const prodProps: CognitoStackProps = {
  environment: 'prod',
  cognitoDomainPrefix: 'memoru-prod-test',
  callbackUrls: ['https://app.example.com/callback'],
  logoutUrls: ['https://app.example.com/'],
};

function createStack(props: CognitoStackProps): CognitoStack {
  const app = new cdk.App();
  return new CognitoStack(app, 'TestCognitoStack', props);
}

describe('CognitoStack', () => {
  describe('Snapshot', () => {
    test('dev environment matches snapshot', () => {
      const template = Template.fromStack(createStack(devProps));
      expect(template.toJSON()).toMatchSnapshot();
    });

    test('prod environment matches snapshot', () => {
      const template = Template.fromStack(createStack(prodProps));
      expect(template.toJSON()).toMatchSnapshot();
    });
  });

  describe('Environment differences', () => {
    test('dev: DeletionProtection is INACTIVE', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        DeletionProtection: 'INACTIVE',
      });
    });

    test('prod: DeletionProtection is ACTIVE', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        DeletionProtection: 'ACTIVE',
      });
    });

    test('dev: RemovalPolicy is DESTROY', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResource('AWS::Cognito::UserPool', {
        UpdateReplacePolicy: 'Delete',
        DeletionPolicy: 'Delete',
      });
    });

    test('prod: RemovalPolicy is RETAIN', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResource('AWS::Cognito::UserPool', {
        UpdateReplacePolicy: 'Retain',
        DeletionPolicy: 'Retain',
      });
    });
  });

  describe('Security', () => {
    test('password policy meets requirements', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        Policies: {
          PasswordPolicy: {
            MinimumLength: 8,
            RequireLowercase: true,
            RequireUppercase: true,
            RequireNumbers: true,
            RequireSymbols: true,
          },
        },
      });
    });

    test('MFA is OPTIONAL with TOTP', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        MfaConfiguration: 'OPTIONAL',
        EnabledMfas: ['SOFTWARE_TOKEN_MFA'],
      });
    });
  });

  describe('OIDC', () => {
    test('OAuth flows and scopes are correctly configured', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        AllowedOAuthFlows: ['code'],
        AllowedOAuthScopes: ['openid', 'profile', 'email'],
        AllowedOAuthFlowsUserPoolClient: true,
      });
    });

    test('CallbackURLs are set from props', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        CallbackURLs: ['http://localhost:3000/callback'],
      });
    });

    test('LogoutURLs are set from props', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        LogoutURLs: ['http://localhost:3000/'],
      });
    });

    test('prod: CallbackURLs and LogoutURLs use production URLs', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        CallbackURLs: ['https://app.example.com/callback'],
        LogoutURLs: ['https://app.example.com/'],
      });
    });

    test('token validity is configured correctly', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        AccessTokenValidity: 60,
        IdTokenValidity: 60,
        RefreshTokenValidity: 43200,
        TokenValidityUnits: {
          AccessToken: 'minutes',
          IdToken: 'minutes',
          RefreshToken: 'minutes',
        },
      });
    });

    test('client is public (no secret)', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        GenerateSecret: false,
      });
    });
  });

  describe('Domain', () => {
    test('UserPool domain prefix is set from props', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolDomain', {
        Domain: 'memoru-dev-test',
      });
    });

    test('prod: UserPool domain prefix is set correctly', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolDomain', {
        Domain: 'memoru-prod-test',
      });
    });
  });

  // ============================================================
  // LINE Login IdP テスト（TASK-0146）
  // 【テスト目的】: LINE Login 外部 OIDC IdP の条件付き登録機能をテスト
  // 【期待される動作】: LINE Props 指定時は IdP が作成され、未指定時は既存動作を維持
  // ============================================================

  // 🔵 CognitoStackProps に lineLoginChannelId/lineLoginChannelSecret が追加されたため型安全
  const devPropsWithLine: CognitoStackProps = {
    ...devProps,
    lineLoginChannelId: 'test-channel-id',
    lineLoginChannelSecret: 'test-channel-secret',
  };

  const prodPropsWithLine: CognitoStackProps = {
    ...prodProps,
    lineLoginChannelId: 'test-channel-id',
    lineLoginChannelSecret: 'test-channel-secret',
  };

  describe('LINE Login IdP', () => {
    // ============================================================
    // LINE Props 指定時のテスト
    // ============================================================
    describe('LINE Props 指定時', () => {
      test('TC-001: UserPoolIdentityProvider リソースが作成される', () => {
        // 🔵 REQ-001: lineLoginChannelId/Secret 両方指定時に OIDC IdP リソースが生成されること
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderType: 'OIDC',
        });
      });

      test('TC-002: LINE IdP の ProviderName が LINE であること', () => {
        // 🔵 architecture.md「UserPoolIdentityProviderOidc の追加」より: name: 'LINE' が ProviderName に出力される
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderName: 'LINE',
        });
      });

      test('TC-003: LINE OIDC エンドポイントが正しく設定されていること', () => {
        // 🟡 LINE Developers ドキュメントからの推測。CloudFormation プロパティ名は CDK の内部変換に依存
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderDetails: {
            authorize_url: 'https://access.line.me/oauth2/v2.1/authorize',
            token_url: 'https://api.line.me/oauth2/v2.1/token',
            attributes_url: 'https://api.line.me/v2/profile',
            jwks_uri: 'https://api.line.me/oauth2/v2.1/certs',
            oidc_issuer: 'https://access.line.me',
          },
        });
      });

      test('TC-004: LINE 属性マッピング（sub, name, picture）が設定されていること', () => {
        // 🔵 REQ-003・architecture.md「属性マッピング」より: sub→username, name→name, picture→picture
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          AttributeMapping: {
            username: 'sub',
            name: 'name',
            picture: 'picture',
          },
        });
      });

      test('TC-005: UserPoolClient の SupportedIdentityProviders に COGNITO と LINE が含まれること', () => {
        // 🔵 REQ-004/005: supportedIdentityProviders に LINE が条件付きで追加されること
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
          SupportedIdentityProviders: ['COGNITO', 'LINE'],
        });
      });

      test('TC-006: LINE IdP の clientId と clientSecret が Props から正しく設定されること', () => {
        // 🟡 CloudFormation 出力のプロパティ名（client_id/client_secret）は CDK の内部変換に依存
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderDetails: {
            client_id: 'test-channel-id',
            client_secret: 'test-channel-secret',
          },
        });
      });

      test('TC-007: LINE IdP の OIDC スコープが openid, profile であること', () => {
        // 🟡 CDK が scopes 配列をスペース区切り文字列に変換して ProviderDetails に出力する
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderDetails: {
            authorize_scopes: 'openid profile',
          },
        });
      });
    });

    // ============================================================
    // スナップショットテスト（LINE あり）
    // ============================================================
    describe('Snapshot（LINE あり）', () => {
      test('TC-008: dev + LINE IdP のスナップショットが一致すること', () => {
        // 🔵 既存テストパターンより: LINE IdP を含む dev 環境テンプレートの整合性を保証
        const template = Template.fromStack(createStack(devPropsWithLine));
        expect(template.toJSON()).toMatchSnapshot();
      });

      test('TC-009: prod + LINE IdP のスナップショットが一致すること', () => {
        // 🔵 prod 固有設定（DeletionProtection: ACTIVE, RemovalPolicy: RETAIN）が LINE IdP 追加後も維持される
        const template = Template.fromStack(createStack(prodPropsWithLine));
        expect(template.toJSON()).toMatchSnapshot();
      });
    });

    // ============================================================
    // 後方互換性テスト（LINE Props 未指定時）
    // ============================================================
    describe('LINE Props 未指定時（後方互換性）', () => {
      test('TC-012: LINE Props 未指定時に UserPoolIdentityProvider リソースが存在しないこと', () => {
        // 🔵 REQ-401: LINE Props 未指定時は既存動作を維持し、IdP リソースは生成されない
        const template = Template.fromStack(createStack(devProps));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });

      test('TC-016: LINE Props 未指定時に UserPoolClient の SupportedIdentityProviders が COGNITO のみであること', () => {
        // 🔵 REQ-401: LINE が追加されず、既存の COGNITO のみが設定されていること
        const template = Template.fromStack(createStack(devProps));
        template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
          SupportedIdentityProviders: ['COGNITO'],
        });
      });

      test('TC-010: Channel ID のみ指定（Secret 未指定）で LINE IdP が作成されないこと', () => {
        // 🟡 条件分岐「両方指定時のみ作成」: Secret 未指定の場合は IdP を作成しない
        const propsWithIdOnly: CognitoStackProps = {
          ...devProps,
          lineLoginChannelId: 'test-channel-id',
          // lineLoginChannelSecret は未指定（undefined）
        };
        const template = Template.fromStack(createStack(propsWithIdOnly));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });

      test('TC-011: Channel Secret のみ指定（ID 未指定）で LINE IdP が作成されないこと', () => {
        // 🟡 条件分岐「両方指定時のみ作成」: ID 未指定の場合は IdP を作成しない
        const propsWithSecretOnly: CognitoStackProps = {
          ...devProps,
          lineLoginChannelSecret: 'test-channel-secret',
          // lineLoginChannelId は未指定（undefined）
        };
        const template = Template.fromStack(createStack(propsWithSecretOnly));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });

      test('TC-013: LINE Props 両方空文字列で LINE IdP が作成されないこと', () => {
        // 🟡 TypeScript の truthy/falsy 評価: 空文字列は falsy のため IdP は作成されない
        const propsWithEmptyLine: CognitoStackProps = {
          ...devProps,
          lineLoginChannelId: '',
          lineLoginChannelSecret: '',
        };
        const template = Template.fromStack(createStack(propsWithEmptyLine));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });
    });
  });
});
