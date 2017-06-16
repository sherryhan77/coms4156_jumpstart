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

def first_test():
    context = create_common_context()

    assert True

    destroy_context(context)
