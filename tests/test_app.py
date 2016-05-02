# -*- encoding: utf-8 -*-
# Author: Epix

import unittest
import uuid
from random import random

import requests

base_url = 'http://192.168.1.233:8233'


class TestApp(unittest.TestCase):
    username = 'test' + str(random())
    password = 'test' + str(random())

    def test_register(self):
        # empty data
        token_url = base_url + '/token'
        r = requests.post(token_url)
        self.assertEqual(r.status_code, 400)

        # corrupt data
        r = requests.post(token_url, json={'test': 'test'})
        self.assertEqual(r.status_code, 400)

        # register correct data
        r = requests.post(token_url, json={'username': self.username, 'password': self.password})
        self.assertEqual(r.status_code, 200)
        token_str = r.json().get('token', None)
        self.assertIsInstance(token_str, str)

        # logout with token
        logout_url = base_url + '/revoke'
        r = requests.get(logout_url, headers={'Authorization': 'Token {0}'.format(token_str)})
        self.assertEqual(r.status_code, 200)

        # login wrong password
        r = requests.post(token_url, json={'username': self.username, 'password': 'test_wrong' + str(random())})
        self.assertEqual(r.status_code, 400)

        # login correct data
        r = requests.post(token_url, json={'username': self.username, 'password': self.password})
        self.assertEqual(r.status_code, 200)
        token_str = r.json().get('token', None)
        self.assertIsInstance(token_str, str)

        # logout with no header
        r = requests.get(logout_url)
        self.assertEqual(r.status_code, 401)

        # logout with wrong auth method
        r = requests.get(logout_url, headers={'Authorization': 'Bearer {0}'.format(token_str)})
        self.assertEqual(r.status_code, 401)

        # logout with wrong token
        r = requests.get(logout_url, headers={'Authorization': 'Token {0}'.format(uuid.uuid4().hex)})
        self.assertEqual(r.status_code, 401)

        # logout with correct token
        r = requests.get(logout_url, headers={'Authorization': 'Token {0}'.format(token_str)})
        self.assertEquals(r.status_code, 200)

        # logout with revoked token
        r = requests.get(logout_url, headers={'Authorization': 'Token {0}'.format(token_str)})
        self.assertEqual(r.status_code, 401)
