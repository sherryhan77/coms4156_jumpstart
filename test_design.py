from models import users_model, index_model, teachers_model, students_model, \
        courses_model, model

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
    # register student and TA as students
    student= students_model.Student(**student_user_data).get_or_create().register_as_student(uni='student1')
    ta = students_model.Student(**ta_user_data).get_or_create().register_as_student(uni='student2')

    # register teacher as teacher
    teacher = teachers_model.Teacher(**teacher_user_data).get_or_create().register_as_teacher()

    # create course
    course = teacher.add_course('Course 1')

    return {
        'teacher': teacher,
        'student': student,
        'ta': ta,
        'course': course
    }

def destroy_context(context):
    users_model.User(id=context['student_id']).destroy()
    users_model.User(id=context['teacher_id']).destroy()
    users_model.User(id=context['ta_id']).destroy()

    courses_model.Course(id=context['course_id']).destroy()

def add_attendance_records(course, students, num_attendance_recs=1):
    for i in range(num_attendance_recs):
        secret = course.open_session()
        for student in students:
            student.sign_in(course, secret)
        course.close_session()
    attendance_records = course.get_attendance_records()

    assert len(attendance_records) == num_attendance_recs, (
        "Found {0} attendance records, expected {}.".format(
            len(attendance_records), num_attendance_recs
        )
    )

def remove_from_course(student, course):
    course.remove_student(student)     # Test 3.
    attendance_records = course.get_attendance_records(student=student)
    assert len(attendance_records) == 0, (
        "Found {0} attendance records after {1} removed from course.".format(
            len(attendance_records),
            student.get('uni'))
    )

def test_enrolling_and_hiring():
    context = create_common_context()
    try:
        course = context['course']
        ta = context['ta']
        student = context['student']

        course.add_student(student)
        assert course.has_student(student), "Student not reported as enrolled in course after enrollment"
        assert not course.has_TA(student), 'Student reported as TA for course after enrollment'

        course.add_TA(student)
        assert course.has_student(student), "Student not reported as enrolled in course after hiring"
        assert course.has_TA(student), 'Student not reported as TA for course after hiring'

        course.add_TA(ta)
        assert not course.has_student(student), "TA reported as enrolled in course after hiring"
        assert course.has_TA(student), 'TA not reported as TA for course after hiring'

        course.add_student(ta)
        assert course.has_student(student), "TA not reported as enrolled in course after enrollment"
        assert course.has_TA(student), 'TA not reported as TA for course after enrollment'
    finally:
        destroy_context(context)

def test_dropping_and_firing():
    context = create_common_context()
    try:
        course = context['course']
        ta = context['ta']
        student = context['student']

        course.add_student(student)
        course.add_TA(ta)
        add_attendance_records(course, [student, ta], 2)
        course.remove_student(student)
        course.remove_TA(ta)

        assert len(course.get_attendance_records(student=student)) == 0, 'Student\'s records not destroyed after dropping class'

        assert len(course.get_attendance_records(ta=ta)) == 0, 'TA\'s records not destroyed after dropping class'

        # reuse TA as student-TA
        student_ta = ta
        course.add_student(student_ta)
        course.add_TA(student_ta)
        add_attendance_records(course, [student_ta], 2)
        course.remove_student(student_ta)

        assert len(course.get_attendance_records(student=student)) == 2, 'Student-TA\'s records destroyed after dropping class'

        course.add_student(student_ta)
        course.remove_TA(student_ta)

        assert len(course.get_attendance_records(student=student)) == 2, 'Student-TA\'s records destroyed after dropping class'

    finally:
        destroy_context(context)
'''
def test_TA_session_window():
    num_attendance_recs = 3
    context = create_common_context()

    course = context['course']
    ta = context['ta']
    course.add_TA(ta)     # Test 1.

    assert course.get_active_session() is None
    assert course.close_sessions()
    assert course.get_active_session() is None
    add_attendance_records(course, [ta], num_attendance_recs=num_attendance_recs)

    course.remove_TA(ta)  # Test 2.

    ta_attendance = course.get_attendance_records(student=ta)
    assert  == num_attendance_recs, (
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

def test_student_registration():
    students_model.Student(uni='one').destroy()
    students_model.Student(uni='two').destroy()
    student = students_model.Student(**student_user_data).get_or_create().register_as_student(uni='one')

    ta = students_model.Student(**ta_user_data).get_or_create()
    with pytest.raises(students_model.DuplicateUNIException):
        ta.register_as_student(uni='one')

    with pytest.raises(ValueError, message='Students must have UNIs'):
        ta.register_as_student(uni='')

    with pytest.raises(ValueError, message='Students must have UNIs'):
        ta.register_as_student()

    ta.register_as_student(uni='two')
'''
