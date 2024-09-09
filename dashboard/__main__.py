import os, shlex, subprocess
import pulumi
import pulumi_threefold as threefold

import vars

MNEMONIC = vars.MNEMONIC
NETWORK = vars.NETWORK

with open(os.path.expanduser("~/.ssh/id_rsa.pub")) as file:
    SSH_KEY = file.read()

NODEID = vars.NODEID
GATEWAY = vars.GATEWAY
NAME = vars.NAME
NETWORK_NAME = "net"
FLIST = "https://hub.grid.tf/tf-official-apps/threefoldtech-ubuntu-22.04.flist"
CPU = 1
RAM = 2048  # MB
ROOTFS = 1024 * 15  # MB

provider = threefold.Provider("provider", mnemonic=MNEMONIC, network=NETWORK)

opts = pulumi.ResourceOptions(provider=provider)

network = threefold.Network(
    "network",
    name="test",
    description="test network",
    nodes=list({NODEID, GATEWAY}), # Use a set for deduplication
    ip_range="10.1.0.0/16",
    mycelium=True,
    opts=pulumi.ResourceOptions(provider=provider),
)

deployment = threefold.Deployment(
    "deployment",
    node_id=NODEID,
    name="deployment",
    network_name="test",
    vms=[
        threefold.VMInputArgs(
            name="vm",
            flist=FLIST,
            entrypoint="/sbin/zinit init",
            network_name="test",
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

gateway_name = threefold.GatewayName("gatewayName",
    name=NAME,
    node_id=GATEWAY,
    network="test",
    backends=[deployment.vms_computed.apply(lambda vms_computed: f"http://{vms_computed[0].ip}:5173")],
    opts = pulumi.ResourceOptions(provider=provider, depends_on=[network, deployment])
)

pulumi.export("backend", gateway_name.backends)

pulumi.export("node_deployment_id", deployment.node_deployment_id)
pulumi.export("planetary_ip", deployment.vms_computed[0].planetary_ip)
pulumi.export("mycelium_ip", deployment.vms_computed[0].mycelium_ip)
pulumi.export("ipv6", deployment.vms_computed[0].computed_ip6)
pulumi.export("fqdn", gateway_name.fqdn)

deployment.vms_computed[0].mycelium_ip.apply(lambda mycelium_ip: run_script_ssh(mycelium_ip, SCRIPT))

def run_script_ssh(ip, script):
    with open('post_deploy.log', 'w') as logfile:
        subprocess.run(
            [
                "ssh",
                "-oStrictHostKeyChecking=accept-new",
                "root@" + ip,
                "bash",
                "-c",
                script,
            ],
            stdout=logfile,
            stderr=logfile
        )

SCRIPT = f"""
# Simple check if the script has already been run
if [ -f /etc/zinit/dashboard.yaml ]; then
  exit
fi

apt update && apt install -y git wget build-essential python3
wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \\. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \\. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
nvm install 18
corepack enable
corepack prepare yarn@stable --activate
git clone {vars.REPO}
cd tfgrid-sdk-ts
git checkout {vars.REF}
yarn install
make build
pushd .
cd packages/playground/public/
MODE=main bash ../scripts/build-env.sh
popd
echo 'exec: bash -c "export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh && cd /root/tfgrid-sdk-ts/packages/playground && yarn dev --host"' > /etc/zinit/dashboard.yaml
zinit monitor dashboard
"""
