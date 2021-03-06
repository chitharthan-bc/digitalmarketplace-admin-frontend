from distutils.util import strtobool

from dmutils.email.user_account_email import send_user_account_email
from dmutils.forms.helpers import get_errors_from_wtform
from dmutils.flask import timed_render_template as render_template
from flask import request, redirect, url_for, flash
from flask_login import current_user

from .. import main
from ..auth import role_required
from ..forms import InviteAdminForm, EditAdminUserForm
from ... import data_api_client


INVITATION_SENT_MESSAGE = "An invitation has been sent to {email_address}."
EMAIL_ADDRESS_UPDATED_MESSAGE = "{email_address} has been updated."


@main.route('/admin-users', methods=['GET'])
@role_required('admin-manager')
def manage_admin_users():
    # The API doesn't support filtering users by multiple roles at once, and it's not worth adding that feature
    # just for this one view that (currently, and for the foreseeable future) will be very rarely used.
    # In future, if we have many many admin users and/or this page is heavily used we should:
    # (1) Fix the API to allow fetching all relevant user roles with a single call
    # (2) Stop using the _iter method and properly paginate this page

    support_users = data_api_client.find_users_iter(role='admin')
    category_users = data_api_client.find_users_iter(role='admin-ccs-category')
    sourcing_users = data_api_client.find_users_iter(role='admin-ccs-sourcing')
    framework_manager_users = data_api_client.find_users_iter(role='admin-framework-manager')
    data_controller_users = data_api_client.find_users_iter(role='admin-ccs-data-controller')

    # We want to sort so all Active users are above all Suspended users, and alphabetical by name within these groups.
    # In Python False < True (False is zero, True is one) so sorting on "active is False" puts Active users first.
    admin_users = sorted(
        list(support_users) + list(category_users) +
        list(sourcing_users) + list(framework_manager_users) + list(data_controller_users),
        key=lambda k: (k['active'] is False, k['name'])
    )

    return render_template("view_admin_users.html",
                           admin_users=admin_users)


@main.route('/admin-users/invite', methods=['GET', 'POST'])
@role_required('admin-manager')
def invite_admin_user():
    notify_template_id = '08ab7791-6038-4ad2-9560-740bbcb675b7'

    form = InviteAdminForm()

    if request.method == 'POST' and form.validate_on_submit():
        email_address = form.data.get('email_address')
        role = form.data.get('role')

        send_user_account_email(
            role,
            email_address,
            notify_template_id,
            personalisation={'name': current_user.name}
        )
        flash(INVITATION_SENT_MESSAGE.format(email_address=email_address))
        return redirect(url_for('main.manage_admin_users'))

    errors = get_errors_from_wtform(form)

    return render_template(
        "invite_admin_user.html",
        form=form,
        errors=errors,
    ), 200 if not errors else 400


@main.route("/admin-users/<string:admin_user_id>/edit", methods=["GET", "POST"])
@role_required("admin-manager")
def edit_admin_user(admin_user_id):
    admin_user = data_api_client.get_user(admin_user_id)["users"]
    status_code = 200
    edit_admin_user_form = EditAdminUserForm(
        edit_admin_name=admin_user["name"],
        edit_admin_permissions=admin_user["role"],
        edit_admin_status=admin_user["active"])

    if edit_admin_user_form.validate_on_submit():
        edited_admin_name = edit_admin_user_form.edit_admin_name.data
        edited_admin_permissions = edit_admin_user_form.edit_admin_permissions.data
        edited_admin_status = bool(strtobool(edit_admin_user_form.edit_admin_status.data))

        data_api_client.update_user(
            admin_user_id,
            name=edited_admin_name,
            role=edited_admin_permissions,
            active=edited_admin_status
        )
        flash(EMAIL_ADDRESS_UPDATED_MESSAGE.format(email_address=admin_user["emailAddress"]))
        return redirect(url_for('.manage_admin_users'))
    elif edit_admin_user_form.edit_admin_name.errors:
        status_code = 400

    return render_template(
        "edit_admin_user.html",
        admin_user=admin_user,
        edit_admin_user_form=edit_admin_user_form,
    ), status_code
