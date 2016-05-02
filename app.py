# -*- encoding: utf-8 -*-
# Author: Epix
import os
import uuid
from functools import wraps

from flask import Flask, request, jsonify, Response, abort, make_response
from flask.ext.sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context as pwd_context
from redis import StrictRedis

app = Flask(__name__)
app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(128))

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


@app.route('/')
def index():
    return "233"


@app.route('/token', methods=['POST'])
@check_login
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    user = User.query.filter_by(username=username).first()
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
    user_token_redis.setex(user_token, 120, user_id)
    return jsonify({'token': user_token})


@app.route('/revoke', methods=['GET'])
@need_token
def logout(token):
    user_token_redis.delete(token)
    return jsonify({'success': 1})


if __name__ == '__main__':
    if not os.path.exists('db.sqlite'):
        db.create_all()
    user_token_redis = StrictRedis(host='localhost', port=6379, db=0)
    app.run(host="0.0.0.0", port=8233, debug=True)
