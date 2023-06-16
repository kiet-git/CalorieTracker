from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, session
from flask_login import login_required, current_user
from . import db 
from .models import Food, Log, log_food
from datetime import datetime
from sqlalchemy import update
import requests, os
from deep_translator import GoogleTranslator

main = Blueprint('main', __name__)

@main.route('/search', methods=['GET','POST'])
@login_required
def search():
    foods_temp = Food.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        food_name = request.form.get('food-name')

        if food_name == '':
            flash('Food name must be filled!', category='error')
            return redirect(url_for('main.add'))

        session['ori_food_name'] = food_name
        ori_food_name = food_name
        food_name =  GoogleTranslator(source='vi', target='en').translate(food_name)


        api_key = os.environ.get('API_KEY')  # Replace with your actual API key
        base_url = 'https://api.nal.usda.gov/fdc/v1/foods/search'
        limit = 10

        params = {
            'api_key': api_key,
            'query': food_name,
            "dataType": [
                "Foundation",
                "Survey (FNDDS)"
            ],
            'pageSize': limit
        }

        response = requests.get(base_url, params=params)
        data = response.json()

        if 'foods' in data:
            foods = data['foods']
            result = []

            for food in foods:
                nutrients = food['foodNutrients']
                name = food['description']
                fdcId = food['fdcId']
                fats = next((n for n in nutrients if n['nutrientName'] == 'Total lipid (fat)'), {}).get('value')
                carbs = next((n for n in nutrients if n['nutrientName'] == 'Carbohydrate, by difference'), {}).get('value')
                proteins = next((n for n in nutrients if n['nutrientName'] == 'Protein'), {}).get('value')

                result.append({
                    'name': name,
                    'fdcId': fdcId,
                    'fats': fats,
                    'carbs': carbs,
                    'proteins': proteins
                })

            session['searchResult'] = result
            return render_template('add.html', foods=foods_temp, food=None, user=current_user, searchResult=result, searchTerm = ori_food_name)

        return render_template('add.html', foods=foods_temp, food=None, user=current_user, searchResult=[], searchTerm = '')
    else:
        if 'ori_food_name' in session:  # Check if 'ori_food_name' exists in session
            ori_food_name = session['ori_food_name']
        else:
            ori_food_name = ''  # Default value if 'ori_food_name' does not exist in session

        if 'searchResult' in session:  # Check if 'searchResult' exists in session
            search_result = session['searchResult']
        else:
            search_result = []  # Default value if 'searchResult' does not exist in session

        return render_template('add.html', foods=foods_temp, food=None, user=current_user, searchResult=search_result, searchTerm=ori_food_name)

#show index page
@main.route('/')
@login_required
def index():
    logs = Log.query.filter_by(user_id=current_user.id).order_by(Log.date.desc()).all()

    log_dates = []
    dates = []
    proteins = []
    carbs = []
    fats = []
    calories = []

    counter = 0
    for log in logs:
        totals = {
            'proteins': 0,
            'carbs': 0,
            'fats': 0,
            'calories': 0
        }
        for food in log.foods:
            quantity = db.session.query(log_food.c.quantity).filter_by(log_id=log.id, food_id=food.id).scalar()
            totals['proteins'] += food.proteins * quantity
            totals['carbs'] += food.carbs * quantity
            totals['fats'] += food.fats * quantity
            totals['calories'] += food.calories * quantity
        totals['proteins'] = round(totals['proteins'], 3)
        totals['carbs'] = round(totals['carbs'], 3)
        totals['fats'] = round(totals['fats'], 3)
        totals['calories'] = round(totals['calories'], 3)

        log_dates.append({
            'log': log,
            'totals': totals
        })

        if counter <= 30:
            dates.insert(0, log.date.strftime('%d/%m/%y'))
            proteins.insert(0, totals['proteins'])
            carbs.insert(0, totals['carbs'])
            fats.insert(0, totals['fats'])
            calories.insert(0, totals['calories'])

        counter += 1

    return render_template('index.html', log_dates=log_dates, user=current_user, dates=dates, proteins=proteins, carbs=carbs, fats=fats, calories=calories)

