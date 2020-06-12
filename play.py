#!/usr/bin/env python3
import sys
import yaml
from pathlib import Path
from subprocess import run
from pylxd import Client
import time
import warnings
import pprint
import json

# pylxd gives a warning on bionic for client.container.get('myc')
warnings.filterwarnings("ignore")

client = Client()  # we focus on local LXD socket
confs_vault = {}
confs_consul = {}
join_retry = []

provision_cmds = [
    # "bash /tmp/pubkeys.sh".split(),
]

base_cmd = [
    "apt-get update".split(),
    "apt-get upgrade -y".split(),
    "apt-get install -y jq mc joe".split(),
    "apt autoremove -y".split(),
]


def main():
    cluster_name = sys.argv[1]
    create_proxy()
    create_cluster(cluster_name)


def create_proxy():

    c_name = "proxy"
    if not client.containers.exists(c_name):
        create_base("primary", "lxdbr0")
        container = copy_c(f"base-primary", c_name)
        container.config.update(
            {
                "user.network-config": """
version: 1
config:
    - type: physical
      name: eth0
      subnets:
          - type: dhcp
            control: auto
    - type: physical
      name: eth1
      subnets:
          - type: dhcp
            control: auto
    - type: physical
      name: eth2
      subnets:
          - type: dhcp
            control: auto                        
"""
            }
        )
        container.devices.update(
            {
                "eth0": {
                    "name": "eth0",
                    "nictype": "bridged",
                    "parent": "lxdbr0",
                    "type": "nic",
                },
                "eth1": {
                    "name": "eth1",
                    "nictype": "bridged",
                    "parent": "lxdbr1",
                    "type": "nic",
                },
                "eth2": {
                    "name": "eth2",
                    "nictype": "bridged",
                    "parent": "lxdbr2",
                    "type": "nic",
                },
            }
        )
        container.save(wait=True)
        container.start(wait=True)
        while container.state().network["eth0"]["addresses"][0]["family"] != "inet":
            print(".. waiting for container", container.name, "to get ipv4 ..")
            time.sleep(3)
        srv_ip = container.state().network["eth0"]["addresses"][0]["address"]
        devices = {
            "api_port": {
                "connect": f"tcp:{srv_ip}:1936",
                "listen": f"tcp:0.0.0.0:9900",
                "type": "proxy",
            }
        }
        print(f"Using devices:{devices}")
        container.devices.update(devices)
        container.save(wait=True)
        execute_c(
            container,
            "apt-get install haproxy -y".split(),
            {"DEBIAN_FRONTEND": "noninteractive"},
        )
        pub_key = str(Path.home()) + "/.ssh/id_rsa.pub"
        print(f"\tCopying pub key: {pub_key}")
        copy_file(
            pub_key, "/root/.ssh/authorized_keys", container,
        )
        print(f"\tCopying pub key: haproxy.cfg")
        copy_file(
            "ansible/vault/templates/haproxy.cfg",
            "/etc/haproxy/haproxy.cfg",
            container,
        )
        print(f"\tStarting haproxy")
        execute_c(
            container,
            "systemctl enable haproxy".split(),
            {"DEBIAN_FRONTEND": "noninteractive"},
        )
        execute_c(
            container,
            "systemctl start haproxy".split(),
            {"DEBIAN_FRONTEND": "noninteractive"},
        )


