#!/bin/bash -x
. ./setup.vars
#mkdir /sys/fs/cgroup/systemd
#cgroup on /sys/fs/cgroup/systemd type cgroup (rw,nosuid,nodev,noexec,relatime,xattr,name=systemd)
#mount -n -t cgroup -o none,name=systemd systemd /sys/fs/cgroup/systemd
lxc network set lxdbr0 ipv6.address none
lxc network set lxdbr1 ipv6.address none
lxc network set lxdbr2 ipv6.address none 

sudo systemd-resolve --interface lxdbr0 --set-dns $LXDBR0_IP --set-domain lxd
sudo systemd-resolve --interface lxdbr1 --set-dns $LXDBR1_IP --set-domain lxd
sudo systemd-resolve --interface lxdbr2 --set-dns $LXDBR2_IP --set-domain lxd

echo -e "auth-server=lxdbr0\nauth-zone=lxd\ndns-loop-detect\nserver=192.168.50.1\nno-resolv" | lxc network set lxdbr0 raw.dnsmasq -
echo -e "auth-server=lxdbr1\nauth-zone=lxd\ndns-loop-detect\nserver=192.168.50.1\nno-resolv" | lxc network set lxdbr1 raw.dnsmasq -
echo -e "auth-server=lxdbr2\nauth-zone=lxd\ndns-loop-detect\nserver=192.168.50.1\nno-resolv" | lxc network set lxdbr2 raw.dnsmasq - 

#iptables -A FORWARD -i lxdbr1 -o lxdbr0 -j DROP
#iptables -A FORWARD -i lxdbr2 -o lxdbr0 -j DROP
#iptables -A FORWARD -i lxdbr0 -o lxdbr1 -j DROP
#iptables -A FORWARD -i lxdbr0 -o lxdbr2 -j DROP
