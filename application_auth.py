from flask import Flask, render_template, url_for, jsonify, redirect
from flask import request, flash, session as login_session, make_response
import psycopg2
from sqlalchemy.orm import sessionmaker
# from sqlalchemy.ext.declarative import declarative_base
from database import db_connect, create_base
from category import create_category
from category_items import create_category_items
from user_info import create_user
import settings
import sys
import pytz
import datetime
import random
import string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

import httplib2
import json
import requests

from functools import wraps

with open('client_secret.json', 'r') as ci:
    CLIENT_ID = json.loads(ci.read())['web']['client_id']

APPLICATION_NAME = 'Catalog Application'
app = Flask(__name__)
app.secret_key = 'mysecretkey'
engine = db_connect()
Base = create_base(engine)
Category = create_category(Base)
Category_items = create_category_items(Base)
User_info = create_user(Base)
Session = sessionmaker(bind=engine)
session = Session()


# get user info using user email
def getUserId(email):
    try:
        user = session.query(User_info).filter(User_info.email == email).one()
        return user.id
    except:
        return None


# get user info using user id
def getUserInfo():
    if 'user_id' in login_session:
        user_id = login_session['user_id']
        user = session.query(User_info).filter(User_info.id == user_id).one()
        return user
    else:
        return None


# create user using login_session data
def createUser(login_session):
    newUser = User_info(
            name=login_session['username'],
            email=login_session['email'],
            picture=login_session['picture']
            )
    session.add(newUser)
    session.commit()
    user = session.query(User_info).filter(
           User_info.email == login_session['email']
           ).one()
    return user.id


# check category name and id
def check_category_name_id(category, category_id):
    all_categories = session.query(Category).all()
    catg = [cat for cat in all_categories if category == cat.name]
    if catg != [] and catg[0].id == category_id:
        return catg, all_categories
    else:
        return None, None


# check category items names and id
def check_sub_category_name_id(sub_category, sub_category_id):
    try:
        category_item = session.query(Category_items).filter(
            Category_items.id == sub_category_id).one()
    except Exception as e:
        category_item = None
    if category_item is not None and category_item.name == sub_category:
        return category_item
    else:
        return None


# check category and category items
def check_category_sub_category(category, category_id, sub_category,
                                sub_category_id):
    catg, all_categories = check_category_name_id(category, category_id)
    catg_item = check_sub_category_name_id(sub_category, sub_category_id)
    if catg is not None and \
            all_categories is not None and \
            catg_item is not None:
        category_item = session.query(Category, Category_items).filter(
            Category.id == Category_items.category_id
        ).filter(
            Category_items.id == sub_category_id
        ).filter(
            Category_items.expiry_date == None
        ).one()
        return catg, category_item, all_categories
    else:
        return None, None, None


