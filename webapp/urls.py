from django.urls import path
from .views import CustomLoginView,DashboardView,CustomLogoutView,ContactView,CompaignView,ConversationView,ConversationDetail,ReceiveSMSView
app_name = "app_webapp"
urlpatterns = [
    path('receive-sms/', ReceiveSMSView.as_view(), name='receive_sms'),
    path("conversations/<int:pk>/",ConversationDetail.as_view(), name="conversation_detail"),
    path("conversations/",ConversationView.as_view(),name="conversations"),
    path("campaigns/",CompaignView.as_view(),name="campaigns"),
    path("contacts/",ContactView.as_view(),name="contacts"),
    path("login/",CustomLoginView.as_view(),name="login"),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path("",DashboardView.as_view(),name="dashboard"),
]
