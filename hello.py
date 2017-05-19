from flask import Flask, render_template
from flask_bootstrap import Bootstrap
from models import init_database, Post

app = Flask(__name__)
Bootstrap(app)
init_database('postgres', 'postgres-credentials.json')

@app.route('/')
def hello_world():
    #return 'Not dead. Yet.'
    ten = Post.select().where(Post.title.contains('Django')).limit(10)
    print(ten[0].title)
    return render_template('index.html',results=ten)

if __name__ == "__main__":
    app.run()


