# AWS S3 discovery pipeline

This workspace contains a GitHub Actions workflow that scans AWS accounts for S3 buckets and maintains a reference inventory in [data/s3_reference.json](data/s3_reference.json).

## How it works

- The workflow runs every hour with a cron schedule.
- It uses AWS credentials from GitHub secrets to call AWS Organizations and assume a role in each member account.
- Each discovered bucket is appended to the inventory if it did not exist yet.
- Existing entries are refreshed with the latest discovery timestamp.

## Required GitHub secrets

Set these repository secrets before enabling the workflow:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (if your account uses temporary credentials)

## Optional environment variables

You can override the defaults in the workflow if your AWS organization uses a different role name:

- `AWS_ASSUME_ROLE_NAME` (default: `OrganizationAccountAccessRole`)