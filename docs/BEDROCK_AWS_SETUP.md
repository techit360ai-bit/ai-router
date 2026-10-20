# AWS Bedrock setup

The router authenticates to Bedrock with AWS SigV4 through the standard boto3
credential chain. Credentials are never stored in source code.

## Environment variables

For Docker, set the following in `.env` (or the deployment secret store):

```dotenv
AWS_ACCESS_KEY_ID=<access-key-id>
AWS_SECRET_ACCESS_KEY=<secret-access-key>
AWS_SESSION_TOKEN=<temporary-session-token-if-applicable>
AWS_REGION=us-east-1
BEDROCK_ENABLED=true
BEDROCK_REGION=us-east-1
AI_BEDROCK_LIVE_PROBE=true
```

`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` take precedence over a shared
profile. For host-only runs, `aws configure` is also accepted; boto3 reads the
resulting `~/.aws/credentials` and `~/.aws/config`. Docker containers do not
automatically inherit the host profile.

To copy the shared profile's non-secret region and Bedrock flags into the
git-ignored `.env` without copying credentials:

```bash
python scripts/sync_aws_env.py --profile default --enable-bedrock
```

The helper never writes `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or
`AWS_SESSION_TOKEN`. Supply those through the deployment secret store, an IAM
role, or the runtime environment. Avoid committing credentials to an env file.

## Required IAM policy

Attach the policy in `config/aws/bedrock-minimum-policy.json` to the IAM user or
role used by the router. The account root user is not an appropriate runtime
principal.

```bash
aws iam create-policy \
  --policy-name TechITBedrockMinimum \
  --policy-document file://config/aws/bedrock-minimum-policy.json
```

The principal also needs model access enabled for each Bedrock model it uses.
The IAM policy alone does not grant access to a model that has not been enabled
in the account.

## Verification

```bash
aws sts get-caller-identity
aws bedrock list-foundation-models --region "${BEDROCK_REGION:-us-east-1}"
```

`ListFoundationModels` verifies the control-plane permission. The router's
normal Converse call exercises `bedrock:InvokeModel`; streaming clients exercise
`bedrock:InvokeModelWithResponseStream`.
