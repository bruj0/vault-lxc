lxc network set lxdbr0 ipv6.address none
lxc network set lxdbr1 ipv6.address none
lxc network set lxdbr2 ipv6.address none 

systemd-resolve --interface lxdbr0 --set-dns 10.140.31.1 --set-domain lxd
systemd-resolve --interface lxdbr1 --set-dns 10.0.148.1 --set-domain lxd
systemd-resolve --interface lxdbr2 --set-dns 10.101.170.1 --set-domain lxd

echo -e "auth-zone=lxd\ndns-loop-detect\nserver=192.168.50.1\nno-resolv" | lxc network set lxdbr0 raw.dnsmasq -
echo -e "auth-zone=lxd\ndns-loop-detect\nserver=192.168.50.1\nno-resolv" | lxc network set lxdbr1 raw.dnsmasq -
echo -e "auth-zone=lxd\ndns-loop-detect\nserver=192.168.50.1\nno-resolv" | lxc network set lxdbr2 raw.dnsmasq - 

sudo iptables -A FORWARD -i lxdbr1 -o lxdbr0 -j DROP
sudo iptables -A FORWARD -i lxdbr2 -o lxdbr0 -j DROP
sudo iptables -A FORWARD -i lxdbr0 -o lxdbr1 -j DROP
sudo iptables -A FORWARD -i lxdbr0 -o lxdbr2 -j DROP
