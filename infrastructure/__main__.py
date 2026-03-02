"""Tunnel Server - Google Cloud Infrastructure with Pulumi."""

import os
from string import Template

import pulumi
import pulumi_gcp as gcp

# Configuration
config = pulumi.Config()
gcp_config = pulumi.Config("gcp")

project_id = gcp_config.require("project")
region = gcp_config.get("region") or "us-central1"
zone = f"{region}-a"

# Plain config
tunnel_domain = config.require("tunnel_domain")
machine_type = config.get("machine_type") or "e2-micro"
disk_size_gb = int(config.get("disk_size_gb") or "30")
acme_email = config.get("acme_email") or "neves.erick@gmail.com"
netlify_dns_zone_id = config.get("netlify_dns_zone_id") or ""

# Secret config
jwt_secret = config.require_secret("jwt_secret")
admin_password = config.require_secret("admin_password")
admin_token = config.require_secret("admin_token")
frp_token = config.require_secret("frp_token")
netlify_api_token = config.get_secret("netlify_api_token") or pulumi.Output.from_input("")
frps_dash_password = config.require_secret("frps_dash_password")

# Common labels
labels = {
    "app": "tunnel-server",
    "environment": "production",
    "managed-by": "pulumi",
}

# Enable Compute API
compute_api = gcp.projects.Service(
    "compute-api",
    service="compute.googleapis.com",
    disable_on_destroy=False,
)

# VPC Network
network = gcp.compute.Network(
    "tunnel-network",
    name="tunnel-prod",
    auto_create_subnetworks=False,
    opts=pulumi.ResourceOptions(depends_on=[compute_api]),
)

# Subnet
subnet = gcp.compute.Subnetwork(
    "tunnel-subnet",
    name="tunnel-prod-subnet",
    ip_cidr_range="10.0.0.0/24",
    region=region,
    network=network.id,
)

# Firewall rules
firewall_ssh = gcp.compute.Firewall(
    "tunnel-allow-ssh",
    name="tunnel-allow-ssh",
    network=network.id,
    allows=[gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["22"])],
    source_ranges=["0.0.0.0/0"],
    target_tags=["tunnel-server"],
)

firewall_http = gcp.compute.Firewall(
    "tunnel-allow-http-https",
    name="tunnel-allow-http-https",
    network=network.id,
    allows=[gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["80", "443"])],
    source_ranges=["0.0.0.0/0"],
    target_tags=["tunnel-server"],
)

firewall_frps = gcp.compute.Firewall(
    "tunnel-allow-frps",
    name="tunnel-allow-frps",
    network=network.id,
    allows=[gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["7000"])],
    source_ranges=["0.0.0.0/0"],
    target_tags=["tunnel-server"],
)

firewall_admin = gcp.compute.Firewall(
    "tunnel-allow-admin-api",
    name="tunnel-allow-admin-api",
    network=network.id,
    allows=[gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["8000"])],
    source_ranges=["0.0.0.0/0"],
    target_tags=["tunnel-server"],
)

firewall_internal = gcp.compute.Firewall(
    "tunnel-allow-internal",
    name="tunnel-allow-internal",
    network=network.id,
    allows=[
        gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["7500"]),
    ],
    source_ranges=["10.0.0.0/24"],
    target_tags=["tunnel-server"],
)

# Static external IP
static_ip = gcp.compute.Address(
    "tunnel-ip",
    name="tunnel-prod-ip",
    region=region,
    address_type="EXTERNAL",
    network_tier="PREMIUM",
)

# Service account
service_account = gcp.serviceaccount.Account(
    "tunnel-sa",
    account_id="tunnel-server",
    display_name="Tunnel Server Service Account",
)

# IAM bindings for logging and monitoring
sa_logging = gcp.projects.IAMMember(
    "tunnel-sa-logging",
    project=project_id,
    role="roles/logging.logWriter",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

sa_monitoring = gcp.projects.IAMMember(
    "tunnel-sa-monitoring",
    project=project_id,
    role="roles/monitoring.metricWriter",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Read and template the startup script
startup_script_path = os.path.join(os.path.dirname(__file__), "startup.sh")
with open(startup_script_path, "r") as f:
    startup_template = Template(f.read())

# Substitute template variables using pulumi.Output.all()
startup_script = pulumi.Output.all(
    tunnel_domain=tunnel_domain,
    acme_email=acme_email,
    jwt_secret=jwt_secret,
    admin_password=admin_password,
    admin_token=admin_token,
    frp_token=frp_token,
    netlify_api_token=netlify_api_token,
    netlify_dns_zone_id=netlify_dns_zone_id,
    frps_dash_password=frps_dash_password,
).apply(
    lambda args: startup_template.safe_substitute(
        tunnel_domain=args["tunnel_domain"],
        acme_email=args["acme_email"],
        jwt_secret=args["jwt_secret"],
        admin_password=args["admin_password"],
        admin_token=args["admin_token"],
        frp_token=args["frp_token"],
        netlify_api_token=args["netlify_api_token"],
        netlify_dns_zone_id=args["netlify_dns_zone_id"],
        frps_dash_password=args["frps_dash_password"],
    )
)

# Ubuntu 22.04 LTS image
ubuntu_image = gcp.compute.get_image(
    family="ubuntu-2204-lts",
    project="ubuntu-os-cloud",
)

# Compute instance
instance = gcp.compute.Instance(
    "tunnel-vm",
    name="tunnel-prod",
    machine_type=machine_type,
    zone=zone,
    tags=["tunnel-server"],
    labels=labels,
    boot_disk=gcp.compute.InstanceBootDiskArgs(
        initialize_params=gcp.compute.InstanceBootDiskInitializeParamsArgs(
            image=ubuntu_image.self_link,
            size=disk_size_gb,
            type="pd-standard",
        ),
    ),
    network_interfaces=[
        gcp.compute.InstanceNetworkInterfaceArgs(
            network=network.id,
            subnetwork=subnet.id,
            access_configs=[
                gcp.compute.InstanceNetworkInterfaceAccessConfigArgs(
                    nat_ip=static_ip.address,
                    network_tier="PREMIUM",
                ),
            ],
        ),
    ],
    service_account=gcp.compute.InstanceServiceAccountArgs(
        email=service_account.email,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    ),
    metadata={
        "startup-script": startup_script,
    },
    shielded_instance_config=gcp.compute.InstanceShieldedInstanceConfigArgs(
        enable_secure_boot=True,
        enable_vtpm=True,
        enable_integrity_monitoring=True,
    ),
    allow_stopping_for_update=True,
    opts=pulumi.ResourceOptions(
        depends_on=[compute_api, firewall_ssh, firewall_http, firewall_frps],
    ),
)

# Exports
pulumi.export("vm_name", instance.name)
pulumi.export("external_ip", static_ip.address)
pulumi.export("admin_url", static_ip.address.apply(lambda ip: f"http://{ip}:8000"))
pulumi.export(
    "ssh_command",
    pulumi.Output.concat(
        "gcloud compute ssh tunnel-prod --zone=", zone, " --project=", project_id
    ),
)
pulumi.export(
    "startup_log_command",
    pulumi.Output.concat(
        "gcloud compute ssh tunnel-prod --zone=",
        zone,
        " --project=",
        project_id,
        " --command='sudo tail -f /var/log/tunnel-startup.log'",
    ),
)
