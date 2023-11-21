from Event import app
from flask import render_template, redirect, url_for, flash, request, session, abort
from Event.models import User
from Event.forms import RegisterForm, LoginForm, UploadFileForm, AdminForm, InviteLinks, EventForm
from Event import db, flow, GOOGLE_CLIENT_ID, mail, ALLOWED_EXTENSIONS
from flask_login import login_user, logout_user, login_required, current_user
from flask_dance.contrib.google import google
from google.oauth2 import id_token
import google.auth.transport.requests
from datetime import datetime
import pytz
import secrets
from flask_mail import Message
import requests
from werkzeug.utils import secure_filename
import os

#The Home Route is executed just right after running of the application.
@app.route('/')             
@app.route('/home')
def home_page():
    return render_template('home.html')

#Manual Registration route
@app.route("/register", methods=['GET', 'POST'])            
def register_page():
    form = RegisterForm()                                   #Creating an object for the regsitration form  
    token = None                                    

    if form.validate_on_submit():                           #To check if the form is successfully submitted by the user.
        recaptcha_response = request.form.get('g-recaptcha-response')               
        secret_key = '6LdCjhAoAAAAAPl5hO22mP8--Erm1FQUladGgvS8' 

        data = {
        'secret': secret_key,
        'response': recaptcha_response,
        }

        response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data, timeout=10)      #To check the recpatcha response submitted by user to verify the human.
       
        result = response.json()
        print(result)

        if not result['success']:                                           #If the response is successful, a new user is created in the db.
            user_to_create = User(username=form.username.data,
                full_name = form.full_name.data,
                email_address=form.email_address.data,
                password=form.password1.data
                )
        
            token = generate_verification_token(user_to_create.email_address)           #To generate unique verification token for each user to send them on mail.
            print(token)
            user_to_create.verification_token=token
            db.session.add(user_to_create)
            db.session.commit()                                                         #Initial commit of the user before final registration.
            verification_link = url_for('verify_email', token=token, _external=True)

            # Mail to send to the registered users fto verify thier account.
            msg = Message('Verify Your Email', sender='bharat.aggarwal@iic.ac.in', recipients=[user_to_create.email_address])
            msg.body = f'Click on the following link to verify your email: {verification_link}'
            mail.send(msg)

            return redirect(url_for('redirect_page'))

        else:
            flash('reCaptcha verification failed. Please try again.', category='danger')



            '''login_user(user_to_create)

            flash(f"Account Created Successfully! You are now logged in as {user_to_create.username}", category='success')

            return redirect(url_for('Event_page'))
            '''

            '''if form.errors != {}:       #If there are no errors from the validations.
                for err_msg in form.errors.values():
                    flash(f'There was an error with creating a user: {err_msg}', category='danger')'''

    return render_template('register.html', form=form)

def generate_verification_token(email):
    token = secrets.token_hex(16)                       #To Generate a random token

    '''user = User.query.filter_by(email_address=email).first()
    user.verification_token = token'''

    return token


#Manual login route
@app.route("/login", methods=['GET', 'POST'])
def login_page():
    form = LoginForm()
    if form.validate_on_submit():                       #To validate the form submission by the user.
        attempted_user = User.query.filter_by(username=form.username.data).first()
        print(attempted_user.username)
        print(attempted_user.hash_password)
        attempted_user.role = form.role.data
        db.session.add(attempted_user)
        db.session.commit()  
        print(f"Form Role: {form.role.data}")
        print(f"User Role: {attempted_user.role}")

        if attempted_user and attempted_user.is_verified and attempted_user.check_password_correction(attempted_password=form.password.data):
              #To verify all the credentials of the user like username existence, password and verification done or not.
            print(attempted_user.role)
            login_user(attempted_user)
            attempted_user.update_last_login()

            if attempted_user.role == 'participant':
                flash(f'Success!! Username - {attempted_user.username} ', category='success')
                return redirect(url_for('event_page', role=attempted_user.role))        
            else:
                flash(f'Success!! Username - {attempted_user.username} ', category='success')
                return redirect(url_for('organizer_page', role=attempted_user.role))                 
        else:
            flash('Username and password are not match! or Email Verification is not done. Please try again', category='danger')

    return render_template('login.html', form=form) 


