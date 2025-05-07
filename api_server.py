from flask import Flask, request, jsonify

app = Flask(__name__)

# Sample user data
users = {
    1: {
        "id": 1,
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "(555) 123-4567",
        "dob": "01/15/90"
    }
}

# Template for resetting user 1
initial_user_template = users[1].copy()

@app.before_request
def ensure_initial_user():
    if 1 not in users:
        users[1] = initial_user_template.copy()

@app.route('/users', methods=['GET'])
def get_users():
    return jsonify(list(users.values())), 200

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    if user_id in users:
        return jsonify(users[user_id]), 200
    return jsonify({"error": "User not found"}), 404

@app.route('/users/<int:user_id>/details', methods=['GET'])
def get_user_details(user_id):
    if user_id in users:
        details = {
            "user": {
                "profile": {
                    "address": "123 Main St",
                    "contacts": [
                        {"type": "home", "phone": users[user_id]["phone"]}
                    ]
                }
            },
            "roles": ["admin", "user"]
        }
        return jsonify(details), 200
    return jsonify({"error": "User not found"}), 404

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    new_id = max(users.keys()) + 1 if users else 1
    new_user = {
        "id": new_id,
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "dob": data.get("dob", "")
    }
    users[new_id] = new_user
    return jsonify(new_user), 201

@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if user_id not in users:
        return jsonify({"error": "User not found"}), 404
    
    data = request.get_json()
    users[user_id].update(data)
    return jsonify(users[user_id]), 200

@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if user_id not in users:
        return jsonify({"error": "User not found"}), 404
    
    del users[user_id]
    return '', 204

if __name__ == '__main__':
    app.run(port=5000)
