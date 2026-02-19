# PostgreSQL MCP Server - AWS Bedrock AgentCore Deployment Guide

This guide covers deploying the PostgreSQL MCP Server to **AWS Bedrock AgentCore Runtime** for production use.

## Quick Start (Recommended Method)

This is the **verified working deployment method** using AWS Bedrock AgentCore CLI with Direct Code Deploy.

### Prerequisites

- Python 3.10+ with virtual environment
- AWS credentials configured (temporary credentials with session token supported)
- AWS account with appropriate permissions

### Step 1: Install AgentCore Toolkit

```bash
# Activate your virtual environment
source .venv/bin/activate

# Install the toolkit
pip install bedrock-agentcore-starter-toolkit

# Verify installation
agentcore --help
```

### Step 2: Configure AWS Credentials

Create or update `.aws/credentials` in your project directory:

```ini
[637423343847_ITDeveloperAccess]
aws_access_key_id=YOUR_ACCESS_KEY_ID
aws_secret_access_key=YOUR_SECRET_ACCESS_KEY
aws_session_token=YOUR_SESSION_TOKEN  # Required for temporary credentials
```

Create or update `.aws/config`:

```ini
[profile 637423343847_ITDeveloperAccess]
region = us-west-2
output = json
```

### Step 3: Configure MCP Server for Deployment

```bash
# Set AWS credentials
export AWS_SHARED_CREDENTIALS_FILE=$(pwd)/.aws/credentials
export AWS_PROFILE=637423343847_ITDeveloperAccess

# Configure the agent (use underscores, not hyphens in name)
agentcore configure -e mcp_server.py \
  --protocol MCP \
  --disable-memory \
  --name postgres_mcp \
  --non-interactive \
  --region us-west-2
```

This creates `.bedrock_agentcore.yaml` with your deployment configuration.

### Step 4: Deploy to AWS

```bash
# Deploy using the same AWS credentials
export AWS_SHARED_CREDENTIALS_FILE=$(pwd)/.aws/credentials
export AWS_PROFILE=637423343847_ITDeveloperAccess

agentcore deploy
```

The deployment will:
- Create IAM execution role automatically
- Create S3 bucket for deployment packages
- Package and upload your code
- Deploy to AgentCore Runtime with Direct Code Deploy (no Docker required)
- Configure CloudWatch logging and observability

### Step 5: Verify Deployment

```bash
# Check agent status
agentcore status

# View the agent ARN and endpoint details
```

**Example Output:**
```
Agent ARN: arn:aws:bedrock-agentcore:us-west-2:637423343847:runtime/postgres_mcp-M7k4jR9aLJ
Endpoint: DEFAULT (READY)
Status: Ready - Agent deployed and endpoint available
```

### Step 6: Invoke the Deployed Agent

**List available tools:**
```bash
agentcore invoke '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

**Call a tool (MCP JSON-RPC format):**
```bash
# Math tools
agentcore invoke '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"math_add","arguments":{"a":10,"b":5}},"id":2}'
agentcore invoke '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"math_subtract","arguments":{"a":10,"b":5}},"id":3}'
agentcore invoke '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"math_multiply","arguments":{"a":10,"b":5}},"id":4}'
agentcore invoke '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"math_divide","arguments":{"a":10,"b":5}},"id":5}'

# Database query
agentcore invoke '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"postgres_query","arguments":{"sql":"SELECT 1"}},"id":6}'
```

**Available Tools:**

| Tool | Description |
|------|-------------|
| `postgres_query` | Run read-only SQL SELECT queries against PostgreSQL |
| `math_add` | Add two numbers (a + b) |
| `math_subtract` | Subtract two numbers (a - b) |
| `math_multiply` | Multiply two numbers (a * b) |
| `math_divide` | Divide two numbers (a / b), handles division by zero |

### Step 7: Monitor and Debug

**View CloudWatch Logs:**
```bash
# Tail runtime logs
aws logs tail /aws/bedrock-agentcore/runtimes/postgres_mcp-XXX-DEFAULT \
  --log-stream-name-prefix "2026/02/17/[runtime-logs" \
  --follow

# View recent logs
aws logs tail /aws/bedrock-agentcore/runtimes/postgres_mcp-XXX-DEFAULT \
  --log-stream-name-prefix "2026/02/17/[runtime-logs" \
  --since 1h
