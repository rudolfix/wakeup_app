#!/bin/bash
uwsgi --http-socket :5001 --enable-threads --wsgi-file /vagrant/sleep_server/server/run.py --callable app --py-autoreload=1 --pythonpath /vagrant/sleep_server/server