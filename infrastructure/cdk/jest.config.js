// Suppress JSII deprecation warnings from CDK internal PropInjectable
// (e.g. containerInsights injected despite using containerInsightsV2)
process.env.JSII_DEPRECATED = process.env.JSII_DEPRECATED ?? 'quiet';

module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/test'],
  testMatch: ['**/*.test.ts'],
  transform: {
    '^.+\\.tsx?$': [
      'ts-jest',
      {
        tsconfig: {
          isolatedModules: true,
        },
      },
    ],
  },
};
