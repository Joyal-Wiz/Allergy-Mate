from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re

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
        cursor.execute('SELECT allergy_intensities, ingredients FROM users WHERE id = %s', (session['id'],))
        user_data = cursor.fetchone()
        if user_data and user_data['allergy_intensities']:
            allergy_data = eval(user_data['allergy_intensities']) 
        else:
            allergy_data = {}
        available_ingredients = user_data['ingredients'].split(',') if user_data['ingredients'] else []
        cursor.execute("SELECT * FROM recipes")
        all_recipes = cursor.fetchall()
        filtered_recipes = []
        for recipe in all_recipes:
            ingredients = recipe['ingredients'].split(',')
            allergy_flag = False
            allergy_message = ""
            for allergy, intensity in allergy_data.items():
                if allergy in ingredients:
                    if intensity == "basic":
                        allergy_message += f"Contains {allergy}. You can include a small amount.\n"
                    elif intensity == "average":
                        allergy_message += f"Contains {allergy}. Consider reducing the amount.\n"
                    elif intensity == "high":
                        allergy_message += f"Contains {allergy}. Avoid this recipe.\n"
                        allergy_flag = True
            if not allergy_flag:
                recipe['allergy_message'] = allergy_message
                filtered_recipes.append(recipe)
        return render_template('dashboard.html', recipes=filtered_recipes)
    else:
        
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
            cursor.execute("INSERT INTO recipe_comments (user_id, recipe_id, comment) VALUES (%s, %s, %s)",
                           (session['id'], recipe_id, comment))
        mysql.connection.commit()
        cursor.close()

    flash("Your rating and comment have been submitted!", "success")
    return redirect(url_for('dashboard'))


@app.route('/save-recipe', methods=['POST'])
def save_recipe():
    if 'loggedin' in session:
        recipe_id = request.form['recipe_id']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM saved_recipes WHERE user_id = %s AND recipe_id = %s', (session['id'], recipe_id))
        existing = cursor.fetchone()

        if not existing:
            cursor.execute('INSERT INTO saved_recipes (user_id, recipe_id) VALUES (%s, %s)', (session['id'], recipe_id))
            mysql.connection.commit()
            flash('Recipe saved successfully!', 'success')
        else:
            flash('Recipe already saved!', 'info')

        return redirect(url_for('dashboard'))
    else:
        flash("Please login first!", "danger")
        
        
        return redirect(url_for('login'))

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



















@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('name', None)
    flash('You have been logged out.', 'success')
    return render_template('org-index.html')

if __name__ == "__main__":
    app.run(debug=True)