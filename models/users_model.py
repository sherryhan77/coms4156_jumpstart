from model import Model
from google.cloud import datastore

class User(Model):
    def __init__(self, **kwargs):
        self.datastore = self.get_client()

        self.fetched = False

        # try to fetch by id
        if 'id' in kwargs:
            key = self.datastore.key('user', kwargs['id'])
            self.model = self.datastore.get(key)
            self.fetched = bool(self.model)

        # try to fetch by uni
        if not self.fetched and 'uni' in kwargs:
            model_query = self.datastore.query(kind='user')
            model_query.add_filter('uni', '=', kwargs['uni'])
            users = list(model_query.fetch())
            if len(users) > 0:
                self.model = users[0]
                self.fetched = True

        # try to fetch by email
        if not self.fetched and 'email' in kwargs:
            model_query = self.datastore.query(kind='user')
            model_query.add_filter('email', '=', kwargs['email'])
            users = list(model_query.fetch())
            if len(users) == 0:
                self.fetched = False
                self.model = kwargs
            else:
                self.fetched = True
                self.model = users[0]

        # no other unique fields
        if not self.fetched:
            self.fetched = False
            self.model = kwargs

    def is_teacher(self):
        return self.get('teacher')

    def is_student(self):
        return bool(self.get('uni'))

    def get_or_create(self):
        if not self.fetched:
            key = self.create_entity(
                kind='user',
                **self.model
            )
            self.model = self.datastore.get(key)
            self.fetched = True

        return self

class Users(Model):

    def __init__(self, data, **kwargs):
        self.ds = self.get_client()

    


    def get_or_create_user(self, user):
        query = self.ds.query(kind='user')
        query.add_filter('email', '=', user['email'])
        result = list(query.fetch())
        if result:
            print result
        else:
            try:
                key = self.ds.key('user')
                entity = datastore.Entity(
                    key=key)
                entity.update(user)
                self.ds.put(entity)
            except:  # TODO
                pass
        result = list(query.fetch())
        return result[0]['id']


    def is_valid_uni(self, uni):
        query = self.ds.query(kind='student')
        query.add_filter('uni', '=', uni)
        result = list(query.fetch())
        return True if len(result) == 1 else False
