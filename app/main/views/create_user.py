from flask import abort, current_app, flash, render_template, Markup
from flask_login import login_user

from dmapiclient import HTTPError
from dmutils.email import decode_invitation_token
from dmutils.user import User

from .. import main
from ..forms.auth_forms import CreateUserForm
from ..helpers.login_helpers import redirect_logged_in_user
from ... import data_api_client


INVALID_TOKEN_MESSAGE = Markup(
    """The link you used to create an account is not valid. Check you’ve entered the correct link.
    If you still can’t create an account, email
    <a href="mailto:enquiries@digitalmarketplace.service.gov.uk">enquiries@digitalmarketplace.service.gov.uk</a>
    """
)


@main.route('/create/<string:encoded_token>', methods=["GET"])
def create_user(encoded_token):
    token = decode_invitation_token(encoded_token)

    if token.get('error') == 'token_invalid':
        current_app.logger.warning(
            "createuser.token_invalid: {encoded_token}",
            extra={'encoded_token': encoded_token}
        )
        abort(400, INVALID_TOKEN_MESSAGE)

    role = token["role"]

    if token.get('error') == 'token_expired':
        current_app.logger.warning(
            "createuser.token_expired: {encoded_token}",
            extra={'encoded_token': encoded_token}
        )
        return render_template(
            "auth/create-user-error.html",
            error=None,
            role=role,
            token=None,
            user=None), 400

    form = CreateUserForm()

    user_json = data_api_client.get_user(email_address=token["email_address"])

    if not user_json:
        return render_template(
            "auth/create-user.html",
            email_address=token['email_address'],
            form=form,
            role=role,
            supplier_name=token.get('supplier_name'),
            token=encoded_token), 200

    user = User.from_json(user_json)
    return render_template(
        "auth/create-user-error.html",
        error=None,
        role=role,
        token=token,
        user=user), 400


@main.route('/create/<string:encoded_token>', methods=["POST"])
def submit_create_user(encoded_token):
    token = decode_invitation_token(encoded_token)

    if token.get('error') == 'token_invalid':
        current_app.logger.warning(
            "createuser.token_invalid: {encoded_token}",
            extra={'encoded_token': encoded_token}
        )
        abort(400, INVALID_TOKEN_MESSAGE)

    role = token["role"]

    if token.get('error') == 'token_expired':
        current_app.logger.warning(
            "createuser.token_expired: {encoded_token}",
            extra={'encoded_token': encoded_token}
        )
        return render_template(
            "auth/create-user-error.html",
            error=None,
            role=role,
            token=None,
            user=None), 400

    form = CreateUserForm()

    if not form.validate_on_submit():
        current_app.logger.warning(
            "createuser.invalid: {form_errors}",
            extra={'form_errors': ", ".join(form.errors)})
        return render_template(
            "auth/create-user.html",
            email_address=token['email_address'],
            form=form,
            role=role,
            supplier_name=token.get('supplier_name'),
            token=encoded_token), 400

    try:
        user_data = {
            'name': form.name.data,
            'password': form.password.data,
            'emailAddress': token['email_address'],
            'role': role
        }

        if role == 'buyer':
            user_data.update({'phoneNumber': form.phone_number.data})
        elif role == 'supplier':
            user_data.update({'supplierId': token['supplier_id']})

        user_create_response = data_api_client.create_user(user_data)
        user = User.from_json(user_create_response)
        login_user(user)

    except HTTPError as e:
        if e.status_code == 409 or e.message == 'invalid_buyer_domain':
            return render_template(
                "auth/create-user-error.html",
                error=e.message,
                role=role,
                token=None), 400
        else:
            raise

    flash('account-created', 'flag')
    return redirect_logged_in_user()
