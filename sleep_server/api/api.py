from api import app


@app.route('/')
def hello_world():
    return str.format('Hello World {0} {1}', __name__, app.config['AUTH_HEADER'])
