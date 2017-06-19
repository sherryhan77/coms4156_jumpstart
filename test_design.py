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

other_user_data = {
    'family_name': 'Mysterious',
    'name': 'Mister Mysterious',
    'email': 'senor@misterioso.mys',
    'given_name': 'Mister'
}

def create_common_context():
    # register student and TA as students
    student = students_model.Student(**student_user_data).get_or_create().register_as_student(uni='student1')
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
    context['student'].destroy()
    context['teacher'].destroy()
    context['ta'].destroy()
    context['course'].destroy()

def add_attendance_records(course, students, num_attendance_recs=1):
    for i in range(num_attendance_recs):
        secret = course.open_session()
        for student in students:
            student.sign_in(course, secret)
        course.close_session()

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
        assert student.takes_course(course), 'Student doesn\'t take course after enrollment'
        assert not student.tas_course(course), 'Student TAs course after only enrollment'
        assert len(student.get_courses()) == 1, 'Student is enrolled in 1 course, but course list is {}'.format(
            student.get_courses()
        )
        assert len(student.get_taed_courses()) == 0, 'Student doesn\'t TA any courses, but TAed course list is {}'.format(
            student.get_taed_courses()
        )

        course.add_TA(student)
        assert course.has_student(student), "Student not reported as enrolled in course after hiring"
        assert course.has_TA(student), 'Student not reported as TA for course after hiring'
        assert student.takes_course(course), 'Student doesn\'t take course after hiring'
        assert len(student.get_courses()) == 1, 'Student is enrolled and hired in 1 course, but course list is {}'.format(
            student.get_courses()
        )
        assert student.tas_course(course), 'Student doesn\'t TA course after hiring'
        assert len(student.get_taed_courses()) == 1, 'Student is enrolled and hired in 1 course, but TAed course list is {}'.format(
            student.get_courses()
        )

        course.add_TA(ta)
        assert not course.has_student(ta), "TA reported as enrolled in course after hiring"
        assert course.has_TA(ta), 'TA not reported as TA for course after hiring'
        assert not ta.takes_course(course), 'TA takes course after only hiring'
        assert ta.tas_course(course), 'TA doesn\'t TA course after hiring'
        assert len(ta.get_taed_courses()) == 1, 'TA is hired in 1 course, but TAed course list is {}'.format(
            ta.get_courses()
        )
        assert len(ta.get_courses()) == 0, 'TA doesn\'t take any courses, but course list is {}'.format(
            student.get_courses()
        )


        course.add_student(ta)
        assert course.has_student(ta), "TA not reported as enrolled in course after enrollment"
        assert course.has_TA(ta), 'TA not reported as TA for course after enrollment'
        assert ta.takes_course(course), 'TA doesn\'t take course after enrollment'
        assert ta.tas_course(course), 'TA no longer TAs course after enrollment'
        assert len(ta.get_courses()) == 1, 'TA is hired and enrolled in 1 course, but course list is {}'.format(
            ta.get_courses()
        )
        assert len(ta.get_taed_courses()) == 1, 'TA is hired and enrolled in 1 course, but TAed course list is {}'.format(
            ta.get_courses()
        )
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
        assert not course.has_student(student), 'Course still has student after dropping'
        assert not student.takes_course(course), 'Student till takes course after dropping'
        assert len(student.get_courses()) == 0, 'Student takes no course, but course list is {}'.format(student.get_courses())
        assert not course.has_TA(ta), 'Course still has TA after firing'
        assert len(ta.get_taed_courses()) == 0, 'TA TAs no course, but TAed course list is {}'.format(ta.get_taed_courses())

        # reuse TA as student-TA
        student_ta = ta
        course.add_student(student_ta)
        course.add_TA(student_ta)
        add_attendance_records(course, [student_ta], 2)
        course.remove_student(student_ta)
        assert course.has_TA(student_ta), 'Course does not have Student-TA after dropping'
        assert student_ta.tas_course(course), 'Student-TA does not TA course after dropping'
        assert len(student_ta.get_taed_courses()) == 1, 'Student-TA TAs one course but TAed course list is {}'.format(student_ta.get_taed_courses())
        assert not course.has_student(student_ta), 'Course has Student-TA after dropping'
        assert not student_ta.takes_course(course), 'Student-TA takes course after dropping'
        assert len(student_ta.get_courses()) == 0, 'Student-TA takes no courses but course list is {}'.format(student_ta.get_courses())

        assert len(course.get_attendance_records(ta=student_ta)) == 2, 'Student-TA\'s records destroyed after dropping class'

        course.add_student(student_ta)
        course.remove_TA(student_ta)

        assert not course.has_TA(student_ta), 'Course has Student-TA after firing'
        assert not student_ta.tas_course(course), 'Student-TA TAs course after firing'
        assert len(student_ta.get_taed_courses()) == 0, 'Student-TA TAs no courses but TAed course list is {}'.format(student_ta.get_taed_courses())
        assert course.has_student(student_ta), 'Course does not have Student-TA after firing'
        assert student_ta.takes_course(course), 'Student-TA does not take course after firing'
        assert len(student_ta.get_courses()) == 1, 'Student-TA takes 1 course but course list is {}'.format(student_ta.get_courses())

        assert len(course.get_attendance_records(ta=student_ta)) == 2, 'Student-TA\'s records destroyed after dropping class'

    finally:
        destroy_context(context)


