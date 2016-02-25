from api import app

if __name__ == '__main__':
    app.run(app.config['HOST_NAME'], debug=app.config['DEBUG'])
