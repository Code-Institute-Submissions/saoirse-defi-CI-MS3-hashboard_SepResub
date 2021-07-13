# Imports
import os
import uuid
import asyncio
import json
import httpx
import time
from os import path
from operator import itemgetter
from web3 import Web3
if os.path.exists("env.py"):
    import env

from flask import Flask, render_template, flash, redirect, request, session, url_for, send_from_directory
from flask_pymongo import PyMongo
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import logic.models
import logic.etherscan_api

# Application setup

app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.config["SESSION_TYPE"] = 'filesystem'
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)

transaction_table_headings = ['Date created', 'Hash', 'To', 'From', 'Value', 'Token Involved', 'Gas Price (GWEI)', 'Gas Spent (ETH)', 'Favourite']

# Decorator Functions


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return wrap

# Formatting functions


def shorten(string):  # formatting functions
    return "0x..." + string[38:]


def shorten2(string):
    return "0x..." + string[62:]


def toInt(x):
    return int(float(x))


def threeDecimals(y):
    return "%.3f" % y


# Routes
@login_required
@app.route("/")
@app.route("/index", methods=['GET', 'POST'])
def index():
    transactions_list = list(mongo.db.Transaction.find({"user_id": session['user']['_id']})) # list of cursor query
    transactions_list.sort(reverse=True, key=itemgetter('time'))  # sort combined list by time/date

    fav_list = list(mongo.db.Transaction.find({"user_id": session['user']['_id'], "isFav": True}))
    fav_list.sort(reverse=True, key=itemgetter('time'))

    print(mongo.db.Transaction.find_one({'hash': '0xa461b27f1159532a28f6ebae83ecc1d861dbda46398ccf43d691ba4a4d12b0cf'}))

    return render_template("index.html",
                            transactions_list=transactions_list,
                            fav_list=fav_list,
                            transaction_table_headings=transaction_table_headings,
                            shorten=shorten,
                            shorten2=shorten2,
                            toInt=toInt,
                            threeDecimals=threeDecimals)


# Add transaction to favourites
@login_required
@app.route('/favourite/<t_id>', methods=['GET', 'POST'])
def favourite(t_id):
    transaction = mongo.db.Transaction.find_one({'_id': t_id})

    if request.method == 'POST':
        note = request.form.get('note')
        mongo.db.Transaction.update({"_id": t_id}, {"$set": {"note": note, "isFav": True}})
        flash("Note added successfully", category='success')
        return redirect(url_for('index'))
    
    return render_template('favourite.html',
                            transaction=transaction)


# Delete transaction from favourites
@login_required
@app.route('/delete_fav/<t_id>', methods=['GET', 'POST'])
def delete_fav(t_id):
    mongo.db.Transaction.update({"_id": t_id}, {"$set": {"note": "", "isFav": False}})
    flash("Favourite removed", category='success')

    return redirect(url_for('index'))


# Clear all transactions except favourites
@login_required
@app.route('/clear', methods=['GET', 'POST'])
def clear():
    mongo.db.Transaction.remove({"user_id": session['user']['_id'], 'isFav': False})

    return redirect(url_for('index'))


