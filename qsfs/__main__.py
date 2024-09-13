import os
import sys
import secrets
import shutil
import pulumi
import pulumi_threefold as threefold

import vars

sys.path.append("..")  # Dirty hack, will fix soon of course ;)
import util

MNEMONIC = vars.MNEMONIC
NETWORK = vars.NETWORK

with open(os.path.expanduser("~/.ssh/id_rsa.pub")) as file:
    SSH_KEY = file.read()

VM_NODE = vars.VM_NODE
FLIST = "https://hub.grid.tf/tf-official-apps/threefoldtech-ubuntu-22.04.flist"
CPU = 1
RAM = 2048  # MB
ROOTFS = 1024 * 15  # MB
NET_NAME = "net"

META_NODES = vars.META_NODES
DATA_NODES = vars.DATA_NODES
DATA_SIZE = vars.DATA_SIZE

# Generate separate secrets for Zstor key and Zdb namespaces passwords
ZSTOR_KEY = secrets.token_hex(32)
ZDB_PW = secrets.token_urlsafe(32)

encryption_config = f"""
[encryption]
algorithm = "AES"
key = "{ZSTOR_KEY}"

[meta.config.encryption]
algorithm = "AES"
key = "{ZSTOR_KEY}"
"""

provider = threefold.Provider("provider", mnemonic=MNEMONIC, network=NETWORK)

network = threefold.Network(
    "network",
    name=NET_NAME,
    description="A network",
    nodes=[VM_NODE],
    ip_range="10.1.0.0/16",
    mycelium=True,
    opts=pulumi.ResourceOptions(provider=provider),
)
nodes = set([VM_NODE] + META_NODES + DATA_NODES)

deployments = {}

for node in nodes:
    net_name = ""
    vms = []
    depends = []
    if node == VM_NODE:
        net_name = NET_NAME
        depends.append(network)
        vms.append(
            threefold.VMInputArgs(
                name="vm",
                flist=FLIST,
                entrypoint="/sbin/zinit init",
                network_name=net_name,
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
        )
    zdbs = []
    if node in DATA_NODES:
        zdbs.append(
            threefold.ZDBInputArgs(
                name="data" + str(node), size=DATA_SIZE, mode="seq", password=ZDB_PW
            )
        )
    if node in META_NODES:
        zdbs.append(
            threefold.ZDBInputArgs(
                name="meta" + str(node), size=1, mode="user", password=ZDB_PW
            )
        )

    deployments[node] = threefold.Deployment(
        "deployment" + str(node),
        node_id=node,
        name="node" + str(node),
        network_name=net_name,
        vms=vms,
        zdbs=zdbs,
        opts=pulumi.ResourceOptions(provider=provider, depends_on=depends),
    )


def post_deploy(args):
    # TODO: Don't overwrite existing file if it's there
    shutil.copy("zstor_config.toml.base", "zstor_config.toml")

    meta_zdbs = []
    data_zdbs = []
    for vm_list, zdb_list in args:
        if vm_list:
            vm = vm_list[0]

        for zdb in zdb_list:
            if "meta" in zdb["namespace"]:
                meta_zdbs.append(zdb)
            else:
                data_zdbs.append(zdb)
    meta_zdbs = sorted(meta_zdbs, key=lambda z: z["namespace"].split("-")[-1])
    data_zdbs = sorted(data_zdbs, key=lambda z: z["namespace"].split("-")[-1])

    with open("zstor_config.toml", "a") as file:
        file.write(encryption_config)
        for zdb in meta_zdbs:
            ip = zdb["ips"][1]
            ns = zdb["namespace"]
            file.write("[[meta.config.backends]]\n")
            file.write(f'address = "[{ip}]:9900"\n')
            file.write(f'namespace = "{ns}"\n')
            file.write(f'password = "{ZDB_PW}"\n\n')

        file.write("[[groups]]\n")
        for zdb in data_zdbs:
            ip = zdb["ips"][1]
            ns = zdb["namespace"]
            file.write("[[groups.backends]]\n")
            file.write(f'address = "[{ip}]:9900"\n')
            file.write(f'namespace = "{ns}"\n')
            file.write(f'password = "{ZDB_PW}"\n\n')

    # ssh_ip = vm["mycelium_ip"]
    ssh_ip = vm["computed_ip6"].split("/")[0]
    util.scp(ssh_ip, "zinit/", "/etc/")
    util.scp(ssh_ip, "zstor_config.toml", "/etc/zstor-default.toml")
    util.run_script_ssh(ssh_ip, SCRIPT)


pulumi.Output.all(
    *[(d.vms_computed, d.zdbs_computed) for d in deployments.values()]
).apply(post_deploy)

vm = deployments[VM_NODE].vms_computed[0]
pulumi.export("mycelium_ip", vm.mycelium_ip)
pulumi.export("pub_ipv6", vm.computed_ip6)

SCRIPT = """
# Grab binaries and hook script. Make sure that all are executable
wget -O /usr/local/bin/zdbfs https://github.com/threefoldtech/0-db-fs/releases/download/v0.1.11/zdbfs-0.1.11-amd64-linux-static
wget -O /usr/local/bin/zdb https://github.com/threefoldtech/0-db/releases/download/v2.0.8/zdb-2.0.8-linux-amd64-static
wget -O /bin/zstor https://github.com/threefoldtech/0-stor_v2/releases/download/v0.4.0/zstor_v2-x86_64-linux-musl
wget -O /usr/local/bin/zdb-hook.sh https://raw.githubusercontent.com/threefoldtech/quantum-storage/master/lib/zdb-hook.sh

echo
echo Setting permissions for downloaded binaries
chmod +x /usr/local/bin/* /bin/zstor

echo
echo Creating Zdbfs mountpoint
mkdir -p /mnt/qsfs

echo
echo Starting up zinit services
zinit monitor zstor
zinit monitor zdb
zinit monitor zdbfs

# Zdbfs will fail on first attempt because zdb isn't actually (could add a test to zdb to fix this, maybe using redis-cli, nc, or ss)
sleep 1 
zinit
"""
