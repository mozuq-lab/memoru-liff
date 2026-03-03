import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as targets from 'aws-cdk-lib/aws-route53-targets';
import type { Construct } from 'constructs';

type Environment = 'dev' | 'staging' | 'prod';

export interface LiffHostingStackProps extends cdk.StackProps {
  environment: Environment;
  domainName?: string;
  hostedZoneName?: string;
  certificateArn?: string;
  hostedZoneId?: string;
  apiEndpoint?: string;
}

export class LiffHostingStack extends cdk.Stack {
  public readonly bucket: s3.Bucket;
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props: LiffHostingStackProps) {
    super(scope, id, props);

    const isProd = props.environment === 'prod';

    // Validate: custom domain requires certificate
    if (props.domainName && !props.certificateArn) {
      throw new Error('CertificateArn (in us-east-1) is required when domainName is specified');
    }

    // ============================================================
    // S3 Bucket for Static Files
    // ============================================================
    this.bucket = new s3.Bucket(this, 'LiffBucket', {
      bucketName: `memoru-liff-${props.environment}-${cdk.Aws.ACCOUNT_ID}`,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
        {
          id: 'AbortIncompleteMultipartUpload',
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
        },
      ],
      cors: [
        {
          allowedHeaders: ['*'],
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: props.domainName
            ? [`https://${props.domainName}`]
            : ['*'],
          maxAge: 3600,
        },
      ],
    });

    // Log Bucket (for production only)
    let logBucket: s3.Bucket | undefined;
    if (isProd) {
      logBucket = new s3.Bucket(this, 'LogBucket', {
        bucketName: `memoru-logs-${props.environment}-${cdk.Aws.ACCOUNT_ID}`,
        removalPolicy: cdk.RemovalPolicy.RETAIN,
        encryption: s3.BucketEncryption.S3_MANAGED,
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
        lifecycleRules: [
          {
            id: 'DeleteOldLogs',
            expiration: cdk.Duration.days(90),
          },
        ],
      });
    }

    // ============================================================
    // Security Response Headers Policy
    // ============================================================
    const connectSrc = props.apiEndpoint
      ? `'self' ${props.apiEndpoint} https://api.line.me https://access.line.me`
      : "'self' https://api.line.me https://access.line.me";

    const responseHeadersPolicy = new cloudfront.ResponseHeadersPolicy(
      this, 'SecurityHeadersPolicy', {
        responseHeadersPolicyName: `memoru-liff-security-headers-${props.environment}`,
        securityHeadersBehavior: {
          strictTransportSecurity: {
            accessControlMaxAge: cdk.Duration.seconds(31536000),
            includeSubdomains: true,
            override: true,
            preload: true,
          },
          contentTypeOptions: { override: true },
          // frameOptions は CSP frame-ancestors と競合するため設定しない
          // LIFF は liff.line.me 内の iframe で動作するため frame-ancestors で制御
          xssProtection: {
            protection: true,
            modeBlock: true,
            override: true,
          },
          referrerPolicy: {
            referrerPolicy: cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
            override: true,
          },
          contentSecurityPolicy: {
            contentSecurityPolicy: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' https://static.line-scdn.net",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https: blob:",
              "font-src 'self' data:",
              `connect-src ${connectSrc}`,
              "frame-ancestors 'self' https://liff.line.me",
            ].join('; '),
            override: true,
          },
        },
      },
    );

    // ============================================================
    // Static Assets Cache Policy (long-term cache)
    // ============================================================
    const staticAssetsCachePolicy = new cloudfront.CachePolicy(
      this, 'StaticAssetsCachePolicy', {
        cachePolicyName: `memoru-liff-static-${props.environment}`,
        defaultTtl: cdk.Duration.days(1),
        maxTtl: cdk.Duration.days(365),
        minTtl: cdk.Duration.seconds(0),
        enableAcceptEncodingBrotli: true,
        enableAcceptEncodingGzip: true,
      },
    );

    // ============================================================
    // CloudFront Distribution
    // ============================================================
    const s3Origin = origins.S3BucketOrigin.withOriginAccessControl(this.bucket);

    // Certificate (optional)
    const certificate = props.certificateArn
      ? acm.Certificate.fromCertificateArn(this, 'Cert', props.certificateArn)
      : undefined;

    this.distribution = new cloudfront.Distribution(this, 'Distribution', {
      comment: `Memoru LIFF Distribution - ${props.environment}`,
      defaultRootObject: 'index.html',
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      enableIpv6: true,
      priceClass: cloudfront.PriceClass.PRICE_CLASS_200,
      // Default behavior (CachingOptimized)
      defaultBehavior: {
        origin: s3Origin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        responseHeadersPolicy,
        compress: true,
      },
      // Additional cache behaviors
      additionalBehaviors: {
        // Long-term cache for static assets (JS, CSS, images with hash)
        '/assets/*': {
          origin: s3Origin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
          cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
          cachePolicy: staticAssetsCachePolicy,
          responseHeadersPolicy,
          compress: true,
        },
        // No cache for index.html
        '/index.html': {
          origin: s3Origin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
          cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          responseHeadersPolicy,
          compress: true,
        },
      },
      // SPA routing: 403/404 → index.html
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
      ],
      // Custom domain (optional)
      domainNames: props.domainName ? [props.domainName] : undefined,
      certificate,
      // Logging (prod only)
      logBucket,
      logFilePrefix: logBucket ? 'cloudfront/' : undefined,
      logIncludesCookies: false,
    });

    // ============================================================
    // Route53 DNS Record (Optional)
    // ============================================================
    if (props.domainName && props.hostedZoneId) {
      const zone = route53.HostedZone.fromHostedZoneAttributes(this, 'Zone', {
        hostedZoneId: props.hostedZoneId,
        zoneName: props.hostedZoneName ?? props.domainName,
      });
      new route53.ARecord(this, 'DNSRecord', {
        zone,
        recordName: props.domainName,
        target: route53.RecordTarget.fromAlias(
          new targets.CloudFrontTarget(this.distribution),
        ),
      });
    }

    // ============================================================
    // Outputs
    // ============================================================
    new cdk.CfnOutput(this, 'BucketName', {
      value: this.bucket.bucketName,
      exportName: `memoru-${props.environment}-liff-bucket`,
      description: 'S3 Bucket name for LIFF app',
    });

    new cdk.CfnOutput(this, 'BucketArn', {
      value: this.bucket.bucketArn,
      exportName: `memoru-${props.environment}-liff-bucket-arn`,
      description: 'S3 Bucket ARN',
    });

    new cdk.CfnOutput(this, 'DistributionId', {
      value: this.distribution.distributionId,
      exportName: `memoru-${props.environment}-liff-distribution-id`,
      description: 'CloudFront Distribution ID',
    });

    new cdk.CfnOutput(this, 'DistributionDomainName', {
      value: this.distribution.distributionDomainName,
      exportName: `memoru-${props.environment}-liff-distribution-domain`,
      description: 'CloudFront Distribution Domain Name',
    });

    const liffUrl = props.domainName
      ? `https://${props.domainName}`
      : `https://${this.distribution.distributionDomainName}`;
    new cdk.CfnOutput(this, 'LiffUrl', {
      value: liffUrl,
      exportName: `memoru-${props.environment}-liff-url`,
      description: 'LIFF Application URL',
    });

    new cdk.CfnOutput(this, 'DeployCommand', {
      value: `aws s3 sync ./dist s3://${this.bucket.bucketName} --delete && aws cloudfront create-invalidation --distribution-id ${this.distribution.distributionId} --paths "/*"`,
      description: 'Command to deploy LIFF app',
    });
  }
}
