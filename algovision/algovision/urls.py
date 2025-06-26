from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from fv_analysis.views import HomepageView, FileManagerView, AnalysisView, RenameFileView, ResultsView, DownloadOutputView, CreateAlgorithmView, ManageAlgorithmsView, UpdateAlgorithmView, DeleteAlgorithmView, Custom403View, Custom404View
from accounts.views import LoginHomeView, DashboardView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomepageView.as_view(), name='index'),
    path('accounts/', include('accounts.urls')),
    path('fv-analysis-home/', LoginHomeView.as_view(), name='fv_analysis_home'),
    path('people-analysis-home/', LoginHomeView.as_view(),
         name='people_analysis_home'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('files/', FileManagerView.as_view(), name='file_manager'),
    path('files/rename/<int:file_id>/',
         RenameFileView.as_view(), name='rename_file'),
    path('analysis/', AnalysisView.as_view(), name='analysis'),
    path('results/', ResultsView.as_view(), name='results'),
    path('results/download/<int:output_id>/',
         DownloadOutputView.as_view(), name='results_download'),
    path("algorithms/", ManageAlgorithmsView.as_view(),
         name="manage_algorithms"),
    path("algorithms/create/", CreateAlgorithmView.as_view(),
         name="create_algorithm"),
    path("algorithms/delete/<int:pk>/",
         DeleteAlgorithmView.as_view(), name="delete_algorithm"),
    path('algorithms/<int:pk>/edit/',
         UpdateAlgorithmView.as_view(), name='edit_algorithm')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = Custom403View.as_view()
handler404 = Custom404View.as_view()
