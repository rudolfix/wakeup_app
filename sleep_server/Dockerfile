FROM sleep_python

LABEL description='image with sleep server /api and /server endpoints'

ENV WAKEUPP_APP_CONFIG_FILE config.production.py
RUN mkdir /var/log/sleep_server/
RUN chmod 757 /var/log/sleep_server/
RUN mkdir /var/local/sleep_server/
RUN mkdir /var/local/sleep_server/data/
RUN mkdir /var/local/sleep_server/user_storage/
ADD . /usr/local/sleep_server/
RUN chmod +x /usr/local/sleep_server/*.sh