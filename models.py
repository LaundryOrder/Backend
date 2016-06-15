# -*- encoding: utf-8 -*-
# Author: Epix
from flask_sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(128))
    orders = db.relationship('Order', backref='user', uselist=True)

    def hash_password(self, password):
        self.password_hash = custom_app_context.encrypt(password)

    def verify_password(self, password):
        return custom_app_context.verify(password, self.password_hash)

    def generate_auth_token(self):
        pass


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
