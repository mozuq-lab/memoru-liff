import * as cdk from 'aws-cdk-lib';
import { Annotations, Match, Template } from 'aws-cdk-lib/assertions';
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
  describe('スナップショット', () => {
    test('dev 環境のテンプレートがスナップショットと一致する', () => {
      const template = Template.fromStack(createStack(devProps));
      expect(template.toJSON()).toMatchSnapshot();
    });

    test('prod 環境のテンプレートがスナップショットと一致する', () => {
      const template = Template.fromStack(createStack(prodProps));
      expect(template.toJSON()).toMatchSnapshot();
    });
  });

  describe('環境別設定', () => {
    test('dev: DeletionProtection が INACTIVE である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        DeletionProtection: 'INACTIVE',
      });
    });

    test('prod: DeletionProtection が ACTIVE である', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        DeletionProtection: 'ACTIVE',
      });
    });

    test('dev: RemovalPolicy が DESTROY である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResource('AWS::Cognito::UserPool', {
        UpdateReplacePolicy: 'Delete',
        DeletionPolicy: 'Delete',
      });
    });

    test('prod: RemovalPolicy が RETAIN である', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResource('AWS::Cognito::UserPool', {
        UpdateReplacePolicy: 'Retain',
        DeletionPolicy: 'Retain',
      });
    });
  });

  describe('セキュリティ', () => {
    test('パスワードポリシーが要件を満たしている', () => {
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

    test('MFA が OPTIONAL（TOTP）で設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        MfaConfiguration: 'OPTIONAL',
        EnabledMfas: ['SOFTWARE_TOKEN_MFA'],
      });
    });
  });

  describe('OIDC', () => {
    test('OAuth フローとスコープが正しく設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        AllowedOAuthFlows: ['code'],
        AllowedOAuthScopes: ['openid', 'profile', 'email'],
        AllowedOAuthFlowsUserPoolClient: true,
      });
    });

    test('CallbackURLs が Props から設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        CallbackURLs: ['http://localhost:3000/callback'],
      });
    });

    test('LogoutURLs が Props から設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        LogoutURLs: ['http://localhost:3000/'],
      });
    });

    test('prod: CallbackURLs と LogoutURLs が本番 URL になっている', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        CallbackURLs: ['https://app.example.com/callback'],
        LogoutURLs: ['https://app.example.com/'],
      });
    });

    test('トークン有効期間が正しく設定されている', () => {
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

    test('クライアントが Public（シークレットなし）である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        GenerateSecret: false,
      });
    });
  });

  describe('ドメイン', () => {
    test('UserPool ドメインプレフィックスが Props から設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolDomain', {
        Domain: 'memoru-dev-test',
      });
    });

    test('prod: UserPool ドメインプレフィックスが正しく設定されている', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolDomain', {
        Domain: 'memoru-prod-test',
      });
    });
  });

  const devPropsWithLine: CognitoStackProps = {
    ...devProps,
    lineLoginChannelId: 'test-channel-id',
    lineLoginChannelSecret: 'test-channel-secret',
  };

  // prod は平文 secret を許容しないため Secrets Manager 名で指定する
  const prodPropsWithLine: CognitoStackProps = {
    ...prodProps,
    lineLoginChannelId: 'test-channel-id',
    lineLoginChannelSecretName: 'memoru/prod/line-channel-secret',
  };

  describe('LINE Login IdP', () => {
    describe('LINE Props 指定時', () => {
      test('UserPoolIdentityProvider OIDC リソースが作成される', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderType: 'OIDC',
        });
      });

      test('ProviderName が LINE である', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderName: 'LINE',
        });
      });

      test('LINE OIDC エンドポイントが正しく設定されている', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderDetails: {
            authorize_url: 'https://access.line.me/oauth2/v2.1/authorize',
            token_url: 'https://api.line.me/oauth2/v2.1/token',
            attributes_url: 'https://api.line.me/oauth2/v2.1/userinfo',
            jwks_uri: 'https://api.line.me/oauth2/v2.1/certs',
            oidc_issuer: 'https://access.line.me',
          },
        });
      });

      test('属性マッピング（name, picture）が設定されている', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          AttributeMapping: {
            name: 'name',
            picture: 'picture',
          },
        });
      });

      test('SupportedIdentityProviders に COGNITO と LINE が含まれている', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
          SupportedIdentityProviders: ['COGNITO', 'LINE'],
        });
      });

      test('client_id と client_secret が Props から設定されている (dev: 平文 fallback)', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderDetails: {
            client_id: 'test-channel-id',
            client_secret: 'test-channel-secret',
          },
        });
      });

      test('Secrets Manager 名指定時は client_secret が dynamic reference になる', () => {
        const propsWithSecretName: CognitoStackProps = {
          ...devProps,
          lineLoginChannelId: 'test-channel-id',
          lineLoginChannelSecretName: 'memoru/dev/line-channel-secret',
        };
        const template = Template.fromStack(createStack(propsWithSecretName));
        const idps = template.findResources('AWS::Cognito::UserPoolIdentityProvider');
        const idp = Object.values(idps)[0] as {
          Properties: { ProviderDetails: { client_secret: unknown } };
        };
        // CDK は SecretValue.unsafeUnwrap() を Fn::Join + 内部 Token として返す。
        // 文字列化して `{{resolve:secretsmanager:...}}` を含むか確認する。
        const serialized = JSON.stringify(idp.Properties.ProviderDetails.client_secret);
        expect(serialized).toContain('{{resolve:secretsmanager:');
        expect(serialized).toContain('memoru/dev/line-channel-secret');
        expect(serialized).toContain(':SecretString');
        // 平文 fallback の値が紛れ込まないこと
        expect(serialized).not.toContain('test-channel-secret');
      });

      test('prod で平文 lineLoginChannelSecret を渡すと synth が失敗する', () => {
        const prodPropsWithPlaintext: CognitoStackProps = {
          ...prodProps,
          lineLoginChannelId: 'test-channel-id',
          lineLoginChannelSecret: 'plaintext-not-allowed',
        };
        expect(() => createStack(prodPropsWithPlaintext)).toThrow(
          /Secrets Manager 経由/,
        );
      });

      test('OIDC スコープが openid と profile である', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderDetails: {
            authorize_scopes: 'openid profile',
          },
        });
      });

      test('UserPoolClient が LINE IdP に DependsOn を持っている', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        const clients = template.findResources('AWS::Cognito::UserPoolClient');
        const clientKey = Object.keys(clients)[0];
        const client = clients[clientKey];
        expect(client.DependsOn).toBeDefined();
        expect(client.DependsOn).toEqual(
          expect.arrayContaining([
            expect.stringContaining('LineLoginProvider'),
          ]),
        );
      });
    });

    describe('スナップショット（LINE あり）', () => {
      test('dev + LINE IdP のテンプレートがスナップショットと一致する', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        expect(template.toJSON()).toMatchSnapshot();
      });

      test('prod + LINE IdP のテンプレートがスナップショットと一致する', () => {
        const template = Template.fromStack(createStack(prodPropsWithLine));
        expect(template.toJSON()).toMatchSnapshot();
      });
    });

    describe('LINE Props 未指定時（後方互換性）', () => {
      test('LINE Props 未指定時は IdP リソースが作成されない', () => {
        const template = Template.fromStack(createStack(devProps));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });

      test('LINE Props 未指定時は SupportedIdentityProviders が COGNITO のみである', () => {
        const template = Template.fromStack(createStack(devProps));
        template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
          SupportedIdentityProviders: ['COGNITO'],
        });
      });

      test('Channel ID のみ指定時は IdP が作成されない', () => {
        const propsWithIdOnly: CognitoStackProps = {
          ...devProps,
          lineLoginChannelId: 'test-channel-id',
        };
        const template = Template.fromStack(createStack(propsWithIdOnly));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });

      test('Channel Secret のみ指定時は IdP が作成されない', () => {
        const propsWithSecretOnly: CognitoStackProps = {
          ...devProps,
          lineLoginChannelSecret: 'test-channel-secret',
        };
        const template = Template.fromStack(createStack(propsWithSecretOnly));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });

      test('空文字列指定時は IdP が作成されない', () => {
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

  describe('PreSignUp トリガー（サインアップ許可リスト）', () => {
    const presignupLambdaArn =
      'arn:aws:lambda:ap-northeast-1:999988887777:function:memoru-presignup-dev';

    test('preSignUpLambdaArn 指定時に LambdaConfig.PreSignUp が設定される', () => {
      const propsWithPreSignUp: CognitoStackProps = {
        ...devProps,
        preSignUpLambdaArn: presignupLambdaArn,
      };
      const template = Template.fromStack(createStack(propsWithPreSignUp));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        LambdaConfig: {
          PreSignUp: presignupLambdaArn,
        },
      });
    });

    test('preSignUpLambdaArn 指定時に Lambda Permission は CDK 側で作成されない（SAM 側で一元管理）', () => {
      const propsWithPreSignUp: CognitoStackProps = {
        ...devProps,
        preSignUpLambdaArn: presignupLambdaArn,
      };
      const template = Template.fromStack(createStack(propsWithPreSignUp));
      template.resourceCountIs('AWS::Lambda::Permission', 0);
    });

    test('未指定時は LambdaConfig が設定されない', () => {
      const template = Template.fromStack(createStack(devProps));
      const userPools = template.findResources('AWS::Cognito::UserPool');
      const userPool = Object.values(userPools)[0] as {
        Properties: Record<string, unknown>;
      };
      expect(userPool.Properties.LambdaConfig).toBeUndefined();
    });

    describe('未配線時の警告（prod のみ）', () => {
      test('prod + preSignUpLambdaArn 未指定で Annotations warning が出る', () => {
        const stack = createStack(prodProps);
        Template.fromStack(stack);
        Annotations.fromStack(stack).hasWarning(
          '*',
          Match.stringLikeRegexp('PreSignUp トリガー'),
        );
      });

      test('prod + preSignUpLambdaArn 指定時は warning が出ない', () => {
        const stack = createStack({
          ...prodProps,
          preSignUpLambdaArn: presignupLambdaArn,
        });
        Template.fromStack(stack);
        Annotations.fromStack(stack).hasNoWarning(
          '*',
          Match.stringLikeRegexp('PreSignUp トリガー'),
        );
      });

      test('dev + preSignUpLambdaArn 未指定では warning が出ない', () => {
        const stack = createStack(devProps);
        Template.fromStack(stack);
        Annotations.fromStack(stack).hasNoWarning(
          '*',
          Match.stringLikeRegexp('PreSignUp トリガー'),
        );
      });
    });
  });
});
