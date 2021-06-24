import os
from os import path
if os.path.exists("env.py"):
    import env

from flask import Flask, render_template, flash, redirect, request, session, url_for
from flask_login import login_user, logout_user, current_user, login_required
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from logic.models import User


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.config["SESSION_TYPE"] = 'filesystem'
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


@app.route("/")
@app.route("/get_user")
def get_user():
    users = mongo.db.Users.find()
    return render_template("users.html", users=users)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        eth = request.form.get('eth')
        password = request.form.get('password')
        _password = request.form.get('password-confirm')

        existing_user = mongo.db.Users.find_one({
            "email": email.lower()
        })
        if existing_user:
            flash("Email address is already taken.", category='error')
            return redirect(url_for("register"))
        elif len(email) < 4:
            flash('Email Address is too short', category='error')
        elif len(name) < 2:
            flash('Your nickname is too short', category='error')
        elif eth:
            if len(eth) != 42:
                flash('The format of your Ethereum public address is incorrect', category='error')
        elif password != _password:
            flash('Your passwords dont match', category='error')
        elif len(password) < 8:
            flash('Your password is too short', category='error')
        else:
            signup = {
                "name": name,
                "email": email.lower(),
                "eth": eth,
                "password": generate_password_hash(password)
            }
            mongo.db.Users.insert_one(signup)
            session['user'] = email.lower()
            flash("Signup Successful!", category='success')
    
    return render_template("signup.html", user=current_user)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)


