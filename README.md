# TFG

Trabajo de Fin de Grado

## Autor: Rubén Argenta García

## ¿Cómo añadir un nuevo proyecto?

1. Añadirlo a la base de datos
2. En _accounts/views.py_, añadir en la clase **SetSourceAndRedirectToLogin**, dentro de la función _post(self, request: HttpRequest):_ sustituyendo _example_project_ por nuestro nombre de proyecto (**manteniendo el sufijo _-home_**):

   ```python
    elif source == 'example-project':
        return redirect('example_project_home')
   ```

3. En _algovision/urls.py_, añadir la siguiente línea, sustituyendo _example_project_ por nuestro nombre de proyecto (**manteniendo el sufijo _-home_**):
   ```python
   path('example-project-home/', LoginHomeView.as_view(), name='example_project_home'),
   ```
4. En _fv_analysis/templates/index.html_, añadir un elemento similar al siguiente, para crear un botón con un enlace al nuevo proyecto, cambiando Example y _value="example-project"_ por el nombre del proyecto:

   ```html
   <div class="col-auto">
     <form method="post" action="{% url 'accounts:set_source' %}">
       {% csrf_token %}
       <input type="hidden" name="source" value="example-project" />
       <button type="submit" class="btn btn-primary px-4">Example</button>
     </form>
   </div>
   ```

5. Es importante crear un usuario para este nuevo proyecto o dar permisos a un administrador. En caso negativo, no nos dejará entrar al proyecto.

El resto de la funcionalidad es común a cualquier proyecto, por lo que con estos simples pasos debería ser suficiente para añadir un nuevo proyecto. Es muy importante ser lo más fiel posible a la nomenclatura reflejada en estos pasos.

---

## ¿Cómo hacer que funcione la aplicación?

- Lanzar aplicación

python manage.py runserver

- Lanzar celery

celery -A algovision worker --loglevel=info

- Lanzar redis

redis-server
