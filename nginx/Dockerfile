FROM tutum/nginx
ARG PUBLIC_URL
ADD .ssl/server.key /etc/ssl/server.key
ADD .ssl/SSL.crt /etc/ssl/SSL.crt
RUN rm /etc/nginx/sites-enabled/default
ADD sites-enabled/ /etc/nginx/sites-enabled
RUN sed -i s#example.com#$PUBLIC_URL#g /etc/nginx/sites-enabled/flask_project