import os

import pulumi
import pulumi_threefold as threefold

from vars import (
    CPU,
    FLIST,
    IP_TYPE,
    IPV6,
    MNEMONIC,
    MYCELIUM,
    NETWORK,
    NODE_IDS,
    PLANETARY,
    RAM,
    ROOTFS,
    SSH_KEY_PATH,
)

INVENTORY_FILE = "inventory.ini"


def generate_ansible_inventory(vms):
    """Generate ansible inventory content from VM IPs"""
    # Create a list of Outputs for each node line
    node_lines = []
    for node, vm in vms:
        if IP_TYPE == "ipv6":
            line = f"node{node} ansible_host={vm["computed_ip6"].split('/')[0]} service_host={vm["ip"]}\n"

        else:  # wireguard
            line = f"node{node} ansible_host={vm["ip"]}\n"
        node_lines.append(line)

        # Combine all node lines with the header and vars
        inventory_content = (
            "[cluster]\n"
            + "".join(node_lines)
            + "\n[cluster:vars]\nansible_connection=ssh\nansible_user=root\n"
        )

        inventory_path = os.path.join(os.getcwd(), INVENTORY_FILE)
        with open(inventory_path, "w") as file:
            file.write(inventory_content)

        pulumi.export("ansible_inventory_path", inventory_path)


with open(os.path.expanduser(SSH_KEY_PATH)) as file:
    SSH_KEY = file.read()

NET_NAME = "net"

provider = threefold.Provider("provider", mnemonic=MNEMONIC, network=NETWORK)

network = threefold.Network(
    "network",
    name=NET_NAME,
    description="network",
    nodes=NODE_IDS,
    ip_range="10.1.0.0/16",
    mycelium=MYCELIUM,
    opts=pulumi.ResourceOptions(provider=provider),
)

deployments = {}

for node in NODE_IDS:
    deployments[node] = threefold.Deployment(
        f"deployment-{node}",
        node_id=node,
        name=f"node{node}",
        network_name=NET_NAME,
        vms=[
            threefold.VMInputArgs(
                name=f"vm{node}",
                node_id=node,
                flist=FLIST,
                entrypoint="/sbin/zinit init",
                network_name=NET_NAME,
                cpu=CPU,
                memory=RAM,
                rootfs_size=ROOTFS,
                mycelium=MYCELIUM,
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
    if MYCELIUM:
        pulumi.export(f"node_{node}_mycelium_ip", vm.mycelium_ip)
    if IPV6:
        pulumi.export(f"node_{node}_pub_ipv6", vm.computed_ip6)
    pulumi.export(f"node_{node}_wireguard_ip", vm.ip)

# Generate and write ansible inventory
pulumi.Output.all(*vms).apply(generate_ansible_inventory)
