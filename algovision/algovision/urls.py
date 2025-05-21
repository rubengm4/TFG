from django.contrib import admin
from django.urls import path, include
# o donde sea tu vista principal
from fv_analysis.views import HomepageView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomepageView.as_view(), name='index'),
    path('accounts/', include('accounts.urls')),
]
