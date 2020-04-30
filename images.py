#!/usr/bin/env python3

from pylxd import Client
client = Client() # we focus on local LXD socket

#info about images
images = client.images.all()
for image in images:
    print("fingerprint ", image.fingerprint)
    if "description" in image.properties:
        print("description ", image.properties["description"])
    if "os" in image.properties:
        print("os ", image.properties["os"])
    if "release" in image.properties:
        print("release ", image.properties["release"])

