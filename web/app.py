# app.py

from datetime import datetime
import hashlib
import logging
import urllib
import json

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
    code = request.form['activation_code']
    if code is None:
        flash('Activation code is not set', 'danger')
        return redirect(url_for('show_activate'))

    # Verify if activation code is in Redis
    if not app.redis.exists("code:" + code):
        flash('Activation code is not recognized or expired, try to sign in again', 'danger')
        return redirect(url_for('show_activate'))

    # TODO: Store client_id in db to support multiple accounts

    params = {
        'client_id': app.config['AWS']['CLIENT_ID'],
        'scope': 'clouddrive:read_image clouddrive:read_video',
        'response_type': 'code',
        'redirect_uri': url_for('authenticated', _external=True, _scheme='https'),
        'state': code  # pass the activation code as a state
    }
    url = app.config['AWS']['LOGIN_URL'] + urllib.parse.urlencode(params)
    return redirect(url)


@app.route('/activate_device', methods=['GET'])
def activate_device():
    authenticate_request()
    if request.args.get('install_id') is None:
        raise ApiError('request missing install_id', 404)

    new_code = ''.join(random.choice('0123456789ABCDEF') for i in range(8))
    app.logger.warning('code is %s ', new_code)

    creds = {'activation_code': new_code}

    app.redis.setex("code:" + creds['activation_code'], ACTIVATION_CODE_EXPIRES_IN, creds)
    app.logger.warning('redis set')

    return response(200, payload={
        'activation_code': creds['activation_code'],
        'activation_url': url_for('activate', _external=True, _scheme='https')
    })


@app.route('/authenticated')
def authenticated():
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

    creds = eval(creds)
    # Exchange auth code for tokens
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    params = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'client_id': app.config['AWS']['CLIENT_ID'],
        'client_secret': app.config['AWS']['CLIENT_SECRET'],
        'redirect_uri': url_for('authenticated', _external=True, _scheme='https')
    }
    res = requests.post(app.config['AWS']['TOKEN_URL'], headers=headers, data=params)
    if res is None:
        raise ApiError('Problem authenticating with Amazon', 404)

    json_res = res.json()
    creds['access_token'] = json_res['access_token']
    creds['refresh_token'] = json_res['refresh_token']
    creds['expires_in'] = json_res['expires_in']
    creds['token_created_at'] = json.dumps(datetime.now().isoformat())

    app.redis.setex("code:" + activation_code, ACTIVATION_CODE_EXPIRES_IN, creds)
    flash('You were successfully logged in', 'success')
    return render_template('activated.html')


# Get oAuth credentials if ready
@app.route('/oauth', methods=['GET'])
def oauth():
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
    creds = eval(creds)
    if 'access_token' not in creds:
        return response(202, 'access_token not ready yet for the supplied activation_code')

    payload = {
        'access_token': creds['access_token'],
        'refresh_token': creds['refresh_token'],
        'expires_in': creds['expires_in'],
        'created_at': creds['token_created_at'],
        'client_id': app.config['AWS']['CLIENT_ID'],
        'client_secret': app.config['AWS']['CLIENT_SECRET']
    }
    return response(200, payload=payload)



def authenticate_request():
    api_key = request.headers.get('X-TVOAUTH-API-KEY')
    api_sig = request.headers.get('X-TVOAUTH-API-SIG')
    # app.logger.warning('key %s sig %s', api_key, api_sig)
    # app.logger.warning(request.headers)
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
