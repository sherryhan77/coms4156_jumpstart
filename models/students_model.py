from models import courses_model, users_model
from model import Model
from datetime import datetime
from google.cloud import datastore


class DuplicateUNIException(Exception):
    pass


class Student(users_model.User):
    def register_as_student(self, uni=None):
        if uni is None or len(uni) == 0:
            raise ValueError('Students must have UNIs')

        query = self.datastore.query(kind='user')
        query.add_filter('uni', '=', uni)
        conflicting_students = list(query.fetch())
        if len(conflicting_students) > 0:
            raise DuplicateUNIException('Student with UNI ' + uni + ' already exists.')

        self.update(uni=uni)

        return self

    def sign_in(self, course, secret=None):
        if not self.fetched:
            raise ValueError('User must be saved to sign in')

        return course.sign_student_in(self, secret)

    def is_signed_into(self, course):
        return course.currently_signed_in(self)

    def takes_course(self, course):
        if not self.fetched or not self.is_student():
            raise ValueError('User must be a registered student to take a course')

        return course.has_student(self)

    def get_courses(self):
        if not self.fetched or not self.is_student():
            raise ValueError('User must be saved to have a course')

        query = self.datastore.query(kind='takes')
        query.add_filter('student_id', '=', self.get_id())
        takes = list(query.fetch())
        return [courses_model.Course(id=take['course_id']) for take in takes]

    def tas_course(self, course):
        if not self.fetched:
            raise ValueError('TA must be saved to TA a course')

        return course.has_TA(self)

    def get_taed_courses(self):
        if not self.fetched:
            raise ValueError('TA must be saved to TA a course')

        query = self.datastore.query(kind='tas')
        query.add_filter('ta_id', '=', self.get_id())
        tas = list(query.fetch())
        return [courses_model.Course(id=ta['course_id']) for ta in tas]


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
