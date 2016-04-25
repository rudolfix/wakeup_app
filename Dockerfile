#this will be a proper docker file later
#instance DNS 52.28.90.131 wakeupapp.dev.army
#ssh -i sleep_server.pem ubuntu@wakeupapp.dev.army
#install uwsgi
#set UWSGI_PROFILE_OVERRIDE=ssl=true;routing=true;pcre=true
#pip3 install uwsgi
#letsencrypt used for ssl cert https://letsencrypt.readthedocs.org/en/latest/using.html#installation

#create dirs
##mkdir /home/ubuntu/wakeupapp
##chmod 777 /home/ubuntu/wakeupapp
##mkdir /home/ubuntu/wakeupapp/user_storage
##chmod 777 /home/ubuntu/wakeupapp/user_storage
#copy files
##scp -i sleep_server.pem ../src/run_uwsgi_prod.sh ubuntu@wakeupapp.dev.army:/home/ubuntu/wakeupapp
##scp -r -i sleep_server.pem ../src/sleep_server/* ubuntu@wakeupapp.dev.army:/home/ubuntu/wakeupapp/sleep_server/
##scp -i sleep_server.pem ../src/requirements.txt ubuntu@wakeupapp.dev.army:/home/ubuntu/wakeupapp
#execute vagrant provision file
