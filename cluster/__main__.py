import os
import pulumi
import pulumi_threefold as threefold
from vars import MNEMONIC, NETWORK, NODE_IDS, FLIST, CPU, RAM, ROOTFS, SSH_KEY_PATH


def generate_ansible_inventory(vms):
    """Generate ansible inventory content from VM IPs"""
    # Create a list of Outputs for each node line
    node_lines = [
        ip.apply(lambda ip, node=node: f"node{node} ansible_host={ip.split('/')[0]}\n")
        for node, ip in vms.items()
    ]

    # Combine all node lines with the header and vars
    return pulumi.Output.all(*node_lines).apply(
        lambda lines: "[cluster]\n"
        + "".join(lines)
        + "\n[cluster:vars]\nansible_connection=ssh\nansible_user=root\n"
    )


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
    mycelium=True,
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
                mycelium=True,
                planetary=True,
                public_ip6=True,
                env_vars={
                    "SSH_KEY": SSH_KEY,
                },
            )
        ],
        opts=pulumi.ResourceOptions(provider=provider, depends_on=[network]),
    )

# Collect VM IPs and generate ansible inventory
vm_ips = {}
for node in NODE_IDS:
    vm = deployments[node].vms_computed[0]
    vm_ips[node] = vm.computed_ip6
    pulumi.export(f"node_{node}_mycelium_ip", vm.mycelium_ip)
    pulumi.export(f"node_{node}_pub_ipv6", vm.computed_ip6)

# Generate and write ansible inventory
inventory_content = generate_ansible_inventory(vm_ips)
inventory_path = os.path.join(os.getcwd(), "inventory.ini")
inventory_content.apply(lambda content: open(inventory_path, "w").write(content))

pulumi.export("ansible_inventory_path", inventory_path)
