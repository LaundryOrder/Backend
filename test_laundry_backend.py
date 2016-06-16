# -*- encoding: utf-8 -*-
# Author: Epix
import json
import os
import unittest

from flask import jsonify

import laundry_backend
from models import db


class FlaskTestCase(unittest.TestCase):
    def setUp(self):
        laundry_backend.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.sqlite'
        laundry_backend.app.config['TESTING'] = True
        db.init_app(laundry_backend.app)
        with laundry_backend.app.app_context():
            if os.path.exists('test.sqlite'):
                db.drop_all()
            db.create_all()
        self.app = laundry_backend.app.test_client()

    def tearDown(self):
        pass

    def login(self, username, password):
        rv = self.app.post('/token', data=json.dumps({'username': username, 'password': password}),
                           headers={'content-type': 'application/json'})
        return rv

    def test_login(self):
        rv = self.login('a', '1')
        self.assertEqual(rv.status_code, 200)


if __name__ == '__main__':
    unittest.main()