'''The login required function to check if the google user is in session or not.'''

def login_is_required(function):            #function to check if the current google id is in session or not.
    def wrapper(*args, **kwargs):
        print(session)
        if "google_id" not in session: 
            return abort(401)               # Authorizaion Required
        else:
            print(session['google_id'])
            return function()               #return to the calling function (successful).

    return wrapper

@app.route('/event-page/<role>')                   #route for redirecting the authenticated users to the main event page.
def event_page(role):
    return render_template('event_page.html', role=role)
def google_event_page():
    return render_template('event_page.html', google_id=session["google_id"], name=session["name"], Email_id=session["Email_id"])

@app.route('/hackathon', methods=['GET', 'POST'])           #Separate Event details route
def hackathon_page():
    upload_form = UploadFileForm()                          
    if upload_form.validate_on_submit():                    #Validating the successful upload done by user.
        file = upload_form.file.data

        if file.filename == '':                             
            flash('No file selected for uploading')
            return redirect(request.url)

        if file and allowed_file(file.filename):            #checking if file extension is allowed
            file.save(os.path.join(os.path.abspath(os.path.dirname(__file__)),app.config['UPLOAD_FOLDER'], secure_filename(file.filename)))     #The uploaded file get saved in the specified folder.
            flash('File has been Succesfully uploaded.','success')
        else:
            flash('File did not uploaded!!! Allowed file types are txt, pdf, png, jpg, jpeg, gif', 'danger')
            return redirect(request.url)
    return render_template('hackathon.html', form=upload_form)



def allowed_file(filename):                                     #function used to define all the allowed extensions.
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/organizer/<role>")                                        #Route to display the current events under an organizer and option to create a new one.
def organizer_page(role):
    return render_template('organizer.html', role=role)

@app.route("/event-details", methods=['GET', 'POST'])                                #To create and store new event details 
def event_details_form():
    form = EventForm()
    if form.validate_on_submit():
        event_to_create = Event(category=form.category.data,
        title=form.title.data,
        acronym=form.acronym.data,
        web_page_url=form.web_page_url.data,
        venue=form.venue.data,
        city=form.city.data,
        country=form.country.data,
        first_day=form.first_day.data,
        last_day=form.last_day.data,
        primary_area=form.primary_area.data,
        secondary_area=form.secondary_area.data,
        area_notes=form.area_notes.data,
        organizer_name=form.organizer_name.data,
        organizer_web_page=form.organizer_web_page.data,
        phone_no=form.phone_no.data,
        other_info=form.other_info.data
        )
        db.session.add(event_to_create)
        db.session.commit() 
        return redirect(url_for('event_details_form'))

    return render_template('event_form.html', form=form)
    

@app.route('/google-wait')                                      #Function to check if the current google session is correct or not.
@login_is_required
def event_page_google():
    return redirect(url_for('google_event_page'))

@app.route('/redirect')                                         #Redirect route to wait for user to verify their email.
def redirect_page():
    return render_template('redirect.html')

@app.route('/verify')                                           #Route to verify the unique token send to a user to their mail to redirect them to login page.
def verify_email():
    token = request.args.get('token')
    print(token)
    user = User.query.filter_by(verification_token=token).first()

    if user:
        user.is_verified = True
        print(user.is_verified)
        db.session.commit()
        flash('Your email has been verified. You can now log in.', 'success')
        return redirect(url_for('login_page'))

    else:
        flash('Invalid verification token. Please try again.', 'danger')
        return redirect(url_for('register_page'))


@app.route("/logout")                                           #logout Route to end the cuurent session.
def logout_page():
    logout_user()
    session.clear()
    flash('You have been logged out!', category='info')
    return redirect(url_for('home_page'))

''' Google authentication code was written from here.
    '''

