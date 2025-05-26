from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from fv_analysis.views import HomepageView, FileManagerView, AnalysisView
from accounts.views import fv_analysis_home, dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomepageView.as_view(), name='index'),
    path('accounts/', include('accounts.urls')),
    path('fv-analysis-home/', fv_analysis_home, name='fv_analysis_home'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('files/', FileManagerView.as_view(), name='file_manager'),
    path('analysis/', AnalysisView.as_view(), name='analysis'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
