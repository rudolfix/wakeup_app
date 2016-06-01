# Deployment information

Service is deployed using Docker. Dockerfiles and docker compose file are provided. Currently following services and resources are defined

1. api service containing external and internal apis done with Flask.
2. mysql server
3. volumes to persist database files and user profiles/cache
4. r/o volume with cache and music graph my sql database dump

##Build process
1. build intermediary python image (make subsequent deployments od flasks apps much quicker)
```javascript
docker build -f sleep_server\Dockerfile_Python -t sleep_python sleep_server
```
2. use docker-compose to build all images as defined in docker-compose.yml
```javascript
docker-compose --verbose build
```
3. we use standard mysql configuration (todo: use custom config to set sql-mode=TRADITIONAL,ANSI_QUOTES)
4. docker-compose up -d to run all services. there is initialization process on first run, see later.

##Local deployment
You may deploy on your local docker host to test the deployment. There is a callback defined in spotify app for that purpose
http://dev.docker.wakeupapp.com/admin/login_completed
host file:
127.0.0.1 dev.wakeupapp.com wakeupapp.com
192.168.99.100 dev.docker.wakeupapp.com

##Remote deployment

1. uses ssh connection to server
2. port 2376 must be opened
```javascript
(aws) docker-machine create --driver generic --generic-ip-address=wakeupapp.dev.army --generic-ssh-key=sleep_server.pem --generic-ssh-user=ubuntu awssleepo
(droplet)docker-machine create --driver generic --generic-ip-address=sleepapi.dev.army --generic-ssh-key=droplet_sleep.rsa --generic-ssh-user=root sleepdroplet
```javascript

Minimum machine specs: 1GB ram, 10 GB SSD with reasonable speed (AWS t2 crap does not work, credits immediately expire)

##Monitoring
api container produces logs in /var/log/sleep_server. get there by docker exec -i -t src_api_1 /bin/bash and 
tail -f /var/log/sleep_server/server.log
##Procedures
###rebuild cache and database dump
there is read only volume "data" containing initial cache and music graph database. 
### docker run script in api container (run_all.sh)
1. wait for database to go up
2. if database is empty, restore a dump from "data" volume
3. if cache is empty, restore from "data" volume
4. run server api
5. run frontend api

ACHTUNG: restoring db dump will take a lot of time (this is how mysql works)
If the initial script fails, (disk full etc) there is a huge chance that it will not recover when container restarts. Kill all volumes and restart container

### Recreating cache
### Updating db schema
### Periodically getting similar artists and infering genres 