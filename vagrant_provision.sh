#!/bin/bash
apt-get update
apt-get -y install build-essential
apt-get -y install python3-dev 
apt-get -y install python3-pip
apt-get -y install python3-scipy
apt-get -y install git
apt-get -y install libpcre3 libpcre3-dev
apt-get -y install libmysqlclient-dev
pip3 install -r /vagrant/requirements.txt
#add development server to localhosts
echo "0.0.0.0 dev.wakeupapp.com wakeupapp.com" >> /etc/hosts

#prepare file user storage - we'll remove it when mongo is implemented
mkdir /home/vagrant/user_storage/
#install mysql
apt-get -y install mysql-server # vagrant root password is oiqwj0a-a
#set binding ip address https://help.ubuntu.com/12.04/serverguide/mysql.html: /etc/mysql/my.cnf to 0:0:0:0, port 3306
#mysql -u root -p then CREATE USER 'dev'@'%';CREATE DATABASE music_graph;GRANT ALL ON music_graph.* TO 'dev'@'%';



#configure python dev web server port forwarding from loopback to eth0
#sysctl -w net.ipv4.conf.eth0.route_localnet=1
#iptables -t nat -I PREROUTING -p tcp -i eth0 --dport 5000 -j DNAT --to-destination 127.0.0.1:5000

#apt-get -y install libblas-dev checkinstall
#apt-get -y install libblas-doc checkinstall
#apt-get -y install liblapacke-dev checkinstall
#apt-get -y install liblapack-doc checkinstall

