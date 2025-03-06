from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
import random


app = Flask(__name__)
app.secret_key = 'your_secret_key'  


app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'allergy_db'

mysql = MySQL(app)

@app.route('/')
def home():
    return render_template('org-index.html')

@app.route('/home')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()
        if account:
            flash('Account already exists!', 'danger')
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Invalid email address!', 'danger')
        elif not name or not email or not password:
            flash('Please fill out the form!', 'danger')
        else:
            cursor.execute('INSERT INTO users (name, email, password) VALUES (%s, %s, %s)', (name, email, password))
            mysql.connection.commit()
            flash('Registration successful!', 'success')
            
            return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()
        print("Account Found:", account)  
        if account and account['password'] == password: 
            session['loggedin'] = True
            session['id'] = account['id']
            session['name'] = account['name']
            flash('Login successful!', 'success')
            return render_template('index.html')
        else:
            flash('Invalid email or password!', 'danger')    
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Fetch user's allergies and available ingredients
        cursor.execute('SELECT allergy_intensities, ingredients FROM users WHERE id = %s', (session['id'],))
        user_data = cursor.fetchone()

        # Parse allergy data
        allergy_data = eval(user_data['allergy_intensities']) if user_data and user_data['allergy_intensities'] else {}
        available_ingredients = user_data['ingredients'].split(',') if user_data['ingredients'] else []

        # Fetch recipes from database
        cursor.execute("SELECT * FROM recipes")
        all_recipes = cursor.fetchall()

        # Fetch ingredient substitutions
        cursor.execute("SELECT * FROM ingredient_substitutions")
        substitutions = {row['original_ingredient'].lower(): row['substitute_ingredient'] for row in cursor.fetchall()}

        filtered_recipes = []

        for recipe in all_recipes:
            ingredients = recipe['ingredients'].split(',')
            allergy_flag = False
            allergy_message = ""

            # Check allergies and apply ingredient substitutions
            modified_ingredients = []
            for ingredient in ingredients:
                ingredient_lower = ingredient.strip().lower()

                # If an ingredient is an allergen, generate an allergy message
                if ingredient_lower in allergy_data:
                    intensity = allergy_data[ingredient_lower]
                    if intensity == "basic":
                        allergy_message += f"Contains {ingredient}. You can include a small amount.\n"
                    elif intensity == "average":
                        allergy_message += f"Contains {ingredient}. Consider reducing the amount.\n"
                    elif intensity == "high":
                        allergy_message += f"Contains {ingredient}. Avoid this recipe.\n"
                        allergy_flag = True

                # Substitute ingredients if possible
                if ingredient_lower in substitutions:
                    modified_ingredients.append(substitutions[ingredient_lower] + " (Substituted)")
                else:
                    modified_ingredients.append(ingredient)

            # If high-intensity allergy exists, exclude the recipe
            if not allergy_flag:
                recipe['allergy_message'] = allergy_message
                recipe['ingredients'] = ', '.join(modified_ingredients)
                filtered_recipes.append(recipe)

        return render_template('dashboard.html', recipes=filtered_recipes)
    
    flash("Please login first!", "danger")
    return redirect(url_for('login'))