#create log with date
@main.route('/create_log', methods=['POST'])
def create_log():
    date = request.form.get('date')
    if date == '':
        flash('Date must be valid', category='error')
        return redirect(url_for('main.index'))

    log = Log(date=datetime.strptime(date, '%Y-%m-%d'), user_id=current_user.id)
    db.session.add(log)
    db.session.commit()

    return redirect(url_for('main.view', log_id=log.id))

#show add page
@main.route('/add')
@login_required
def add():
    foods = Food.query.filter_by(user_id=current_user.id).all()

    return render_template('add.html', foods=foods, food=None, user=current_user, searchResult=[], searchTerm = '')

#create and edit food
@main.route('/add', methods=['POST'])
def add_post():
    food_name = request.form.get('food-name')
    proteins = request.form.get('protein')
    carbs = request.form.get('carbohydrates')
    fats = request.form.get('fat')
    quantity = request.form.get('quantity')
    unit = request.form.get('unit')

    if food_name == '' or proteins == '' or carbs == '' or fats == '':
        flash('All fields must be filled!', category='error')
        return redirect(url_for('main.add'))
    
    if Food.query.filter_by(name=food_name).first():
        flash('Food name already exist!', category='error')
        return redirect(request.referrer)
    
    if int(quantity) <= 0:
        flash('Quantity must be greater than 0', category='error')
        return redirect(url_for('main.add'))

    food_id = request.form.get('food-id')


    if food_id:
        food = Food.query.get(food_id)
        if session['language'] == 'vi':
            food.name = GoogleTranslator(source='vi', target='en').translate(food_name)
        else: 
            food.name = food_name
        food.proteins = proteins
        food.carbs = carbs
        food.fats = fats
        food.quantity = quantity
        food.unit = unit
    else: 
        new_food = Food(
            name=food_name,
            proteins=proteins,
            carbs=carbs,
            fats=fats, 
            quantity=quantity,
            unit = unit,
            user_id=current_user.id
        )

        db.session.add(new_food)
    
    db.session.commit()

    return redirect(url_for('main.add'))

#delete food
@main.route('/delete_food/<int:food_id>')
def delete_food(food_id):
    food = Food.query.get(food_id)
    db.session.delete(food)
    db.session.commit()
    return redirect(url_for('main.add'))

#render placeholder to edit food
@main.route('/edit_food/<int:food_id>')
def edit_food(food_id):
    food = Food.query.get(food_id)
    if session['language'] == 'vi':
        food.name = GoogleTranslator(source='en', target='vi').translate(food.name)

    foods = Food.query.filter_by(user_id=current_user.id).all()
    return render_template('add.html', food=food, foods=foods, user=current_user)

#show view with the foods
@main.route('/view/<int:log_id>')
@login_required
def view(log_id):
    log = Log.query.get_or_404(log_id)

    foods = Food.query.filter_by(user_id=current_user.id).all()

    totals = {
        'proteins': 0,
        'carbs': 0,
        'fats': 0,
        'calories': 0
    }

    rendered_food = []

    for food in log.foods:
        quantity = db.session.query(log_food.c.quantity).filter_by(log_id=log.id, food_id=food.id).scalar()
        totals['proteins'] += food.proteins * quantity
        totals['carbs'] += food.carbs * quantity
        totals['fats'] += food.fats * quantity
        totals['calories'] += food.calories * quantity
    
        rendered_food.append({
            'food': food,
            'quantity': quantity
        })

    totals['proteins'] = round(totals['proteins'], 3)
    totals['carbs'] = round(totals['carbs'], 3)
    totals['fats'] = round(totals['fats'], 3)
    totals['calories'] = round(totals['calories'], 3)

    return render_template('view.html', foods=foods, log=log, totals=totals, rendered_food=rendered_food, user=current_user)

#add new foods to log
@main.route('/add_food_to_log/<int:log_id>', methods=['POST'])
def add_food_to_log(log_id):
    log = Log.query.get_or_404(log_id)

    quantity = request.form.get('quantity')

    if int(quantity) <= 0:
        flash('Quantity must be greater than 0', category='error')
        return redirect(url_for('main.view', log_id=log_id))

    selected_food = request.form.get('food-select')

    food = Food.query.get(int(selected_food))
    
    log_food_entry = db.session.query(log_food).filter_by(log_id=log.id, food_id=int(selected_food)).first()
    
    if log_food_entry:
        updated_quantity = log_food_entry.quantity + int(quantity)
        update_query = update(log_food).where(log_food.c.log_id == log.id).where(log_food.c.food_id == food.id).values(quantity=updated_quantity)
        db.session.execute(update_query)
    else:
        log_food_entry = log_food.insert().values(log_id=log.id, food_id=food.id, quantity=int(quantity))
        db.session.execute(log_food_entry)
    
    db.session.commit()

    return redirect(url_for('main.view', log_id=log_id))

