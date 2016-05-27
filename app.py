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
WASH_TIME = 30 * 60 * 1000
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
    user = User.query.filter_by(username=username).one_or_none()
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
    door = db.relationship('Door', backref='order', uselist=False)


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
    user = User.query.filter_by(id=token2user_id(token)).one()
    d = {i: get_avail_machine(i) for i in range(MACHINE_COUNT)}
    avail_machine, avail_time = min(d.items(), key=lambda x: x[1])
    order = Order(user=user, order_time=get_current_timestamp(), status=3)
    db.session.add(order)
    db.session.commit()
    order_id = order.id
    door = request.json.get('door')
    if door:
        door = Door(start=avail_time, end=avail_time + WASH_TIME, order_time=order.order_time, phone=door.get('phone'),
                    address=door.get('address'), order=order)
        db.session.add(door)
        db.session.commit()
        pass
    while True:
        order_without_start_before = Order.query.filter(Order.id < order_id).filter(Order.start.is_(None)).first()
        if order_without_start_before is None:
            break
    order.machine = avail_machine
    order.start = avail_time
    order.end = avail_time + WASH_TIME
    order.order_token = uuid.uuid4().hex
    order_token_redis.setex(order.order_token, int((order.end - get_current_timestamp()) / 1000) + 1 * 60, order.id)
    return jsonify(order2json(order))


@app.route('/orders', methods=['GET'])
@need_token
def get_orders(token):
    user = User.query.filter_by(id=token2user_id(token)).one()
    refresh_status(user)
    orders = Order.query.filter_by(user=user).order_by(Order.order_time.desc()).all()
    result_orders = []
    for order in orders:
        result_orders.append(order2json(order))
    return jsonify({'orders': result_orders})


def refresh_status(user):
    orders = Order.query.filter_by(user=user, status=3).all()
    current_time = get_current_timestamp()
    for order in orders:
        if order.end < current_time:
            order.status = 1
    db.session.commit()


@app.route('/order/<int:order_id>', methods=['GET', 'DELETE', 'PUT'])
@need_token
def order(token, order_id):
    user = User.query.filter_by(id=token2user_id(token)).one()
    order = Order.query.filter_by(id=order_id).one()
    if order.user != user:
        return make_response(error_json_str('order not belong to you'), 403)
    else:
        if request.method == 'GET':
            return jsonify(order2json(order))
        elif request.method == 'DELETE':
            if order.status == 3:
                order.status = 1
                db.session.commit()
                return jsonify({'success': 1})
            else:
                return make_response(error_json_str('order can not be canceled now'), 400)
        elif request.method == 'PUT':
            order_json = request.json
            if order_json is None:
                return make_response(error_json_str('empty body'), 400)
            else:
                new_door = order_json.get('door')
                door = order.door
                if not door:
                    current_time = get_current_timestamp()
                    door = Door(start=current_time, end=current_time + WASH_TIME, order_time=current_time)
                    door.order = order
                if new_door:
                    new_address = new_door.get('address')
                    if new_address:
                        door.address = new_address
                        db.session.commit()
                    new_phone = new_door.get('phone')
                    if new_phone:
                        door.phone = new_phone
                        db.session.commit()
                    return jsonify(order2json(order))
                else:
                    return make_response(error_json_str('nothing modified'), 400)
        else:
            pass


def order2json(order):
    order_json = {
        'order_id': order.id,
        'start': order.start,
        'end': order.end,
        'machine': order.machine,
        'order_time': order.order_time,
        'order_token': order.order_token,
        'status': order.status
    }
    door = order.door
    if door:
        door_json = {
            'start': door.start,
            'end': door.end,
            'order_time': door.order_time,
            'phone': door.phone,
            'address': door.address
        }
        order_json['door'] = door_json
    return order_json


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
