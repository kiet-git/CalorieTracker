from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from . import db 
from .models import Food, Log, log_food
from datetime import datetime
from sqlalchemy import update
import requests, os
# from .foods import *

main = Blueprint('main', __name__)


@main.route('/search', methods=['POST'])
def search():
    foods_temp = Food.query.filter_by(user_id=current_user.id).all()

    food_name = request.form.get('food-name')
    api_key = os.environ.get('API_KEY')  # Replace with your actual API key
    base_url = 'https://api.nal.usda.gov/fdc/v1/foods/search'
    limit = 5

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

        return render_template('add.html', foods=foods_temp, food=None, user=current_user, searchResult=result, searchTerm = food_name)

    return render_template('add.html', foods=foods_temp, food=None, user=current_user, searchResult=[], searchTerm = '')


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
    
    if int(quantity) <= 0:
        flash('Quantity must be greater than 0', category='error')
        return redirect(url_for('main.add'))

    food_id = request.form.get('food-id')


    if food_id:
        food = Food.query.get(food_id)
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