# Client Integration Guide

How to integrate your project with the tunnel-server secrets system.

## Overview

There are two options for secrets management:

### Option A: 1Password (Recommended)

Secrets are stored in 1Password vault and injected at runtime using `op run`.

**You'll need:**
1. **1Password service account token** - For headless/server environments
2. **Vault access** - Read access to the "Tunnel" vault

### Option B: Age-Encrypted Files (Legacy)

Secrets are stored as encrypted JSON files.

**You'll receive:**
1. **Age private key** - For decrypting secrets (keep this secure!)
2. **Pre-signed URL** - Time-limited URL to download your encrypted secrets

---

## Option A: 1Password Integration (Recommended)

### Prerequisites

```bash
# Alpine Linux
apk add curl unzip

# Install 1Password CLI
OP_VERSION="2.32.0"
curl -sS "https://downloads.1password.com/linux/op2/pkg/v${OP_VERSION}/op_linux_amd64_v${OP_VERSION}.zip" -o op.zip
unzip -q op.zip && mv op /usr/local/bin/ && chmod +x /usr/local/bin/op
rm -f op.zip
```

### What You'll Receive

| Item | Description | Security |
|------|-------------|----------|
| Service account token | `ops_xxxxx...` | **Keep secret** - don't commit to git |
| Vault name | e.g., "Tunnel" | Need read access |
| Item name | e.g., "tunnel-server" | Contains all secrets |

### Quick Start

```bash
# 1. Set the service account token
export OP_SERVICE_ACCOUNT_TOKEN="ops_your_token_here"

# 2. Read individual secrets
FRP_TOKEN=$(op read "op://Tunnel/tunnel-server/frp-token")
DOMAIN=$(op read "op://Tunnel/tunnel-server/domain")

# 3. Or use op run with an env file
cat > .env.1password << 'EOF'
FRP_TOKEN=op://Tunnel/tunnel-server/frp-token
DOMAIN=op://Tunnel/tunnel-server/domain
EOF

op run --env-file=.env.1password -- ./your-app
```

### frpc Configuration Example

```bash
# Fetch token and generate config
FRP_TOKEN=$(op read "op://Tunnel/tunnel-server/frp-token")
DOMAIN=$(op read "op://Tunnel/tunnel-server/domain")

cat > frpc.ini << EOF
[common]
server_addr = ${DOMAIN}
server_port = 7000
token = ${FRP_TOKEN}

[my-tunnel]
type = http
local_ip = 127.0.0.1
local_port = 3000
subdomain = myapp
EOF

# Connect
frpc -c frpc.ini
```

### Service Account Setup

1. Go to https://my.1password.com
2. Developer Tools → Service Accounts
3. Create new service account
4. Grant read access to the vault containing secrets
5. Copy the token (starts with `ops_`)

---

## Option B: Age-Encrypted Secrets (Legacy)

### Prerequisites

Install these on your server:

```bash
# Alpine Linux
apk add curl jq

# Install age
AGE_VERSION="1.2.0"
wget -q "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-amd64.tar.gz"
tar -xzf "age-v${AGE_VERSION}-linux-amd64.tar.gz"
mv age/age /usr/local/bin/
rm -rf age "age-v${AGE_VERSION}-linux-amd64.tar.gz"
```

### What You'll Receive

From the admin, you'll get:

| Item | Description | Security |
|------|-------------|----------|
| Age private key | Contents of `/root/.age/key.txt` from management server | **Keep secret** - never commit to git |
| Pre-signed URL | URL like `https://...?X-Amz-Signature=...` | Time-limited (default 1 hour) |

## Quick Start

```bash
# 1. Save the age key (do this once)
mkdir -p /root/.age
cat > /root/.age/key.txt << 'EOF'
# created: 2024-01-01T00:00:00Z
# public key: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AGE-SECRET-KEY-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
EOF
chmod 600 /root/.age/key.txt

# 2. Download and decrypt secrets
curl -sf "$SECRETS_URL" | age -d -i /root/.age/key.txt > /tmp/secrets.json

# 3. Use secrets
NETLIFY_TOKEN=$(jq -r '.NETLIFY_TOKEN' /tmp/secrets.json)
FRP_TOKEN=$(jq -r '.FRP_TOKEN' /tmp/secrets.json)

# 4. Clean up
rm -f /tmp/secrets.json
```

## Bootstrap Script

Save this as `/root/load-secrets.sh`:

