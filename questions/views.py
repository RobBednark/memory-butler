from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max, Min
from django.forms.models import modelformset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render

from .forms import FormAttempt, ModelFormSchedule
from .models import Attempt, Question, QuestionTag, Tag, User, UserTag

def _next_question(user):
    ''' Find and return the next question for the currently logged-in user.
    '''
    '''
        Query for all questions that contain at least one of the UserTags
        Input:
            UserTags with enabled=True
        Output:
            questions that have one or more QuestionTag's 
            WHERE 
                QuestionTag.enabled=True
            AND
                QuestionTag.

    '''

    # Find all the tags that the user has selected
    user_tags = UserTag.objects.filter(user=user, enabled=True)
    # Find all the QuestionTag's that the user selected that are  associated with selected tags
    question_tags = QuestionTag.objects.filter(enabled=True, tag__in=user_tags)
    # Also get the questions so that we don't need to do additional queries
    question_tags = question_tags.select_related('question')

    # Find the newest attempt for each question.
    question_tags = question_tags.annotate(attempt_newest=Max('question__attempt__datetime_added'))

    # First look for questions without any attempts, ordered oldest to newest.
    question_tags_no_attempt = question_tags.filter(attempt_newest=None).order_by('question__datetime_added')
    # If there is a question with no attempts, then use that one.
    if question_tags_no_attempt:
        # This will be the question with the oldest datetime_added
        question = question_tags_no_attempt[0].question
        return question
    else:
        # Assert: there are no questions with no attempts
        # Find the oldest attempt of all the newest attempts
        # order_by defaults to ascending order (oldest to newest dates)
        question_tags = question_tags.order_by('attempt_newest')
        question = question_tags[0].question if question_tags else None
        return question


def _create_and_get_usertags(request):
    ModelFormset_UserTag = modelformset_factory(model=UserTag,
                                                extra=0,
                                                fields=('enabled',))
    user = request.user
    queryset=UserTag.objects.filter(user=user).order_by('tag__name')
    if request.method == 'GET':
        # Get the user, find all the tags, and create a form for each tag.
        #        GET:
        #            For each of the tags, show a checkbox.
        #            If there is no UserTag for that tag, then show the tag and default to False.

        # Get all the Tag's
        tags = Tag.objects.all()

        # Get all the UserTag's associated with this user
        qs_user_tags = UserTag.objects.filter(user=user)
        user_tags_by_tagname = { user_tag.tag.name : user_tag for user_tag in qs_user_tags }

        # Create UserTag's for any new tags
        for tag in tags:
            if not tag.name in user_tags_by_tagname:
                # There isn't a tag, so create one
                UserTag(user=user, tag=tag, enabled=False).save()

        modelformset_usertag = ModelFormset_UserTag(queryset=queryset)
        for form in modelformset_usertag.forms:
            form.fields['enabled'].label = form.instance.tag.name

        return modelformset_usertag
    elif request.method == 'POST':
        modelformset_usertag = ModelFormset_UserTag(queryset=queryset, data=request.POST)
        for form in modelformset_usertag.forms:
            form.fields['enabled'].label = form.instance.tag.name

        if modelformset_usertag.is_valid(): # All validation rules pass
            modelformset_usertag.save()
        else:
            # ASSERT: modelformset_usertag.is_valid() was called, so modelformset_usertag modified itself to contain
            # any errors, and these errors will be displayed in the form using the form.as_p
            # attribute.
            #  It puts the errors in form._errors and form.errors, 
            #   e.g., form.errors['sender'] == 'Enter a valid email address.'
            pass
        return modelformset_usertag

