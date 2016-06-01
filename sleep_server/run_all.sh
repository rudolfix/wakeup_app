#!/bin/bash

#start rabbit mq server
rabbitmq-server -detached
if [ $? -ne 0 ]; then
        echo "rabbit MQ cannot be started ABANDON"
        #exit -1
fi
# wait for database to be ready
dbu="prod"
dbp="prod"
host="mysql"
db="music_graph"
user_storage="/var/local/sleep_server/user_storage/"

status=1
echo 'checking mysql server availability'
until [ $status -eq 0 ]; do
        mysql -u $dbu --password=$dbp -h $host $db --execute='SHOW TABLES IN music_graph'
        status=$?
        echo "mysql test returned $status"
        sleep 1s
done

echo "checking $db schema"
schema=$(mysql -u $dbu --password=$dbp -h $host $db --execute='SHOW TABLES IN music_graph')
if [ ${#schema} -lt 5 ]; then
        echo 'restoring database dump'
        gunzip -c /var/local/sleep_server/data/music_graph_db.sql.gz | mysql -u $dbu --password=$dbp -h $host $db
        if [ $? -ne 0 ]; then
                echo "restore database fail ABANDON"
                exit -1
        fi
fi
echo "initializing cache"
files=$(ls $user_storage)
if [ ${#files} -eq 0 ]; then
        cp /var/local/sleep_server/data/user_storage/* $user_storage
        if [ $? -ne 0 ]; then
                echo "copy cache failed"
                exit -1
        fi
fi
echo "starting api"
/usr/local/sleep_server/run_uwsgi_server_prod.sh&
/usr/local/sleep_server/run_uwsgi_prod.sh