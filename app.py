from flask import Flask, request, jsonify, render_template
import time
from backend.pipeline import GithubPipeline
import yaml

app = Flask(__name__)

usernames = []

@app.route('/')
def home():
    return render_template('homepage.html')

@app.route('/url', methods=['POST'])
def url():
    if request.method == 'POST':
        url = request.form['url']
        msg = 'Please enter a username'
        if url:
            usernames.append(url)
            msg = "Username Submitted!"
    return render_template('url.html', msg=msg)


@app.route('/pipeline', methods=['POST'])
def run_pipeline():
    if request.method == 'POST':
        time.sleep(20)
        # Extract data from the request
        username =  usernames[-1]

        url = f'https://github.com/{username}/'

        
        # getting API Keys
        with open("keys.yml", 'r') as f:
            keys = yaml.safe_load(f)

        # Perform pipeline operations on the data
        gp = GithubPipeline(username, keys)

        result, justification = gp.pipeline()
        final_url = url+result

        # Return the rendered template
    return render_template('pipeline.html', text=final_url, justification=justification)


if __name__ == '__main__':
    app.run()