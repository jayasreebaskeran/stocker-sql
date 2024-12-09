from flask import Flask, render_template, jsonify, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user, UserMixin, login_user, logout_user
import requests
import os
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
import random
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Load environment variables
DB_USER = os.environ.get("DB_USER", "admin")  # Default to "admin" if DB_USER is not set
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mega2203")  # Default to "RamyaRani2005" if not set
DB_HOST = os.environ.get("DB_HOST", "localhost")  # Default to "localhost" if not set
DB_NAME = os.environ.get("DB_NAME", "stocker")  # Default to "stocker" if not set
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "4QITL9CQJ51G81D2")  # Default API key

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "your_secret_key_here")  # Replace with a real secret key

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Add this function to create tables
def create_tables():
    try:
        with app.app_context():
            db.create_all()
    except Exception as e:
        print(f"Error while connecting to the database: {e}")

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=0.0)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    action = db.Column(db.String(4), nullable=False)  # 'buy' or 'sell'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Transaction {self.id}: {self.action} {self.shares} shares of {self.symbol}>'

class StockTransactionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(4), nullable=False)  # 'buy' or 'sell'
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class TransactionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'deposit' or 'withdraw'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class StockPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    exchange = db.Column(db.String(10), nullable=False)
    asset_type = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<StockPrice {self.id}: {self.symbol} at ${self.price}>'

# Helper functions
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_stock_price(symbol):
    # Check if the stock price is already in the database
    stock_price = StockPrice.query.filter_by(symbol=symbol).first()
    if stock_price:
        return stock_price.price
    else:
        # If not, fetch the price and store it in the database
        url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}'
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            price = float(data["Global Quote"]["05. price"])
            return price
        else:
            return random.randint(1, 100)

def update_portfolio(user_id, symbol, shares, action):
    user = User.query.get(user_id)
    stock_price = get_stock_price(symbol)  # Fetch stock price here
    if stock_price is None:  # Check if stock price retrieval failed
        return 0
    if action == 'buy':
        user.balance = current_user.balance
    elif action == 'sell':
        user.balance = current_user.balance
        # Remove shares from the transaction records
        transaction = Transaction.query.filter_by(user_id=user_id, symbol=symbol, action='buy').first()
        if transaction:
            transaction.shares -= shares
            if transaction.shares <= 0:
                db.session.delete(transaction)  # Remove transaction if no shares left
    db.session.commit()

def has_enough_shares(user_id, symbol, shares):
    existing_shares = Transaction.query.filter_by(user_id=user_id, symbol=symbol, action='buy').with_entities(db.func.sum(Transaction.shares)).scalar()
    if existing_shares is None:
        existing_shares = 0
    return existing_shares >= shares

def get_nasdaq_stocks():
    # Fetch NASDAQ stocks and their prices, and store them in the database
    if StockPrice.query.count() != 0:
        return StockPrice.query.all()
    else:
        url = f'https://www.alphavantage.co/query?function=LISTING_STATUS&market=NASDAQ&apikey={ALPHA_VANTAGE_API_KEY}'
        response = requests.get(url)
        if response.status_code == 200:
            stocks = []
            lines = response.text.strip().split('\n')
            headers = lines[0].split(',')
            for line in lines[1:]:
                values = line.split(',')
                stock = dict(zip(headers, values))
                stocks.append(stock)
                stock_price = get_stock_price(stock['symbol'])
                # Check if the stock is already in the database
                existing_stock = StockPrice.query.filter_by(symbol=stock['symbol']).first()
                if existing_stock:
                    # If it is, update its price and other details
                    existing_stock.price = float(stock_price)
                    existing_stock.name = stock['name']
                    existing_stock.exchange = stock['exchange']
                    existing_stock.asset_type = stock['assetType']
                    existing_stock.status = stock['"status\r"']
                    db.session.commit()
                else:
                    # If not, add it to the database
                    symbol = stock['symbol']
                    name = stock['name']
                    exchange = stock['exchange']
                    asset_type = stock['assetType']
                    status = stock["status\r"]
                    price = float(stock_price)
                    new_stock_price = StockPrice(symbol=symbol, name=name, exchange=exchange, asset_type=asset_type, status=status, price=price)
                    db.session.add(new_stock_price)
                    db.session.commit()
            return stocks
        else:
            return []

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('portfolio'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        # Add more fields as necessary
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists', 'error')
        else:
            new_user = User(username=username, password=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            flash('Registered successfully', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()  # This will log out the user
    return redirect(url_for('index'))  # Redirect to the index page

@app.route('/add_stock', methods=['GET', 'POST'])
@login_required
def add_stock():
    if request.method == 'POST':
        symbol = request.form['symbol']
        quantity = request.form['quantity']
        # Add logic to add stock to user's portfolio
        flash('Stock added successfully', 'success')
        return redirect(url_for('portfolio'))
    return render_template('add_stock.html')


@app.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/portfolio')
@login_required
def portfolio():
    user_balance = current_user.balance
    user_stocks = Transaction.query.filter_by(user_id=current_user.id, action='buy').all()
    transaction_history = TransactionHistory.query.filter_by(user_id=current_user.id).order_by(TransactionHistory.timestamp.desc()).all()
    stock_transaction_history = StockTransactionHistory.query.filter_by(user_id=current_user.id).order_by(StockTransactionHistory.timestamp.desc()).all()
    return render_template('portfolio.html', user_balance=user_balance, user_stocks=user_stocks, transaction_history=transaction_history, stock_transaction_history=stock_transaction_history)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/execute_trade', methods=['POST'])
@login_required
def execute_trade():
    data = request.json
    symbol = data['symbol']
    shares = int(data['shares'])
    action = data['action']
    
    current_price = get_stock_price(symbol)

    if current_price is None:  # Check if stock price retrieval failed
        return jsonify({'success': False, 'message': 'Unable to fetch stock price'})

    if action == 'buy':
        total_cost = shares * current_price
        if current_user.balance >= total_cost:
            current_user.balance -= total_cost
            db.session.commit()  # Commit balance change before adding transaction
            transaction = Transaction(user_id=current_user.id, symbol=symbol, shares=shares, price=current_price, action='buy')
            db.session.add(transaction)
            # Log the stock transaction
            stock_transaction = StockTransactionHistory(user_id=current_user.id, symbol=symbol, shares=shares, action='buy', price=current_price)
            db.session.add(stock_transaction)
            db.session.commit()
            return jsonify({'success': True, 'message': f'Successfully bought {shares} shares of {symbol}'})


    elif action == 'sell':
        if has_enough_shares(current_user.id, symbol, shares):
            total_earnings = shares * current_price
            current_user.balance += total_earnings
            db.session.commit()  # Commit balance change before adding transaction
            update_portfolio(current_user.id, symbol, shares, 'sell')
            transaction = Transaction(user_id=current_user.id, symbol=symbol, shares=shares, price=current_price, action='sell')
            db.session.add(transaction)
            # Log the stock transaction
            stock_transaction = StockTransactionHistory(user_id=current_user.id, symbol=symbol, shares=shares, action='sell', price=current_price)
            db.session.add(stock_transaction)
            db.session.commit()
            return jsonify({'success': True, 'message': f'Successfully sold {shares} shares of {symbol}'})


    else:
        return jsonify({'success': False, 'message': 'Invalid action'})


if __name__ == '__main__':
    create_tables()  # Call create_tables when the app starts
    app.run(debug=True)
