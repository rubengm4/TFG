from django.urls import path
from .views import (
    RegisterView,
    CustomLoginView,
    SetSourceAndRedirectToLogin,
    CustomLogoutView,
    UserUpdateView,
    CustomPasswordChangeView
)


app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('set-source/', SetSourceAndRedirectToLogin.as_view(),
         name='set_source'),
    path("manage/", UserUpdateView.as_view(), name="manage_user"),
    path('password/change/', CustomPasswordChangeView.as_view(),
         name="password_change")
]
