def chat():
    data = request.get_json()  # Ensure JSON is received correctly
    if not data or "message" not in data:
        return jsonify({"error": "Invalid request"}), 400
    
    user_message = data["message"].lower()
    username = session.get("name", "guest")  # Get logged-in user or default to 'guest'

    # Debugging
    print(f"Received message: {user_message} from {username}")

    # Check for user allergies
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT allergy_intensities FROM users WHERE name = %s", (username,))
    user_data = cursor.fetchone()
    
    allergies = eval(user_data["allergy_intensities"]) if user_data and user_data["allergy_intensities"] else {}

    cursor.execute("SELECT * FROM recipes")
    all_recipes = cursor.fetchall()

    # Filter recipes based on allergies
    safe_recipes = [recipe for recipe in all_recipes if not any(ingredient.lower() in allergies for ingredient in recipe["ingredients"].split(","))]

    # Generate a chatbot response
    if "recipe" in user_message or "suggest" in user_message:
        if safe_recipes:
            response = f"I recommend: {random.choice(safe_recipes)['name']}"
        else:
            response = "Sorry, I couldn't find a suitable recipe for you."
    else:
        response = "I'm here to help with recipes! Ask me for a suggestion."

    return jsonify({"response": response})






@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')
