import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)

# --- Configuration ---
# Use environment variable for secret key, fallback to a default (less secure)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your_secret_key_here')
# Configure the database URI from environment variable
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
# Disable modification tracking to save resources, unless needed
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Database Initialization ---
db = SQLAlchemy(app)

# --- Database Model ---
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(120), nullable=True, default='')

    def to_dict(self):
        """Helper method to convert model instance to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }

    def __repr__(self):
        return f'<Item {self.name}>'

# Remove the in-memory database
# items = [
#     {"id": 1, "name": "Sample Item", "description": "This is a sample item"}
# ]

# Weather API configuration (remains the same)
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
WEATHER_API_URL = "http://api.weatherapi.com/v1/current.json"

# --- Routes ---

@app.route('/')
def index():
    # Query all items from the database
    all_items = Item.query.all()
    return render_template('index.html', items=all_items) # Pass SQLAlchemy objects directly

# --- API Endpoints (Using Database) ---

@app.route('/items', methods=['GET'])
def get_items():
    all_items = Item.query.all()
    # Convert list of Item objects to list of dictionaries
    return jsonify([item.to_dict() for item in all_items])

@app.route('/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    # Use get_or_404 to automatically return 404 if not found
    item = Item.query.get_or_404(item_id)
    return jsonify(item.to_dict())

@app.route('/items', methods=['POST'])
def create_item():
    if not request.json or 'name' not in request.json or not request.json['name']:
        return jsonify({"error": "Name is required and cannot be empty"}), 400

    name = request.json['name']
    description = request.json.get('description', '') # Get description or default to empty string

    new_item = Item(name=name, description=description)

    try:
        db.session.add(new_item)
        db.session.commit()
        # After commit, new_item will have an ID assigned by the database
        return jsonify(new_item.to_dict()), 201
    except Exception as e:
        db.session.rollback() # Rollback in case of error
        return jsonify({"error": "Database error", "details": str(e)}), 500


@app.route('/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    item = Item.query.get_or_404(item_id)

    if not request.json:
        return jsonify({"error": "Request must be JSON"}), 400

    # Update fields only if they are present in the request JSON
    if 'name' in request.json:
        if not request.json['name']:
             return jsonify({"error": "Name cannot be empty"}), 400
        item.name = request.json['name']
    if 'description' in request.json:
        item.description = request.json['description']

    try:
        db.session.commit()
        return jsonify(item.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500

@app.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    try:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"result": "Item deleted"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500

# --- Weather Route (remains the same) ---
@app.route('/weather', methods=['GET'])
def get_weather():
    city = request.args.get('city')
    if not city:
        return jsonify({"error": "City parameter is required"}), 400

    if not WEATHER_API_KEY:
         return jsonify({"error": "Weather API key is not configured"}), 500

    try:
        params = {
            'key': WEATHER_API_KEY,
            'q': city,
        }
        response = requests.get(WEATHER_API_URL, params=params)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        weather_data = response.json()

        # Check if weather API returned an error within the JSON
        if 'error' in weather_data:
            return jsonify({"error": f"Weather API error: {weather_data['error']['message']}"}), 400

        # Extract relevant data safely using .get()
        location = weather_data.get('location', {})
        current = weather_data.get('current', {})
        condition = current.get('condition', {})

        simplified_data = {
            'city': location.get('name', 'N/A'),
            'temperature': current.get('temp_c', 'N/A'),
            'description': condition.get('text', 'N/A'),
            'humidity': current.get('humidity', 'N/A'),
            'wind_speed': current.get('wind_kph', 'N/A')
        }
        return jsonify(simplified_data)
    except requests.exceptions.RequestException as e:
        # Handle connection errors, timeouts, etc.
        return jsonify({"error": f"Could not connect to weather service: {e}"}), 503 # 503 Service Unavailable
    except Exception as e:
        # Catch other potential errors during processing
        app.logger.error(f"Error processing weather data: {e}") # Log the error server-side
        return jsonify({"error": "An internal error occurred while fetching weather data"}), 500


# --- Main Execution ---
if __name__ == '__main__':
    # Create database tables if they don't exist
    # This is okay for simple development, but for production/migrations, use Flask-Migrate
    with app.app_context():
        db.create_all()
    app.run(debug=True) # Debug=True reloads on code changes and shows detailed errors