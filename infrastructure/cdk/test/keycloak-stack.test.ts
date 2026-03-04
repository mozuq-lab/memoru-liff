import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { KeycloakStack, type KeycloakStackProps } from '../lib/keycloak-stack';

const devProps: KeycloakStackProps = {
  environment: 'dev',
  domainName: 'keycloak-dev.example.com',
};

const prodProps: KeycloakStackProps = {
  environment: 'prod',
  domainName: 'keycloak.example.com',
  hostedZoneName: 'example.com',
  certificateArn: 'arn:aws:acm:ap-northeast-1:123456789012:certificate/test-cert',
  hostedZoneId: 'Z0123456789ABCDEF',
};

function createStack(props: KeycloakStackProps): KeycloakStack {
  const app = new cdk.App();
  return new KeycloakStack(app, 'TestKeycloakStack', props);
}

describe('KeycloakStack', () => {
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

  describe('バリデーション', () => {
    test('prod 環境で certificateArn 未指定時にエラーが発生する', () => {
      expect(() => createStack({
        environment: 'prod',
        domainName: 'keycloak.example.com',
      })).toThrow('CertificateArn is required for prod environment');
    });
  });

  describe('環境別設定', () => {
    test('dev: NAT Gateway がない', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::EC2::NatGateway', 0);
    });

    test('prod: NAT Gateway が 1 つある', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.resourceCountIs('AWS::EC2::NatGateway', 1);
    });

    test('dev: RDS MultiAZ が false である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        MultiAZ: false,
      });
    });

    test('prod: RDS MultiAZ が true である', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        MultiAZ: true,
      });
    });

    test('dev: RDS DeletionProtection が false である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        DeletionProtection: false,
      });
    });

    test('prod: RDS DeletionProtection が true である', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        DeletionProtection: true,
      });
    });

    test('dev: ECS AssignPublicIp が ENABLED である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::ECS::Service', {
        NetworkConfiguration: {
          AwsvpcConfiguration: {
            AssignPublicIp: 'ENABLED',
          },
        },
      });
    });

    test('prod: ECS AssignPublicIp が DISABLED である', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::ECS::Service', {
        NetworkConfiguration: {
          AwsvpcConfiguration: {
            AssignPublicIp: 'DISABLED',
          },
        },
      });
    });

    test('dev: LogGroup の保持期間が 14 日で RemovalPolicy が DESTROY である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::Logs::LogGroup', 1);
      template.hasResource('AWS::Logs::LogGroup', {
        Properties: {
          LogGroupName: '/ecs/memoru-dev-keycloak',
          RetentionInDays: 14,
        },
        UpdateReplacePolicy: 'Delete',
        DeletionPolicy: 'Delete',
      });
    });

    test('prod: LogGroup の保持期間が 90 日で RemovalPolicy が RETAIN である', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.resourceCountIs('AWS::Logs::LogGroup', 1);
      template.hasResource('AWS::Logs::LogGroup', {
        Properties: {
          LogGroupName: '/ecs/memoru-prod-keycloak',
          RetentionInDays: 90,
        },
        UpdateReplacePolicy: 'Retain',
        DeletionPolicy: 'Retain',
      });
    });
  });

  describe('セキュリティ', () => {
    test('RDS StorageEncrypted が true である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        StorageEncrypted: true,
      });
    });

    test('RDS PubliclyAccessible が false である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        PubliclyAccessible: false,
      });
    });
  });

  describe('HTTPS とロードバランサー', () => {
    test('dev: リスナーがポート 80 の HTTP である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
        Port: 80,
        Protocol: 'HTTP',
      });
    });

    test('prod: リスナーがポート 443 の HTTPS で証明書が設定されている', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
        Port: 443,
        Protocol: 'HTTPS',
        Certificates: [
          { CertificateArn: prodProps.certificateArn },
        ],
      });
    });

    test('prod: HTTP から HTTPS へのリダイレクトリスナーが存在する', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
        Port: 80,
        DefaultActions: Match.arrayWith([
          Match.objectLike({
            Type: 'redirect',
            RedirectConfig: Match.objectLike({
              Protocol: 'HTTPS',
              Port: '443',
              StatusCode: 'HTTP_301',
            }),
          }),
        ]),
      });
    });

    test('dev: HTTP リダイレクトリスナーがない', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::ElasticLoadBalancingV2::Listener', 1);
    });

    test('prod: リスナーが 2 つある（HTTPS + HTTP リダイレクト）', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.resourceCountIs('AWS::ElasticLoadBalancingV2::Listener', 2);
    });
  });

  describe('ヘルスチェック', () => {
    test('TargetGroup のヘルスチェックパスが /health/ready である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::TargetGroup', {
        HealthCheckPath: '/health/ready',
        Matcher: { HttpCode: '200' },
      });
    });
  });

  describe('DNS', () => {
    test('prod: Route53 A レコードが作成される', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Route53::RecordSet', {
        Name: 'keycloak.example.com.',
        Type: 'A',
        HostedZoneId: 'Z0123456789ABCDEF',
      });
    });

    test('hostedZoneId 未指定時は Route53 レコードが作成されない', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::Route53::RecordSet', 0);
    });
  });
});
