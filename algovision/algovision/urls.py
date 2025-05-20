from django.contrib import admin
from django.urls import path, include
from fv_analysis.views import HomepageView  # o donde sea tu vista principal

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomepageView.as_view(), name='index'),
    path('accounts/', include('accounts.urls')),
]