# Search, bulk transaction added to db
@login_required
@app.route('/search', methods=['GET', 'POST'])
async def search():
    errors = {}
    transaction_list = []
    search_eth = ""

    if request.method == 'POST':
        #if request.args.get('fav-button') is not None:
         #   data = json.loads(request.form.get('fav-button'))
          #  print(data)

        search_eth = str(request.form.get('search-eth')).lower()
        print(search_eth)

        async with httpx.AsyncClient() as client:
            eth_res, alt_res, nft_res = await asyncio.gather(
                client.get(f'https://api.etherscan.io/api?module=account&action=txlist&address={search_eth}&startblock=0&endblock=99999999&sort=asc&apikey=PQWGH496A8A1H3YV5TKWNVCPHJZ3S7ITHA'),
                client.get(f'https://api.etherscan.io/api?module=account&action=tokentx&address={search_eth}&startblock=0&endblock=999999999&sort=asc&apikey=PQWGH496A8A1H3YV5TKWNVCPHJZ3S7ITHA'),
                client.get(f'https://api.etherscan.io/api?module=account&action=tokennfttx&address={search_eth}&startblock=0&endblock=999999999&sort=asc&apikey=PQWGH496A8A1H3YV5TKWNVCPHJZ3S7ITHA')
            )

            # search_result = await client.get(f'https://api.etherscan.io/api?module=account&action=txlist&address={search_eth}&startblock=0&endblock=99999999&sort=asc&apikey=PQWGH496A8A1H3YV5TKWNVCPHJZ3S7ITHA')
        
        eth_result_text = eth_res.text  # process repsonses into python list
        eth_json = json.loads(eth_result_text)
        list_eth = eth_json['result']

        alt_result_text = alt_res.text  # process repsonses into python list
        alt_json = json.loads(alt_result_text)
        list_alt = alt_json['result']

        nft_result_text = nft_res.text  # process repsonses into python list
        nft_json = json.loads(nft_result_text)
        list_nft = nft_json['result']

        combined_transaction_list = list_eth + list_alt + list_nft  # combining lists

        for transaction in combined_transaction_list:  # formatting data
            data = {
                'time': time.strftime("%d-%m-%Y", time.localtime(int(transaction['timeStamp']))),
                'hash': transaction['hash'],
                'from': transaction['from'],
                'to': transaction['to'],
                'value': str(round(Web3.fromWei(float(transaction['value']), 'ether'), 5)),
                'gas_price': str(int(Web3.fromWei(int(transaction['gasPrice']), 'ether') * int('1000000000'))),
                'gas_used': str(round(Web3.fromWei(int(transaction['gasPrice']) * int(transaction['gasUsed']), 'ether'), 6)),
                'token_name': 'Ethereum',  # not working
                'token_symbol': 'ETH',
                'contract_address': '',
                'token_id': ''
            }

            try:
                if transaction['tokenName']:
                    data['token_name'] = transaction['tokenName']
            except KeyError:
                print("Exception")

            try:
                if transaction['tokenSymbol']:
                    data['token_symbol'] = transaction['tokenSymbol']
            except KeyError:
                print("Exception")
            
            try:
                if transaction['contractAddress']:
                    data['contract_address'] = transaction['contractAddress']
            except KeyError:
                print("Exception")

            try:
                if transaction['tokenID']:
                    data['token_id'] = transaction['tokenID']
            except KeyError:
                print("Exception")

            transaction_list.append(data)
            logic.models.Account().add_transactions(data)
        
        flash("Transactions added to database", category='success')
        
        transaction_list.sort(reverse=True, key=itemgetter('time'))  # sort combined list by time/date

        print(transaction_list)

        return redirect(url_for('index'))

    return render_template("search.html", 
                            errors=errors, 
                            shorten=shorten,
                            shorten2=shorten2,
                            toInt=toInt,
                            threeDecimals=threeDecimals,
                            search_eth=search_eth,
                            transaction_list=transaction_list,  # get this error only sometimes UnboundLocalError: local variable 'transaction_list' referenced before assignment Traceback (most recent call last)
                            transaction_table_headings=transaction_table_headings)


#@app.route('/_save_transaction')  # background process in order to save transaction to Account fav list
#def _save_transaction(data):
#    logic.models.Account().fav(data)
#    return redirect(url_for('search'))

@app.route('/home', methods=['GET', 'POST'])
def home():
    transactions_list = list(mongo.db.Transaction.find({"user_id": session['user']['_id']}))
    fav_list = list(mongo.db.Transaction.find({"user_id": session['user']['_id'], "isFav": True}))
    return render_template('home.html',
                            transactions_list=transactions_list,
                            fav_list=fav_list,
                            shorten2=shorten2,
                            shorten=shorten)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        logic.models.Account().signup()
        return redirect(url_for('index'))
    return render_template("signup.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        logic.models.Account().login()
        return redirect(url_for('index'))

    return render_template("login.html")


@login_required
@app.route('/signout')
def signout():
    return logic.models.Account().signout()


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

# App config


if __name__ == '__main__':
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
