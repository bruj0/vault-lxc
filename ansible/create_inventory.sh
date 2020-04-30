#!/bin/bash -x -e
echo "[vault]" > inventory
cat ../vault_cluster.json | jq -r .[].ip_addr >> inventory
echo "[consul" >> inventory
cat ../consul_cluster.json | jq -r .[].ip_addr >> inventory

