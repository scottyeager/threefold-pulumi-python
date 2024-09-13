import subprocess


def run_script_ssh(ip, script):
    with open("post_deploy.log", "w") as logfile:
        subprocess.run(
            [
                "ssh",
                "-oStrictHostKeyChecking=accept-new",
                "-oConnectionAttempts=5",
                "root@" + ip,
                # "bash",
                # "-c",
                script,
            ],
            stdout=logfile,
            stderr=logfile,
        )


def scp(ip, source, destination):
    # Meant for ipv6
    with open("scp.log", "w") as logfile:
        subprocess.run(
            [
                "scp",
                "-r",
                "-oStrictHostKeyChecking=accept-new",
                "-oConnectionAttempts=5",
                source,
                f"root@[{ip}]:{destination}",
            ],
            stdout=logfile,
            stderr=logfile,
        )
