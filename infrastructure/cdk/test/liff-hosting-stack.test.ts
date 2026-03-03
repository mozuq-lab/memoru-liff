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

  describe('Validation', () => {
    test('domainName with no certificateArn throws error', () => {
      expect(() => createStack({
        environment: 'dev',
        domainName: 'app.example.com',
      })).toThrow('CertificateArn (in us-east-1) is required when domainName is specified');
    });

    test('no domainName does not throw', () => {
      expect(() => createStack({
        environment: 'dev',
      })).not.toThrow();
    });
  });

  describe('Environment differences', () => {
    test('dev: 1 S3 bucket (no LogBucket)', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::S3::Bucket', 1);
    });

    test('prod: 2 S3 buckets (LiffBucket + LogBucket)', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.resourceCountIs('AWS::S3::Bucket', 2);
    });
  });

  describe('Security', () => {
    test('S3 BlockPublicAccess is BLOCK_ALL', () => {
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

    test('S3 BucketEncryption is S3_MANAGED', () => {
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

    test('CloudFront has HSTS header', () => {
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

    test('CloudFront has CSP with frame-ancestors', () => {
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

    test('CloudFront has X-Content-Type-Options', () => {
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

  describe('Cache', () => {
    test('/assets/* has long-term cache policy', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::CloudFront::CachePolicy', {
        CachePolicyConfig: {
          DefaultTTL: 86400,
          MaxTTL: 31536000,
        },
      });
    });

    test('/index.html uses CachingDisabled policy', () => {
      const template = Template.fromStack(createStack(devProps));
      // CachingDisabled managed policy ID
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

  describe('Custom domain and certificate', () => {
    test('prod: CloudFront has custom domain alias', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          Aliases: ['app.example.com'],
        },
      });
    });

    test('prod: CloudFront has ACM certificate', () => {
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

    test('dev: CloudFront has no custom domain alias', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          Aliases: Match.absent(),
        },
      });
    });
  });

  describe('Logging', () => {
    test('prod: CloudFront logging is enabled', () => {
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

    test('dev: CloudFront logging is not configured', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::CloudFront::Distribution', {
        DistributionConfig: {
          Logging: Match.absent(),
        },
      });
    });
  });

  describe('DNS', () => {
    test('prod: Route53 A record is created', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Route53::RecordSet', {
        Name: 'app.example.com.',
        Type: 'A',
        HostedZoneId: 'Z0123456789ABCDEF',
      });
    });

    test('no Route53 record without hostedZoneId', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::Route53::RecordSet', 0);
    });
  });

  describe('CSP connect-src with apiEndpoint', () => {
    test('apiEndpoint is included in CSP connect-src', () => {
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
