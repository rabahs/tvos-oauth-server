# Run development env under pyenv (https://github.com/yyuu/pyenv)

We will run Postgres and Redis inside docker and web app on local host (for easy debugging)

- Prerequisites 
	- Install Docker Toolbox
	- Create and start a 'dev' Docker machine
	 
     ```
        docker-machine start dev
     ```


- Run Postgres docker container

    ```
        docker-compose up -d postgres
    ```


- Activate python env 

    ```
        source ~/.pyenv/envs/3.4.3/bin/activate

    ```

- Install required Python packages

    ```
        cd to project/web directory
        pip install -r requirements.txt

    ```

- Load env variables
	- rename .env_example to .env and update credentials

    ```
        source .env
        export $(cat .env | xargs)

        # check env set correctly
        echo $SECRET_KEY

    ```

- Setup Postgres database 
    
    - Create a db named $DB_NAME in postgres (if not already created)    
 
    - Run db migrations (we use https://github.com/miguelgrinberg/Flask-Migrate) 
    ```
        python migrate.py db init           # only first time
        python migrate.py db revision --autogenerate
        python migrate.py db upgrade
        
    ```

    ```
        python web/create_db.py

    ```
    - Create an app to use  
        
    ```
        python manage.py create_app --name "CloudPhotos"

    ```

- Setup reverse proxy url to use for oAuth callbacks to localhost 
    
    - On a new shell, run: 

    ```
        ~/dev/ngrok http 9001

    ```

    - Verify access to reverse proxy url
        - e.g. http://ea9f2968.ngrok.io/activate 

    - Update PUBLIC_URL in web/config.py with reverse proxy url
     
    - Update AWS with reverse proxy address

        - https://developer.amazon.com
        - Under allowed urls under security profiles / web settings  

    - Update mobile client with reverse proxy url

- Run web app from pycharm
 
    - Define environment variables under run configuration 

      
