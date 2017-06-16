from google.cloud import datastore
from flask import current_app

class Model(object):
    def get_client(self):
        return datastore.Client('coms4156-168718')
