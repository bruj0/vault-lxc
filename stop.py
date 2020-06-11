#!/usr/bin/env python3
import sys
from pylxd import Client

client = Client()  # we focus on local LXD socket

vault_list = [
    "unsealer",
    "vault01",
    "vault02",
    "vault03",
    "pki",
]
consul_list = ["consul01", "consul02", "consul03"]

all_list = vault_list + consul_list


def main():
    cluster_name = sys.argv[1]
    for c in all_list:
        # delete the containers
        name = cluster_name + "-" + c
        container = client.containers.get(name)
        print("name ", container.name)
        if container.status == "Running":
            container.stop(wait=True)
            print("status ", container.status)


if __name__ == "__main__":
    main()
