from models import users_model, index_model, teachers_model, students_model, \
        courses_model, model

from google.cloud import datastore

import pytest
import imhere

teacher_user_data = {
    'family_name': 'Teacher',
    'name': 'Douglas Teacher',
    'email': 'doug@cs.columbia.edu',
    'given_name': 'Douglas'
}

student_user_data = {
    'family_name': 'Student',
    'name': 'Salguod Student',
    'email': 'salg@cs.columbia.edu',
    'given_name': 'Salguod'
}

ta_user_data = {
    'family_name': 'Assistant',
    'name': 'Teaching Assistant',
    'email': 'ta@cs.columbia.edu',
    'given_name': 'Teaching'
}

def create_common_context():
    # create users
    teacher_id = users_model.User(teacher_user_data).get_or_create()['id']
    student_id = users_model.User(student_user_data).get_or_create()['id']
    ta_id = users_model.User(ta_user_data).get_or_create()['id']

    # register student and TA as students
    students_model.Student(student_id).register_as_student(uni='student1')
    students_model.Student(ta_id).register_as_student(uni='student2')

    # register teacher as teacher
    teacher = teachers_model.Teacher(teacher_id).register_as_teacher()

    # create course
    course = teacher.add_course('Course 1')

    return {
        'teacher_id': teacher_id,
        'student_id': student_id,
        'ta_id': ta_id,
        'course_id': course['id']
    }

def destroy_context(context):
    users_model.User(context['student_id']).destroy()
    users_model.User(context['teacher_id']).destroy()
    users_model.User(context['ta_id']).destroy()

    courses_model.Course(context['course_id']).destroy()

def test_TA_promote_demote():
    context = create_common_context()

    course = context['course_id']
    ta = context['ta_id']
    course.add_student(ta.get_uni())
    assert ta in course.get_students(), "TA not reported as enrolled in course, fails test 1a."
    course.add_TA(ta.get_uni())     # Test 1.
    assert ta in course.get_TAs(), "TA not reported as TA for course, fails test 1., 4a."
    assert ta in course.get_students(), "TA not reported as enrolled in course, fails test 1a."

    course.remove_TA(ta.get_uni())  # Test 2.
    assert ta not in course.get_TAs(), "TA still reported as TA for course, fails test 2., 4b-2."
    assert ta in course.get_students(), "TA not reported as enrolled in course, fails test 2d."

    course.remove_TA(ta.get_uni())  # Test 2c.
    assert ta not in course.get_TAs(), "TA still reported as TA for course, fails test 2c., 4b-2."
    assert ta in course.get_students(), "TA not reported as enrolled in course, fails test 2d."

    destroy_context(context)


    context = create_common_context()

    course = context['course_id']
    ta = context['ta_id']
    assert ta not in course.get_students(), "TA reported as enrolled in course after destroy->create context."
    course.add_TA(ta.get_uni())     # Test 1b.
    assert ta in course.get_students(), "TA not reported as enrolled in course, fails test 1a."
    assert ta in course.get_TAs(), "TA not reported as TA for course, fails test 1b., 4a."

    course.remove_student(ta.get_uni())     # Test 3.
    assert ta not in course.get_students(), "TA reported as enrolled in course after remove_student."
    assert ta not in course.get_TAs(), "TA reported as TA for course after remove_student, fails test 3, 4b-3."


    destroy_context(context)
