from model import Model
import models
from datetime import datetime, date, timedelta
from random import randint
from google.cloud import datastore


class CourseNotTakingAttendance(Exception):
    pass


class Course(Model):
    def __init__(self, **kwargs):
        self.datastore = self.get_client()
        self.fetched = False
        if 'id' in kwargs:
            key = self.datastore.key('course', kwargs['id'])
            self.model = self.datastore.get(key)
            self.fetched = bool(self.model)

        if not self.fetched:
            self.model = kwargs

    def get_or_create(self):
        if not self.fetched:
            key = self.create_entity(
                kind='course',
                **self.model
            )
            self.model = self.datastore.get(key)
            self.fetched = True

        return self

    def has_student(self, student):
        if not self.fetched or not student.fetched:
            return False

        query = self.datastore.query(kind='takes')
        query.add_filter('course_id', '=', self.get_id())
        query.add_filter('student_id', '=', student.get_id())
        return len(list(query.fetch())) > 0

    def get_students(self):
        if not self.fetched:
            return list()

        query = self.datastore.query(kind='takes')
        query.add_filter('course_id', '=', self.get_id())
        takes = list(query.fetch())

        return [models.students_model.Student(id=take['student_id']) for take in takes]

    def add_student(self, student):
        if not student.fetched:
            raise ValueError('Student does not exist')

        if not student.is_student():
            raise ValueError('Must add a registered student to course')

        if self.has_student(student):
            return

        self.create_entity(
            kind='takes',
            course_id=self.get_id(),
            student_id=student.get_id()
        )

        while not self.has_student(student):
            pass

        assert self.has_student(student), (
            'Adding student didn\'t work. Must be something wrong with datastore.')

    def remove_student(self, student):
        if not student.fetched:
            raise ValueError('Student must be saved to remove from course')

        if not self.has_student(student):
            return

        query = self.datastore.query(kind='takes')
        query.add_filter('course_id', '=', self.get_id())
        query.add_filter('student_id', '=', student.get_id())

        keys = [take.key for take in list(query.fetch())]

        # clean up attendance records
        if not self.has_TA(student):
            query = self.datastore.query(kind='attendance_record')
            query.add_filter('course_id', '=', self.get_id())
            query.add_filter('user_id', '=', student.get_id())

            keys = keys + [take.key for take in list(query.fetch())]

        self.datastore.delete_multi(keys)

        while self.has_student(student):
            pass

        assert not self.has_student(student), (
            'Removing student didn\'t work. Must be something wrong with datastore.')

    def get_TAs(self):
        if not self.fetched:
            return list()

        query = self.datastore.query(kind='tas')
        query.add_filter('course_id', '=', self.get_id())
        tas = list(query.fetch())

        return [models.users_model.User(id=ta['ta_id']) for ta in tas]

    def has_TA(self, ta):
        if not self.fetched or not ta.fetched:
            return False

        query = self.datastore.query(kind='tas')
        query.add_filter('course_id', '=', self.get_id())
        query.add_filter('ta_id', '=', ta.get_id())
        query.keys_only()
        return len(list(query.fetch())) > 0

    def add_TA(self, ta):
        if not ta.fetched:
            raise ValueError('TA must be saved to add to course')

        if self.has_TA(ta):
            return

        self.create_entity(
            kind='tas',
            course_id=self.get_id(),
            ta_id=ta.get_id()
        )

        while not self.has_TA(ta):
            pass

        assert self.has_TA(ta), 'Adding TA didn\'t work. Must be something wrong with datastore'

    def remove_TA(self, ta):
        if not ta.fetched:
            raise ValueError('TA must be saved to remove from course')

        if not self.has_TA(ta):
            return

        query = self.datastore.query(kind='tas')
        query.add_filter('course_id', '=', self.get_id())
        query.add_filter('ta_id', '=', ta.get_id())

        keys = [t.key for t in list(query.fetch())]

        # clean up attendance records
        if not self.has_student(ta):
            query = self.datastore.query(kind='attendance_record')
            query.add_filter('course_id', '=', self.get_id())
            query.add_filter('user_id', '=', ta.get_id())

            keys = keys + [take.key for take in list(query.fetch())]

        self.datastore.delete_multi(keys)

        while self.has_TA(ta):
            pass

        assert not self.has_TA(ta), (
            'Removing TA didn\'t work. Must be something wrong with datastore')

    def get_open_session(self):
        if not self.fetched:
            return None

        query = self.datastore.query(kind='attendance_window')
        query.add_filter('course_id', '=', self.get_id())
        query.add_filter('closed_at', '=', None)
        sessions = list(query.fetch())
        if len(sessions) == 0:
            return None

        return sessions[0]

    def open_session(self):
        if not self.fetched:
            raise ValueError('Course must be saved to open its session')

        session = self.get_open_session()

        if session is None:
            key = self.create_entity(
                kind='attendance_window',
                course_id=self.get_id(),
                opened_at=datetime.now(),
                closed_at=None,
                secret=randint(1000, 9999)
            )

            while session is None:
                session = self.datastore.get(key)
                pass

        return session['secret']

    def close_session(self):
        session = self.get_open_session()
        if session is None:
            return

        session.update({
            'closed_at': datetime.now()
        })

        self.datastore.put(session)

        while self.get_open_session() is not None:
            pass

    def session_count(self):
        if not self.fetched:
            return None

        query = self.datastore.query(kind='attendance_window')
        query.add_filter('course_id', '=', self.get_id())
        query.keys_only()
        return len(list(query.fetch()))

    def sign_student_in(self, student, secret=None):
        if not self.fetched:
            raise ValueError('Course must be saved to sign in to')

        if not student.fetched:
            raise ValueError('Student must be saved to sign in')

        if not self.has_student(student) and not self.has_TA(student):
            raise ValueError('Student must be in course to sign in')

        session = self.get_open_session()

        if session is None:
            raise CourseNotTakingAttendance('Course\'s attendance window is not open')

        if str(secret) != str(session['secret']) and not (secret is None and self.has_TA(student)):
            return False

        query = self.datastore.query(kind='attendance_record')
        query.add_filter('attendance_window_id', '=', session.key.id)
        query.add_filter('user_id', '=', student.get_id())
        query.keys_only()
        signed_in = len(list(query.fetch())) > 0

        if signed_in:
            raise ValueError('Student already signed into session')

        self.create_entity(
            kind='attendance_record',
            attendance_window_id=session.key.id,
            user_id=student.get_id(),
            # not strictly necessary, but good for performance in get_attendance_records
            course_id=self.get_id()
        )

        while not self.currently_signed_in(student):
            pass

        return True

    def currently_signed_in(self, student):
        if not student.fetched:
            raise ValueError('Unsaved user cannot be signed into a course')

        if not self.fetched:
            raise ValueError('Cannot be signed into an unsaved course')

        session = self.get_open_session()

        if session is None:
            return False

        query = self.datastore.query(kind='attendance_record')
        query.add_filter('user_id', '=', student.get_id())
        query.add_filter('attendance_window_id', '=', session.key.id)
        query.keys_only()
        return len(list(query.fetch())) > 0

    def get_attendance_records(self, student=None, ta=None):
        query = self.datastore.query(kind='attendance_record')
        query.add_filter('course_id', '=', self.get_id())

        user = student or ta

        if user is not None:
            if not user.fetched:
                return list()
            query.add_filter('user_id', '=', user.get_id())
        return list(query.fetch())

    def get_attendance_details(self, student):
        if not self.fetched:
            raise ValueError('Can\'t get attendance details of an unsaved course')

        if not self.has_student(student) and not self.has_TA(student):
            return []

        query = self.datastore.query(kind='attendance_window')
        query.add_filter('course_id', '=', self.get_id())
        windows = list(query.fetch())

        query = self.datastore.query(kind='attendance_record')
        query.add_filter('user_id', '=', student.get_id())
        query.add_filter('course_id', '=', self.get_id())
        records = list(query.fetch())

        details = list()
        for window in windows:
            relevant_records = [record for record in records
                                if record['attendance_window_id'] == window.key.id]
            details.append({
                'opened_at': window['opened_at'],
                'closed_at': window['closed_at'],
                'user_id': student.get_id(),
                'session_id': window.key.id,
                'attended': len(relevant_records) > 0
            })

        return details

    def edit_attendance_history(self, **kwargs):
        if not self.fetched:
            raise ValueError('Can\'t change attendance of an unsaved course')

        if 'student' not in kwargs and 'ta' not in kwargs:
            raise ValueError('No student or TA specified')

        if 'attended' not in kwargs:
            raise ValueError('`attended` not specified')

        if 'session_id' not in kwargs or kwargs['session_id'] is None:
            raise ValueError('`session_id` not specified')

        user = None
        if 'student' in kwargs:
            user = kwargs['student']
            if not user.takes_course(self):
                raise ValueError('Student does not take course')
        else:
            user = kwargs['ta']
            if not user.tas_course(self):
                raise ValueError('TA does not TA course')

        query = self.datastore.query(kind='attendance_record')
        query.add_filter('user_id', '=', user.get_id())
        query.add_filter('course_id', '=', self.get_id())
        query.add_filter('attendance_window_id', '=', kwargs['session_id'])
        query.keys_only()
        records = list(query.fetch())
        record = records[0] if len(records) > 0 else None

        if kwargs['attended'] == (record is not None):
            return

        if kwargs['attended']:
            self.create_entity(
                kind='attendance_record',
                user_id=user.get_id(),
                course_id=self.get_id(),
                attendance_window_id=kwargs['session_id']
            )
        else:
            self.datastore.delete_multi([r.key for r in records])

    def destroy(self):
        super(self.__class__, self).destroy()

        # clean up attendance windows, records, and join table entities
        keys = list()
        for kind in ['attendance_record', 'attendance_window', 'tas', 'takes', 'teaches']:
            query = self.datastore.query(kind=kind)
            query.add_filter('course_id', '=', self.get_id())
            query.keys_only()
            keys = keys + [e.key for e in list(query.fetch())]

        self.datastore.delete_multi(keys)