#remove food from log
@main.route('/remove_food_from_log/<int:log_id>/<int:food_id>')
def remove_food_from_log(log_id, food_id):
    log = Log.query.get(log_id)
    food = Food.query.get(food_id)

    log.foods.remove(food)
    db.session.commit()
    
    return redirect(url_for('main.view', log_id=log_id))

#remove log
@main.route('/delete_log/<int:log_id>')
def delete_log(log_id):
    log = Log.query.get(log_id)
    db.session.delete(log)
    db.session.commit()
    return redirect(url_for('main.index'))

@main.route('search_recipe', methods=["GET", "POST"])
@login_required
def search_recipe():
    if request.method == "POST":
        food_name = request.form.get('food-name')
        min_calories = request.form.get('min-calories')
        max_calories = request.form.get('max-calories')

        if food_name == '':
            flash('Food name must be filled!', category='error')
            return redirect(url_for('main.search_recipe'))
        
        if int(min_calories) < 0 or int(max_calories) < 0:
            flash('Calories must be 0 and above', category='error')
            return redirect(url_for('main.search_recipe'))

        if int(min_calories) > int(max_calories):
            flash('Min calories must be larger than max calories', category='error')
            return redirect(url_for('main.search_recipe'))

        query_data = {
            'food_name': food_name,
            'min': min_calories,
            'max': max_calories
        }

        food_name =  GoogleTranslator(source='vi', target='en').translate(food_name)

        APP_ID = os.environ.get('APP_ID')
        APP_KEY = os.environ.get('APP_KEY')
        
        api_url = f'https://api.edamam.com/api/recipes/v2?type=public&q={food_name}&app_id={APP_ID}&app_key={APP_KEY}&random=True'
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            if 'hits' in data and len(data['hits']) > 0:
                recipes = []
                for hit in data['hits']:
                    recipe = hit['recipe']
                    if recipe['calories'] >= int(min_calories) and recipe['calories'] <= int(max_calories):
                        recipe_data = {
                            'name': recipe['label'],
                            'image': recipe['image'],
                            'url': recipe['url'],
                            'proteins': round(recipe['totalNutrients']['PROCNT']['quantity'], 3),
                            'carbs': round(recipe['totalNutrients']['CHOCDF']['quantity'], 3),
                            'calories': round(recipe['calories'], 3),
                            'fats': round(recipe['totalNutrients']['FAT']['quantity'], 3),
                            'ingredientList': recipe['ingredientLines'],
                            'labels': recipe['healthLabels']
                        }
                        recipes.append(recipe_data)
                session['query_data'] = query_data
                return render_template('recipe.html', user=current_user, recipes=recipes, data=query_data)
        return render_template('recipe.html', user=current_user, recipes=[], data=query_data)
    else:
        query_data = ''
        if 'query_data' in session:
            query_data = session['query_data']
            session['query_data'] = ''

        return render_template('recipe.html', user=current_user, recipes=[], data=query_data)

        
@main.route('/get_food_suggestions', methods=['POST'])
@login_required
def get_food_suggestions():
    food_name = request.form.get('inputValue')
    
    food_name =  GoogleTranslator(source='vi', target='en').translate(food_name)

    api_key = os.environ.get('API_KEY')  # Replace with your actual API key
    base_url = 'https://api.nal.usda.gov/fdc/v1/foods/search'
    limit = 10

    params = {
        'api_key': api_key,
        'query': food_name,
        "dataType": [
            "Foundation",
            "Survey (FNDDS)"
        ],
        'pageSize': limit
    }

    response = requests.get(base_url, params=params)
    data = response.json()

    if 'foods' in data:
        foods = data['foods']
        suggestions = []

        for food in foods:
            if session['language'] == 'vi':
                name = GoogleTranslator(source='en', target='vi').translate(food['description'])
            else:
                name = food['description']
            suggestions.append(name)

        return jsonify({'suggestions': suggestions})

    return jsonify({'suggestions': []})
