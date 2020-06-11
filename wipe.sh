#!/bin/bash
infra/p stop_vault
infra/p stop_consul

infra/s stop_vault
infra/s stop_consul

infra/dr stop_vault
infra/dr stop_consul

ops/p wipe
ops/s wipe
ops/dr wipe

infra/s wipe_raft
infra/p wipe_raft
infra/dr wipe_raft

infra/s wipe_consul
infra/p wipe_consul
infra/dr wipe_consul