class Courses(Model):

    def __init__(self, cid=-1):
        self.cid = cid
        self.now = datetime.time(datetime.now())
        self.today = date.today()
        self.ds = self.get_client()

    def get_course_name(self):
        query = self.ds.query(kind='courses')
        query.add_filter('cid', '=', int(self.cid))
        result = list(query.fetch())
        return result[0]['name']

    def get_students(self):
        query = self.ds.query(kind='enrolled_in')
        query.add_filter('cid', '=', int(self.cid))
        enrolled_in = list(query.fetch())
        results = list()
        for enrolled in enrolled_in:
            query = self.ds.query(kind='user')
            query.add_filter('id', '=', enrolled['sid'])
            results = results + list(query.fetch())
        return results

    def add_student(self, uni):
        query = self.ds.query(kind='student')
        query.add_filter('uni', '=', uni)
        result = list(query.fetch())

        if len(result) == 1:
            # found a student with uni, attempt to add to enrolled_in
            sid = result[0]['sid']
            query = self.ds.query(kind='enrolled_in')
            query.add_filter('sid', '=', sid)
            query.add_filter('cid', '=', int(self.cid))
            result = list(query.fetch())
            if len(result) > 0:
                # failed because already in enrolled_in
                return -2

            key = self.ds.key('enrolled_in')
            entity = datastore.Entity(
                key=key)
            entity.update({
                'sid': sid,
                'cid': int(self.cid)
            })
            self.ds.put(entity)
            return 0

        else:
            # invalid uni
            return -1

    def remove_student(self, uni):
        query = self.ds.query(kind='student')
        query.add_filter('uni', '=', uni)
        result = list(query.fetch())

        if len(result) == 1:
            # found a student with uni, attempt to remove from enrolled_in
            sid = result[0]['sid']

            query = self.ds.query(kind='enrolled_in')
            query.add_filter('sid', '=', sid)
            query.add_filter('cid', '=', int(self.cid))
            result = list(query.fetch())

            if len(result) > 0:

                self.ds.delete(result[0].key)

                query = self.ds.query(kind='sessions')
                query.add_filter('cid', '=', int(self.cid))
                sessions = list(query.fetch())
                attendanceRecords = list()
                for session in sessions:
                    query = self.ds.query(kind='attendance_records')
                    query.add_filter('seid', '=', int(session['seid']))
                    attendanceRecords = attendanceRecords + list(query.fetch())
                for attendanceRecord in attendanceRecords:
                    self.ds.delete(attendanceRecord.key)
                return 0
            else:
                # failed because it was not in enrolled_in to begin with
                return -3
        else:
            # invalid uni
            return -1

    def get_active_session(self):
        '''Return the seid of an active session if it exists,
        otherwise return -1.
        Note: Undefined which seid is returned when more than one session is active.
        '''
        query = self.ds.query(kind='sessions')
        query.add_filter('cid', '=', int(self.cid))
        sessions = list(query.fetch())
        results = list()
        for session in sessions:
            if session['expires'].replace(tzinfo=None) > datetime.now():
                results.append(session)

        return results[0]['seid'] if len(results) >= 1 else -1

    def close_session(self, seid):
        if seid == -1:
            return

        query = self.ds.query(kind='sessions')
        query.add_filter('seid', '=', int(seid))
        entity = list(query.fetch())[0]
        entity.update({
            'expires': datetime.now()
        })
        self.ds.put(entity)

        query = self.ds.query(kind='courses')
        query.add_filter('cid', '=', int(self.cid))
        entity = list(query.fetch())[0]
        entity.update({
            'active': 0
        })
        self.ds.put(entity)

    def open_session(self):
        '''Opens a session for this course
        and returns the secret code for that session.
        '''
        # auto-generated secret code for now
        randsecret = randint(1000, 9999)

        key = self.ds.key('sessions')
        entity = datastore.Entity(
            key=key)
        entity.update({
            'cid': int(self.cid),
            'secret': int(randsecret),
            'expires': datetime.now() + timedelta(days=1)
        })
        self.ds.put(entity)
        seid = entity.key.id
        entity.update({
            'seid': seid
        })
        self.ds.put(entity)

        key = self.ds.key('courses', int(self.cid))
        results = self.ds.get(key)
        entity = datastore.Entity(
            key=key)
        entity.update({
            'name': results['name'],
            'active': 1,
            'cid': results['cid']
        })
        self.ds.put(entity)

        return randsecret

    def get_secret_code(self):
        query = self.ds.query(kind='courses')
        query.add_filter('cid', '=', int(self.cid))
        courses = list(query.fetch())
        results = list()
        for course in courses:
            query = self.ds.query(kind='sessions')
            query.add_filter('cid', '=', course['cid'])
            sessions = list(query.fetch())
            for session in sessions:
                if session['expires'].replace(tzinfo=None) > datetime.now():
                    results.append(session)
        return results[0]['secret'] if len(results) == 1 else None

    def get_num_sessions(self):
        query = self.ds.query(kind='sessions')
        query.add_filter('cid', '=', int(self.cid))
        results = list(query.fetch())
        return len(results)
