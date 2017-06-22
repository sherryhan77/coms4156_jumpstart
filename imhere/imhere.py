#!/usr/bin/env python2.7

import os
import httplib2

import sys
import traceback
import oauth2client
import apiclient
import flask

from uuid import uuid4
from flask import Flask, render_template, request, abort, url_for
from models import users_model, index_model, teachers_model, students_model, \
        courses_model, model, tas_model
from google.cloud import datastore
from functools import wraps


tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)
app.secret_key = str(uuid4())

def merge_dicts(*dicts):
    result = {}
    for d in dicts:
        result.update(d)
    return result


def templated(template=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            template_name = template
            if template_name is None:
                template_name = request.endpoint \
                    .replace('.', '/') + '.html'
            ctx = f(*args, **kwargs)
            if ctx is None:
                ctx = {}
            elif not isinstance(ctx, dict):
                return ctx
            return render_template(template_name, **ctx)
        return decorated_function
    return decorator

def must_be_teacher(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        teacher = request.user_models.get('teacher', None)
        if teacher is None:
            return flask.redirect(url_for('home'))

        course = kwargs.get('course', None)
        if course and not teacher.teaches_course(course):
            abort(403)

        student = kwargs.get('student', None)
        if student and not student.takes_course(course):
            raise ValueError('Student is not in course')
        return f(*args, **kwargs)
    return decorated

def must_be_teacher_or_ta(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        teacher = request.user_models.get('teacher', None)
        ta = request.user_models.get('ta', None)
        if teacher is None and ta is None:
            return flask.redirect(url_for('home'))

        course = kwargs.get('course', None)

        if course and not (teacher and teacher.teaches_course(course)) and not (ta and ta.tas_course(course)):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def must_be_signed_in(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = request.user_models.get('user', None)
        if user is not None:
            return f(*args, **kwargs)
        return flask.redirect(url_for('home'))
    return decorated

def common_view_variables():
    return merge_dicts(
        request.user_models,
        {
            'messages': request.messages
        }
    )

@app.url_value_preprocessor
def convert_params(endpoint, values):
    if not values:
        return
    if 'course_id' in values:
        course = courses_model.Course(id=values['course_id'])
        if not course.fetched:
            raise ValueError('Course does not exist')
        values['course'] = course

    if 'student_id' in values:
        student = students_model.Student(id=values['student_id'])
        if not student.fetched:
            raise ValueError('Student does not exist')
        values['student'] = student

    if 'ta_id' in values:
        ta = tas_model.TA(id=values['ta_id'])
        if not ta.fetched:
            raise ValueError('TA does not exist')
        values['ta'] = ta

# make sure user is authenticated w/ live session on every request
@app.before_request
def manage_session():
    # want to go through oauth flow for this route specifically
    # not get stuck in redirect loop
    if request.path == '/oauth/callback':
        return

    request.user_models = {}
    user_id = flask.session.get('user_id', None)
    if user_id is not None:
        user = users_model.User(id=user_id)
        request.user_models['user'] = user
        if user.is_teacher():
            request.user_models['teacher'] = teachers_model.Teacher(id=user_id)
        if user.is_student():
            request.user_models['student'] = students_model.Student(id=user_id)
            request.user_models['ta'] = request.user_models['student'].as_TA()

@app.before_request
def manage_messages():
    request.messages = flask.session.get('messages', list())
    flask.session['messages'] = list()

@app.errorhandler(Exception)
def handle_app_error(e):
    if request.method == 'GET':
        traceback.print_exc(file=sys.stdout)
        raise e

    flask.session['messages'].append({
        'type': 'error',
        'message': e.message
    })

    traceback.print_exc(file=sys.stdout)
    return flask.redirect(request.referrer or url_for('home'))

@app.errorhandler(500)
def handle_internal_server_error(e):
    return render_template('error.html')

@app.route('/', methods=['GET'])
@templated('home.html')
def home():
    return common_view_variables()

@app.route('/login', methods=['POST'])
def login():
    if hasattr(request, 'user'):
        return flask.redirect(url_for('home'))

    return flask.redirect(url_for('oauth2callback'))


@app.route('/courses/<int:course_id>/sessions', methods=['POST'])
@must_be_teacher_or_ta
def open_session(course, **kwargs):
    course.open_session()
    return flask.redirect(request.referrer) or url_for('home')


@app.route('/courses/<int:course_id>/sessions/current/close', methods=['POST'])
@must_be_teacher_or_ta
def close_session(course, **kwargs):
    course.close_session()
    return flask.redirect(request.referrer or url_for('home'))

@app.route('/courses/<int:course_id>/sessions/current/sign-in', methods=['POST'])
def sign_in(course, **kwargs):
    signer = request.user_models.get('student', None) or request.user_models.get('ta', None)
    if not course.has_student(signer) and not course.has_TA(signer):
        raise ValueError('User must be in course to sign in')

    secret = request.form.get('secret', None)
    success = signer.sign_in(course, secret)
    if not success:
        flask.session['messages'].append({
            'type': 'error',
            'message': 'Secret was incorrect; not signed in'
        })
    return flask.redirect(request.referrer or url_for('home'))


@app.route('/courses/<int:course_id>/students', methods=['POST'])
@must_be_teacher
def add_student_to_course(course, **kwargs):
    if 'uni' not in request.form or not request.form['uni']:
        raise ValueError('Must include UNI')
    uni = request.form['uni']
    student = students_model.Student(uni=uni)
    course.add_student(student)
    return flask.redirect(request.referrer or url_for('home'))

#  have to allow POST because forms don't support DELETE
#  fortunately, POST /path/to/:id doesn't mean anything in REST (afaik)
@app.route('/courses/<int:course_id>/students/<int:student_id>', methods=['DELETE', 'POST'])
@must_be_teacher
def remove_student_from_course(course, student, **kwargs):
    if not (request.method == 'DELETE' or request.args.get('delete')):
        abort(404)
    course.remove_student(student)
    return flask.redirect(request.referrer or url_for('home'))


@app.route('/courses/<int:course_id>/tas', methods=['POST'])
@must_be_teacher
def add_ta_to_course(course, **kwargs):
    if 'uni' not in request.form or not request.form['uni']:
        raise ValueError('Must include UNI')
    uni = request.form['uni']
    ta = tas_model.TA(uni=uni)
    course.add_TA(ta)
    return flask.redirect(request.referrer or url_for('home'))

#  have to allow POST because forms don't support DELETE
#  fortunately, POST /path/to/:id doesn't mean anything in REST (afaik)
@app.route('/courses/<int:course_id>/tas/<int:ta_id>', methods=['DELETE', 'POST'])
@must_be_teacher
def remove_ta_from_course(course, ta, **kwargs):
    if not (request.method == 'DELETE' or request.args.get('delete')):
        abort(404)
    course.remove_TA(ta)
    return flask.redirect(request.referrer or url_for('home'))


@app.route('/courses', methods=['POST'])
@must_be_teacher
def create_course():
    request.user_models['teacher'].add_course(request.form['name'])
    return flask.redirect(request.referrer) or url_for('home')

@app.route('/courses/<int:course_id>/tas/<int:ta_id>/records')
@must_be_teacher
@templated('view_records.html')
def view_ta_records(course, ta, **kwargs):
    return merge_dicts(
        common_view_variables(),
        {
            'records': course.get_attendance_details(ta),
            'target': ta,
            'course': course,
            'target_type': 'ta'
        }
    )

@app.route('/courses/<int:course_id>/students/<int:student_id>/records')
@must_be_teacher
@templated('view_records.html')
def view_student_records(course, student, **kwargs):
    return merge_dicts(
        common_view_variables(),
        {
            'records': course.get_attendance_details(student),
            'target': student,
            'course': course,
            'target_type': 'student'
        }
    )

@app.route('/courses/<int:course_id>/students/<int:student_id>/records/<int:session_id>', methods=['POST'])
@must_be_teacher
def modify_student_attendance_record(student, course, session_id, **kwargs):
    change_to = request.form['change-to'] == 'True'
    course.edit_attendance_history(student=student, session_id=session_id, attended=change_to)
    return flask.redirect(request.referrer or url_for('home'))

@app.route('/courses/<int:course_id>/tas/<int:ta_id>/records/<int:session_id>', methods=['POST'])
@must_be_teacher
def modify_ta_attendance_record(ta, course, session_id, **kwargs):
    change_to = request.form['change-to'] == 'True'
    course.edit_attendance_history(ta=ta, session_id=session_id, attended=change_to)
    return flask.redirect(request.referrer or url_for('home'))


@app.route('/courses/<int:course_id>', methods=['GET'])
@must_be_teacher_or_ta
@templated('view_course.html')
def view_course(course, **kwargs):
    variables = common_view_variables()
    variables['course'] = course
    return variables

@app.route('/student/', methods=['GET', 'POST'])
def main_student():
    sm = students_model.Students(flask.session['id'])
    courses = sm.get_courses()
    context = dict(data=courses)
    signed_in = True if sm.has_signed_in() else False

    if request.method == 'GET':
        return render_template(
                'main_student.html',
                signed_in=signed_in,
                **context)

    elif request.method == 'POST':
        if 'secret_code' in request.form.keys():
            provided_secret = request.form['secret_code']
            actual_secret, seid = sm.get_secret_and_seid()
            if int(provided_secret) == int(actual_secret):
                sm.insert_attendance_record(seid)
                valid = True
            else:
                valid = False

            return render_template(
                    'main_student.html',
                    submitted=True,
                    valid=valid,
                    **context)


@app.route('/teacher/', methods=['GET', 'POST'])
def main_teacher():
    tm = teachers_model.Teachers(flask.session['id'])

    if request.method == 'POST':
        cm = courses_model.Courses()
        if "close" in request.form.keys():
            cid = request.form["close"]
            cm.cid = cid
            cm.close_session(cm.get_active_session())
        elif "open" in request.form.keys():
            cid = request.form["open"]
            cm.cid = cid
            cm.open_session()

    courses = tm.get_courses_with_session()
    empty = True if len(courses) == 0 else False
    context = dict(data=courses)
    return render_template('main_teacher.html', empty=empty, **context)


@app.route('/teacher/add_class', methods=['POST', 'GET'])
def add_class():
    tm = teachers_model.Teachers(flask.session['id'])

    if request.method == 'GET':
        return render_template('add_class.html')

    elif request.method == 'POST':
        # first check that all unis are valid
        um = users_model.Users()
        for uni in request.form['unis'].split('\n'):
            uni = uni.strip('\r')
            # always reads at least one empty line from form
            if not uni:
                continue
            if not um.is_valid_uni(uni):
                return render_template('add_class.html', invalid_uni=True)

        # then create course and add students to course
        course_name = request.form['classname']
        cid = tm.add_course(course_name)
        cm = courses_model.Courses(cid)

        for uni in request.form['unis'].split('\n'):
            uni = uni.strip('\r')
            cm.add_student(uni)

        return flask.redirect(url_for('main_teacher'))


@app.route('/teacher/remove_class', methods=['POST', 'GET'])
def remove_class():
    tm = teachers_model.Teachers(flask.session['id'])

    # show potential courses to remove on get request
    if request.method == 'GET':
        courses = tm.get_courses()
        context = dict(data=courses)
        return render_template('remove_class.html', **context)

    # remove course by cid
    elif request.method == 'POST':
        cid = request.form['cid']
        tm.remove_course(cid)
        return flask.redirect(url_for('main_teacher'))


@app.route('/teacher/view_class', methods=['POST', 'GET'])
def view_class():
    if request.method == 'GET':
        flask.redirect(url_for('main_teacher'))

    elif request.method == 'POST':
        cm = courses_model.Courses()

        if 'close' in request.form.keys():
            cid = request.form['close']
            cm.cid = cid
            cm.close_session(cm.get_active_session())
        elif 'open' in request.form.keys():
            cid = request.form['open']
            cm.cid = cid
            cm.open_session()
        else:
            cid = request.form['cid']
            cm.cid = cid

        res = 0
        uni = None
        if 'add_student' in request.form.keys():
            uni = request.form['add_student']
            res = cm.add_student(uni)
        elif 'remove_student' in request.form.keys():
            uni = request.form['remove_student']
            res = cm.remove_student(uni)

        course_name = cm.get_course_name()
        secret = cm.get_secret_code()
        num_sessions = cm.get_num_sessions()
        students = cm.get_students()
        students_with_ar = []
        for student in students:
            sm = students_model.Students(student['id'])
            student_uni = sm.get_uni()
            num_ar = sm.get_num_attendance_records(cid)
            students_with_ar.append([student, student_uni, num_ar])

        context = dict(students=students_with_ar)
        return render_template(
                'view_class.html',
                cid=cid,
                secret=secret,
                course_name=course_name,
                num_sessions=num_sessions,
                uni=uni,
                res=res,
                **context)


@app.route('/register', methods=['POST'])
@must_be_signed_in
def register():
    register_as = request.form['register_as']
    user = request.user_models['user']
    if register_as == 'teacher':
        teachers_model.Teacher(id=user.get_id()).register_as_teacher()
    elif register_as == 'student':
        uni = request.form['uni']
        students_model.Student(id=user.get_id()).register_as_student(uni=uni)

    return flask.redirect(url_for('home'))

@app.route('/oauth/callback')
def oauth2callback():
    flow = oauth2client.client.flow_from_clientsecrets(
        'client_secrets_oauth.json',
        scope=[
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'],
        redirect_uri=url_for('oauth2callback', _external=True))
    if 'code' not in flask.request.args:
        auth_uri = flow.step1_get_authorize_url()
        return flask.redirect(auth_uri)
    else:
        auth_code = flask.request.args.get('code')
        credentials = flow.step2_exchange(auth_code)
        flask.session['credentials'] = credentials.to_json()

        # use token to get user profile from google oauth api
        http_auth = credentials.authorize(httplib2.Http())
        userinfo_client = apiclient.discovery.build('oauth2', 'v2', http_auth)
        user = userinfo_client.userinfo().v2().me().get().execute()

        flask.session['google_user'] = user
        flask.session['user_id'] = users_model.User(**user).get_or_create().get_id()

        return flask.redirect(url_for('home'))


@app.route('/logout', methods=['POST', 'GET'])
def logout():
    session = flask.session
    for k in session.keys():
        session.pop(k)
    return flask.redirect(request.referrer or url_for('home'))
