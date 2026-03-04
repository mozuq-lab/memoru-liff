import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { LiffHostingStack, type LiffHostingStackProps } from '../lib/liff-hosting-stack';

const devProps: LiffHostingStackProps = {
  environment: 'dev',
};

const prodProps: LiffHostingStackProps = {
  environment: 'prod',
  domainName: 'app.example.com',
  hostedZoneName: 'example.com',
  certificateArn: 'arn:aws:acm:us-east-1:123456789012:certificate/test-cert',
  hostedZoneId: 'Z0123456789ABCDEF',
};

function createStack(props: LiffHostingStackProps): LiffHostingStack {
  const app = new cdk.App();
  return new LiffHostingStack(app, 'TestLiffHostingStack', props);
}

describe('LiffHostingStack', () => {
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
    test('domainName 指定時に certificateArn がないとエラーが発生する', () => {
      expect(() => createStack({
        environment: 'dev',
        domainName: 'app.example.com',
      })).toThrow('CertificateArn (in us-east-1) is required when domainName is specified');
    });

    test('domainName 未指定時はエラーが発生しない', () => {
      expect(() => createStack({
        environment: 'dev',
      })).not.toThrow();
    });
  });

  describe('環境別設定', () => {
    test('dev: S3 バケットが 1 つである（LogBucket なし）', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::S3::Bucket', 1);
    });

    test('prod: S3 バケットが 2 つである（LiffBucket + LogBucket）', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.resourceCountIs('AWS::S3::Bucket', 2);
    });
  });

  describe('セキュリティ', () => {
    test('S3 BlockPublicAccess が BLOCK_ALL である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::S3::Bucket', {
        PublicAccessBlockConfiguration: {
          BlockPublicAcls: true,
          BlockPublicPolicy: true,
          IgnorePublicAcls: true,
          RestrictPublicBuckets: true,
        },
      });
    });

    test('S3 BucketEncryption が S3_MANAGED である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::S3::Bucket', {
        BucketEncryption: {
          ServerSideEncryptionConfiguration: [
            {
              ServerSideEncryptionByDefault: {
                SSEAlgorithm: 'AES256',
              },
            },
          ],
        },
      });
    });

    test('CloudFront に HSTS ヘッダーが設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::CloudFront::ResponseHeadersPolicy', {
        ResponseHeadersPolicyConfig: {
          SecurityHeadersConfig: {
            StrictTransportSecurity: {
              AccessControlMaxAgeSec: 31536000,
              IncludeSubdomains: true,
              Override: true,
              Preload: true,
            },
          },
        },
      });
    });

    test('CloudFront に frame-ancestors を含む CSP が設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::CloudFront::ResponseHeadersPolicy', {
        ResponseHeadersPolicyConfig: {
          SecurityHeadersConfig: {
            ContentSecurityPolicy: {
              ContentSecurityPolicy: Match.stringLikeRegexp('frame-ancestors'),
              Override: true,
            },
          },
        },
      });
    });

    test('CloudFront に X-Content-Type-Options が設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::CloudFront::ResponseHeadersPolicy', {
        ResponseHeadersPolicyConfig: {
          SecurityHeadersConfig: {
            ContentTypeOptions: {
              Override: true,
            },
          },
        },
      });
    });
  });

  describe('キャッシュ', () => {
    test('/assets/* に長期キャッシュポリシーが設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::CloudFront::CachePolicy', {
        CachePolicyConfig: {
          DefaultTTL: 86400,
          MaxTTL: 31536000,
        },
      });
    });

    test('/index.html に CachingDisabled ポリシーが設定されている', () => {
      const template = Template.fromStack(createStack(devProps));
      const cachingDisabledPolicyId = '4135ea2d-6df8-44a3-9df3-4b5a84be39ad';
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          CacheBehaviors: Match.arrayWith([
            Match.objectLike({
              PathPattern: '/index.html',
              CachePolicyId: cachingDisabledPolicyId,
            }),
          ]),
        },
      });
    });
  });

  describe('カスタムドメインと証明書', () => {
    test('prod: CloudFront にカスタムドメインエイリアスが設定されている', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          Aliases: ['app.example.com'],
        },
      });
    });

    test('prod: CloudFront に ACM 証明書が設定されている', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          ViewerCertificate: {
            AcmCertificateArn: prodProps.certificateArn,
            SslSupportMethod: 'sni-only',
          },
        },
      });
    });

    test('dev: CloudFront にカスタムドメインエイリアスがない', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          Aliases: Match.absent(),
        },
      });
    });
  });

  describe('ロギング', () => {
    test('prod: CloudFront ロギングが有効である', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          Logging: Match.objectLike({
            Prefix: 'cloudfront/',
            IncludeCookies: false,
          }),
        },
      });
    });

    test('dev: CloudFront ロギングが無効である', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          Logging: Match.absent(),
        },
      });
    });
  });

  describe('DNS', () => {
    test('prod: Route53 A レコードが作成される', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Route53::RecordSet', {
        Name: 'app.example.com.',
        Type: 'A',
        HostedZoneId: 'Z0123456789ABCDEF',
      });
    });

    test('hostedZoneId 未指定時は Route53 レコードが作成されない', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::Route53::RecordSet', 0);
    });
  });

  describe('CSP connect-src と apiEndpoint', () => {
    test('apiEndpoint が CSP connect-src に含まれている', () => {
      const template = Template.fromStack(createStack({
        environment: 'dev',
        apiEndpoint: 'https://api.example.com',
      }));
      template.hasResourceProperties('AWS::CloudFront::ResponseHeadersPolicy', {
        ResponseHeadersPolicyConfig: {
          SecurityHeadersConfig: {
            ContentSecurityPolicy: {
              ContentSecurityPolicy: Match.stringLikeRegexp('https://api\\.example\\.com'),
            },
          },
        },
      });
    });
  });
});
