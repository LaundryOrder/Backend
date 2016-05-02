# -*- encoding: utf-8 -*-
# Author: Epix

import unittest
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
        self.assertIsInstance(r.json().get('token', None), str)

        # login wrong password
        r = requests.post(token_url, json={'username': self.username, 'password': 'test_wrong' + str(random())})
        self.assertEqual(r.status_code, 400)

        # login correct data
        r = requests.post(token_url, json={'username': self.username, 'password': self.password})
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json().get('token', None), str)
