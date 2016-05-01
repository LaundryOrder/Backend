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
        register_url = base_url + '/user/new'
        r = requests.post(register_url)
        self.assertEqual(r.status_code, 400)

        # corrupt data
        r = requests.post(register_url, json={'test': 'test'})
        self.assertEqual(r.status_code, 400)

        # correct data
        r = requests.post(register_url, json={'username': self.username, 'password': self.password})
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json().get('token', None), str)

        # existed user
        r = requests.post(register_url, json={'username': self.username, 'password': self.password})
        self.assertEqual(r.status_code, 400)

        # login start
        login_url = base_url + '/login'

        # empty data
        r = requests.post(login_url)
        self.assertEqual(r.status_code, 400)

        # corrupt data
        r = requests.post(login_url, json={'test': 'test'})
        self.assertEqual(r.status_code, 400)

        # non existed user
        r = requests.post(login_url, json={'username': 'test_wrong' + str(random()), 'password': self.password})
        self.assertEqual(r.status_code, 400)

        # wrong password
        r = requests.post(login_url, json={'username': self.username, 'password': 'test_wrong' + str(random())})
        self.assertEqual(r.status_code, 400)

        # correct data
        r = requests.post(login_url, json={'username': self.username, 'password': self.password})
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json().get('token', None), str)