```

**GenAI Observability Dashboard:**
```
https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#gen-ai-observability/agent-core
```

### Important Notes

1. **Agent Naming:** Use underscores only (e.g., `postgres_mcp`), not hyphens
2. **AWS Credentials:** Temporary credentials (ASIA prefix) require `AWS_SESSION_TOKEN`
3. **Deployment Type:** Direct Code Deploy is recommended (no Docker required)
4. **Memory:** Disabled by default with `--disable-memory` flag
5. **Protocol:** Must specify `--protocol MCP` for MCP servers
6. **Region:** Ensure consistent region across all commands (us-west-2)
7. **Config file:** `.bedrock_agentcore.yaml` is in `.gitignore` — do not commit it (contains account/ARN details)
8. **Invoke format:** Always use MCP JSON-RPC format (`{"jsonrpc":"2.0","method":"tools/call",...}`) not plain JSON

### Cleanup

```bash
# Destroy the agent and resources
agentcore destroy
```

---

## Architecture Overview

```mermaid
flowchart TB
    subgraph "Client Layer"
        A[AI Agent / LLM Client]
        B[Windsurf / IDE]
        C[Custom Application]
    end

    subgraph "Local Proxy"
        P[mcp-proxy-for-aws]
    end

    subgraph "AWS Bedrock AgentCore"
        D[AgentCore Runtime]
        E[IAM Auth / SigV4]
    end

    subgraph "MCP Server Code"
        F[mcp_server.py]
        G[postgres_query tool]
        H[math_add / subtract / multiply / divide tools]
    end

    subgraph "Database Layer"
        I[(PostgreSQL RDS)]
    end

    subgraph "AWS Services"
        J[Secrets Manager]
        K[CloudWatch Logs]
    end

    A --> P
    B --> P
    C --> P
    P -->|SigV4 signed| E
    E --> D
    D --> F
    F --> G
    F --> H
    G --> I
    F --> J
    D --> K
```

## Deployment Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as AgentCore CLI
    participant S3 as AWS S3
    participant AC as AgentCore Runtime
    participant CW as CloudWatch

    Dev->>CLI: agentcore configure
    CLI->>Dev: Generate .bedrock_agentcore.yaml
    Dev->>CLI: agentcore deploy
    CLI->>S3: Upload deployment package (zip)
    CLI->>AC: Deploy via Direct Code Deploy
    AC->>CW: Configure logging & observability
    AC->>Dev: Return Agent ARN
    Dev->>AC: agentcore invoke (test)
    AC->>Dev: MCP JSON-RPC Response
```

## Prerequisites

### AWS Requirements

| Requirement | Description |
|-------------|-------------|
| **AWS Account** | With credentials configured (`aws configure`) |
| **IAM Permissions** | `BedrockAgentCoreFullAccess` + `AmazonBedrockFullAccess` |
| **Region** | `us-west-2` (default) or supported region |
| **VPC** | For private database access (optional) |

### Local Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| Docker | Latest (for local testing) |
| AWS CLI | v2 |

### Install AgentCore Toolkit

```bash
pip install bedrock-agentcore bedrock-agentcore-starter-toolkit
```

Verify installation:

```bash
agentcore --help
```

## Deployment Options

```mermaid
flowchart LR
    subgraph "Deployment Methods"
        A[Option 1: CLI Toolkit]
        B[Option 2: CloudFormation]
        C[Option 3: Manual Docker]
    end

    A --> D[Recommended for Quick Start]
    B --> E[Recommended for IaC]
    C --> F[Recommended for Custom Setup]
```

---

## Option 1: AgentCore CLI Deployment (Recommended)

### Step 1: Prepare Project Structure

```
postgres-mcp/
├── mcp_server.py          # Main MCP server (entrypoint)
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (local only)
└── Dockerfile             # Container configuration
```

### Step 2: Configure AgentCore

```bash
cd postgres-mcp
agentcore configure -e mcp_server.py --disable-memory
```

This creates `.bedrock_agentcore.yaml` with deployment configuration.

### Step 3: Set Environment Variables

Create AWS Secrets Manager secret for database credentials:

```bash
aws secretsmanager create-secret \
  --name postgres-mcp/database \
  --secret-string '{"DATABASE_URL":"postgresql://user:pass@host:5432/db","MCP_API_KEY":"your-api-key"}'
```

### Step 4: Update Configuration

Edit `.bedrock_agentcore.yaml` to include secrets:

```yaml
bedrock_agentcore:
  agent_name: postgres-mcp
  entrypoint: mcp_server.py
  runtime:
    environment:
      - name: DATABASE_URL
        valueFrom:
          secretsManagerArn: arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:postgres-mcp/database
      - name: MCP_API_KEY
        valueFrom:
          secretsManagerArn: arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:postgres-mcp/database
```

### Step 5: Deploy

```bash
agentcore deploy
```

This will:
- Build container using AWS CodeBuild
- Push to ECR
- Create IAM roles
- Deploy to AgentCore Runtime

### Step 6: Test Deployment

```bash
# Get agent ARN from deployment output
agentcore invoke '{"prompt": "List all tables"}'
```

### Step 7: Get Agent ARN

```bash
# From .bedrock_agentcore.yaml or deployment output
cat .bedrock_agentcore.yaml | grep agent_runtime_arn
```

