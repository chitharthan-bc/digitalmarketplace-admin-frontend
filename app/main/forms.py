from wtforms import RadioField, validators
from flask.ext.wtf import Form
from wtforms.validators import DataRequired
from dmutils.forms import StripWhitespaceStringField

from .. import data_api_client


class AdminEmailAddressValidator(object):

    def __init__(self, message=None):
        self.message = message

    def __call__(self, form, field):
        if not data_api_client.email_is_valid_for_admin_user(field.data):
            raise validators.StopValidation(self.message)


class EmailAddressForm(Form):
    email_address = StripWhitespaceStringField('Email address', validators=[
        validators.DataRequired(message="Email can not be empty"),
        validators.Email(message="Please enter a valid email address")
    ])


class MoveUserForm(Form):
    user_to_move_email_address = StripWhitespaceStringField('Move an existing user to this supplier', validators=[
        validators.DataRequired(message="Email can not be empty"),
        validators.Email(message="Please enter a valid email address")
    ])


class EmailDomainForm(Form):
    new_buyer_domain = StripWhitespaceStringField('Add a buyer email domain', validators=[
        validators.DataRequired(message="The domain field can not be empty.")
    ])


class InviteAdminForm(Form):
    role_choices = [
        ('admin-ccs-category', 'Category'),
        ('admin-framework-manager', 'Framework Manager'),
        ('admin-ccs-sourcing', 'Sourcing'),
        ('admin', 'Support'),
    ]

    email_address = StripWhitespaceStringField(
        'Email address',
        validators=[
            validators.DataRequired(message='You must provide an email address'),
            validators.Email(message='Please enter a valid email address'),
            AdminEmailAddressValidator(message='The email address must belong to an approved domain')
        ]
    )
    role = RadioField(
        'Permissions',
        validators=[validators.InputRequired(message='You must choose a permission')],
        choices=role_choices
    )

    def __init__(self, *args, **kwargs):
        super(InviteAdminForm, self).__init__(*args, **kwargs)
        self.role.toolkit_macro_options = [{'value': i[0], 'label': i[1]} for i in self.role_choices]


class EditAdminUserForm(Form):
    edit_admin_name = StripWhitespaceStringField('Name', validators=[
        DataRequired(message="You must provide a name.")
    ])

    permissions_choices = [
        ("admin-ccs-category", "Category"),
        ("admin-ccs-sourcing", "Sourcing"),
        ("admin", "Support"),
    ]

    edit_admin_permissions = RadioField('Permissions', choices=permissions_choices)

    status_choices = [
        ("True", "Active"),
        ("False", "Suspended"),
    ]

    edit_admin_status = RadioField('Status', choices=status_choices)

    def __init__(self, *args, **kwargs):
        super(EditAdminUserForm, self).__init__(*args, **kwargs)
        self.edit_admin_permissions.toolkit_macro_options = [
            {'value': choice[0], 'label': choice[1]} for choice in self.permissions_choices
        ]
        self.edit_admin_status.toolkit_macro_options = [
            {'value': choice[0], 'label': choice[1]} for choice in self.status_choices
        ]
