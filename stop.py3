#!/usr/bin/env python3

from pylxd import Client
client = Client() # we focus on local LXD socket

#stop the containers
containers = client.containers.all()
for container in containers:
    print("name ", container.name)
    if any([container.status == 'Running', container.status == 'Frozen']):
        container.stop(wait=True)
        print("status ", container.status)