@app.route('/google-login')                                     #The google login route to initialize the Google OAuth 2.O login process. 
def google_login():
    authorization_url, state = flow.authorization_url()         #This will generate the URL for Google OAuth 2.O authentication.
    print(authorization_url)
    session["state"] = state                                    #The 'state' parameter is stored in the user's session to be checked later for secuity validation.
    print(state)
    return redirect(authorization_url)                          #The user's browser will redirect the user to the mentioned authorization_url.

@app.route("/callback")                                         #This route will call after user has authenticated an account from his side.
def callback():

    flow.fetch_token(authorization_response=request.url)        #This will fetch the access token and other info from google using URL returned by authentication process.

    if not session["state"] == request.args["state"]:           #This will check if the state parameter stored in the user's session matches with the state paramters recieved as query parameters in the callback URl. 
        abort(500)

    credentials = flow.credentials
    token_request = google.auth.transport.requests.Request()

    id_info = id_token.verify_oauth2_token(                     #This code verifies the ID token received from Google using the credentials obtained earlier. It verifies the token's authenticity and decodes it to obtain user information.
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID,
        clock_skew_in_seconds = 300
        ) 

    existing_user = User.query.filter_by(email_address=id_info.get("email")).first()            #This will check if the user's provided email address during google login already exists in the app's database.

    if not existing_user:                                                                   #If user doesn't exists, a new user is created using Google-authenticated data.
        # Create a new user in the database using Google-authenticated data
        new_user = User(
            username=id_info.get("sub"),  # You can use the Google sub as the username
            full_name=id_info.get("name"),
            email_address=id_info.get("email"),
            google_id=id_info.get("sub"),  # Store Google ID for future reference
            profile_picture_url=id_info.get("picture"),
            Created_at = datetime.utcnow().replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Kolkata')),
            last_login = datetime.utcnow().replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Kolkata')),
            is_verified = True
            )
        db.session.add(new_user)
        db.session.commit()
        new_user.update_last_login()
    else: 
        existing_user.update_last_login()

    #The user's details is stored in the session for later use.
    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    session["Email_id"] = id_info.get("email")
    session["Picture_url"] = id_info.get("picture")
    session["First_Name"] = id_info.get("given_name")
    session["Last_Name"] = id_info.get("family_name")

    print(session["Email_id"])
    print(session["Picture_url"])
    print(session["First_Name"])

    return redirect("/google-wait")




# Admin authority to generate unique links for reviewers to send for thier registration.


def generate_invite_links():                    #To generate unique invite links for reviewers to send by the admin. 
    token = secrets.token_hex(20)

    base_url = 'http://127.0.0.1:5000/invite?token='
    links = base_url + token

    return links

@app.route("/admin", methods=['GET', 'POST'])
def admin_login():
    form = AdminForm()                              #Initializes the form for Admin.
    if form.validate_on_submit():
        if form.username.data == 'user0615243' and form.password.data == '855e121a6fed048a30d89cb24c768d1e4c1f40bcc8a64dca61895ab0deb17144':            #Validating the admin details.
            admin_username = form.username.data
            flash(f'Success!! You are successfully logged in.', category='success')
            return redirect(url_for('admin_page', admin_username=admin_username))
        else:
            flash('Username and password are not matched! Please try again', category='danger')

    return render_template('admin_login.html', form=form)

@app.route('/admin-page/<admin_username>', methods=['GET', 'POST'])
def admin_page(admin_username):
    form = InviteLinks()                                    #Initializes the InviteLinks form. 
    Invite_links = []                                       #Initilizes a blank list to store all the invite links.
    
    if form.validate_on_submit():
        number = form.number.data

        for i in range(number):                             #Looping upto the specified number mentioned to generate each unique link.
            links = generate_invite_links()
            Invite_links.append(links)
            
        print(Invite_links)
        flash(f'Here are your {number} number of links', category='success')

    return render_template('admin_page.html', admin_username=admin_username, form=form, Invite_links=Invite_links)

