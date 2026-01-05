# LIFF Hosting Infrastructure Makefile
SHELL := /bin/bash
AWS_REGION ?= ap-northeast-1
STACK_NAME_DEV = memoru-liff-hosting-dev
STACK_NAME_PROD = memoru-liff-hosting-prod

.PHONY: help validate deploy-dev deploy-prod status-dev outputs-dev delete-dev deploy-app invalidate-cache

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

validate: ## Validate CloudFormation template
	aws cloudformation validate-template \
		--template-body file://template.yaml \
		--region $(AWS_REGION)

deploy-dev: ## Deploy to development environment
	aws cloudformation deploy \
		--stack-name $(STACK_NAME_DEV) \
		--template-file template.yaml \
		--parameter-overrides file://parameters-dev.json \
		--capabilities CAPABILITY_IAM \
		--region $(AWS_REGION) \
		--no-fail-on-empty-changeset

deploy-prod: ## Deploy to production environment
	aws cloudformation deploy \
		--stack-name $(STACK_NAME_PROD) \
		--template-file template.yaml \
		--parameter-overrides file://parameters-prod.json \
		--capabilities CAPABILITY_IAM \
		--region $(AWS_REGION) \
		--no-fail-on-empty-changeset

status-dev: ## Check dev stack status
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME_DEV) \
		--query 'Stacks[0].StackStatus' \
		--output text \
		--region $(AWS_REGION) 2>/dev/null || echo "Stack not found"

status-prod: ## Check prod stack status
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME_PROD) \
		--query 'Stacks[0].StackStatus' \
		--output text \
		--region $(AWS_REGION) 2>/dev/null || echo "Stack not found"

outputs-dev: ## Show dev stack outputs
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME_DEV) \
		--query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
		--output table \
		--region $(AWS_REGION)

outputs-prod: ## Show prod stack outputs
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME_PROD) \
		--query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
		--output table \
		--region $(AWS_REGION)

delete-dev: ## Delete dev stack (with confirmation)
	@read -p "Are you sure you want to delete $(STACK_NAME_DEV)? [y/N] " confirm && \
	[ "$$confirm" = "y" ] && \
	aws cloudformation delete-stack \
		--stack-name $(STACK_NAME_DEV) \
		--region $(AWS_REGION) && \
	echo "Deleting stack..." || echo "Deletion cancelled."

# Get bucket name from stack outputs
get-bucket-dev: ## Get S3 bucket name (dev)
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME_DEV) \
		--query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
		--output text \
		--region $(AWS_REGION)

get-distribution-dev: ## Get CloudFront distribution ID (dev)
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME_DEV) \
		--query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
		--output text \
		--region $(AWS_REGION)

# Deploy LIFF app (run from frontend directory)
deploy-app-dev: ## Deploy LIFF app to S3 (dev)
	@BUCKET=$$(make -s get-bucket-dev) && \
	DIST_ID=$$(make -s get-distribution-dev) && \
	echo "Deploying to bucket: $$BUCKET" && \
	aws s3 sync ../../frontend/dist s3://$$BUCKET --delete && \
	echo "Creating CloudFront invalidation..." && \
	aws cloudfront create-invalidation \
		--distribution-id $$DIST_ID \
		--paths "/*" \
		--region $(AWS_REGION)

invalidate-cache-dev: ## Invalidate CloudFront cache (dev)
	@DIST_ID=$$(make -s get-distribution-dev) && \
	aws cloudfront create-invalidation \
		--distribution-id $$DIST_ID \
		--paths "/*" \
		--region $(AWS_REGION)

# Request ACM certificate (us-east-1 for CloudFront)
request-certificate: ## Request ACM certificate (us-east-1)
	@read -p "Enter domain name: " domain && \
	aws acm request-certificate \
		--domain-name $$domain \
		--validation-method DNS \
		--region us-east-1 \
		--output json

list-certificates: ## List ACM certificates (us-east-1)
	aws acm list-certificates \
		--region us-east-1 \
		--output table