---

## Option 2: CloudFormation Deployment

### Architecture with CloudFormation

```mermaid
flowchart TB
    subgraph "CloudFormation Stack"
        A[ECR Repository]
        B[Cognito User Pool]
        C[IAM Execution Role]
        D[AgentCore Runtime]
        E[CloudWatch Logs]
    end

    subgraph "External"
        F[(PostgreSQL Database)]
        G[Secrets Manager]
    end

    A --> D
    B --> D
    C --> D
    D --> E
    D --> F
    G --> D
```

### Step 1: Create CloudFormation Template

Create `cloudformation/mcp-server-template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'PostgreSQL MCP Server on AgentCore Runtime'

Parameters:
  AgentName:
    Type: String
    Default: 'PostgresMCPServer'
    Description: 'Name for the MCP server runtime'

  ECRRepositoryName:
    Type: String
    Default: 'postgres-mcp'
    Description: 'Name of the ECR repository'

  DatabaseSecretArn:
    Type: String
    Description: 'ARN of Secrets Manager secret containing DATABASE_URL and MCP_API_KEY'

Resources:
  # ECR Repository
  ECRRepository:
    Type: AWS::ECR::Repository
    Properties:
      RepositoryName: !Sub '${AWS::StackName}-${ECRRepositoryName}'
      ImageTagMutability: MUTABLE
      ImageScanningConfiguration:
        ScanOnPush: true

  # IAM Execution Role
  AgentExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${AWS::StackName}-execution-role'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: bedrock-agentcore.amazonaws.com
            Action: sts:AssumeRole
            Condition:
              StringEquals:
                aws:SourceAccount: !Ref AWS::AccountId
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess
      Policies:
        - PolicyName: MCPServerPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - ecr:BatchGetImage
                  - ecr:GetDownloadUrlForLayer
                  - ecr:BatchCheckLayerAvailability
                Resource: !GetAtt ECRRepository.Arn
              - Effect: Allow
                Action:
                  - ecr:GetAuthorizationToken
                Resource: '*'
              - Effect: Allow
                Action:
                  - secretsmanager:GetSecretValue
                Resource: !Ref DatabaseSecretArn
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: '*'

Outputs:
  ECRRepositoryUri:
    Description: 'ECR Repository URI'
    Value: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${ECRRepository}'

  ExecutionRoleArn:
    Description: 'Execution Role ARN'
    Value: !GetAtt AgentExecutionRole.Arn
```

### Step 2: Deploy Stack

```bash
aws cloudformation create-stack \
  --stack-name postgres-mcp-stack \
  --template-body file://cloudformation/mcp-server-template.yaml \
  --parameters ParameterKey=DatabaseSecretArn,ParameterValue=arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:postgres-mcp/database \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

### Step 3: Build and Push Container

```bash
# Get ECR URI from stack outputs
ECR_URI=$(aws cloudformation describe-stacks \
  --stack-name postgres-mcp-stack \
  --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
  --output text)

# Login to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin $ECR_URI

# Build and push
docker build -t postgres-mcp .
docker tag postgres-mcp:latest $ECR_URI:latest
docker push $ECR_URI:latest
```

### Step 4: Create AgentCore Runtime

```bash
aws bedrock-agentcore create-agent-runtime \
  --agent-runtime-name PostgresMCPServer \
  --role-arn <EXECUTION_ROLE_ARN> \
  --container-config '{
    "containerUri": "<ECR_URI>:latest",
    "environment": [
      {"name": "DATABASE_URL", "valueFrom": {"secretsManagerArn": "<SECRET_ARN>"}},
      {"name": "MCP_API_KEY", "valueFrom": {"secretsManagerArn": "<SECRET_ARN>"}}
    ]
  }' \
  --network-mode PUBLIC \
  --region us-west-2
```

---

## Option 3: Manual Docker Deployment

For custom infrastructure or non-AgentCore deployments.

### Step 1: Build Container

```bash
docker build -t postgres-mcp:latest .
```

### Step 2: Push to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name postgres-mcp --region us-west-2

# Get login
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.us-west-2.amazonaws.com

# Tag and push
docker tag postgres-mcp:latest <ACCOUNT>.dkr.ecr.us-west-2.amazonaws.com/postgres-mcp:latest
docker push <ACCOUNT>.dkr.ecr.us-west-2.amazonaws.com/postgres-mcp:latest
```

### Step 3: Deploy to ECS/Fargate (Alternative)

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name postgres-mcp-cluster

