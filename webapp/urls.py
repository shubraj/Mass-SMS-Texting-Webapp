from django.urls import path
from django.views.generic import TemplateView
from .views import CustomLoginView,DashboardView,CustomLogoutView,ContactView,CompaignView,ConversationView,ConversationDetail,ReceiveSMSView
app_name = "app_webapp"
urlpatterns = [
    path("terms-and-conditions/", TemplateView.as_view(template_name="webapp/terms-and-conditions.html"), name="terms_and_conditions"),
    path("privacy-policy/", TemplateView.as_view(template_name="webapp/privacy-policy.html"), name="privacy_policy"),
    path('receive-sms/', ReceiveSMSView.as_view(), name='receive_sms'),
    path("conversations/<int:pk>/",ConversationDetail.as_view(), name="conversation_detail"),
    path("conversations/",ConversationView.as_view(),name="conversations"),
    path("campaigns/",CompaignView.as_view(),name="campaigns"),
    path("contacts/",ContactView.as_view(),name="contacts"),
    path("login/",CustomLoginView.as_view(),name="login"),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path("",DashboardView.as_view(),name="dashboard"),
]
