#!/usr/bin/env python3
from subprocess import call
from pylxd import Client
import time
import warnings
import pprint
import json

# pylxd gives a warning on bionic for client.container.get('myc')
warnings.filterwarnings("ignore")

client = Client()  # we focus on local LXD socket
confs = {}
join_retry = []


def main():
    create_cluster("primary")


def create_cluster(cluster_name="primary"):
    vault_list = [
        "unsealer",
        "vault01",
        "vault02",
        "vault03",
        "pki",
    ]
    consul_list = ["consul01", "consul02", "consul03"]

    all_list = vault_list + consul_list
    create_base()
    # create the containers
    port = 0
    for c in all_list:
        port += 1
        if not client.containers.exists(cluster_name + "-" + c):
            container = copy_c("base", cluster_name + "-" + c)
            # we port fwd to the first server
            if container.name in vault_list[0]:
                devices = {
                    "api_port": {
                        "connect": "tcp:127.0.0.1:8200",
                        "listen": "tcp:0.0.0.0:930" + str(port),
                        "type": "proxy",
                    }
                }
                container.devices = devices

            if container.name in consul_list[0]:
                devices = {
                    "api_port": {
                        "connect": "tcp:127.0.0.1:8500",
                        "listen": "tcp:0.0.0.0:950" + str(port),
                        "type": "proxy",
                    }
                }
                container.devices = devices

            container.save(wait=True)
            container.start(wait=True)

    # create the variables for ansible
    for c in all_list:
        start_c(cluster_name + "-" + c)
        container = client.containers.get(cluster_name + "-" + c)
        environment = {"IFACE": "eth0"}
        while container.state().network["eth0"]["addresses"][0]["family"] != "inet":
            print(".. waiting for container", container.name, "to get ipv4 ..")
            time.sleep(2)
        srv_ip = container.state().network["eth0"]["addresses"][0]["address"]
        confs[container.name] = {
            "cluster_ip": srv_ip,
            "hostname": container.name,
        }
        if container.name.split("-")[1] in consul_list:
            join_retry.append(srv_ip)
        print(f"Container {container.name} got IP {srv_ip}")

    # create the join_retry variable for consul agents, it should point to the consul servers IPs
    for c in confs:
        confs[c]["join_retry"] = join_retry

    pprint.pprint(confs)
    # create the inventory list of vault ips, delimited by commans
    hosts_vault = []
    for c in vault_list:
        hosts_vault.append(confs[cluster_name + "-" + c]["cluster_ip"])
    hosts_vault = ",".join(hosts_vault)

    call(
        [
            "ansible-playbook",
            "-i",
            hosts_vault,
            "ansible/vault/playbook.yml",
            "-e",
            json.dumps(confs),
        ]
    )
    ## Run playbook

    #     if container.name in client_list:
    #         commands = client_cmd
    #         environment = {"IFACE": "eth0", "LAN_JOIN": srv_ip}

    #     # we are sure network is working, so lets continue
    #     for command in commands:
    #         execute_c(container, command, environment)


####


def create_c(name):

    # https://github.com/lxc/lxd/blob/master/doc/rest-api.md
    config = {
        "name": name,
        "source": {
            "type": "image",
            "mode": "pull",
            "server": "https://cloud-images.ubuntu.com/daily",
            "protocol": "simplestreams",
            "alias": "focal/amd64",
        },
    }
    print(f"Config {config}")
    print("creating container", name)
    return client.containers.create(config, wait=True)


def create_base():
    base_cmd = [
        "apt-get update".split(),
        "apt-get upgrade -y".split(),
        "apt autoremove -y".split(),
    ]
    # create base container
    if not client.containers.exists("base"):
        create_c("base")
        start_c("base")
        environment = {"DEBIAN_FRONTEND": "noninteractive"}
        container = client.containers.get("base")
        for command in base_cmd:
            execute_c(container, command, environment)
        stop_c("base")


def copy_c(src, dst):

    # https://github.com/lxc/lxd/blob/master/doc/rest-api.md
    config = {
        "name": dst,
        "source": {"type": "copy", "container_only": True, "source": src},
    }

    print(f"copy container {src} to {dst}")
    return client.containers.create(config, wait=True)


def start_c(name):
    l = client.containers.get(name)
    if any([l.status == "Stopped", l.status == "Frozen"]):
        l.start(wait=True)
        print("status ", l.status)


def stop_c(name):
    l = client.containers.get(name)
    if any([l.status == "Running", l.status == "Frozen"]):
        l.stop(wait=True)
        print("status ", l.status)


def execute_c(container, command, environment):
    # wait until there is an ip
    while container.state().network["eth0"]["addresses"][0]["family"] != "inet":
        print(".. waiting for container", container.name, "to get ipv4 ..")
        time.sleep(2)
    print("command: {}".format(command))
    result = container.execute(command, environment)
    print("exit_code: {}".format(result.exit_code))
    print("stdout: {}".format(result.stdout))
    if result.stderr:
        print("stderr: {}".format(result.stderr))


if __name__ == "__main__":
    main()
