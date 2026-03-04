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
    describe('LINE Props 指定時', () => {
      test('UserPoolIdentityProvider OIDC リソースが作成される', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderType: 'OIDC',
        });
      });

      test('ProviderName が LINE であること', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderName: 'LINE',
        });
      });

      test('LINE OIDC エンドポイントが正しく設定されていること', () => {
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

      test('属性マッピング（name, picture）が設定されていること', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          AttributeMapping: {
            name: 'name',
            picture: 'picture',
          },
        });
      });

      test('UserPoolClient の SupportedIdentityProviders に COGNITO と LINE が含まれること', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
          SupportedIdentityProviders: ['COGNITO', 'LINE'],
        });
      });

      test('clientId と clientSecret が Props から正しく設定されること', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderDetails: {
            client_id: 'test-channel-id',
            client_secret: 'test-channel-secret',
          },
        });
      });

      test('OIDC スコープが openid, profile であること', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        template.hasResourceProperties('AWS::Cognito::UserPoolIdentityProvider', {
          ProviderDetails: {
            authorize_scopes: 'openid profile',
          },
        });
      });

      test('UserPoolClient が LINE IdP に DependsOn を持つこと', () => {
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

    describe('Snapshot（LINE あり）', () => {
      test('dev + LINE IdP のスナップショットが一致すること', () => {
        const template = Template.fromStack(createStack(devPropsWithLine));
        expect(template.toJSON()).toMatchSnapshot();
      });

      test('prod + LINE IdP のスナップショットが一致すること', () => {
        const template = Template.fromStack(createStack(prodPropsWithLine));
        expect(template.toJSON()).toMatchSnapshot();
      });
    });

    describe('LINE Props 未指定時（後方互換性）', () => {
      test('LINE Props 未指定時に IdP リソースが存在しないこと', () => {
        const template = Template.fromStack(createStack(devProps));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });

      test('LINE Props 未指定時に SupportedIdentityProviders が COGNITO のみであること', () => {
        const template = Template.fromStack(createStack(devProps));
        template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
          SupportedIdentityProviders: ['COGNITO'],
        });
      });

      test('Channel ID のみ指定（Secret 未指定）で LINE IdP が作成されないこと', () => {
        const propsWithIdOnly: CognitoStackProps = {
          ...devProps,
          lineLoginChannelId: 'test-channel-id',
        };
        const template = Template.fromStack(createStack(propsWithIdOnly));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });

      test('Channel Secret のみ指定（ID 未指定）で LINE IdP が作成されないこと', () => {
        const propsWithSecretOnly: CognitoStackProps = {
          ...devProps,
          lineLoginChannelSecret: 'test-channel-secret',
        };
        const template = Template.fromStack(createStack(propsWithSecretOnly));
        template.resourceCountIs('AWS::Cognito::UserPoolIdentityProvider', 0);
      });

      test('両方空文字列で LINE IdP が作成されないこと', () => {
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
