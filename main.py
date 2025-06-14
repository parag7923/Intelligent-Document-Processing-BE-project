from flask import Flask, render_template
from translation.app import translation_bp
from ner.app import ner_bp
from chatbot.app import chatbot_bp

app = Flask(__name__)

app.register_blueprint(translation_bp, url_prefix='/translation')
app.register_blueprint(ner_bp, url_prefix='/ner')
app.register_blueprint(chatbot_bp, url_prefix='/chatbot')

@app.route('/')
def main_index():
    return render_template('main/index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
