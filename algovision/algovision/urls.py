from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from fv_analysis.views import HomepageView, FileManagerView, AnalysisView, RenameFileView, ResultsView
from accounts.views import FvAnalysisHomeView, DashboardView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomepageView.as_view(), name='index'),
    path('accounts/', include('accounts.urls')),
    path('fv-analysis-home/', FvAnalysisHomeView.as_view(), name='fv_analysis_home'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('files/', FileManagerView.as_view(), name='file_manager'),
    path('files/rename/<int:file_id>/',
         RenameFileView.as_view(), name='rename_file'),
    path('analysis/', AnalysisView.as_view(), name='analysis'),
    path('results/', ResultsView.as_view(), name='results'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
