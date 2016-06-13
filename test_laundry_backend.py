# -*- encoding: utf-8 -*-
# Author: Epix
import os
import unittest
import laundry_backend
from models import db


class FlaskTestCase(unittest.TestCase):
    def setUp(self):
        laundry_backend.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.sqlite'
        laundry_backend.app.config['TESTING'] = True
        db.init_app(laundry_backend.app)
        with laundry_backend.app.app_context():
            if not os.path.exists('test.sqlite'):
                db.create_all()
            db.drop_all()
        self.app = laundry_backend.app.test_client()

    def tearDown(self):
        pass

    def test_login(self):
        rv = self.app.get('/revoke')
        pass


if __name__ == '__main__':
    unittest.main()
