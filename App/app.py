# Import the necessary modules
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from flask_uploads import UploadSet, configure_uploads, IMAGES
import cv2
import base64 
import os
import math

# Create a Flask app
app = Flask(__name__)

# Set the secret key for the app
app.secret_key = "some_secret_key"

# Create a login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Create a user class
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

# Create a dummy user database
users = [
    User(1, "admin", "admin"),
    User(2, "user", "user")
]

# Define a user loader function
@login_manager.user_loader
def load_user(user_id):
    return users[int(user_id) - 1]

# Create a login form class
class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

# Create an upload set for images
images = UploadSet("images", IMAGES)

# Configure the upload folder
app.config["UPLOADED_IMAGES_DEST"] = "static/images"
configure_uploads(app, images)

# Define the route for the login page
@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = next((user for user in users if user.username == username and user.password == password), None)
        if user:
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password.", "danger")
    return render_template("login.html", form=form)


# Define the route for the home page
@app.route("/home")
@login_required
def home():
    return render_template("home.html")

# Define the route for the logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

# Define the route for the image analysis
@app.route("/analyze", methods=["POST"])
def analyze():
    # Get the image from the request
    image_data = request.form.get("image")
    # Remove the data URI prefix
    image_data = image_data.replace("data:image/jpeg;base64,", "")
    # Decode the base64 image
    image = base64.b64decode(image_data)
    # Save the image on the server
    filename = "uploaded_image.jpg"
    with open(os.path.join(app.config["UPLOADED_IMAGES_DEST"], filename), "wb") as f:
        f.write(image)
    # Load the image using OpenCV
    image = cv2.imread(os.path.join(app.config["UPLOADED_IMAGES_DEST"], filename))
    # Convert the image to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Threshold the image to binarize it
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Find the contours of the blood cells
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    # Initialize the counters for WBCs and infected cells
    wbc_count = 0
    infected_count = 0
    # Loop through the contours
    for cnt in contours:
        # Calculate the area of the contour
        area = cv2.contourArea(cnt)
        # Filter out the noise and the background
        if 100 < area < 10000:
            # Increment the WBC count
            wbc_count += 1
            # Calculate the circularity of the contour
            perimeter = cv2.arcLength(cnt, True)
            circularity = 4 * math.pi * (area / (perimeter * perimeter))
            # If the circularity is less than 0.8, assume it is infected
            if circularity < 0.8:
                # Increment the infected count
                infected_count += 1
                # Draw a red contour around the infected cell
                cv2.drawContours(image, [cnt], 0, (0, 0, 255), 2)
                # Put a text label on the infected cell
                cv2.putText(image, "Infected", (cnt[0][0][0], cnt[0][0][1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            else:
                # Draw a green contour around the healthy cell
                cv2.drawContours(image, [cnt], 0, (0, 255, 0), 2)
    # Save the annotated image
    annotated_filename = "/images/annotated_image.jpg"
    cv2.imwrite(os.path.join(app.config["UPLOADED_IMAGES_DEST"], annotated_filename), image)
    # Calculate the percentage of infected cells
    if wbc_count != 0:
        percentage_infected = (infected_count / wbc_count) * 100
    else:
        percentage_infected = 0
    # Create a report
    report = {
        "wbc_count": wbc_count,
        "infected_count": infected_count,
        "percentage_infected": percentage_infected
    }
    # Return the report and the annotated image
    return jsonify(report=report, annotated_image=url_for("static", filename=annotated_filename))

if __name__ == "__main__":
    app.run(debug=True)
