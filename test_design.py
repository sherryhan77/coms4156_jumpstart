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
    teacher_id = users_model.User(data=teacher_user_data).get_or_create()['id']
    student_id = users_model.User(data=student_user_data).get_or_create()['id']
    ta_id = users_model.User(data=ta_user_data).get_or_create()['id']

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


def add_attendance_records(course, students, num_attendance_recs=1):
    for i in range(num_attendance_recs):
        course.open_session()
        for student in students:
            _, seid = student.get_secret_and_seid()
            student.insert_attendance_record(seid)
        course.close_session(seid)
    found_attendance_recs = student.get_num_attendance_records(course.cid)
    assert found_attendance_recs == num_attendance_recs, (
        "Found {0} attendance records, expected {}.".format(found_attendance_recs, num_attendance_recs))


def remove_from_course(student, course):
    course.remove_student(student.get_uni())     # Test 3.
    found_attendance_recs = student.get_num_attendance_records(course.cid)
    assert found_attendance_recs == 0, (
        "Found {0} attendance records after {1} removed from course.".format(found_attendance_recs,
            student.get_uni()))


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

    remove_from_course(ta, course)     # Test 3.
    assert ta not in course.get_students(), "TA reported as enrolled in course after remove_student."
    assert ta not in course.get_TAs(), "TA reported as TA for course after remove_student, fails test 3, 4b-3."

    destroy_context(context)


def test_TA_session_window():
    num_attendance_recs = 3
    context = create_common_context()

    course = context['course_id']
    ta = context['ta_id']
    course.add_TA(ta.get_uni())     # Test 1.

    assert course.get_active_session() == -1
    add_attendance_records(course, [ta], num_attendance_recs=num_attendance_recs)

    course.remove_TA(ta.get_uni())  # Test 2.
    found_attendance_recs = ta.get_num_attendance_records(course.cid)
    assert found_attendance_recs == num_attendance_recs, (
    "After TA demotion, found {0} attendance records, expected {}.".format(found_attendance_recs, num_attendance_recs))

    course.remove_TA(ta.get_uni())  # Test 2c.
    found_attendance_recs = ta.get_num_attendance_records(course.cid)
    assert found_attendance_recs == num_attendance_recs, (
    "After redundant demotion, found {0} attendance records, expected {}.".format(found_attendance_recs, num_attendance_recs))

    destroy_context(context)


    context = create_common_context()

    course = context['course_id']
    ta = context['ta_id']
    student = context['student_id']

    assert ta not in course.get_students(), "TA reported as enrolled in course after destroy->create context."
    course.add_TA(ta.get_uni())     # Test 1b.

    assert course.get_active_session() == -1
    add_attendance_records(course, [ta, student], num_attendance_recs=num_attendance_recs)

    remove_from_course(ta, course)
    remove_from_course(student, course)

    for stu in [ta, student]:
        course.add_TA(stu.get_uni())
        found_attendance_recs = stu.get_num_attendance_records(course.cid)
        assert found_attendance_recs == 0, (
            "Found {0} attendance records after {1} readded to course, test 3a/b.".format(found_attendance_recs,
                stu.get_uni()))

    destroy_context(context)
