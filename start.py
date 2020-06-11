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
    what = sys.argv[2]
    if what == "vault":
        c_list = vault_list
    elif what == "consul":
        c_list = consul_list
    else:
        c_list = all_list

    for c in c_list:
        # delete the containers
        name = cluster_name + "-" + c
        container = client.containers.get(name)
        print("name ", container.name)
        if any([container.status == "Stopped", container.status == "Frozen"]):
            container.start(wait=True)
            print("status ", container.status)
        if container.name.startswith("base"):
            pass


if __name__ == "__main__":
    main()
