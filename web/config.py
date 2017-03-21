# config.py
import os


class BaseConfig(object):
    SECRET_KEY = os.environ['SECRET_KEY']
    DEBUG = os.environ['DEBUG']
    DB_NAME = os.environ['DB_NAME']
    DB_USER = os.environ['DB_USER']
    DB_PASS = os.environ['DB_PASS']
    DB_SERVICE = os.environ['DB_SERVICE']
    DB_PORT = os.environ['DB_PORT']
    SQLALCHEMY_DATABASE_URI = 'postgresql://{0}:{1}@{2}:{3}/{4}'.format(
        DB_USER, DB_PASS, DB_SERVICE, DB_PORT, DB_NAME
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    REDIS_HOST = os.environ['REDIS_HOST']
    REDIS_PORT = os.environ['REDIS_PORT']

    AMAZON = {
        'CLIENT_ID':  os.environ['AWS_CLIENT_ID'],
        'CLIENT_SECRET': os.environ['AWS_CLIENT_SECRET'],
        'AUTHORIZE_URL': 'https://www.amazon.com/ap/oa?',
        'TOKEN_URL': 'https://api.amazon.com/auth/o2/token',
        'SCOPE': 'clouddrive:read_image clouddrive:read_video'
    }

    DROPBOX = {
        'CLIENT_ID':  os.environ['DROPBOX_CLIENT_ID'],
        'CLIENT_SECRET': os.environ['DROPBOX_CLIENT_SECRET'],
        'AUTHORIZE_URL': 'https://www.dropbox.com/oauth2/authorize?',
        'TOKEN_URL': 'https://www.dropbox.com/oauth2/token'
    }


    PUBLIC_URL = os.environ['PUBLIC_URL']

