# Keycloak Infrastructure Makefile
SHELL := /bin/bash
AWS_REGION ?= ap-northeast-1
STACK_NAME_DEV = memoru-dev-keycloak
STACK_NAME_PROD = memoru-prod-keycloak

.PHONY: help validate deploy-dev deploy-prod status-dev status-prod outputs-dev outputs-prod delete-dev logs-dev

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
		--capabilities CAPABILITY_NAMED_IAM \
		--region $(AWS_REGION) \
		--no-fail-on-empty-changeset

deploy-prod: ## Deploy to production environment
	aws cloudformation deploy \
		--stack-name $(STACK_NAME_PROD) \
		--template-file template.yaml \
		--parameter-overrides file://parameters-prod.json \
		--capabilities CAPABILITY_NAMED_IAM \
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
	echo "Deleting stack..." && \
	aws cloudformation wait stack-delete-complete \
		--stack-name $(STACK_NAME_DEV) \
		--region $(AWS_REGION) && \
	echo "Stack deleted." || echo "Deletion cancelled."

logs-dev: ## Tail Keycloak logs (dev)
	aws logs tail /ecs/memoru-dev-keycloak \
		--follow \
		--region $(AWS_REGION)

admin-password-dev: ## Get Keycloak admin password (dev)
	@aws secretsmanager get-secret-value \
		--secret-id memoru-dev-keycloak-admin-secret \
		--query 'SecretString' \
		--output text \
		--region $(AWS_REGION) | jq -r '.password'

db-password-dev: ## Get RDS password (dev)
	@aws secretsmanager get-secret-value \
		--secret-id memoru-dev-keycloak-db-secret \
		--query 'SecretString' \
		--output text \
		--region $(AWS_REGION) | jq -r '.password'

events-dev: ## Show recent stack events (dev)
	aws cloudformation describe-stack-events \
		--stack-name $(STACK_NAME_DEV) \
		--query 'StackEvents[0:10].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
		--output table \
		--region $(AWS_REGION)
