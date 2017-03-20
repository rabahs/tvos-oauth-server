# manage.py

from flask_script import Manager

from app import app
from models import *

manager = Manager(app)


@manager.option('-n', '--name', help='Your app name')
def create_app(name):
    app = App(name=name)
    db.session.add(app)
    db.session.commit()
    print("created app {} with api_key= {}  \n api_secret= {}".format(app.name, app.api_key, app.api_secret))

if __name__ == "__main__":
    manager.run()