# Create task definition and service
# (See AWS ECS documentation for full setup)
```

---

## Security Best Practices

```mermaid
flowchart TB
    subgraph "Security Layers"
        A[API Key Authentication]
        B[AWS Cognito]
        C[IAM Roles]
        D[Secrets Manager]
        E[VPC Private Subnets]
        F[Read-Only Transactions]
    end

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
```

### Recommendations

| Layer | Implementation |
|-------|----------------|
| **API Key** | Store in Secrets Manager, rotate regularly |
| **Database** | Use RDS in private subnet, SSL required |
| **IAM** | Least privilege, use execution roles |
| **Network** | VPC endpoints for AWS services |
| **Logging** | CloudWatch Logs with retention policy |

---

## Monitoring & Observability

### Enable CloudWatch

```bash
# View logs
aws logs describe-log-groups --log-group-name-prefix /aws/bedrock-agentcore

# Tail logs
aws logs tail /aws/bedrock-agentcore/postgres-mcp --follow
```

### Health Check

The MCP server exposes `/health` endpoint:

```bash
curl https://<agent-endpoint>/health
```

---

## Invoking the Deployed Agent

### Using AWS SDK (Python)

```python
import json
import uuid
import boto3

agent_arn = "arn:aws:bedrock-agentcore:us-west-2:637423343847:runtime/postgres_mcp-M7k4jR9aLJ"

client = boto3.client('bedrock-agentcore-runtime', region_name='us-west-2')

response = client.invoke_agent_runtime(
    agentRuntimeArn=agent_arn,
    runtimeSessionId=str(uuid.uuid4()),
    payload=json.dumps({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "postgres_query",
            "arguments": {
                "sql": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' LIMIT 10"
            }
        },
        "id": 1
    }).encode(),
    qualifier="DEFAULT"
)

# Process response
content = []
for chunk in response.get("response", []):
    content.append(chunk.decode('utf-8'))
print(json.loads(''.join(content)))
```

### Using AgentCore CLI

```bash
# List tools
agentcore invoke '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Call a tool
agentcore invoke '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"postgres_query","arguments":{"sql":"SELECT 1"}},"id":2}'
```

---

## Cleanup

### Remove AgentCore Deployment

```bash
agentcore destroy
```

### Remove CloudFormation Stack

```bash
aws cloudformation delete-stack --stack-name postgres-mcp-stack --region us-west-2
```

### Remove Secrets

```bash
aws secretsmanager delete-secret --secret-id postgres-mcp/database --force-delete-without-recovery
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Container fails to start** | Check CloudWatch logs, verify DATABASE_URL |
| **Authentication errors** | Verify MCP_API_KEY in Secrets Manager |
| **Database connection timeout** | Check VPC security groups, RDS accessibility |
| **Permission denied** | Verify IAM execution role policies |

### View Logs

```bash
# AgentCore logs
aws logs tail /aws/bedrock-agentcore/postgres-mcp --follow

# Or via CLI
agentcore logs
```

---

## Windsurf IDE Integration

Connect Windsurf (or any MCP-compatible IDE) to the deployed AgentCore runtime using `mcp-proxy-for-aws`.

### Prerequisites

```bash
# Verify uvx is installed (comes with uv)
brew install uv  # or: pip install uv
uvx --version
```

### Configuration

Add the following entry to your Windsurf `mcp_config.json` (`~/.codeium/windsurf/mcp_config.json`):

```json
"agentcore-postgres-mcp": {
  "command": "uvx",
  "args": [
    "mcp-proxy-for-aws@latest",
    "https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-west-2%3A637423343847%3Aruntime%2Fpostgres_mcp-M7k4jR9aLJ/invocations?qualifier=DEFAULT"
  ],
  "env": {
    "AWS_PROFILE": "637423343847_ITDeveloperAccess",
    "AWS_REGION": "us-west-2",
    "AWS_SHARED_CREDENTIALS_FILE": "/path/to/postgres-mcp/.aws/credentials"
  }
}
```

> **Note:** The ARN in the URL must be URL-encoded. Replace `:` with `%3A` and `/` with `%2F`.

### How It Works

```
Windsurf IDE → uvx mcp-proxy-for-aws → SigV4 signed HTTPS → AgentCore Runtime → MCP Server
```

- `mcp-proxy-for-aws` runs as a local stdio MCP server
- It automatically signs requests with AWS SigV4 using your `AWS_PROFILE`
- No `X-API-Key` needed — IAM handles authentication at the AgentCore layer
- The MCP server's own `X-API-Key` middleware is automatically disabled when running in AWS

### Verify Connection

After adding the config and reloading Windsurf MCP servers, all 5 tools should appear:
- `postgres_query`
- `math_add`
- `math_subtract`
- `math_multiply`
- `math_divide`

---

## References

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [AgentCore Starter Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)
- [AgentCore Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
- [AgentCore in Action - Hosting MCP Servers](https://aws.amazon.com/th/blogs/thailand/agentcore-in-action-part1-hosting-mcp-servers-on-agentcore-runtime/)
- [mcp-proxy-for-aws](https://pypi.org/project/mcp-proxy-for-aws/)
