import os
import textwrap

import pulumi
import pulumi_threefold as threefold

from vars import (
    CLUSTER_NAME,
    CPU,
    FLIST,
    IP_TYPE,
    IPV6,
    MNEMONIC,
    NETWORK,
    NODE_IDS,
    PLANETARY,
    RAM,
    ROOTFS,
    SSH_KEY_PATH,
    WG_ACCESS,
)

# Due to $ISSUE, we only use one relay right now, though the default is still to set two
# This should be unnecessary at some point (and even harmful if we have multiple relays working again)
RELAY_URL = ["wss://relay.grid.tf"]
INVENTORY_FILE = "ansible/inventory.ini"


def generate_ansible_inventory(vms):
    """Generate ansible inventory content from VM IPs"""
    # Create a list of Outputs for each node line
    node_lines = []
    for node, vm in vms:
        if IP_TYPE == "ipv6":
            line = f"{vm_names[node]} ansible_host={vm["computed_ip6"].split('/')[0]} service_host={vm["ip"]}\n"

        else:  # wireguard
            line = f"{vm_names[node]} ansible_host={vm["ip"]} service_host={vm["ip"]}\n"
        node_lines.append(line)

    inventory_content = "".join(node_lines) + textwrap.dedent(
        """
        [all:vars]
        ansible_connection=ssh
        ansible_user=root

        prometheus_remote_write_url="https://your-remote-write-endpoint"
        prometheus_remote_write_user="your-username"
        prometheus_remote_write_password="your-password"
        """
    )

    inventory_path = os.path.join(os.getcwd(), INVENTORY_FILE)
    with open(inventory_path, "w") as file:
        file.write(inventory_content)

    pulumi.export("ansible_inventory_path", inventory_path)


with open(os.path.expanduser(SSH_KEY_PATH)) as file:
    SSH_KEY = file.read()

NET_NAME = "net"

provider = threefold.Provider(
    "provider", mnemonic=MNEMONIC, network=NETWORK, relay_url=RELAY_URL
)

network = threefold.Network(
    "network",
    name=NET_NAME,
    description="network",
    nodes=NODE_IDS,
    ip_range="10.1.0.0/16",
    add_wg_access=WG_ACCESS,
    opts=pulumi.ResourceOptions(provider=provider),
)

deployments = {}

vm_names = {}
for i, node in enumerate(NODE_IDS, 1):
    if CLUSTER_NAME != "":
        vm_name = f"{CLUSTER_NAME}_node{i}"
    else:
        vm_name = f"node{i}"
    vm_names[node] = vm_name
    deployments[node] = threefold.Deployment(
        f"deployment-{node}",
        node_id=node,
        name=f"node{node}",
        network_name=NET_NAME,
        vms=[
            threefold.VMInputArgs(
                name=vm_name,
                node_id=node,
                flist=FLIST,
                entrypoint="/sbin/zinit init",
                network_name=NET_NAME,
                cpu=CPU,
                memory=RAM,
                rootfs_size=ROOTFS,
                planetary=PLANETARY,
                public_ip6=IPV6,
                env_vars={
                    "SSH_KEY": SSH_KEY,
                },
            )
        ],
        opts=pulumi.ResourceOptions(provider=provider, depends_on=[network]),
    )

# Collect VM IPs and generate ansible inventory
vms = []
for node in NODE_IDS:
    vm = deployments[node].vms_computed[0]
    vms.append((node, vm))
    if IPV6:
        pulumi.export(f"node_{node}_pub_ipv6", vm.computed_ip6)
    pulumi.export(f"node_{node}_wireguard_ip", vm.ip)

if WG_ACCESS:
    pulumi.export("WireGuard Config", network.access_wg_config)

# Generate and write ansible inventory
pulumi.Output.all(*vms).apply(generate_ansible_inventory)
