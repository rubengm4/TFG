from django.urls import path
from .views import (
    RegisterView,
    CustomLoginView,
    SetSourceAndRedirectToLogin,
    fv_home,
    dashboard_view,
    CustomLogoutView,
)


app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(next_page='accounts:login'), name='logout'),
    path('set-source/', SetSourceAndRedirectToLogin.as_view(),
         name='set_source'),
]
