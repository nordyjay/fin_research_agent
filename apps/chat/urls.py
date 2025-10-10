from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_interface, name='index'),
    path('test/', views.test_view, name='test'),
    path('conversations/', views.get_conversations, name='conversations'),
    path('conversation/<uuid:conversation_id>/messages/', views.get_messages, name='get_messages'),
    path('<uuid:conversation_id>/', views.chat_detail, name='detail'),
    path('message/', views.chat_message, name='message'),
]