@login_required(login_url='/login')
def view_quiz(request):
    modelformset_usertag = _create_and_get_usertags(request=request)

    if request.method == 'GET':
        # For a GET, show the next question
        question = _next_question(user=request.user)
        form_attempt = FormAttempt()
        if question:
            form_attempt.fields['hidden_question_id'].initial = question.id
        else:
            form_attempt.fields['hidden_question_id'].initial = None
        return render(request=request, 
                      template_name='show_question.html', 
                      dictionary=dict(form_attempt=form_attempt, 
                                      modelformset_usertag=modelformset_usertag,
                                      question=question))
    elif request.method == 'POST':
        # ASSERT: this is a POST, so the user answered a question
        # Show the correct answer, the user's attempt, and the question
        # Show a NEXT button to do a GET and get the next question
        form_attempt = FormAttempt(request.POST)
        if form_attempt.is_valid():
            question_id = form_attempt.cleaned_data['hidden_question_id']
            question = Question.objects.get(id=question_id)
            attempt = Attempt(attempt=form_attempt.cleaned_data['attempt'],
                              question=question,
                              user=request.user)
            try:
                attempt.save()
            except Exception as exception:
                pass
            # Show a page that shows their attempt, the correct answer, the question, and a NEXT button
            return render(request=request, 
                          template_name='show_question_and_answer.html', 
                          dictionary=dict(form_attempt=form_attempt, 
                                          modelformset_usertag=modelformset_usertag,
                                          question=question,
                                          answer=question.answer,
                                          attempt=attempt,
                                         ))
        else:
            # Assert: form is NOT valid
            # Need to return the errors to the template, and have the template show the errors.
            return render(request=request, 
                          template_name='show_question.html', 
                          dictionary=dict(form_attempt=form_attempt, 
                                         ))
    else:
        raise Exception("Unknown request.method=[%s]" % request.method)

@login_required(login_url='/login')
def question_next(request):
    # get the next question and redirect to it
    question = _next_question(user=request.user)
    return HttpResponseRedirect(reverse('question_new', args=(question.id,)))

@login_required(login_url='/login')
def question(request, id_question):
    modelformset_usertag = _create_and_get_usertags(request=request)

    if request.method == 'GET':
        # For a GET, show the next question
        question = _next_question(user=request.user)
        form_attempt = FormAttempt()
        if question:
            form_attempt.fields['hidden_question_id'].initial = question.id
        else:
            form_attempt.fields['hidden_question_id'].initial = None
        return render(request=request, 
                      template_name='show_question.html', 
                      dictionary=dict(form_attempt=form_attempt, 
                                      modelformset_usertag=modelformset_usertag,
                                      question=question))
    elif request.method == 'POST':
        # ASSERT: this is a POST, so the user answered a question
        # Show the correct answer, the user's attempt, and the question
        # Show a NEXT button to do a GET and get the next question
        form_attempt = FormAttempt(request.POST)
        if form_attempt.is_valid():
            question_id = form_attempt.cleaned_data['hidden_question_id']
            question = Question.objects.get(id=question_id)
            attempt = Attempt(attempt=form_attempt.cleaned_data['attempt'],
                              question=question,
                              user=request.user)
            try:
                attempt.save()
            except Exception as exception:
                # TODO: do something else here, e.g., log it, show it to the user  -Rob Bednark 12/21/14
                pass
            # Redirect to the answer page
            return HttpResponseRedirect(reverse('answer', args=(attempt.id,)))
        else:
            # Assert: form is NOT valid
            # Need to return the errors to the template, and have the template show the errors.
            return render(request=request, 
                          template_name='show_question.html', 
                          dictionary=dict(form_attempt=form_attempt, 
                                         ))
    else:
        raise Exception("Unknown request.method=[%s]" % request.method)

def answer(request, id_attempt):
    modelformset_usertag = _create_and_get_usertags(request=request)
    modelform_schedule = ModelFormSchedule(request.POST)
    if request.method == 'GET':
        return render(request=request, 
                      template_name='answer.html', 
                      dictionary=dict(modelform_schedule=modelform_schedule,
                                      modelformset_usertag=modelformset_usertag))
    elif request.method == 'POST':
        # ASSERT: this is a POST, so the user answered a question
        # Show the correct answer, the user's attempt, and the question
        # Show a NEXT button to do a GET and get the next question
        if modelform_schedule.is_valid():
            question_id = form_answer.cleaned_data['hidden_question_id']
            question = Question.objects.get(id=question_id)
            schedule = Schedule(attempt=form_answer.cleaned_data['attempt'],
                              question=question,
                              user=request.user)
            modelform_schedule.save()
            try:
                schedule.save()
            except Exception as exception:
                pass
            # Redirect to the next question
            # TODO
            pass
        else:
            # Assert: form is NOT valid
            # Need to return the errors to the template, and have the template show the errors.
            return render(request=request, 
                          template_name='answer.html', 
                          dictionary=dict(form_answer=form_answer, 
                                         ))
    else:
        raise Exception("Unknown request.method=[%s]" % request.method)
