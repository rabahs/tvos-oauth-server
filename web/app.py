# app.py

from datetime import datetime
import hashlib
import logging
import urllib
import json


import pickle
import requests
import redis
from flask import Flask, flash, request, redirect, render_template, jsonify, g, url_for


from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config.from_object('config.BaseConfig')
db = SQLAlchemy(app)
app.redis = redis.StrictRedis(host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT'], db=0)
from models import *


ACTIVATION_CODE_EXPIRES_IN = 5 * 60


@app.route('/')
@app.route('/activate')
def show_activate():
    return render_template('activate.html')


@app.route('/activate', methods=['POST'])
def activate():
    activation_code = request.form['activation_code']
    if activation_code is None:
        flash('Activation code is not set', 'danger')
        return redirect(url_for('show_activate'))

    # Verify if activation code is in Redis
    creds = app.redis.get("code:" + activation_code)
    if creds is None:
        flash('Activation code is not recognized or expired, try to sign in again', 'danger')
        return redirect(url_for('show_activate'))
    creds = pickle.loads(creds)
    provider = creds['provider']
    params = {
        'client_id': app.config[provider]['CLIENT_ID'],
        'response_type': 'code',
        'redirect_uri': url_for('authenticated', _external=True, _scheme='https'),
        'state': activation_code  # pass the activation code as a state
    }

    if 'scope' in creds:
        params['scope'] = creds['scope']

    url = app.config[provider]['AUTHORIZE_URL'] + urllib.parse.urlencode(params)
    return redirect(url)


@app.route('/activate_device', methods=['GET'])
def activate_device():
    """ Authorize a user on a device
        install_id: a unique device id from requesting device
        provider: oauth2 provider: e.g. 'amazon'
        scope: requested scope to authorize for

    :return
         activation_code
         activation_url
     """
    authenticate_request()

    install_id = request.args.get('install_id')
    if install_id is None:
        raise ApiError('request missing install_id', 404)

    provider = request.args.get('provider')
    if provider is None:
        raise ApiError('request missing provider', 404)
    provider = provider.upper()

    activation_code = ''.join(random.choice('0123456789ABCDEF') for i in range(8))

    creds = {
    	'activation_code': activation_code,
        'install_id': install_id,
        'provider': provider
    }

    scope = request.args.get('scope')
    if scope:
        creds['scope'] = scope

    creds = pickle.dumps(creds)

    app.redis.setex("code:" + activation_code, ACTIVATION_CODE_EXPIRES_IN, creds)

    return response(200, payload={
        'activation_code': activation_code,
        'activation_url': url_for('activate', _external=True, _scheme='https')
    })


@app.route('/authenticated')
def authenticated():
    """ OAuth2 callback
            code:
            state:
            error:
            error_description:
        """
    if request.args.get('error') is not None:
        raise ApiError("{0} : {1}".format(request.args.get('error'), request.args.get('error_description')))

    auth_code = request.args.get('code')
    if auth_code is None:
        raise ApiError('No OAuth code is passed from provider', 404)

    activation_code = request.args.get('state')
    if activation_code is None:
        raise ApiError('Could not get retrieve state for this auth request', 404)

    # Verify if activation code is valid
    creds = app.redis.get("code:" + activation_code)
    if creds is None:
        raise ApiError('Activation code is not recognized or expired, try to sign in again', 404)

    creds = pickle.loads(creds)

    provider = creds['provider']

    # Exchange auth code for tokens
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    params = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'client_id': app.config[provider]['CLIENT_ID'],
        'client_secret': app.config[provider]['CLIENT_SECRET'],
        'redirect_uri': url_for('authenticated', _external=True, _scheme='https')
    }
    res = requests.post(app.config[provider]['TOKEN_URL'], headers=headers, data=params)
    if res is None:
        raise ApiError('Problem authenticating with Amazon', 404)

    json_res = res.json()
    creds['access_token'] = json_res['access_token']
    if 'refresh_token' in json_res:
        creds['refresh_token'] = json_res['refresh_token']
    if 'expires_in' in json_res:
        creds['expires_in'] = json_res['expires_in']
    creds['token_created_at'] = json.dumps(datetime.now().isoformat())

    creds = pickle.dumps(creds)
    app.redis.setex("code:" + activation_code, ACTIVATION_CODE_EXPIRES_IN, creds)
    flash('You were successfully logged in', 'success')
    return render_template('activated.html')


# Poll for OAuth credentials
@app.route('/oauth', methods=['GET'])
def oauth():
    """ An endpoint for devices to periodically poll for oauth credentials (it gets set upon successful login)
           install_id: a unique device id from requesting device
       :return
            access_token
            refresh_token
            expires_in
            created_at
            client_id
            client_secret
        """
    authenticate_request()
    install_id = request.args.get('install_id')
    if install_id is None:
        raise ApiError("request missing install_id", 404)
    activation_code = request.args.get('activation_code')
    if activation_code is None:
        raise ApiError("activation_code is missing", 404)
    creds = app.redis.get("code:" + activation_code)
    if creds is None:
        raise ApiError("Not Authorized", 401)

    creds = pickle.loads(creds)

    provider = creds['provider']
    if 'access_token' not in creds:
        return response(202, 'access_token not ready yet for the supplied activation_code')

    payload = {
        'access_token': creds['access_token'],
        'created_at': creds['token_created_at'],
        'client_id': app.config[provider]['CLIENT_ID'],
        'client_secret': app.config[provider]['CLIENT_SECRET']
    }
    if 'refresh_token' in creds:
        payload['refresh_token'] = creds['refresh_token']

    if 'expires_in' in creds:
        payload['expires_in'] = creds['expires_in']

    return response(200, payload=payload)


def authenticate_request():
    api_key = request.headers.get('X-TVOSOAUTH-API-KEY')
    api_sig = request.headers.get('X-TVOSOAUTH-API-SIG')

    current_app = db.session.query(App).filter_by(api_key=api_key).one_or_none()

    if current_app is None:
        raise ApiError('Unauthorized', status_code=401)

    joined_params = '&'.join('{}&{}'.format(key, val) for key, val in sorted(request.args.items()))
    raw_params = joined_params + "&" + current_app.api_secret

    signature = hashlib.sha1(raw_params.encode('utf-8')).hexdigest()
    if signature != api_sig:
        raise ApiError('Unauthorized', status_code=401)

    g.current_app = current_app


def response(status, message=None, payload=None):
    if message:
        res = jsonify({'status': status, 'message': message})
    else:
        payload['status'] = status
        res = jsonify(payload)

    res.status_code = status
    return res


class ApiError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@app.errorhandler(ApiError)
def handle_api_error(error):
    res = jsonify(error.to_dict())
    res.status_code = error.status_code
    res.mimetype = 'application/json'
    return res


@app.errorhandler(500)
def internal_server_error(e):
    res = jsonify({'status': 500, 'error': 'internal server error', 'message': e.args[0]})
    res.status_code = 500
    res.mimetype = 'application/json'
    return res


@app.before_first_request
def setup_logging():
    # if not app.debug: # In production mode, add log handler to sys.stderr.
    app.logger.addHandler(logging.StreamHandler())
    app.logger.setLevel(logging.WARNING)
    app.logger.warning("logging enabled")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9001, debug=False, use_reloader=True)
