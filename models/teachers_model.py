from model import Model
from datetime import datetime, date
from google.cloud import datastore
from models import courses_model, users_model


class Teacher(users_model.User):
    def register_as_teacher(self):
        self.update(teacher=True)
        return self

    def add_course(self, name):
        if not self.fetched:
            raise ValueError('Unsaved teacher cannot create a course')

        if not self.is_teacher():
            raise ValueError('Must be a registered teacher to create a course')

        if not name:
            raise ValueError('Course must have a name')

        course = courses_model.Course(name=name).get_or_create()
        self.create_entity(
            kind='teaches',
            teacher_id=self.get_id(),
            course_id=course.get_id()
        )

        while not self.teaches_course(course):
            pass

        return course

    def remove_course(self, course):
        if not self.fetched:
            raise ValueError('Unsaved teacher cannot remove a course')

        if not self.is_teacher():
            raise ValueError('Must be a registered teacher to remove a course')

        if not course.fetched:
            raise ValueError('Course must be saved to be removed.')

        if not self.teaches_course(course):
            return

        course.destroy()

    def teaches_course(self, course):
        if not self.fetched or not course.fetched:
            return False

        query = self.datastore.query(kind='teaches')
        query.add_filter('teacher_id', '=', self.get_id())
        query.add_filter('course_id', '=', course.get_id())
        query.keys_only()
        return len(list(query.fetch())) > 0

    def get_courses(self):
        if not self.fetched or not self.is_teacher():
            return list()

        query = self.datastore.query(kind='teaches')
        query.add_filter('teacher_id', '=', self.get_id())
        joins = query.fetch()
        return [courses_model.Course(id=join['course_id']) for join in joins]


class Teachers(Model):

    def __init__(self, tid):
        self.tid = tid
        self.now = datetime.now()
        self.today = datetime.today()
        self.ds = self.get_client()

    def get_courses(self):
        query = self.ds.query(kind='teaches')
        query.add_filter('tid', '=', self.tid)
        teaches = list(query.fetch())
        results = list()
        for teach in teaches:
            query = self.ds.query(kind='courses')
            query.add_filter('cid', '=', teach['cid'])
            results = results + list(query.fetch())
        return results

    def get_courses_with_session(self):
        query = self.ds.query(kind='teaches')
        query.add_filter('tid', '=', self.tid)
        teaches = list(query.fetch())
        courses = list()
        for teach in teaches:
            query = self.ds.query(kind='courses')
            query.add_filter('cid', '=', teach['cid'])
            courses = courses + list(query.fetch())
        for course in courses:
            results = list()
            query = self.ds.query(kind='sessions')
            query.add_filter('cid', '=', course['cid'])
            sessions = list(query.fetch())
            for session in sessions:
                if session['expires'].replace(tzinfo=None) > datetime.now():
                    results.append(session)
            if len(results) == 1:
                course['secret'] = sessions[0]['secret']

        # result = courses + sessions
        return courses

    def add_course(self, course_name):
        key = self.ds.key('courses')
        entity = datastore.Entity(
            key=key)
        entity.update({
            'name': course_name,
            'active': 0
        })
        self.ds.put(entity)
        cid = entity.key.id
        entity.update({
            'cid': cid
        })
        self.ds.put(entity)

        key = self.ds.key('teaches')
        entity = datastore.Entity(
            key=key)
        entity.update({
            'tid': self.tid,
            'cid': cid
        })
        self.ds.put(entity)
        return cid

    def remove_course(self, cid):
        key = self.ds.key('courses', int(cid))
        self.ds.delete(key)

        # remove course from students' enrolled list
        query = self.ds.query(kind='enrolled_in')
        query.add_filter('cid', '=', int(cid))
        results = list(query.fetch())
        for result in results:
            self.ds.delete(result.key)
