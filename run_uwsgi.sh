#!/bin/bash
uwsgi --http :5001 --wsgi-file /vagrant/sleep_server/run.py --callable app --py-autoreload=1 --pythonpath /vagrant/sleep_server/