def create_cluster(cluster_name="primary"):
    network = {
        "primary": {
            "iface": "lxdbr0",
            "vault_base_port": 9300,
            "consul_base_port": 9400,
        },
        "dr": {"iface": "lxdbr1", "vault_base_port": 9700, "consul_base_port": 9800,},
        "secondary": {
            "iface": "lxdbr2",
            "vault_base_port": 9500,
            "consul_base_port": 9600,
        },
    }

    vault_list = [
        "unsealer",
        "vault01",
        "vault02",
        "vault03",
        "pki",
    ]
    consul_list = ["consul01", "consul02", "consul03"]

    all_list = vault_list + consul_list
    create_base(cluster_name, network[cluster_name]["iface"])
    # exit(0)
    # create the containers
    vault_port = network[cluster_name]["vault_base_port"]
    consul_port = network[cluster_name]["consul_base_port"]
    for c in all_list:

        c_name = cluster_name + "-" + c
        devices = {}
        if not client.containers.exists(c_name):
            container = copy_c(f"base-{cluster_name}", c_name)
            container.start(wait=True)
            while container.state().network["eth0"]["addresses"][0]["family"] != "inet":
                print(".. waiting for container", container.name, "to get ipv4 ..")
                time.sleep(3)
            srv_ip = container.state().network["eth0"]["addresses"][0]["address"]

            # we port fwd to the first server
            if c_name.split("-")[1] in vault_list:

                devices = {
                    "api_port": {
                        "connect": f"tcp:{srv_ip}:8200",
                        "listen": f"tcp:0.0.0.0:{vault_port}",
                        "type": "proxy",
                    }
                }
                vault_port += 1

            if c_name.split("-")[1] in consul_list:

                devices = {
                    "api_port": {
                        "connect": f"tcp:{srv_ip}:8500",
                        "listen": f"tcp:0.0.0.0:{consul_port}",
                        "type": "proxy",
                    }
                }
                consul_port += 1

            print(f"Using devices:{devices}")
            container.devices.update(devices)
            container.save(wait=True)
        else:
            # Container already exists
            container = start_c(c_name)
            srv_ip = container.state().network["eth0"]["addresses"][0]["address"]
        # environment = {"IFACE": "eth0", }

        # put cluster_ip and hostname in a dictionary for each container

        # create join_retry variable
        if container.name.split("-")[1] in consul_list:
            join_retry.append(srv_ip)
            confs_consul[container.name] = {
                "cluster_ip": srv_ip,
                "hostname": container.name,
            }
        else:
            confs_vault[container.name] = {
                "cluster_ip": srv_ip,
                "hostname": container.name,
            }

        # Copy public key to connecto to the container
        print(f"Container {container.name} got IP {srv_ip}")
        print(f"Runing provision:")
        pub_key = str(Path.home()) + "/.ssh/id_rsa.pub"
        print(f"\tCopying pub key: {pub_key}")
        copy_file(
            pub_key, "/root/.ssh/authorized_keys", container,
        )
        # for command in provision_cmds:
        #    execute_c(container, command, environment)

    # Create a yaml inventory for ansible
    inventory = {
        "all": {
            "vars": {
                "join_retry": join_retry,
                "cluster_name": cluster_name,
                "ansible_ssh_common_args": "-o StrictHostKeyChecking=no",
            },
        },
        "vault": {"hosts": confs_vault},
        "consul": {"hosts": confs_consul},
    }
    print(yaml.dump(inventory))
    with open(f"ansible/inventory_{cluster_name}.yaml", "w") as file:
        yaml.dump(inventory, file)

    # Run the ansible playbooks
    args = [
        "ansible-playbook",
        "-i",
        f"ansible/inventory_{cluster_name}.yaml",
        "-u",
        "root",
        "--flush-cache",
        # "-v",
        # "-l vault",
        "ansible/vault/playbook.yml",
    ]
    print(f"Calling ansible-playbook with: {' '.join(args)}")
    run(
        args=args, env={"ANSIBLE_HOST_KEY_CHECKING": "False"},
    )


####


def create_c(name, iface):

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
        "config": {"security.privileged": "True",},
        "devices": {"eth0": {"name": "eth0", "network": iface, "type": "nic"},},
    }
    pprint.pprint(config)
    print("creating container", name)
    return client.containers.create(config, wait=True)


def create_base(cluster_name, iface):
    # create base container
    if not client.containers.exists("base-" + cluster_name):
        container = create_c("base-" + cluster_name, iface)
        # container.config = {"security.privileged": "True"}
        container.start(wait=True)
        container.save(wait=True)
        while container.state().network["eth0"]["addresses"][0]["family"] != "inet":
            print(".. waiting for container", container.name, "to get ipv4 ..")
            time.sleep(3)
        environment = {"DEBIAN_FRONTEND": "noninteractive"}
        for command in base_cmd:
            execute_c(container, command, environment)
        # container.stop()


def copy_file(src, dst, container):
    try:
        filedata = open(src).read()
        container.files.put(dst, filedata)
    except Exception as e:
        print(f"Error: {e}")
        exit(0)


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
    return l


def stop_c(name):
    l = client.containers.get(name)
    if any([l.status == "Running", l.status == "Frozen"]):
        l.stop(wait=True)
        print("status ", l.status)


def execute_c(container, command, environment):
    print("\tcommand: {}".format(command))
    result = container.execute(command, environment)
    print("\texit_code: {}".format(result.exit_code))
    print("\tstdout: {}".format(result.stdout))
    if result.stderr:
        print("\tstderr: {}".format(result.stderr))


if __name__ == "__main__":
    main()
