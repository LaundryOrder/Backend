# -*- encoding: utf-8 -*-
# Author: Epix
import os
from functools import wraps

from flask import Flask, request, jsonify, Response, abort
from flask.ext.sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context as pwd_context

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
            return Response(error_json_str('empty body'), 400)
        username = request.json.get('username')
        password = request.json.get('password')
        if username is None or password is None:
            return Response(error_json_str('lack of username or password'), 400)
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
    user = User.query.filter_by(username=username).first()
    if user:  # user exist, login
        if not user.verify_password(password):
            return Response(error_json_str('wrong password'), 400)
    else:  # user not exist, register
        user = User(username=username)
        user.hash_password(password)
        db.session.add(user)
        db.session.commit()
    return jsonify({'token': 'bgm38'})


@app.route('/logout', methods=['GET'])
def logout():
    return jsonify({'success': 1})


if __name__ == '__main__':
    if not os.path.exists('db.sqlite'):
        db.create_all()
    app.run(host="0.0.0.0", port=8233, debug=True)
