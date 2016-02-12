#!/bin/bash
apt-get update
apt-get -y install build-essential
apt-get -y install python3-dev 
apt-get -y install python3-pip
apt-get -y install python3-scipy
pip3 install -r /vagrant/requirements.txt
#add development server to localhosts
echo "0.0.0.0 dev.wakeupapp.com wakeupapp.com" >> /etc/hosts
#configure python dev web server port forwarding from loopback to eth0
#sysctl -w net.ipv4.conf.eth0.route_localnet=1
#iptables -t nat -I PREROUTING -p tcp -i eth0 --dport 5000 -j DNAT --to-destination 127.0.0.1:5000

#apt-get -y install libblas-dev checkinstall
#apt-get -y install libblas-doc checkinstall
#apt-get -y install liblapacke-dev checkinstall
#apt-get -y install liblapack-doc checkinstall

