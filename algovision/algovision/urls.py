from django.contrib import admin
from django.urls import path, include
# o donde sea tu vista principal
from fv_analysis.views import HomepageView
from accounts.views import fv_analysis_home, dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomepageView.as_view(), name='index'),
    path('accounts/', include('accounts.urls')),
    path('fv-analysis-home/', fv_analysis_home, name='fv_analysis_home'),
    path('dashboard/', dashboard_view, name='dashboard'),
]
