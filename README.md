# DOCKER build

docker build -t calorie_tracker_app .

# run the app at port 9000

docker run --rm -p 9000:8000 calorie_tracker_app