def test_attendance_taking():
    context = create_common_context()
    student_ta = students_model.Student(**other_user_data).get_or_create().register_as_student(uni='oooh')
    try:
        course = context['course']
        ta = context['ta']
        student = context['student']
        course.add_TA(ta)
        course.add_student(student)
        course.add_TA(student_ta)
        course.add_student(student_ta)

        secret = course.open_session()
        assert course.sign_student_in(student, secret), 'Sign in failed for student with secret gleaned from course.open_session()'
        assert len(course.get_attendance_records()) == 1, 'Signed in student but got {} course attendance records'.format(len(course.get_attendance_records()))
        assert len(course.get_attendance_records(student=student)) == 1, 'Signed in student but got {} student attendance records'.format(len(course.get_attendance_records(student=student)))
        assert course.currently_signed_in(student) and student.is_signed_into(course), 'Student not signed into course after signing in'

        assert ta.sign_in(course, secret), 'Sign in failed for TA with secret gleaned from course.open_session()'
        assert len(course.get_attendance_records()) == 2, 'Signed in TA but got {} course attendance records'.format(len(course.get_attendance_records()))
        assert len(course.get_attendance_records(ta=ta)) == 1, 'Signed in TA but got {} TA attendance records'.format(len(course.get_attendance_records(ta=ta)))
        assert course.currently_signed_in(ta) and ta.is_signed_into(course), 'TA not signed into course after signing in'

        assert student_ta.sign_in(course, secret), 'Sign in failed for Student-TA with secret gleaned from course.open_session()'
        assert len(course.get_attendance_records()) == 3, 'Signed in Student-TA but got {} course attendance records'.format(len(course.get_attendance_records()))
        assert len(course.get_attendance_records(ta=student_ta)) == 1, 'Signed in Student-TA but got {} Student-TA attendance records'.format(len(course.get_attendance_records(student=student_ta)))
        assert course.currently_signed_in(student_ta) and student_ta.is_signed_into(course), 'Student-TA not signed into course after signing in'

        course.close_session()

        with pytest.raises(courses_model.CourseNotTakingAttendance):
            student.sign_in(course, secret)

        with pytest.raises(courses_model.CourseNotTakingAttendance):
            course.sign_student_in(ta, student)

        with pytest.raises(courses_model.CourseNotTakingAttendance):
            course.sign_student_in(student_ta, student)

        assert len(course.get_attendance_records()) == 3, 'Closing attendance window changed number of attendance records to {}'.format(len(course.get_attendance_records()))
        assert len(course.get_attendance_records(ta=ta)) == 1, 'Closing attendance window changed number of TA attendance records to {}'.format(len(course.get_attendance_records(ta=ta)))
        assert len(course.get_attendance_records(student=student)) == 1, 'Closing attendance window changed number of Student attendance records to {}'.format(len(course.get_attendance_records(student=student)))
        assert len(course.get_attendance_records(student=student_ta)) == 1, 'Closing attendance window changed number of Student-TA attendance records to {}'.format(len(course.get_attendance_records(student=student_ta)))
        course.open_session()

        assert len(course.get_attendance_records()) == 3, 'Reopening attendance window changed number of attendance records to {}'.format(len(course.get_attendance_records()))
        assert len(course.get_attendance_records(ta=ta)) == 1, 'Reopening attendance window changed number of TA attendance records to {}'.format(len(course.get_attendance_records(ta=ta)))
        assert len(course.get_attendance_records(student=student)) == 1, 'Reopening attendance window changed number of Student attendance records to {}'.format(len(course.get_attendance_records(student=student)))
        assert len(course.get_attendance_records(student=student_ta)) == 1, 'Reopening attendance window changed number of Student-TA attendance records to {}'.format(len(course.get_attendance_records(student=student_ta)))

        assert ta.sign_in(course), 'Sign in failed for TA with no secret'
        assert len(course.get_attendance_records()) == 4, 'TA sign in without secret did not add to course attendance records'
        assert len(course.get_attendance_records(ta=ta)) == 2, 'TA sign in without secret did not add to TA attendance records'

        assert not student.sign_in(course), 'Sign in succeeded for Student with no secret'
        assert len(course.get_attendance_records()) == 4, 'Student sign in without secret changed course attendance records to'.format(len(course.get_attendance_records()))
        assert len(course.get_attendance_records(student=student)) == 1, 'Student sign in without secret changed student attendance records to {}'.format(len(course.get_attendance_records(student=student)))
    finally:
        student_ta.destroy()
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
