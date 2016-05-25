import sys
import traceback
import time
from threading import Thread, Lock
from flask import json
import pika
from functools import wraps

from common.user_base import UserBase
from server import app, fpika, song_helper, user_library, music_graph_helper
from server.exceptions import MqMalformedMessageException

_ch_user_lib_updater = 'user_lib_updater'
_ch_user_lib_resolver = 'user_lib_resolver'
_mq_lock = Lock()
_mq_channels = {_ch_user_lib_updater: None, _ch_user_lib_resolver: None}


def mq_callback(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        ch = args[0]
        method = args[1]
        try:
            r = f(*args, **kwargs)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return r
        except MqMalformedMessageException as mf:
            app.logger.error('queue message malformed, MESSAGE DISCARDED (%s)' % str(mf))
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:
            app.logger.error(exc)
            # traceback.print_exc(file=sys.stdout)
            ch.basic_nack(delivery_tag=method.delivery_tag)

    return _wrap


def _parse_user_library_mq_msg(body):
    try:
        body = json.loads(body)
        # must have proper version
        user = UserBase.from_jsons(body['user'])
        user_id = body['user_id']
        return user_id, user
    except Exception as e:
        raise MqMalformedMessageException(str(e))


@mq_callback
def _user_lib_resolver_callback(ch, method, properties, body):
    app.logger.debug('RESOLVER CONSUMER received')
    start_time = time.time()
    user_id, user = _parse_user_library_mq_msg(body)
    library = user_library.load_library(user_id)
    if library.unresolved_tracks:
        _, _, _, new_artists = user_library.resolve_user_library(library, music_graph_helper.G.genres_names)
        user_library.save_library(library)
        song_helper.infer_and_store_genres_for_artists(user, new_artists, music_graph_helper.G.genres_names)
    app.logger.info('RESOLVER CONSUMER done elapsed %f' % (time.time() - start_time))


@mq_callback
def _user_lib_updater_callback(ch, method, properties, body):
    app.logger.debug('UPDATER CONSUMER received')
    start_time = time.time()
    user_id, user = _parse_user_library_mq_msg(body)
    library = user_library.load_library(user_id)
    # quickly mark as processing
    library.unresolved_tracks = []
    user_library.save_library(library)
    user_library.build_user_library(user, library)
    user_library.save_library(library)
    _send_mq_message(_ch_user_lib_resolver, body)  # forward the same body to resolve queue
    app.logger.info('UPDATER CONSUMER done elapsed %f' % (time.time() - start_time))


def _run_mq_consumer(name, callback, thread):
    while True:
        channel = None
        with _mq_lock:
            _mq_channels[name] = (thread, None)
        try:
            app.logger.info('queue %s starting' % name)
            channel = fpika.channel()
            channel.queue_declare(queue=name, durable=True)
            channel.basic_qos(prefetch_count=1)
            tag = channel.basic_consume(callback, queue=name)
            with _mq_lock:
                _mq_channels[name] = (thread, channel)
        except Exception as exc:
            app.logger.error('cannot start queue %s [%s], will try again' % (name, repr(exc)))
            if channel:
                fpika.return_broken_channel(channel)
            time.sleep(5)
            continue
        try:
            app.logger.info('queue %s is consuming' % name)
            channel.start_consuming()
            fpika.return_channel(channel)
            app.logger.info('queue %s shutdown' % name)
            return
        except Exception as exc:
            with _mq_lock:
                _mq_channels[name] = (thread, None)
            app.logger.error('error when consuming queue %s [%s], will try again' % (name, repr(exc)))
            time.sleep(5)


def _send_mq_message(name, body):
    channel = fpika.channel()
    try:
        # todo: handle rabbit mq errors that destroy connections (fpika.return_broken_channel)
        channel.queue_declare(queue=name, durable=True)
        channel.basic_publish(exchange='',
                              routing_key=name,
                              body=body,
                              properties=pika.BasicProperties(
                                  delivery_mode=2,  # make message persistent
                              ))
    finally:
        fpika.return_channel(channel)


def send_update_message(body):
    _send_mq_message(_ch_user_lib_updater, body)


def start():
    thread = Thread(target=_run_mq_consumer)
    thread.daemon = True
    thread._args = (_ch_user_lib_resolver, _user_lib_resolver_callback, thread)
    thread.start()
    thread = Thread(target=_run_mq_consumer)
    thread.daemon = True
    thread._args = (_ch_user_lib_updater, _user_lib_updater_callback, thread)
    thread.start()


def stop():
    with _mq_lock:
        for name, value in _mq_channels.items():
            if value:
                thread, channel = value
                if channel:
                    channel.start_consuming()
                thread.join(10)  # wait 10 seconds then give up
