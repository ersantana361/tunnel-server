# DNS & Subdomain Management Guide

How to configure DNS for your tunnel server while keeping existing services (like a Netlify site) working.

## Table of Contents

- [Common Scenario](#common-scenario)
- [Solution 1: Automatic Netlify DNS (Recommended)](#solution-1-automatic-netlify-dns-recommended)
- [Solution 2: Dedicated Subdomain (Manual)](#solution-2-dedicated-subdomain-manual)
- [Solution 3: Cloudflare DNS](#solution-3-cloudflare-dns)
- [Solution 4: Netlify DNS Manual Records](#solution-4-netlify-dns-manual-records)
- [Comparison](#comparison)
- [Quick Decision Guide](#quick-decision-guide)

---

## Common Scenario

You have:
- A domain (e.g., `example.com`) registered at GoDaddy/Namecheap/etc.
- DNS managed by Netlify for your main website
- A tunnel server on Vultr/DigitalOcean/etc.

**Goal**: Keep your main site on Netlify AND add tunnel subdomains.

```
Current:
example.com       -> Netlify (your site)
www.example.com   -> Netlify (your site)

Desired:
example.com       -> Netlify (your site)     [keep]
www.example.com   -> Netlify (your site)     [keep]
*.tunnel.example.com -> Tunnel Server        [add]
```

---

## Solution 1: Automatic Netlify DNS (Recommended)

**Best for**: Zero-configuration DNS that updates automatically when the server IP changes.

### Architecture

```
On server startup:
  1. Server detects its public IP
  2. Creates/updates DNS records via Netlify API:
     - tunnel.ersantana.com -> SERVER_IP
     - *.tunnel.ersantana.com -> SERVER_IP
  3. If IP hasn't changed, no API calls made
```

### Prerequisites

1. Domain managed by Netlify DNS (ersantana.com)
2. Netlify API token (Personal Access Token)
3. DNS zone ID for your domain

### Step 1: Get Netlify API Token

1. Go to [Netlify User Settings](https://app.netlify.com/user/applications)
2. Under **Personal access tokens**, click **New access token**
3. Give it a name like "tunnel-server-dns"
4. Copy the token

### Step 2: Get DNS Zone ID

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.netlify.com/api/v1/dns_zones | jq '.[] | {name, id}'

# Output:
# { "name": "ersantana.com", "id": "5f1234567890abcdef123456" }
```

### Step 3: Configure Environment

Add to 1Password (`Tunnel/tunnel-server`):
- `netlify-api-token` - Your Netlify API token
- `netlify-dns-zone-id` - The zone ID from step 2

Or set environment variables:
```bash
export NETLIFY_API_TOKEN="your_token"
export NETLIFY_DNS_ZONE_ID="your_zone_id"
export TUNNEL_DOMAIN="tunnel.ersantana.com"
```

### Step 4: Deploy

The server automatically creates DNS records on startup:
```bash
# Startup log shows:
# INFO: Setting up DNS records for tunnel.ersantana.com pointing to 1.2.3.4
# INFO: Created DNS record: tunnel.ersantana.com -> 1.2.3.4
# INFO: Created DNS record: *.tunnel.ersantana.com -> 1.2.3.4
# INFO: DNS setup complete
```

### Result

Your tunnels will use URLs like:
- `api.tunnel.ersantana.com`
- `app.tunnel.ersantana.com`
- `staging.tunnel.ersantana.com`

**Pros**:
- Zero manual DNS configuration
- Automatically updates when server IP changes
- Works with Vultr, DigitalOcean, AWS, etc.
- No DNS propagation wait (records created instantly)

**Cons**:
- Requires Netlify for DNS management
- Needs API token configuration

---

## Solution 2: Dedicated Subdomain (Manual)

**Best for**: Quick manual setup with zero risk to existing services.

### Architecture

```
example.com           -> Netlify (your site)
www.example.com       -> Netlify (your site)
*.tunnel.example.com  -> Tunnel Server (Vultr)
```

### Step 1: Add DNS Records in Netlify

Go to **Netlify Dashboard > Domain Settings > DNS Settings** and add:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | tunnel | YOUR_VULTR_IP | 3600 |
| A | *.tunnel | YOUR_VULTR_IP | 3600 |

> **Note**: If Netlify doesn't support `*.tunnel` wildcard, add individual records:
> - `api.tunnel` -> YOUR_VULTR_IP
> - `app.tunnel` -> YOUR_VULTR_IP
> - `dev.tunnel` -> YOUR_VULTR_IP

### Step 2: Configure frps

Edit `/etc/frp/frps.ini` on your server:

```ini
[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
subdomain_host = tunnel.example.com

log_file = /var/log/frps.log
log_level = info
max_pool_count = 5
```

Restart frps:

```bash
# Alpine
rc-service frps restart

# Ubuntu/Debian
systemctl restart frps
```

### Step 3: Test

```bash
# Check DNS propagation (wait 5-30 min)
dig tunnel.example.com
# Should return: YOUR_VULTR_IP

# Test wildcard
dig test.tunnel.example.com
# Should return: YOUR_VULTR_IP
```

### Result

Your tunnels will use URLs like:
- `api.tunnel.example.com`
- `app.tunnel.example.com`
- `staging.tunnel.example.com`

**Pros**:
- Zero risk to your Netlify site
- Setup in 10 minutes
- Works immediately

**Cons**:
- Slightly longer URLs

---

## Solution 3: Cloudflare DNS

**Best for**: Cleaner URLs (`api.example.com`) with extra features like firewall and CDN.

### Architecture

```
example.com           -> Netlify (Proxy ON)
www.example.com       -> Netlify (Proxy ON)
*.example.com         -> Tunnel Server (Proxy OFF)
```

### Step 1: Create Cloudflare Account

1. Go to [cloudflare.com](https://cloudflare.com) and sign up
2. Add your site: `example.com`
3. Cloudflare provides nameservers like:
   - `clark.ns.cloudflare.com`
   - `lily.ns.cloudflare.com`

### Step 2: Update Nameservers at Registrar

At GoDaddy/Namecheap:

1. Go to **Domain Settings > Nameservers**
2. Change to **Custom**
3. Enter Cloudflare's nameservers
4. Save and wait 24-48 hours for propagation

### Step 3: Configure DNS in Cloudflare

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | @ | NETLIFY_IP (104.198.14.52) | ON (orange) |
| CNAME | www | your-site.netlify.app | ON (orange) |
| A | * | YOUR_VULTR_IP | **OFF (gray)** |

> **Important**: Wildcard must have **Proxy OFF** for frp to work properly.

### Step 4: Update frps Configuration

```ini
[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
subdomain_host = example.com  # Now using root domain!

log_file = /var/log/frps.log
log_level = info
max_pool_count = 5
```

### Step 5: Verify

```bash
# Your site should work
curl -I https://example.com
curl -I https://www.example.com

# Tunnels should resolve to Vultr
dig api.example.com
# Should return: YOUR_VULTR_IP
```

### Result

Clean tunnel URLs:
- `api.example.com`
- `app.example.com`
- `staging.example.com`

**Pros**:
- Clean URLs (no `.tunnel.` prefix)
- Free Cloudflare firewall
- Free SSL
- Analytics
- CDN for your main site

**Cons**:
- 24-48h migration time
- More complex initial setup

---

## Solution 4: Netlify DNS Manual Records

**Best for**: Keeping everything in Netlify without API integration, but with limited flexibility.

### Limitation

Netlify free tier doesn't support true wildcard (`*`) DNS records.

### Workaround

Add individual A records for each subdomain:

| Type | Name | Value |
|------|------|-------|
| A | api | YOUR_VULTR_IP |
| A | app | YOUR_VULTR_IP |
| A | staging | YOUR_VULTR_IP |
| A | admin | YOUR_VULTR_IP |

### frps Configuration

Don't use `subdomain_host`. Instead, clients specify full custom domains:

```ini
[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
# No subdomain_host line

log_file = /var/log/frps.log
log_level = info
```

### Client Configuration

Clients use `custom_domains` instead of `subdomain`:

```ini
# Client frpc.ini
[web]
type = http
local_port = 8080
custom_domains = api.example.com
```

**Pros**:
- No DNS migration needed
- Works with existing Netlify setup

**Cons**:
- Must manually add DNS for each subdomain
- Less flexible
- More maintenance

---

## Comparison

| Feature | Solution 1 | Solution 2 | Solution 3 | Solution 4 |
|---------|------------|------------|------------|------------|
| Setup Time | 5 min | 10 min | 1-2 hours | 30 min |
| DNS Migration | None | None | Yes (24-48h) | None |
| URL Format | `*.tunnel.domain` | `*.tunnel.domain` | `*.domain` | `sub.domain` |
| Wildcard Support | Yes | Yes | Yes | No |
| Auto IP Update | Yes | No | No | No |
| Risk to Site | Zero | Zero | Low | Medium |
| Extra Features | Auto DNS | None | Firewall, SSL, CDN | None |
| Flexibility | High | High | Very High | Low |

---

## Quick Decision Guide

### Choose Solution 1 (Automatic Netlify DNS) if:
- You use Netlify DNS for your domain
- You want zero-configuration DNS
- You want automatic IP updates on server restart
- You're using dynamic IP or frequently redeploying

### Choose Solution 2 (Dedicated Subdomain) if:
- You want manual control over DNS
- You don't want to store API tokens
- Slightly longer URLs are acceptable

### Choose Solution 3 (Cloudflare) if:
- You want clean URLs (`api.example.com`)
- You can wait 24-48 hours for DNS propagation
- You want extra features (firewall, CDN)

### Choose Solution 4 (Manual Netlify) if:
- You only need a few specific subdomains
- You want to keep everything in Netlify without API
- You don't need wildcard support

---

## SSL/TLS for Tunnels

### Option A: Let's Encrypt with Caddy

Caddy automatically handles SSL for all subdomains:

```
*.tunnel.example.com {
    reverse_proxy localhost:80
    tls {
        dns cloudflare {env.CF_API_TOKEN}
    }
}
```

### Option B: frp with HTTPS

Configure frp to handle HTTPS directly:

```ini
[common]
bind_port = 7000
vhost_https_port = 443

# Enable HTTPS
https_proxy = true
```

### Option C: Cloudflare Flexible SSL

If using Cloudflare (Solution 2), enable **Flexible SSL**:
- Cloudflare terminates HTTPS
- Connection to your server is HTTP
- Easiest setup, but less secure

---

## Troubleshooting

### DNS Not Resolving

```bash
# Check current DNS
dig +short tunnel.example.com

# Check propagation worldwide
# Visit: https://dnschecker.org
```

### Wildcard Not Working

```bash
# Test specific subdomain
dig test.tunnel.example.com

# If it fails, your DNS provider may not support wildcards
# Use Solution 3 with individual records
```

### Netlify Site Broken After DNS Change

1. Check that `@` and `www` records still point to Netlify
2. Verify Netlify SSL certificate is still valid
3. Wait for DNS propagation (up to 48 hours)

### frp Connection Issues

```bash
# Check frps is listening
netstat -tuln | grep 7000

# Check firewall
sudo iptables -L -n | grep 7000
# or
sudo ufw status

# Check frps logs
tail -f /var/log/frps.log
```

---

## Related Documentation

- [Server Configuration Guide](./server-configuration.md) - Complete step-by-step server setup
- [Configuration](../configuration/README.md) - frp configuration options
- [Deployment](../deployment/README.md) - Server deployment guide
- [Security](../security/README.md) - SSL/TLS setup
