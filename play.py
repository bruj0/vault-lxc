#!/usr/bin/env python3
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
confs = {}
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
    # exit(0)
    # create the containers
    port = -1
    for c in all_list:
        port += 1
        c_name = cluster_name + "-" + c
        devices = {}
        if not client.containers.exists(c_name):
            container = copy_c("base", c_name)
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
                        "listen": "tcp:0.0.0.0:930" + str(port),
                        "type": "proxy",
                    }
                }

            if c_name.split("-")[1] in consul_list:
                devices = {
                    "api_port": {
                        "connect": f"tcp:{srv_ip}:8500",
                        "listen": "tcp:0.0.0.0:950" + str(port),
                        "type": "proxy",
                    }
                }
            print(f"Using devices:{devices}")
            container.devices = devices
            container.save(wait=True)
        else:
            # Container already exists
            container = start_c(c_name)
            srv_ip = container.state().network["eth0"]["addresses"][0]["address"]
        # environment = {"IFACE": "eth0", }

        # put cluster_ip and hostname in a dictionary for each container
        confs[container.name] = {
            "cluster_ip": srv_ip,
            "hostname": container.name,
        }
        # create join_retry variable
        if container.name.split("-")[1] in consul_list:
            join_retry.append(srv_ip)

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
        "all": {"vars": {"join_retry": join_retry, "cluster_name": cluster_name},},
        "vault": {"hosts": confs},
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
        "-v",
        "-v",
        "-l vault",
        "ansible/vault/playbook.yml",
    ]
    print(f"Calling ansible-playbook with: {' '.join(args)}")
    run(
        args=args, env={"ANSIBLE_HOST_KEY_CHECKING": "False"},
    )


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
        "config": {"security.privileged": "True",},
    }
    pprint.pprint(config)
    print("creating container", name)
    return client.containers.create(config, wait=True)


def create_base():
    # create base container
    if not client.containers.exists("base"):
        container = create_c("base")
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