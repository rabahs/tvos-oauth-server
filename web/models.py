# models.py

import hashlib
import random
from datetime import datetime, timedelta

from app import db


def random_token():
    return hashlib.sha224(str(random.getrandbits(256)).encode('utf-8')).hexdigest()


class App(db.Model):
    __tablename__ = 'apps'
    id = db.Column(db.Integer, primary_key=True, unique=True)
    api_key = db.Column(db.String, primary_key=True, unique=True, default=random_token)
    api_secret = db.Column(db.String, nullable=True, unique=True, default=random_token)
    name = db.Column(db.String, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


db.Index('app_index', App.api_key, unique=True)


class Auth(db.Model):
    __tablename__ = 'auths'

    id = db.Column(db.Integer, primary_key=True, unique=True)
    install_id = db.Column(db.String, primary_key=True, unique=True)
    app_id = db.Column(db.Integer, db.ForeignKey('apps.id'))
    app = db.relationship('App', backref=db.backref('auths', lazy='dynamic'))


    activation_code = db.Column(db.String, index=True)

    auth_provider = db.Column(db.String, nullable=False, default='amazon')
    access_token = db.Column(db.String, nullable=True)
    refresh_token = db.Column(db.String, nullable=True)
    expires_in = db.Column(db.Integer, nullable=True)
    token_created_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def is_active_token(self):
        return self.access_token and datetime.now() - self.token_created_at < timedelta(seconds=self.expires_in)

    def update_from_json(self, json):
        self.access_token = json['access_token']
        self.refresh_token = json['refresh_token']
        self.expires_in = json['expires_in']
        self.token_created_at = datetime.now()
        db.session.commit()

    @staticmethod
    def generate_activation_code():
        return ''.join(random.choice('0123456789ABCDEF') for i in range(8))

    @staticmethod
    def cleanup_activation_codes():
        db.session.query(Auth).filter(Auth.updated_at < datetime.now() - timedelta(minutes=10)).update(
            {Auth.activation_code: None})
        #db.session.commit()


db.Index('app_auth_install_index', Auth.id, Auth.app_id, Auth.install_id, unique=False)