```bash
#!/bin/sh
set -e

# Configuration
SECRETS_URL="${SECRETS_URL:-}"
AGE_KEY="${AGE_KEY:-/root/.age/key.txt}"

# Validate
if [ -z "$SECRETS_URL" ]; then
    echo "Error: SECRETS_URL environment variable required"
    exit 1
fi

if [ ! -f "$AGE_KEY" ]; then
    echo "Error: Age key not found at $AGE_KEY"
    exit 1
fi

# Download and decrypt
echo "Fetching secrets..."
SECRETS=$(curl -sf "$SECRETS_URL" | age -d -i "$AGE_KEY")

if [ -z "$SECRETS" ]; then
    echo "Error: Failed to fetch or decrypt secrets"
    exit 1
fi

# Export all keys as environment variables
eval $(echo "$SECRETS" | jq -r 'to_entries | .[] | "export \(.key)=\"\(.value)\""')

echo "Secrets loaded successfully"
```

Usage:
```bash
chmod +x /root/load-secrets.sh
export SECRETS_URL="https://..."
source /root/load-secrets.sh

# Now use the variables
echo $NETLIFY_TOKEN
```

## Cloud-init Integration

To bootstrap a new server with secrets:

```yaml
#cloud-config
write_files:
  # Age private key
  - path: /root/.age/key.txt
    permissions: '0600'
    content: |
      # created: 2024-01-01T00:00:00Z
      # public key: age1xxx...
      AGE-SECRET-KEY-XXX...

  # Bootstrap script
  - path: /root/load-secrets.sh
    permissions: '0755'
    content: |
      #!/bin/sh
      set -e
      SECRETS_URL="${SECRETS_URL:-}"
      AGE_KEY="/root/.age/key.txt"

      if [ -z "$SECRETS_URL" ]; then
          echo "Error: SECRETS_URL required"
          exit 1
      fi

      SECRETS=$(curl -sf "$SECRETS_URL" | age -d -i "$AGE_KEY")
      eval $(echo "$SECRETS" | jq -r 'to_entries | .[] | "export \(.key)=\"\(.value)\""')
      echo "Secrets loaded"

runcmd:
  # Install age
  - |
    AGE_VERSION="1.2.0"
    wget -q "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-amd64.tar.gz"
    tar -xzf "age-v${AGE_VERSION}-linux-amd64.tar.gz"
    mv age/age /usr/local/bin/
    rm -rf age "age-v${AGE_VERSION}-linux-amd64.tar.gz"

  # Load secrets (pass URL as environment variable or inline)
  - |
    export SECRETS_URL="https://your-presigned-url-here"
    source /root/load-secrets.sh
    # Now use $NETLIFY_TOKEN, $FRP_TOKEN, etc.
```

## Refreshing Secrets

Pre-signed URLs expire (default: 1 hour). To get a new URL:

1. Contact admin to run:
   ```bash
   ./get-secrets-url.sh your-project-name 86400  # 24 hour expiry
   ```

2. Update your `SECRETS_URL` and re-run `load-secrets.sh`

For long-running servers, consider:
- Storing decrypted secrets in a secure location after first load
- Setting up a cron job to refresh periodically
- Using longer URL expiry times (up to 7 days)

## Secrets JSON Format

Your secrets file is a simple JSON object:

```json
{
  "NETLIFY_TOKEN": "nfp_xxx",
  "FRP_TOKEN": "abc123",
  "DOMAIN": "tunnel.example.com",
  "DATABASE_URL": "postgres://..."
}
```

Access any key with `jq -r '.KEY_NAME' secrets.json`

## Security Checklist

### 1Password
- [ ] Service account token is NOT committed to git
- [ ] Service account has minimal vault permissions (read-only)
- [ ] Token is stored securely (not in logs or scripts)

### Age (Legacy)
- [ ] Age private key has `chmod 600` permissions
- [ ] Age private key is NOT committed to git
- [ ] Decrypted secrets file is deleted after loading
- [ ] Pre-signed URLs are not logged or stored long-term

### General
- [ ] Server has restricted network access if possible

## Troubleshooting

### 1Password Issues

#### "could not resolve item"
- Check the vault name and item name are correct
- Verify service account has access to the vault
- Try: `op vault list` to see accessible vaults

#### "authentication required"
- Ensure `OP_SERVICE_ACCOUNT_TOKEN` is set
- Verify token hasn't been revoked
- Check token format (should start with `ops_`)

### Age Issues (Legacy)

#### "Failed to decrypt"
- Check the age key matches what was used to encrypt
- Verify the key file format (should start with `AGE-SECRET-KEY-`)

#### "URL expired"
- Pre-signed URLs have a time limit
- Request a new URL from admin

### General Issues

#### "curl: (6) Could not resolve host"
- Check network connectivity
- Verify the URL is correct

#### "jq: command not found"
- Install jq: `apk add jq` (Alpine) or `apt install jq` (Debian/Ubuntu)

---

## Related Documentation

- [Configuration](docs/configuration/README.md) - Full configuration options
- [Security](docs/security/README.md) - Security best practices
- [Troubleshooting](docs/troubleshooting/README.md) - Common issues
