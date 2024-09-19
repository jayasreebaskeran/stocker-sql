   from flask import Flask
   from flask_sqlalchemy import SQLAlchemy

   app = Flask(__name__)
   app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:Ut2DBsHFM1JZEdEr8mvn@database-1.cp8osk6oad8n.ap-south-1.rds.amazonaws.com/stocker'
   db = SQLAlchemy(app)

   @app.route('/')
   def index():
       return "Database connection successful!"

   if __name__ == '__main__':
       app.run(debug=True)