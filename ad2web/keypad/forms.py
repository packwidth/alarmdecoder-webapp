# -*- coding: utf-8 -*-

from flask.ext.wtf import Form
from flask.ext.wtf.html5 import URLField, EmailField, TelField
from wtforms import (ValidationError, HiddenField, TextField, HiddenField,
        PasswordField, SubmitField, TextAreaField, IntegerField, RadioField,
        FileField, DecimalField, BooleanField, SelectField, FormField, FieldList)
from wtforms.validators import (Required, Length, EqualTo, Email, NumberRange, URL, AnyOf, Optional)
from flask.ext.login import current_user

from ..user import User
from ..utils import PASSWORD_LEN_MIN, PASSWORD_LEN_MAX, AGE_MIN, AGE_MAX, DEPOSIT_MIN, DEPOSIT_MAX

from ..widgets import ButtonField

class KeypadButtonForm(Form):
    label = TextField(u'Label', [Required(), Length(max=32)])
    code = TextField(u'Code', [Required(), Length(max=32)])

    submit = SubmitField(u'Save')
    cancel = ButtonField(u'Cancel', onclick="location.href='/keypad/button_index'") 
