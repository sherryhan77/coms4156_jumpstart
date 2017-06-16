from models import users_model
from model import Model
from datetime import datetime, date
from google.cloud import datastore

class DuplicateUNIException(Exception):
    pass

class Student(users_model.User):
    def register_as_student(self, **kwargs):
        if 'uni' not in kwargs or len(kwargs['uni']) == 0:
            raise ValueError('Students must have UNIs')

        uni = kwargs['uni']
        query = self.datastore.query(kind='user')
        query.add_filter('uni', '=', uni)
        conflicting_students = len(list(query.fetch()))
        if conflicting_students > 0:
            raise DuplicateUNIException('Student with UNI ' + uni + ' already exists.')

        self.update(uni=uni)

class Students(Model):

    def __init__(self, sid):
        self.sid = sid
        self.ds = self.get_client()

    def get_uni(self):
        query = self.ds.query(kind='student')
        query.add_filter('sid', '=', self.sid)
        result = list(query.fetch())
        return result[0]['uni']

    def get_courses(self):
        query = self.ds.query(kind='enrolled_in')
        query.add_filter('sid', '=', self.sid)
        enrolledCourses = list(query.fetch())
        result = list()
        for enrolledCourse in enrolledCourses:
            query = self.ds.query(kind='courses')
            query.add_filter('cid', '=', enrolledCourse['cid'])
            result = result + list(query.fetch())

        return result

    def get_secret_and_seid(self):
        query = self.ds.query(kind='enrolled_in')
        enrolled_in = list(query.fetch())
        results = list()
        for enrolled in enrolled_in:
            query = self.ds.query(kind='sessions')
            query.add_filter('cid', '=', enrolled['cid'])
            sessions = list(query.fetch())
            for session in sessions:
                if session['expires'].replace(tzinfo=None) > datetime.now():
                    results.append(session)
            # results = results + list(query.fetch())
        if len(results) == 1:
            secret = results[0]['secret']
            seid = results[0]['seid']
        else:
            secret, seid = None, -1
        return secret, seid

    def has_signed_in(self):
        _, seid = self.get_secret_and_seid()

        if seid == -1:
            return False
        else:
            query = self.ds.query(kind='sessions')
            query.add_filter('seid', '=', int(seid))
            sessions = list(query.fetch())
            results = list()
            for session in sessions:
                query = self.ds.query(kind='attendance_records')
                query.add_filter('seid', '=', int(session['seid']))
                query.add_filter('sid', '=', self.sid)
                results = results + list(query.fetch())
            return True if len(results) == 1 else False

    def insert_attendance_record(self, seid):
        key = self.ds.key('attendance_records')
        entity = datastore.Entity(
            key=key)
        entity.update({
            'sid': self.sid,
            'seid': int(seid)
        })
        self.ds.put(entity)

    def get_num_attendance_records(self, cid):
        query = self.ds.query(kind='sessions')
        query.add_filter('cid', '=', int(cid))
        sessions = list(query.fetch())
        results = list()
        for session in sessions:
            query = self.ds.query(kind='attendance_records')
            query.add_filter('seid', '=', session['seid'])
            query.add_filter('sid', '=', self.sid)
            results = results + list(query.fetch())
        return len(results)