@app.route('/allergy-input', methods=['GET', 'POST'])
def allergy_input():
    if 'loggedin' not in session:
        flash("Please login first!", "danger")
        return redirect(url_for('login'))
    if request.method == 'POST':
        allergies = request.form.getlist('allergies[]')
        intensities = [] 
        for i in range(len(allergies)):
            intensity = request.form.get(f'intensity_{i}')
            if intensity:
                intensities.append(intensity)
        ingredients = request.form['ingredients']
        if len(allergies) != len(intensities):
            flash('Please select an intensity level for each allergy.', 'danger')
            return redirect(url_for('allergy_input'))
        allergy_data = {allergies[i].strip(): intensities[i].strip() for i in range(len(allergies))}
        allergy_data_str = str(allergy_data)

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE users SET allergy_intensities = %s, ingredients = %s WHERE id = %s', 
                       (allergy_data_str, ingredients, session['id']))
        mysql.connection.commit()

        flash('Allergy details updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('allergy_input.html')




@app.route('/rate_recipe', methods=['POST'])
def rate_recipe():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    recipe_id = request.form.get('recipe_id')
    rating = request.form.get('rating')
    comment = request.form.get('comment')

    if recipe_id:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        if rating:
            cursor.execute("INSERT INTO recipe_ratings (user_id, recipe_id, rating) VALUES (%s, %s, %s)",
               (session['id'], recipe_id, rating))

        if comment:
            cursor.execute("INSERT INTO comments (user_id, recipe_id, comment) VALUES (%s, %s, %s)",
                           (session['id'], recipe_id, comment))
        mysql.connection.commit()
        cursor.close()

    flash("Your rating and comment have been submitted!", "success")
    return redirect(url_for('dashboard'))




@app.route('/add-comment', methods=['POST'])
def add_comment():
    if 'loggedin' in session:
        recipe_id = request.form['recipe_id']
        comment = request.form['comment']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('INSERT INTO comments (user_id, recipe_id, comment) VALUES (%s, %s, %s)', 
                       (session['id'], recipe_id, comment))
        mysql.connection.commit()
        flash('Comment added!', 'success')

        return redirect(url_for('dashboard'))
    else:
        
        flash("Please login first!", "danger")
        return redirect(url_for('login'))






# Chatbot Route
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Invalid request"}), 400

    user_message = data["message"].strip().lower()

    # Rule-Based Responses
    responses = {
    # Greetings & Introduction
    "hello": "Hey there! How’s your day going? 😊",
    "hi": "Hi! Need help with recipes or allergies?",
    "hey": "Hey! What can I do for you today?",
    "hello": "Hey there! How’s your day going? 😊",
    "hi": "Hi! Need help with recipes or allergies?",
    "hey": "Hey! What can I do for you today?",
    "how are you": "I'm great! Thanks for asking. How about you?",
    "what is your name": "I’m your personal Allergy-Friendly Recipe Assistant! 🍽️",
    "who are you": "I'm an AI named SHIGI here to help you with safe and tasty recipes!",
    "what can you do": "I can suggest allergy-friendly recipes, find ingredient substitutes, and help with meal planning!",
    "who made you": "I was created to assist people with allergies in finding safe and delicious recipes. 😊",
    "how are you": "I'm great! Thanks for asking. How about you?",
    "what is your name": "I’m your personal Allergy-Friendly Recipe Assistant SHIGI! 🍽️",
    "who are you": "I'm an AI assistant SHIGI here to help you with safe and tasty recipes!",
    
    # Help & Features
    "help": "Sure! You can ask me about allergy-friendly recipes, ingredient substitutes, or healthy food choices.",
    "what can you do": "I can suggest allergy-friendly recipes, find ingredient substitutes, and help with meal planning!",
    "who made you": "I was created to assist people with allergies in finding safe and delicious recipes. 😊",
    
    
    # Recipe Suggestions
    "suggest a recipe": "I'd love to! What ingredients do you have right now?",
    "can you suggest a recipe": "Of course! Just let me know what’s in your kitchen. 🍳",
    "i have an allergy": "Oh no! Don't worry, I’ll help you find a safe recipe. What are you allergic to?",
    "list common allergies": "Common food allergies include peanuts, dairy, gluten, shellfish, and soy. Do you have any specific allergies?",
    "what is the best food for allergies": "That depends on your allergies! Fresh fruits, vegetables, and lean proteins are usually safe options.",
    "can you recommend something healthy": "Absolutely! Are you looking for a snack, breakfast, lunch, or dinner idea?",
    "suggest a recipe": "I'd love to! What ingredients do you have right now?",
    "can you suggest a recipe": "Of course! Just let me know what’s in your kitchen. 🍳",
    "i have an allergy": "Oh no! Don't worry, I’ll help you find a safe recipe. What are you allergic to?",
    "list common allergies": "Common food allergies include peanuts, dairy, gluten, shellfish, and soy. Do you have any specific allergies?",
    "what is the best food for allergies": "That depends on your allergies! Fresh fruits, vegetables, and lean proteins are usually safe options.",
    "can you recommend something healthy": "Absolutely! Are you looking for a snack, breakfast, lunch, or dinner idea?",
    "what is an allergy": "An allergy is when your immune system reacts to certain foods, causing discomfort or health issues.",
    "how to cook pasta": "Cooking pasta is easy! Just boil water, add salt, cook the pasta for 8-10 minutes, and drain it. Want a recipe?",
    "how to bake a cake": "To bake a cake, mix flour, sugar, eggs, butter, and baking powder, then bake at 180°C (350°F) for about 30 minutes.",
    
    # Ingredient Substitutions
    "ingredient substitute": "Sure! Tell me which ingredient you want to replace, and I'll suggest alternatives.",
    "can i replace milk in a recipe": "Yes! You can try almond milk, coconut milk, or oat milk as dairy-free alternatives.",
    "i am allergic to nuts": "Got it! I’ll make sure to suggest nut-free recipes for you.",
    "ingredient substitute": "Sure! Tell me which ingredient you want to replace, and I'll suggest alternatives.",
    "can i replace milk in a recipe": "Yes! You can try almond milk, coconut milk, or oat milk as dairy-free alternatives.",
    "i am allergic to nuts": "Got it! I’ll make sure to suggest nut-free recipes for you.",
    "substitute for eggs": "You can use mashed bananas, applesauce, or flaxseed mixed with water instead of eggs!",
    "what can i use instead of sugar": "You can use honey, maple syrup, or stevia as natural sugar alternatives.",
    
    # Food & Diets
    "do you know about keto diet": "Yes! A keto diet is low in carbs and high in fats. I can suggest keto-friendly recipes too.",
    "do you know about vegan food": "Of course! Vegan food avoids all animal products. Let me know if you need vegan recipes.",
    "is gluten-free food healthy": "For people with gluten intolerance, yes! But for others, it depends on the overall diet balance.",
    "do you know about keto diet": "Yes! A keto diet is low in carbs and high in fats. I can suggest keto-friendly recipes too.",
    "do you know about vegan food": "Of course! Vegan food avoids all animal products. Let me know if you need vegan recipes.",
    "is gluten-free food healthy": "For people with gluten intolerance, yes! But for others, it depends on the overall diet balance.",
    "best protein sources": "Great protein sources include chicken, fish, lentils, beans, and tofu!",
    "low-calorie snacks": "Try carrot sticks, Greek yogurt, or air-popped popcorn for a healthy snack.",
    
    # Casual & Fun Responses
    "do you like food": "I love talking about food! I can’t eat, but I can help you cook delicious meals. 😃",
    "tell me a joke": "Sure! Why don’t eggs tell jokes? Because they might crack up! 😆",
    "are you human": "Nope, I’m a chatbot! But I try my best to be as helpful as possible. 🤖",
    "do you have feelings": "Not exactly, but I can understand emotions and respond accordingly. 😊",
    "do you like food": "I love talking about food! I can’t eat, but I can help you cook delicious meals. 😃",
    "tell me a joke": "Why don’t eggs tell jokes? Because they might crack up! 😆",
    "tell me a fun fact": "Did you know honey never spoils? Archaeologists found 3000-year-old honey that’s still edible!",
    "are you human": "Nope, I’m a chatbot! But I try my best to be as helpful as possible. 🤖",
    "do you have feelings": "Not exactly, but I can understand emotions and respond accordingly. 😊",
    "what is your favorite food": "I don’t eat, but I’d love to talk about delicious recipes!",
    
    # Gratitude & Goodbye
    "thank you": "You're very welcome! Let me know if you need anything else. 😊",
    "thanks": "No problem! Happy to help!",
    "thanku": "You're very welcome! Keep cooking delicious meals! 🍲",
    "goodbye": "Goodbye! Stay safe and eat healthy! 😊",
    "bye": "Bye! Hope to chat with you again soon. 👋",
    "see you later": "See you later! Take care. 😊",
    "thank you": "You're very welcome! Let me know if you need anything else. 😊",
    "thanks": "No problem! Happy to help!",
    "thanku": "You're very welcome! Keep cooking delicious meals! 🍲",
    "goodbye": "Goodbye! Stay safe and eat healthy! 😊",
    "bye": "Bye! Hope to chat with you again soon. 👋",
    "see you later": "See you later! Take care. 😊"
    
}


    # Check if user input is in predefined responses
    if user_message in responses:
        return jsonify({"response": responses[user_message]})

    # If no predefined response, check the database for matching recipes
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM recipes WHERE ingredients LIKE %s", ('%' + user_message + '%',))
    matching_recipes = cursor.fetchall()

    if matching_recipes:
        suggested_recipe = random.choice(matching_recipes)  # Pick a random recipe
        return jsonify({"response": f"I found a recipe with {user_message}: {suggested_recipe['name']}!"})

    # If no match, suggest a general response
    return jsonify({"response": "I'm not sure about that. Try asking about recipes, allergies, or ingredient substitutes."})

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

if __name__ == "__main__":
    app.run(debug=True)




@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('name', None)
    flash('You have been logged out.', 'success')
    return render_template('org-index.html')

if __name__ == "__main__":
    app.run(debug=True)
    

