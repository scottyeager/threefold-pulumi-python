import os
import textwrap

import pulumi
import pulumi_threefold as threefold

from vars import (
    CLUSTER_NAME,
    CPU,
    FLIST,
    IP_TYPE,
    MNEMONIC,
    MYCELIUM,
    NETWORK,
    NODE_IDS,
    PLANETARY,
    RAM,
    ROOTFS,
    SSH_KEY_PATH,
    WG_NETWORK,
    WG_PORT,
    WG_KEEPALIVE,
)

if MNEMONIC is None:
    MNEMONIC = os.getenv("MNEMONIC")

# Due to $ISSUE, we only use one relay right now, though the default is still to set two
# This should be unnecessary at some point (and even harmful if we have multiple relays working again)
RELAY_URL = ["wss://relay.grid.tf"]
INVENTORY_FILE = "ansible/inventory.ini"


def generate_ansible_inventory(vms):
    """Generate ansible inventory content from VM IPs"""
    # Get network prefix and assign Wireguard IPs sequentially starting from .1
    network_prefix = WG_NETWORK.split('.')[:3]
    wireguard_ips = [f"{'.'.join(network_prefix)}.{i+1}" for i in range(len(vms))]

    # Create a list of Outputs for each node line
    node_lines = []
    for i, (node, vm) in enumerate(vms):
        ipv6_address = vm["computed_ip6"].split('/')[0]
        if IP_TYPE == "ipv6":
            ansible_host = ipv6_address

        elif IP_TYPE == "mycelium":
            ansible_host= vm["mycelium_ip"]

        else:
            raise ValueError("IP_TYPE for SSH must be ipv6 or mycelium")

        node_lines.append(f"{vm_names[node]} ansible_host={ansible_host} wireguard_ip={wireguard_ips[i]} ipv6_address={ipv6_address}\n")



    inventory_content = "\n".join(node_lines) + textwrap.dedent(
        """
        [all:vars]
        ansible_connection=ssh
        ansible_user=root
        wireguard_port={WG_PORT}
        wireguard_keepalive={WG_KEEPALIVE}

        prometheus_remote_write_url="https://your-remote-write-endpoint"
        prometheus_remote_write_user="your-username"
        prometheus_remote_write_password="your-password"
        """
    ).format(WG_PORT=WG_PORT, WG_KEEPALIVE=WG_KEEPALIVE)

    inventory_path = os.path.join(os.getcwd(), INVENTORY_FILE)
    with open(inventory_path, "w") as file:
        file.write(inventory_content)

    pulumi.export("ansible_inventory_path", inventory_path)


with open(os.path.expanduser(SSH_KEY_PATH)) as file:
    SSH_KEY = file.read()

provider = threefold.Provider(
    "provider", mnemonic=MNEMONIC, network=NETWORK, relay_url=RELAY_URL
)

networks = {}
deployments = {}

vm_names = {}
for i, node in enumerate(NODE_IDS, 1):
    if CLUSTER_NAME != "":
        vm_name = f"{CLUSTER_NAME}_node{i}"
    else:
        vm_name = f"node{i}"
    vm_names[node] = vm_name

    network_name = f"{CLUSTER_NAME}_net{node}"
    networks[node] = threefold.Network(
        network_name,
        name=network_name,
        description=f"network for node {node}",
        nodes=[node],
        ip_range="10.1.0.0/16",
        mycelium=MYCELIUM,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    deployments[node] = threefold.Deployment(
        f"deployment-{node}",
        node_id=node,
        name=f"node{node}",
        network_name=network_name,
        vms=[
            threefold.VMInputArgs(
                name=vm_name,
                node_id=node,
                flist=FLIST,
                entrypoint="/sbin/zinit init",
                network_name=network_name,
                cpu=CPU,
                memory=RAM,
                rootfs_size=ROOTFS,
                planetary=PLANETARY,
                mycelium=MYCELIUM,
                public_ip6=True,
                env_vars={
                    "SSH_KEY": SSH_KEY,
                },
            )
        ],
        opts=pulumi.ResourceOptions(provider=provider, depends_on=[networks[node]]),
    )

# Collect VM IPs and generate ansible inventory
vms = []
for node in NODE_IDS:
    vm = deployments[node].vms_computed[0]
    vms.append((node, vm))
    pulumi.export(f"node_{node}_pub_ipv6", vm.computed_ip6)
    if MYCELIUM:
        pulumi.export(f"node_{node}_mycelium_ip", vm.mycelium_ip)


# Generate and write ansible inventory
pulumi.Output.all(*vms).apply(generate_ansible_inventory)
