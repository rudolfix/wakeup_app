#!/bin/bash
uwsgi --http :5000 --wsgi-file /vagrant/sleep_server/api/run.py --callable app --py-autoreload=1 --pythonpath /vagrant/sleep_server/api