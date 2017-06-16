from google.cloud import datastore
from flask import current_app

class Model(object):
    def get_client(self):
        return datastore.Client('coms4156-168718')

    def get(self, key):
        return self.model[key]

    def get_id(self):
        return self.get_key().id

    def get_key(self):
        try:
            return self.model.key
        except AttributeError:
            raise 'Tried to get key of unsaved ' + str(self.__class__)

    def destroy(self):
        if not self.fetched:
            return

        self.datastore.delete(self.get_key())

    def update(self, **kwargs):
        self.model.update(kwargs)
        self.datastore.put(self.model)

    def create_entity(self, **kwargs):
        key = self.datastore.key(kwargs['kind'])
        entity = datastore.Entity(key=key)
        kwargs.pop('kind')
        entity.update(kwargs)
        self.datastore.put(entity)
        return entity.key
