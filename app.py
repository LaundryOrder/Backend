# -*- encoding: utf-8 -*-
# Author: Epix
import os
import uuid
from functools import wraps

import time
from flask import Flask, request, jsonify, Response, abort, make_response
from flask.ext.sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context as pwd_context
from redis import StrictRedis
from sqlalchemy import desc

app = Flask(__name__)
app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

db = SQLAlchemy(app)

LOGIN_TOKEN_EXPIRE_TIME = 24 * 60 * 60 * 1000
MACHINE_COUNT = 3
WASH_TIME = 2 * 60 * 1000
REDIS_ADDRESS = 'localhost'


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(128))
    orders = db.relationship('Order', backref='user', uselist=True)

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_auth_token(self):
        pass


def error_json_str(msg):
    return jsonify({'success': 0, 'msg': msg})


def check_login(f):
    @wraps(f)
    def w(*args, **kwargs):
        if request.json is None:
            return make_response(error_json_str('empty body'), 400)
        username = request.json.get('username')
        password = request.json.get('password')
        if username is None or password is None:
            return make_response(error_json_str('lack of username or password'), 400)
        return f(*args, **kwargs)

    return w


def need_token(f):
    @wraps(f)
    def w(*args, **kwargs):
        http_auth = request.headers.get('Authorization', None)
        if http_auth:
            auth_type, auth_token = http_auth.split(None, 1)
            if auth_type == "Token":
                if user_token_redis.exists(auth_token):
                    return f(auth_token, *args, **kwargs)
                else:  # non exist token
                    return make_response(error_json_str('token not exist'), 401)
            else:  # not start with Token
                return make_response(error_json_str('wrong auth token method'), 401)
        else:  # no auth
            return make_response(error_json_str('need auth token'), 401)

    return w


def check_json(f):
    @wraps(f)
    def w(*args, **kwargs):
        if request.json is None:
            return make_response(error_json_str('empty body'), 400)
        else:
            return f(*args, **kwargs)

    return w


@app.route('/')
def index():
    return "233"


@app.route('/token', methods=['POST'])
@check_login
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    user = User.query.filter_by(username=username).one()
    if user:  # user exist, login
        if not user.verify_password(password):
            return make_response(error_json_str('wrong password'), 400)
    else:  # user not exist, register
        user = User(username=username)
        user.hash_password(password)
        db.session.add(user)
        db.session.commit()
    user_token = uuid.uuid4().hex
    user_id = user.id
    user_token_redis.setex(user_token, LOGIN_TOKEN_EXPIRE_TIME, user_id)
    return jsonify({'token': user_token})


@app.route('/revoke', methods=['GET'])
@need_token
def logout(token):
    user_token_redis.delete(token)
    return jsonify({'success': 1})


def get_avail_machine(i):
    order = Order.query.filter_by(machine=i).order_by(desc(Order.end)).first()
    if order:
        return max(order.end, get_current_timestamp())
    else:
        return get_current_timestamp()


@app.route('/avail')
@need_token
def available(token):
    d = {i: get_avail_machine(i) for i in range(MACHINE_COUNT)}
    avail_time = min(d.values())
    return jsonify({'time': avail_time})


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    start = db.Column(db.Integer)
    end = db.Column(db.Integer)
    machine = db.Column(db.Integer)
    order_time = db.Column(db.Integer)
    order_token = db.Column(db.String(128), index=True)
    status = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    door = db.relationship('Door', backref='order', uselist=True)


class Door(db.Model):
    __tablename__ = 'doors'
    id = db.Column(db.Integer, primary_key=True)
    start = db.Column(db.Integer)
    end = db.Column(db.Integer)
    order_time = db.Column(db.Integer)
    phone = db.Column(db.String(32))
    address = db.Column(db.String(128))
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))


@app.route('/order', methods=['POST'])
@need_token
@check_json
def make_order(token):
    door = request.json.get('door')
    if door:
        # todo add door service
        pass

    user = User.query.filter_by(id=token2user_id(token)).one()
    order = Order(user=user, order_time=get_current_timestamp(), status=3)
    db.session.add(order)
    db.session.commit()
    order_id = order.id
    while True:
        order_without_start_before = Order.query.filter(Order.id < order_id).filter(Order.start.is_(None)).first()
        if order_without_start_before is None:
            break
    d = {i: get_avail_machine(i) for i in range(MACHINE_COUNT)}
    avail_machine, avail_time = min(d.items(), key=lambda x: x[1])
    order.machine = avail_machine
    order.start = avail_time
    order.end = avail_time + WASH_TIME
    order.order_token = uuid.uuid4().hex
    order_token_redis.setex(order.order_token, int((order.end - get_current_timestamp()) / 1000) + 1 * 60, order.id)
    return jsonify({'success': 1})


def token2user_id(token):
    return int(user_token_redis.get(token))


def token2order_id(token):
    return int(order_token_redis.get(token))


def get_current_timestamp():
    return int(time.time() * 1000)


if __name__ == '__main__':
    if not os.path.exists('db.sqlite'):
        db.create_all()
    user_token_redis = StrictRedis(host=REDIS_ADDRESS, port=6379, db=0)
    order_token_redis = StrictRedis(host=REDIS_ADDRESS, port=6379, db=1)
    app.run(host="0.0.0.0", port=8233, debug=True)
