#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';

const app = new cdk.App();

// Stacks will be added by TASK-0130
app.synth();