@app.route('/login')
def login():
    '''login page to authenticate user using google and facebook login'''
    # generate 32 bit state token
    state = ''.join(
        random.choice(
            string.ascii_uppercase + string.digits
        ) for x in xrange(32)
    )
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate State Token

    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    code = request.data
    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secret.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps(
            'Failed to upgrade the authorization code.'
            ), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's User ID doesn't match given User ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(json.dumps(
            "Token's Client Id does not match app's."
            ), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    # credentials = credentials.to_json()
    login_session['token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # Add provider to login session
    login_session['provider'] = 'google'
    user_id = getUserId(data['email'])
    if user_id:
        login_session['user_id'] = user_id
    else:
        user_id = createUser(login_session)
        login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += '''" style = "width: 300px; height: 300px; border-radius: 150px;
                 -webkit-border-radius: 150px; -moz-border-radius: 150px;">'''
    flash("you are now logged in as %s" % login_session['username'])

    return output


@app.route('/gdisconnect/')
def gdisconnect():
    # Only disconnect a connected user.
    token = login_session.get('token')
    if "token" is None:
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Execute HTTP GET request to revoke current token.

    access_token = token
    url = ('https://accounts.google.com/o/oauth2/revoke?token=%s'
           % access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] != '200':
        # For whatever reason, the given token was invalid.
        response = make_response(json.dumps(
            'Failed to revoke token for given user.'
            ), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data

    app_id = json.loads(
        open('fb_client_secrets.json', 'r').read()
    )['web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read()
    )['web']['app_secret']

    url = '''https://graph.facebook.com/v2.8/me?access_token=%s&fields=name,id,email''' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data['email']
    login_session['facebook_id'] = data['id']

    # The token must be storedin the login_session in order to properly logout,
    # let's strip out the Information
    # before the equals sign in our token
    login_session['access_token'] = access_token
    # Get user picture
    url = '''https://graph.facebook.com/v2.4/me/picture?access_token=%s&redirect=0&height=100&width=100''' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)
    login_session['picture'] = data['data']['url']

    # see if user exists
    user_id = getUserId(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += '''"style="width:300px;height:300px;border-radius:150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;">'''

    flash("Now logged in as %s" % login_session['username'])
    return output


@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    # The access token must be includded to successfully logout
    access_token = login_session['access_token']
    url = """https://graph.facebook.com/%s/permissions?access_token=
             %s""" % (facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "you have been logged out"


# Decorator function to validate if user is logged in
def authenticate(f):
    @wraps(f)
    def decorated_func(*args, **kwargs):

        user = getUserInfo()
        if user:
            request.user = user
            retVal = f(*args, **kwargs)
            request.user = None
            return retVal
        else:
            return redirect(url_for('catelog_home'))
    return decorated_func


@app.route('/', methods=['GET'])
def catelog_home():
    '''Serving GET requests to show home page'''
    if 'username' in login_session:
        return redirect(url_for('catelog_home_auth'))
    else:
        all_categories = session.query(Category).all()
        latest_subcatagories = session.query(Category, Category_items).filter(
                        Category.id == Category_items.category_id).filter(
                        Category_items.expiry_date == None).order_by(
                        Category_items.modified_time.desc())[:5]
        return render_template('home.html', all_categories=all_categories,
                               latest_subcatagories=latest_subcatagories)


@app.route('/home', methods=['GET', 'POST'])
@authenticate
def catelog_home_auth():
    '''If user is logged in show the home with previleged features.'''
    '''i.e Add items'''
    all_categories = session.query(Category).all()
    latest_subcatagories = session.query(Category, Category_items).filter(
                Category.id == Category_items.category_id).filter(
                Category_items.expiry_date == None).order_by(
                Category_items.modified_time.desc())[:5]
    return render_template('home_auth.html',
                           all_categories=all_categories,
                           latest_subcatagories=latest_subcatagories,
                           login_session=login_session)


@app.route('/catalog/<category>/<int:category_id>/items/')
def category_list(category, category_id):
    '''Display Category and category items'''
    # If user is logged in then show category items on home page
    # instead of latest category items.
    user = getUserInfo()
    catg, all_categories = check_category_name_id(category, category_id)
    if catg is not None or all_categories is not None:
        category_items = session.query(Category_items, Category).filter(
            Category.id == Category_items.category_id).filter(
            Category.id == category_id).filter(
            Category_items.expiry_date == None)
        if category_items.count() == 0:
            catg = [cat for cat in all_categories if category == cat.name]
            if catg[0].id == category_id:
                if user:
                    return render_template('category_items.html',
                                           category=category,
                                           all_categories=all_categories,
                                           category_items=category_items)
                else:
                    return render_template('category_items_auth.html',
                                           category=category,
                                           all_categories=all_categories,
                                           category_items=category_items,
                                           login_session=login_session)
            else:
                return redirect(url_for('catelog_home'))
        else:
            for category_item in category_items:
                if category_item.Category.name != category or \
                        category_item.Category.id != category_id:
                    return redirect(url_for('catelog_home'))
                else:
                    if user:
                        return render_template('category_items.html',
                                               category=category,
                                               all_categories=all_categories,
                                               category_items=category_items)
                    else:
                        return render_template('category_items_auth.html',
                                               category=category,
                                               all_categories=all_categories,
                                               category_items=category_items,
                                               login_session=login_session)
    else:
        return redirect(url_for('catelog_home'))


@app.route(
    """/catalog/<category>/<int:category_id>/"""
    """<sub_category>/<int:sub_category_id>/"""
)
def sub_category(category, category_id, sub_category, sub_category_id):
    '''Display category items'''

    # If user logged in the show category page with added features like edit
    # and delete
    user = getUserInfo()
    catg, category_item, all_categories = check_category_sub_category(
                                                category, category_id,
                                                sub_category, sub_category_id)
    if category_item is not None and \
            catg is not None and \
            all_categories is not None:
        if user:
            if category_item.Category_items.user_id == login_session['user_id']:
                return render_template('item_description_auth.html',
                                       category_item=category_item,
                                       login_session=login_session)
            else:
                return render_template('item_description_valid_user_auth.html',
                                       category_item=category_item,
                                       login_session=login_session)
        else:
            return render_template('item_description.html',
                                   category_item=category_item)

    else:
        return redirect(url_for('catelog_home'))


@app.route('/catalog/add_item/', methods=['GET', 'POST'])
@authenticate
def add_item():
    '''Show add item to the database and redirect to category items page'''
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category_id = request.form['category_id']
        user_id = login_session['user_id']
        catg = session.query(Category).filter(
            Category.id == category_id).one()
        if catg is not None:
            item = Category_items()
            item.name = title
            item.description = description
            item.category_id = category_id
            item.user_id = user_id
            session.add(item)
            session.commit()
            flash('Item added successfully')
            category_item = session.query(Category_items).filter(
                Category_items.id == item.id).one()
            category = catg.name
            category_id = catg.id
            sub_category = category_item.name
            sub_category_id = category_item.id
            return redirect(url_for('sub_category',
                                    category=category,
                                    category_id=category_id,
                                    sub_category=sub_category,
                                    sub_category_id=sub_category_id))
    else:
        categories = session.query(Category).all()
        return render_template('add_item.html',
                               categories=categories,
                               login_session=login_session)


@app.route(
    '/catalog/<sub_category>/<int:sub_category_id>/edit/',
    methods=['GET', 'POST']
)
@authenticate
def edit_item(sub_category, sub_category_id):
    '''Edit category items'''
    category_item = check_sub_category_name_id(sub_category, sub_category_id)
    if category_item is not None and \
            category_item.user_id == login_session['user_id']:
        if request.method == 'POST':
            title = request.form['title']
            description = request.form['description']
            category_id = request.form['category_id']
            category_item = session.query(Category_items).filter(
                Category_items.id == sub_category_id).one()
            category_item.name = title
            category_item.description = description
            category_item.category_id = int(category_id)
            category_item.modified_time = datetime.datetime.now(pytz.utc)
            session.add(category_item)
            session.commit()
            flash("Item updated successfully")
            category_item = session.query(Category, Category_items).filter(
                            Category.id == Category_items.category_id).filter(
                            Category_items.id == sub_category_id).one()
            category = category_item.Category.name
            category_id = category_item.Category.id
            sub_category = category_item.Category_items.name
            sub_category_id = category_item.Category_items.id
            return redirect(url_for('sub_category',
                                    category=category,
                                    category_id=category_id,
                                    sub_category=sub_category,
                                    sub_category_id=sub_category_id,
                                    login_session=login_session))
        else:
            categories = session.query(Category).all()
            category_item = session.query(Category, Category_items).filter(
                            Category.id == Category_items.category_id).filter(
                            Category_items.id == sub_category_id).one()
            return render_template('edit_item.html',
                                   category_item=category_item,
                                   categories=categories,
                                   login_session=login_session)
    else:
        return redirect(url_for('catelog_home'))


@app.route('/catalog/<sub_category>/<int:sub_category_id>/delete/')
@authenticate
def delete_item(sub_category, sub_category_id):
    '''Delete category items'''
    category_item = check_sub_category_name_id(sub_category, sub_category_id)
    if category_item is not None and \
            category_item.user_id == login_session['user_id']:
        category_item.expiry_date = datetime.datetime.now(pytz.utc)
        session.add(category_item)
        session.commit()
        flash("Item deleted successfully")
    return redirect(url_for('catelog_home'))


@app.route('/catalog/<category>/<int:category_id>/items/JSON')
def category_list_JSON(category, category_id):
    '''Category and category item JSON response'''
    category_items = session.query(Category_items, Category).filter(
                    Category.id == Category_items.category_id).filter(
                    Category.id == category_id).filter(
                    Category_items.expiry_date == None)
    if category_items.count() != 0:
        items = [category_item[0] for category_item in category_items]
        category = [category_item[1] for category_item in category_items]
        items.append(category[0])
        data = jsonify(category_items=[i.serialize for i in items])
    else:
        data = json.dumps({"message": "No item found"})
    return data


@app.route('/catalogs/JSON')
def categories_JSON():
    '''Categories JSON response'''
    categories = session.query(Category).all()
    return jsonify(category=[i.serialize for i in categories])


@app.route(
    """/catalog/<category>/<int:category_id>/"""
    """<sub_category>/<int:sub_category_id>/JSON"""
)
def sub_category_JSON(category, category_id, sub_category, sub_category_id):
    '''Category item JSON response'''
    category_items = session.query(Category, Category_items).filter(
            Category.id == Category_items.category_id).filter(
            Category_items.id == sub_category_id).filter(
            Category_items.expiry_date == None)
    if category_items.count() != 0:
        items = [category_item for category_item in category_items]
        data = jsonify(category_items=[i.serialize for i in items])
    else:
        data = json.dumps({"message": "No item found"})
    return data


# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['token']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('catelog_home'))

    else:
        flash("You were not logged in")
        return redirect(url_for('catelog_home'))


if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
